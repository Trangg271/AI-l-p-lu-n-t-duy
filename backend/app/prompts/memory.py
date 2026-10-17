# backend/app/prompts/memory.py
"""
Prompt builders for the memory extraction pipeline.

Used by: ``graph/nodes.py`` → ``memory_node`` (configured fast model)

Extracts atomic factual and normative claims from the latest AI
response (and optionally the user's turn) for storage in Qdrant.
The structured JSON output is parsed into ``list[Claim]``.
"""

from __future__ import annotations

_MEMORY_EXTRACTION_PROMPT_EN = """\
You are a claim extraction specialist. Your task is to extract atomic, self-contained claims from the following debate exchange.

**Debate topic**: {topic}
**Speaker**: {speaker}
**Text to extract claims from**:
{text}

**Instructions**:
- Extract every distinct factual assertion, normative claim, concession, retraction, commitment, or question.
- Each claim should be self-contained — understandable without the surrounding context.
- Classify each claim into one of these types: "assertion", "concession", "retraction", "commitment", "question".
- Identify key named entities (people, organisations, concepts, statistics) referenced in each claim.
- Return at most 10 claims.

Respond ONLY with valid JSON in this exact format:
{{
  "claims": [
    {{
      "claim_text": "...",
      "claim_type": "assertion|concession|retraction|commitment|question",
      "key_entities": ["entity1", "entity2"]
    }}
  ]
}}\
"""

_MEMORY_EXTRACTION_PROMPT_VI = """\
Bạn là chuyên gia trích xuất luận điểm. Nhiệm vụ của bạn là trích xuất các luận điểm nguyên tử, độc lập từ đoạn tranh luận sau.

**Chủ đề tranh luận**: {topic}
**Người nói**: {speaker}
**Văn bản cần trích xuất**:
{text}

**Hướng dẫn**:
- Trích xuất mọi khẳng định sự kiện, tuyên bố quy phạm, nhượng bộ, rút lại, cam kết, hoặc câu hỏi riêng biệt.
- Mỗi luận điểm phải độc lập — có thể hiểu được mà không cần ngữ cảnh xung quanh.
- Phân loại mỗi luận điểm thành: "assertion", "concession", "retraction", "commitment", "question".
- Xác định các thực thể có tên (người, tổ chức, khái niệm, thống kê) được nhắc đến.
- Trả về tối đa 10 luận điểm.

Chỉ trả lời bằng JSON hợp lệ theo đúng định dạng này:
{{
  "claims": [
    {{
      "claim_text": "...",
      "claim_type": "assertion|concession|retraction|commitment|question",
      "key_entities": ["entity1", "entity2"]
    }}
  ]
}}\
"""


def build_memory_extraction_prompt(
    text: str,
    topic: str,
    speaker: str,
    language: str,
) -> str:
    """Build the memory extraction prompt.

    Args:
        text: The text to extract claims from (AI response or user turn).
        topic: The debate topic for context.
        speaker: Who produced the text (``"user"`` or ``"ai"``).
        language: Session language (``"en"``, ``"vi"``, or ``"bilingual"``).

    Returns:
        A fully rendered prompt string requesting JSON output.
    """
    template = _MEMORY_EXTRACTION_PROMPT_VI if language == "vi" else _MEMORY_EXTRACTION_PROMPT_EN
    return template.format(topic=topic, speaker=speaker, text=text)
