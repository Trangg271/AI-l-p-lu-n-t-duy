# backend/app/graph/nodes.py
"""
LangGraph node functions for the SocraticAI debate workflow.

Each function is an async node that takes a ``SessionState`` TypedDict
and returns a partial dict that LangGraph merges back into state.

**Functional Core / Imperative Shell**:
  - Node functions orchestrate the *logic* (prompt construction, response parsing)
  - I/O (LLM calls, DB writes, embedding) is delegated to the service/repo layer
  - All I/O operations use ``async def``

**Graph topology** (defined in ``graph.py``):
    START → debate_node
    debate_node → conditional:
        if is_ended → grader_node → END
        else → fan-out [fallacy_node, memory_node] → END
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

import structlog
from langchain_core.runnables import RunnableConfig

from app.config import get_settings
from app.models.session import (
    Claim,
    FallacyResult,
    SessionScore,
    SessionState,
    Turn,
)
from app.prompts.debate import build_debate_system_prompt, build_user_turn_prompt
from app.prompts.fallacy import build_fallacy_detection_prompt
from app.prompts.grader import build_grading_prompt
from app.prompts.memory import build_memory_extraction_prompt
from app.repositories.qdrant_repo import QdrantRepository
from app.utils.embeddings import embed_single, embed_texts

logger = structlog.get_logger(__name__)

# Module-level repository singletons (initialised on first use)
_qdrant_repo: QdrantRepository | None = None


def _get_qdrant_repo() -> QdrantRepository:
    """Lazy-initialise the Qdrant repository singleton."""
    global _qdrant_repo
    if _qdrant_repo is None:
        _qdrant_repo = QdrantRepository()
    return _qdrant_repo


# ─── Node: debate_node ───────────────────────────────────────────────────────


async def debate_node(state: SessionState, config: RunnableConfig) -> dict[str, Any]:
    """Generate the AI's debate response with memory-augmented context.

    This is the entry node of the graph.  It:
      1. Embeds the current user message
      2. Queries Qdrant for the top-5 related past claims
      3. Builds contradiction alerts if retrieved claims conflict
      4. Calls gemini-2.5-flash with the Debate Adversary system prompt
      5. Returns the full AI response and any contradiction alerts

    Args:
        state: The current LangGraph session state.

    Returns:
        Partial state dict with ``ai_response`` and ``contradiction_alerts``.
    """
    session_id = state.get("session_id", "")
    debate_config = state.get("config")
    current_msg = state.get("current_user_message", "")
    turns = state.get("turns", [])

    log = logger.bind(session_id=session_id, node="debate_node")

    if not current_msg:
        log.warning("empty_user_message")
        return {"ai_response": "", "contradiction_alerts": []}

    if debate_config is None:
        raise ValueError("Missing debate configuration")

    # ── Step 1: Retrieve related past claims from Qdrant ──────────────────
    retrieved_claims: list[str] = []
    contradiction_alerts: list[str] = []

    if state.get("extracted_claims"):
        try:
            query_embedding = await asyncio.to_thread(embed_single, current_msg)
            repo = _get_qdrant_repo()
            results = await repo.search(
                vector=query_embedding,
                filter_={"session_id": session_id} if session_id else None,
                top_k=get_settings().memory_top_k,
            )
            retrieved_claims = [
                r["payload"].get("claim_text", r["payload"].get("claim", ""))
                for r in results
                if r.get("payload")
            ]

            # Similarity alone cannot establish a contradiction. Give related claims
            # to the debate model as context without issuing false accusations.
            log.info(
                "memory_retrieved",
                claims=len(retrieved_claims),
                contradictions=len(contradiction_alerts),
            )

        except Exception as exc:
            log.error("memory_retrieval_failed", error=str(exc))

    # ── Step 3: Build prompts and call Gemini ─────────────────────────────
    settings = get_settings()

    client, model_name = settings.get_gemini_model("fast")

    system_prompt = build_debate_system_prompt(
        config=debate_config,
        retrieved_claims=retrieved_claims,
        contradiction_alerts=contradiction_alerts,
    )
    user_prompt = build_user_turn_prompt(
        user_input=current_msg,
        turns=turns[:-1],
        is_vi=debate_config.language == "vi",
    )

    token_queue = config.get("configurable", {}).get("token_queue")
    full_response = ""

    try:
        response_stream = await client.aio.models.generate_content_stream(
            model=model_name,
            contents=user_prompt,
            config={"system_instruction": system_prompt},
        )
        async for chunk in response_stream:
            log.info("received_chunk")
            text_chunk = chunk.text or ""
            if text_chunk:
                full_response += text_chunk
                if token_queue:
                    await token_queue.put(text_chunk)

        log.info("response_generated", length=len(full_response))
    except Exception:
        log.exception("response_generation_failed")
        raise
    finally:
        await client.aio.aclose()
        client.close()

    if not full_response.strip():
        raise RuntimeError("The model returned an empty response")

    ai_turn = Turn(
        turn_number=len(turns),
        speaker="ai",
        content=full_response,
        timestamp=datetime.now(UTC),
    )

    if token_queue:
        # Sentinel to end the stream loop in debate_service
        try:
            token_queue.put_nowait(None)
        except Exception:
            pass

    return {
        "ai_response": full_response,
        "contradiction_alerts": contradiction_alerts,
        "turns": turns + [ai_turn],
    }


# ─── Node: fallacy_node ──────────────────────────────────────────────────────


async def fallacy_node(state: SessionState) -> dict[str, Any]:
    """Detect logical fallacies in the user's argument.

    Runs **concurrently** with ``memory_node`` via LangGraph fan-out.
    Uses gemini-2.5-pro (complex tier) for careful multi-step reasoning.
    Forces JSON output conforming to the ``FallacyResult`` schema.

    Args:
        state: The current LangGraph session state.

    Returns:
        Partial state dict with ``fallacy_analysis``.
    """
    session_id = state.get("session_id", "")
    config = state.get("config")
    current_msg = state.get("current_user_message", "")

    log = logger.bind(session_id=session_id, node="fallacy_node")

    if not current_msg:
        return {"fallacy_analysis": []}

    settings = get_settings()
    client, model_name = settings.get_gemini_model("complex")

    try:
        prompt = build_fallacy_detection_prompt(
            argument=current_msg,
            topic=config.topic if config else "",
            language=config.language if config else "en",
        )

        response = await client.aio.models.generate_content(
            model=model_name,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        raw_text = response.text or "{}"

        # Parse JSON response
        parsed = json.loads(raw_text)
        fallacy_dicts = parsed.get("fallacies", [])

        fallacies: list[FallacyResult] = []
        for fd in fallacy_dicts:
            try:
                fallacies.append(FallacyResult.model_validate(fd))
            except Exception as parse_err:
                log.warning("fallacy_parse_error", error=str(parse_err), raw=fd)

        log.info("fallacies_detected", count=len(fallacies))
        return {"fallacy_analysis": fallacies}

    except json.JSONDecodeError as exc:
        log.error("fallacy_json_parse_failed", error=str(exc))
        return {"fallacy_analysis": []}
    except Exception as exc:
        log.error("fallacy_detection_failed", error=str(exc))
        return {"fallacy_analysis": []}
    finally:
        await client.aio.aclose()
        client.close()


# ─── Node: memory_node ───────────────────────────────────────────────────────


async def memory_node(state: SessionState) -> dict[str, Any]:
    """Extract claims from the AI response and upsert to Qdrant.

    Runs **concurrently** with ``fallacy_node`` via LangGraph fan-out.
    Uses gemini-2.5-flash (fast tier) for lightweight extraction.

    Pipeline:
      1. Call LLM with Memory Extractor prompt → JSON list of claims
      2. Embed each claim text using sentence-transformers
      3. Upsert embeddings to Qdrant with metadata

    Args:
        state: The current LangGraph session state.

    Returns:
        Partial state dict with ``extracted_claims`` (appended).
    """
    session_id = state.get("session_id", "")
    config = state.get("config")
    ai_response = state.get("ai_response", "")
    current_msg = state.get("current_user_message", "")
    existing_claims = list(state.get("extracted_claims", []))
    turns = state.get("turns", [])

    log = logger.bind(session_id=session_id, node="memory_node")

    if not ai_response:
        return {"extracted_claims": existing_claims}

    settings = get_settings()

    client, model_name = settings.get_gemini_model("fast")

    new_claims: list[Claim] = []

    try:
        # ── Extract claims from AI response ───────────────────────────────
        for speaker, text in [("ai", ai_response), ("user", current_msg)]:
            if not text:
                continue

            prompt = build_memory_extraction_prompt(
                text=text,
                topic=config.topic if config else "",
                speaker=speaker,
                language=config.language if config else "en",
            )

            response = await client.aio.models.generate_content(
                model=model_name,
                contents=prompt,
                config={"response_mime_type": "application/json"},
            )
            raw_text = response.text or "{}"

            try:
                parsed = json.loads(raw_text)
                claim_dicts = parsed.get("claims", [])
            except json.JSONDecodeError:
                log.warning("memory_json_parse_failed", speaker=speaker)
                continue

            for cd in claim_dicts[:10]:
                try:
                    claim = Claim(
                        session_id=session_id,
                        turn_number=next(
                            t.turn_number for t in reversed(turns) if t.speaker == speaker
                        ),
                        speaker=speaker,
                        claim_text=cd.get("claim_text", ""),
                        claim_type=cd.get("claim_type", "assertion"),
                        key_entities=cd.get("key_entities", []),
                    )
                    new_claims.append(claim)
                except (ValueError, AttributeError, StopIteration):
                    log.warning("invalid_extracted_claim", speaker=speaker)

        log.info("claims_extracted", count=len(new_claims))

        # ── Embed and upsert to Qdrant ────────────────────────────────────
        if new_claims:
            claim_texts = [c.claim_text for c in new_claims]
            embeddings = await asyncio.to_thread(embed_texts, claim_texts)

            points: list[dict[str, Any]] = []
            for claim, embedding in zip(new_claims, embeddings):
                point_id = claim.claim_id
                claim.vector_id = point_id
                points.append(
                    {
                        "id": point_id,
                        "vector": embedding,
                        "payload": {
                            "session_id": session_id,
                            "claim_text": claim.claim_text,
                            "claim_type": claim.claim_type,
                            "speaker": claim.speaker,
                            "turn_number": claim.turn_number,
                            "key_entities": claim.key_entities,
                        },
                    }
                )

            repo = _get_qdrant_repo()
            await repo.upsert_points(points)
            log.info("claims_upserted_to_qdrant", count=len(points))

    except Exception as exc:
        log.error("memory_extraction_failed", error=str(exc))

    finally:
        await client.aio.aclose()
        client.close()

    return {"extracted_claims": existing_claims + new_claims}


# ─── Node: grader_node ────────────────────────────────────────────────────────


async def grader_node(state: SessionState) -> dict[str, Any]:
    """Grade the complete debate session after it ends.

    Only invoked when ``state["is_ended"] == True``.
    Aggregates the full transcript and all extracted claims,
    then calls gemini-2.5-pro with the Session Grader prompt.

    Args:
        state: The current LangGraph session state.

    Returns:
        Partial state dict with ``session_score``.
    """
    session_id = state.get("session_id", "")
    config = state.get("config")
    turns = state.get("turns", [])
    claims = state.get("extracted_claims", [])

    log = logger.bind(session_id=session_id, node="grader_node")

    settings = get_settings()
    client, model_name = settings.get_gemini_model("complex")

    # Count total user fallacies across all turns
    total_fallacies = 0
    for turn in turns:
        if hasattr(turn, "fallacies_detected"):
            total_fallacies += len(turn.fallacies_detected)

    try:
        prompt = build_grading_prompt(
            topic=config.topic if config else "",
            difficulty=config.difficulty if config else "beginner",
            user_position=config.user_position if config else "pro",
            turns=turns,
            claims=claims,
            fallacy_count=total_fallacies,
        )

        response = await client.aio.models.generate_content(
            model=model_name,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        raw_text = response.text or "{}"

        parsed = json.loads(raw_text)
        score = SessionScore.model_validate(parsed)
        score.fallacies_committed = total_fallacies
        score.contradictions_caught = len(state.get("contradiction_alerts", []))

        log.info(
            "session_graded",
            total=score.total,
            grade=score.grade,
        )
        return {"session_score": score}

    except json.JSONDecodeError as exc:
        log.error("grading_json_parse_failed", error=str(exc))
        return {"session_score": None}
    except Exception as exc:
        log.error("grading_failed", error=str(exc))
        return {"session_score": None}
    finally:
        await client.aio.aclose()
        client.close()
