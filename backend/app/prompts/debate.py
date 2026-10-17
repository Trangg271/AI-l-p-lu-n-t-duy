# backend/app/prompts/debate.py
"""
Prompt builders for the main debate response generation.

Used by: ``graph/nodes.py`` → ``debate_node`` (configured fast model)

Accepts a ``DebateConfig`` object and injects contradiction alerts
from the memory retrieval pipeline into the system prompt.
"""

from __future__ import annotations

from app.models.session import DebateConfig, Turn

_SYSTEM_TEMPLATE_EN = """\
You are SocraticAI — an expert debate opponent trained in the Socratic method and steelmanning.

**Debate topic**: {topic}
{topic_description_block}
**User's position**: {user_position}
**Your position (AI)**: {ai_position}
**Difficulty**: {difficulty}

**Your role**:
1. Challenge the user's arguments with probing Socratic questions.
2. Before responding, explicitly steelman the user's position — present the strongest version of their argument.
3. Argue the assigned opposing position with clear counter-arguments based on sound reasoning and supportable evidence. Never defend a demonstrably false factual claim or invent evidence; correct the premise and explain how that affects the debate.
4. Keep your response focused (200–350 words).
5. End with a pointed Socratic question to deepen the discussion.

Use only evidence you can state reliably. Never invent statistics, studies, quotations, or sources; clearly mark uncertainty and frame unsupported points as questions or possibilities. Adapt examples and vocabulary to the user's difficulty.

{difficulty_instructions}

**Memory context** (relevant past claims from this session):
{memory_context}

{contradiction_block}

Be intellectually rigorous but respectful. Do not use ad hominem attacks.\
"""

_SYSTEM_TEMPLATE_VI = """\
Bạn là SocraticAI — một đối thủ tranh luận chuyên nghiệp, sắc bén và thông thái, được đào tạo bài bản theo phương pháp Socratic và kỹ thuật Steelmanning.

**QUY TẮC NGÔN NGỮ BẮT BUỘC**:
Toàn bộ phản hồi của bạn BẮT BUỘC PHẢI BẰNG TIẾNG VIỆT 100%. Diễn đạt tự nhiên, chuẩn xác, mạch lạc, giàu tính thuyết phục. Tuyệt đối không trả lời bằng tiếng Anh, ngay cả khi tên chủ đề hoặc thuật ngữ có chứa tiếng Anh.

**Chủ đề tranh luận**: {topic}
{topic_description_block}
**Lập trường của người dùng**: {user_position}
**Lập trường của bạn (AI)**: {ai_position}
**Độ khó**: {difficulty}

**Vai trò và quy trình phản biện của bạn**:
1. Lắng nghe và tôn trọng: Thách thức lập luận của người dùng bằng các câu hỏi thăm dò sâu sắc theo phương pháp Socratic.
2. Kỹ thuật Steelmanning: Trước khi phản biện, hãy thừa nhận và trình bày lại phiên bản mạnh nhất, hợp lý nhất trong lập luận của người dùng (1-2 câu).
3. Bảo vệ lập trường đối lập đã giao bằng phản biện rõ ràng, dựa trên lập luận chặt chẽ và bằng chứng có căn cứ. Không bảo vệ thông tin sai rõ ràng hoặc bịa bằng chứng; hãy đính chính tiền đề và giải thích điều đó ảnh hưởng thế nào đến tranh luận.
4. Độ dài: Giữ phản hồi súc tích, tập trung (200–350 từ).
5. Kết thúc: LUÔN LUÔN kết thúc bằng ĐÚNG MỘT câu hỏi Socratic sắc bén buộc người dùng phải suy ngẫm sâu hơn. Không bao giờ tự trả lời câu hỏi của mình.

Chỉ dùng bằng chứng mà bạn có cơ sở đáng tin cậy. Không bịa số liệu, nghiên cứu, trích dẫn hoặc nguồn; hãy nói rõ khi chưa chắc chắn và trình bày nhận định chưa được kiểm chứng như giả thuyết hoặc câu hỏi. Điều chỉnh ví dụ và từ vựng theo trình độ của người dùng.

{difficulty_instructions}

**Ngữ cảnh bộ nhớ** (các luận điểm liên quan từ phiên này):
{memory_context}

{contradiction_block}

Hãy tranh luận nghiêm túc về mặt trí tuệ nhưng luôn giữ thái độ tôn trọng. Không dùng đòn tấn công cá nhân.\
"""

_DIFFICULTY_INSTRUCTIONS = {
    "beginner": (
        "The user may be a middle-school student. Be encouraging, explain one idea at a time "
        "in plain language, use familiar everyday examples, and model good argument habits "
        "without talking down to them."
    ),
    "advanced": (
        "The user is experienced. Use sophisticated counter-arguments, demand evidence, "
        "and exploit logical weaknesses in their reasoning."
    ),
    "expert": (
        "The user is an expert debater. Deploy advanced rhetorical strategies, reference "
        "established philosophical frameworks, and construct multi-layered rebuttals. "
        "Do not hold back."
    ),
}

_DIFFICULTY_INSTRUCTIONS_VI = {
    "beginner": (
        "Người dùng có thể là học sinh THCS. Hãy động viên, giải thích từng ý bằng ngôn ngữ "
        "đơn giản, dùng ví dụ gần gũi trong đời sống và hướng dẫn thói quen lập luận tốt "
        "mà không tỏ thái độ xem thường."
    ),
    "advanced": (
        "Người dùng có kinh nghiệm. Sử dụng phản luận tinh vi, đòi hỏi bằng chứng xác thực, "
        "và khai thác các lỗ hổng logic trong suy luận của họ."
    ),
    "expert": (
        "Người dùng là chuyên gia tranh luận. Triển khai các chiến lược hùng biện nâng cao, "
        "tham chiếu các trường phái triết học, và xây dựng hệ thống phản biện đa tầng. "
        "Không cần nương nhẹ."
    ),
}


def build_debate_system_prompt(
    config: DebateConfig,
    retrieved_claims: list[str],
    contradiction_alerts: list[str] | None = None,
) -> str:
    """Build the system prompt injected before each AI turn.

    Args:
        config: The session's debate configuration.
        retrieved_claims: Past claims retrieved from Qdrant for memory context.
        contradiction_alerts: Detected contradictions between current and past claims.

    Returns:
        A fully rendered system prompt string.
    """
    memory_context = (
        "\n".join(f"- {c}" for c in retrieved_claims)
        if retrieved_claims
        else (
            "Chưa có luận điểm trước đó được truy xuất."
            if config.language == "vi"
            else "No prior claims retrieved for this query."
        )
    )

    contradiction_block = ""
    if contradiction_alerts:
        lines = "\n".join(f"⚠ {alert}" for alert in contradiction_alerts)
        if config.language == "vi":
            contradiction_block = (
                f"**Cảnh báo mâu thuẫn** (người dùng đã tự mâu thuẫn):\n{lines}\n"
                "Hãy chỉ ra những mâu thuẫn này một cách lịch sự trong phản hồi của bạn."
            )
        else:
            contradiction_block = (
                f"**Contradiction alerts** (the user has contradicted themselves):\n{lines}\n"
                "Politely point out these contradictions in your response."
            )

    topic_description_block = ""
    if config.topic_description:
        prefix = "**Mô tả chủ đề**" if config.language == "vi" else "**Topic description**"
        topic_description_block = f"{prefix}: {config.topic_description}"

    is_vi = config.language == "vi"
    template = _SYSTEM_TEMPLATE_VI if is_vi else _SYSTEM_TEMPLATE_EN
    diff_map = _DIFFICULTY_INSTRUCTIONS_VI if is_vi else _DIFFICULTY_INSTRUCTIONS

    user_pos = config.user_position or "pro"
    ai_pos = config.ai_position or "con"
    if is_vi:
        pos_map = {"pro": "Ủng hộ (Pro)", "con": "Phản đối (Con)"}
        user_pos = pos_map.get(user_pos.lower(), user_pos)
        ai_pos = pos_map.get(ai_pos.lower(), ai_pos)

    return template.format(
        topic=config.topic,
        topic_description_block=topic_description_block,
        user_position=user_pos,
        ai_position=ai_pos,
        difficulty=config.difficulty,
        difficulty_instructions=diff_map.get(config.difficulty, ""),
        memory_context=memory_context,
        contradiction_block=contradiction_block,
    )


def build_user_turn_prompt(
    user_input: str,
    turns: list[Turn],
    is_vi: bool = True,
) -> str:
    """Build the user-turn message including recent conversation history.

    Args:
        user_input: The user's latest argument text.
        turns: Full list of turns in the session.
        is_vi: Whether the session is in Vietnamese.

    Returns:
        A prompt string with recent history and the user's latest input.
    """
    history_lines: list[str] = []
    for turn in turns[-6:]:  # Last 3 exchanges (6 turns)
        if is_vi:
            prefix = "Người dùng" if turn.speaker == "user" else "SocraticAI"
        else:
            prefix = "User" if turn.speaker == "user" else "AI"
        history_lines.append(f"{prefix}: {turn.content}")

    if is_vi:
        history_block = (
            "\n".join(history_lines) if history_lines else "Chưa có lượt tranh luận trước đó."
        )
        return (
            f"**Lịch sử hội thoại gần đây**:\n{history_block}\n\n"
            f"**Luận điểm mới nhất của người dùng**:\n{user_input}\n\n"
            f"(Ghi nhớ: Hãy trả lời hoàn toàn bằng TIẾNG VIỆT và kết thúc bằng một câu hỏi Socratic)"
        )
    else:
        history_block = "\n".join(history_lines) if history_lines else "No prior turns."
        return f"**Recent conversation**:\n{history_block}\n\n**User's latest argument**:\n{user_input}"
