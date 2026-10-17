import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.graph import nodes
from app.graph.graph import build_debate_graph
from app.main import create_app
from app.models.session import (
    CreateSessionRequest,
    DebateConfig,
    SessionMetadata,
    SessionScore,
    Turn,
)
from app.services import debate_service
from app.services.debate_service import DebateService
from app.services.session_service import SessionService


async def new_session():
    return await SessionService().create_session(
        CreateSessionRequest(topic="Nuclear energy is essential", max_turns=2)
    )


async def frames(iterator):
    return [frame async for frame in iterator]


@pytest.mark.parametrize("field", ["user_position", "user_stance"])
async def test_stance_and_snapshot_persist(test_client, field):
    response = await test_client.post(
        "/session/create",
        json={
            "topic": "  Debate this motion  ",
            field: "con",
            "language": "vi",
            "difficulty": "expert",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["config"]["topic"] == "Debate this motion"
    assert data["config"]["user_position"] == "con"
    assert data["config"]["ai_position"] == "pro"
    assert data["config"]["language"] == "vi"
    assert (await test_client.get(f"/session/{data['session_id']}")).json() == data


async def test_session_history_returns_compact_entries_and_missing_ids(test_client):
    session = await new_session()
    missing_id = UUID("00000000-0000-0000-0000-000000000001")
    response = await test_client.post(
        "/session/history",
        json={"session_ids": [str(session.session_id), str(missing_id)]},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["sessions"][0]["session_id"] == str(session.session_id)
    assert data["sessions"][0]["topic"] == session.config.topic
    assert "turns" not in data["sessions"][0]
    assert data["missing_session_ids"] == [str(missing_id)]


@pytest.mark.parametrize(
    "payload",
    [
        {"topic": "     "},
        {"topic": "valid topic", "user_position": "invalid"},
        {"topic": "valid topic", "max_turns": 1},
    ],
)
async def test_invalid_input(test_client, payload):
    assert (await test_client.post("/session/create", json=payload)).status_code == 422


async def test_storage_failure(test_client, memory_repo, monkeypatch):
    monkeypatch.setattr(memory_repo, "set", AsyncMock(side_effect=RedisConnectionError()))
    response = await test_client.post("/session/create", json={"topic": "valid topic"})
    assert response.status_code == 503
    assert "storage" in response.json()["detail"]


async def test_graph_failure_before_token_never_hangs(monkeypatch):
    session = await new_session()
    monkeypatch.setattr(
        debate_service,
        "_DEBATE_GRAPH",
        SimpleNamespace(ainvoke=AsyncMock(side_effect=RuntimeError("private provider detail"))),
    )
    result = await asyncio.wait_for(
        frames(DebateService().process_user_turn(session, "argument")), 1
    )
    assert [f.type for f in result] == ["error", "sync"]
    assert "private" not in result[0].data
    assert (await SessionService().get_session(session.session_id)).turn_count == 0


async def test_no_fallacies_still_finishes_and_restores_transcript(monkeypatch):
    session = await new_session()

    async def invoke(state, config):
        await config["configurable"]["token_queue"].put("AI answer")
        return {
            **state,
            "turns": state["turns"] + [Turn(turn_number=1, speaker="ai", content="AI answer")],
            "ai_response": "AI answer",
        }

    monkeypatch.setattr(debate_service, "_DEBATE_GRAPH", SimpleNamespace(ainvoke=invoke))
    result = await frames(DebateService().process_user_turn(session, "argument"))
    assert [f.type for f in result] == ["token", "turn_done"]
    persisted = await SessionService().get_session(session.session_id)
    sync = await DebateService().get_sync_frame(persisted)
    assert len(sync.data["turns"]) == 2
    assert persisted.turn_count == 1
    assert [t.turn_number for t in persisted.turns] == [0, 1]


async def test_disconnect_cancels_graph(monkeypatch):
    session = await new_session()
    cancelled = asyncio.Event()

    async def invoke(state, config):
        try:
            await config["configurable"]["token_queue"].put("chunk")
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(debate_service, "_DEBATE_GRAPH", SimpleNamespace(ainvoke=invoke))
    generator = DebateService().process_user_turn(session, "argument")
    assert (await anext(generator)).type == "token"
    await generator.aclose()
    assert cancelled.is_set()


async def test_rest_grading_persists_and_is_idempotent(monkeypatch, test_client, score_data):
    session = await new_session()
    session.turns = [Turn(turn_number=0, speaker="user", content="argument")]
    await SessionService().update_session(session)
    invoke = AsyncMock(return_value={"session_score": SessionScore(**score_data)})
    monkeypatch.setattr(debate_service, "_DEBATE_GRAPH", SimpleNamespace(ainvoke=invoke))
    for _ in range(2):
        response = await test_client.post(f"/session/{session.session_id}/end", json={})
        assert response.status_code == 200
        assert response.json()["status"] == "graded"
    assert invoke.await_count == 1
    saved = await SessionService().get_session(session.session_id)
    assert saved.grade.total == 82 and saved.ended_at is not None


async def test_grading_failure_preserves_history_and_can_retry(monkeypatch, score_data):
    session = await new_session()
    session.turns = [Turn(turn_number=0, speaker="user", content="argument")]
    invoke = AsyncMock(
        side_effect=[RuntimeError("bad provider"), {"session_score": SessionScore(**score_data)}]
    )
    monkeypatch.setattr(debate_service, "_DEBATE_GRAPH", SimpleNamespace(ainvoke=invoke))
    failed = await frames(DebateService().end_session(session))
    assert [f.type for f in failed] == ["grading", "error", "session_ended"]
    persisted = await SessionService().get_session(session.session_id)
    assert persisted.status == "ended" and len(persisted.turns) == 1
    assert any(f.type == "score" for f in await frames(DebateService().end_session(persisted)))


async def test_busy_session_rejects_rest_end(test_client):
    session = await new_session()
    async with SessionService().lock_session(session.session_id):
        response = await test_client.post(f"/session/{session.session_id}/end", json={})
    assert response.status_code == 409


async def test_empty_session_rejects_grading(test_client):
    session = await new_session()
    assert (
        await test_client.post(f"/session/{session.session_id}/end", json={})
    ).status_code == 409


def test_score_recomputes_total(score_data):
    score = SessionScore(**{**score_data, "total": 1, "grade": "F"})
    assert score.total == 82 and score.grade == "B"


class ASGIWebSocket:
    """Exercise the ASGI WebSocket protocol without sockets or worker threads."""

    def __init__(self, path):
        self.path = path
        self.incoming = asyncio.Queue()
        self.outgoing = asyncio.Queue()

    async def __aenter__(self):
        scope = {
            "type": "websocket",
            "asgi": {"version": "3.0"},
            "path": self.path,
            "raw_path": self.path.encode(),
            "query_string": b"",
            "headers": [],
            "scheme": "ws",
            "client": ("test", 123),
            "server": ("test", 80),
            "subprotocols": [],
            "root_path": "",
        }
        self.task = asyncio.create_task(create_app()(scope, self.incoming.get, self.outgoing.put))
        await self.incoming.put({"type": "websocket.connect"})
        assert (await self.receive())["type"] == "websocket.accept"
        return self

    async def __aexit__(self, *args):
        await self.incoming.put({"type": "websocket.disconnect", "code": 1000})
        await asyncio.wait_for(self.task, 2)

    async def receive(self):
        return await asyncio.wait_for(self.outgoing.get(), 2)

    async def receive_json(self):
        return json.loads((await self.receive())["text"])

    async def send_text(self, text):
        await self.incoming.put({"type": "websocket.receive", "text": text})

    async def send_json(self, data):
        await self.send_text(json.dumps(data))


async def test_websocket_validates_frames(memory_repo):
    session = SessionMetadata(config=DebateConfig(topic="Test debate"), status="active")
    memory_repo.values[f"socratic:session:{session.session_id}"] = session.model_dump_json()
    async with ASGIWebSocket(f"/ws/debate/{session.session_id}") as ws:
        assert (await ws.receive_json())["type"] == "sync"
        for content in [None, 123, [], "  ", "x" * 1001]:
            await ws.send_json({"type": "user_message", "data": {"content": content}})
            assert (await ws.receive_json())["type"] == "error"
        await ws.send_text("broken json")
        assert (await ws.receive_json())["type"] == "error"
        await ws.send_json({"type": "ping"})
        assert (await ws.receive_json())["type"] == "pong"
    async with ASGIWebSocket(f"/ws/debate/{UUID(int=0)}") as ws:
        assert (await ws.receive_json())["type"] == "error"
        assert (await ws.receive())["code"] == 1008


async def test_max_turns_grades_and_reconnect_restores_score(memory_repo, monkeypatch, score_data):
    session = SessionMetadata(
        config=DebateConfig(topic="Test debate"), status="active", max_turns=2, turn_count=1
    )
    memory_repo.values[f"socratic:session:{session.session_id}"] = session.model_dump_json()

    async def invoke(state, config=None):
        if state["is_ended"]:
            return {"session_score": SessionScore(**score_data)}
        return {
            **state,
            "turns": state["turns"] + [Turn(turn_number=1, speaker="ai", content="answer")],
        }

    monkeypatch.setattr(debate_service, "_DEBATE_GRAPH", SimpleNamespace(ainvoke=invoke))
    async with ASGIWebSocket(f"/ws/debate/{session.session_id}") as ws:
        assert (await ws.receive_json())["type"] == "sync"
        await ws.send_json({"type": "user_message", "data": {"content": "argument"}})
        assert [(await ws.receive_json())["type"] for _ in range(4)] == [
            "turn_done",
            "grading",
            "score",
            "session_ended",
        ]
        assert (await ws.receive())["code"] == 1000
    saved = SessionMetadata.model_validate_json(
        memory_repo.values[f"socratic:session:{session.session_id}"]
    )
    assert saved.status == "graded" and saved.turn_count == 2
    async with ASGIWebSocket(f"/ws/debate/{session.session_id}") as ws:
        assert (await ws.receive_json())["data"]["session_score"]["total"] == 82
        assert (await ws.receive())["code"] == 1000


async def test_real_graph_receives_stream_config(monkeypatch):
    async def stream(prompt, *, system_instruction=None):
        assert system_instruction
        yield "Test answer"

    complete = AsyncMock(return_value='{"fallacies":[],"claims":[]}')
    client = SimpleNamespace(
        stream=stream,
        complete=complete,
        aclose=AsyncMock(),
    )
    monkeypatch.setattr(
        nodes,
        "get_settings",
        lambda: SimpleNamespace(get_ai_client=lambda task: (client, "test"), memory_top_k=5),
    )
    monkeypatch.setattr(nodes, "embed_single", lambda text: [0.5, 0.8])
    monkeypatch.setattr(
        nodes, "_get_qdrant_repo", lambda: SimpleNamespace(search=AsyncMock(return_value=[]))
    )
    queue = asyncio.Queue()
    state = {
        "session_id": "test",
        "config": DebateConfig(topic="Test motion"),
        "turns": [Turn(turn_number=0, speaker="user", content="argument")],
        "current_user_message": "argument",
    }
    result = await build_debate_graph().ainvoke(
        state, config={"configurable": {"token_queue": queue}}
    )
    assert result["ai_response"] == "Test answer"
    assert await queue.get() == "Test answer"
    assert result["fallacy_analysis"] == []


async def test_fallacy_node_requires_confident_exact_contextual_quote(monkeypatch):
    response = SimpleNamespace(
        text=json.dumps(
            {
                "fallacies": [
                    {
                        "fallacy_type": "Ad Hominem",
                        "fallacy_name_vi": "Tấn công cá nhân",
                        "severity": "moderate",
                        "offending_excerpt": "Bạn sai vì bạn lười",
                        "explanation": "Tấn công người nói thay vì lập luận.",
                        "suggestion": "Phản biện vào nội dung.",
                        "confidence": 0.94,
                    },
                    {
                        "fallacy_type": "Straw Man",
                        "severity": "minor",
                        "offending_excerpt": "Tôi không đồng ý",
                        "explanation": "Không đủ chắc chắn.",
                        "confidence": 0.65,
                    },
                    {
                        "fallacy_type": "False Dilemma",
                        "severity": "moderate",
                        "offending_excerpt": "Không có trong bài",
                        "explanation": "Trích dẫn không khớp.",
                        "confidence": 0.99,
                    },
                ]
            }
        )
    )
    generate = AsyncMock(return_value=response.text)
    client = SimpleNamespace(
        complete=generate,
        aclose=AsyncMock(),
    )
    monkeypatch.setattr(
        nodes,
        "get_settings",
        lambda: SimpleNamespace(get_ai_client=lambda task: (client, "test")),
    )

    result = await nodes.fallacy_node(
        {
            "config": DebateConfig(topic="Phone use at school", language="vi"),
            "turns": [
                Turn(turn_number=0, speaker="user", content="Ý trước đó"),
                Turn(turn_number=1, speaker="user", content="Bạn sai vì bạn lười"),
                Turn(turn_number=2, speaker="ai", content="Phản biện"),
            ],
            "current_user_message": "Bạn sai vì bạn lười",
        }
    )

    assert [item.fallacy_type for item in result["fallacy_analysis"]] == ["Ad Hominem"]
    prompt = generate.await_args.args[0]
    assert "Ý trước đó" in prompt
    assert "Phản biện" not in prompt


@pytest.mark.parametrize(
    "total,grade",
    [
        (100, "A"),
        (85, "A"),
        (84, "B"),
        (70, "B"),
        (69, "C"),
        (55, "C"),
        (54, "D"),
        (40, "D"),
        (39, "F"),
        (0, "F"),
    ],
)
def test_grade_matches_documented_rubric(total, grade):
    values = [min(25, max(0, total - index * 25)) for index in range(4)]
    result = SessionScore(
        argument_depth=values[0],
        logical_consistency=values[1],
        evidence_quality=values[2],
        rebuttal_effectiveness=values[3],
        total=0,
        grade="F",
    )
    assert result.total == total and result.grade == grade


async def test_memory_embeds_real_claims_and_preserves_turn_numbers(monkeypatch):
    response = '{"claims":[{"claim_text":""},{"claim_text":"Energy is useful"}]}'
    client = SimpleNamespace(
        complete=AsyncMock(return_value=response),
        aclose=AsyncMock(),
    )
    monkeypatch.setattr(
        nodes,
        "get_settings",
        lambda: SimpleNamespace(get_ai_client=lambda task: (client, "test")),
    )
    embeddings = Mock(return_value=[[0.5, 0.2], [0.3, 0.6]])
    monkeypatch.setattr(nodes, "embed_texts", embeddings)
    repo = SimpleNamespace(upsert_points=AsyncMock())
    monkeypatch.setattr(nodes, "_get_qdrant_repo", lambda: repo)
    result = await nodes.memory_node(
        {
            "session_id": "test",
            "config": DebateConfig(topic="Energy policy"),
            "turns": [
                Turn(turn_number=4, speaker="user", content="user"),
                Turn(turn_number=5, speaker="ai", content="ai"),
            ],
            "current_user_message": "user",
            "ai_response": "ai",
        }
    )
    claims = result["extracted_claims"]
    assert [(c.speaker, c.turn_number) for c in claims] == [("ai", 5), ("user", 4)]
    embeddings.assert_called_once_with(["Energy is useful", "Energy is useful"])
    assert repo.upsert_points.await_args.args[0][0]["vector"] == [0.5, 0.2]


async def test_grader_counts_all_fallacies_once(monkeypatch, score_data):
    from app.models.session import FallacyResult

    fallacy = FallacyResult(
        fallacy_type="Ad Hominem",
        severity="minor",
        offending_excerpt="x",
        explanation="x",
        confidence=0.9,
    )
    generate = AsyncMock(return_value=json.dumps(score_data))
    client = SimpleNamespace(
        complete=generate,
        aclose=AsyncMock(),
    )
    monkeypatch.setattr(
        nodes,
        "get_settings",
        lambda: SimpleNamespace(get_ai_client=lambda task: (client, "test")),
    )
    result = await nodes.grader_node(
        {
            "config": DebateConfig(topic="Test topic"),
            "turns": [
                Turn(turn_number=0, speaker="user", content="a", fallacies_detected=[fallacy]),
                Turn(turn_number=2, speaker="user", content="b", fallacies_detected=[fallacy]),
            ],
            "fallacy_analysis": [fallacy],
        }
    )
    assert result["session_score"].fallacies_committed == 2
    assert "**Total fallacies committed by the user**: 2" in generate.await_args.args[0]
