# backend/app/prompts/fallacy.py
"""
Prompt builders for logical fallacy detection.

Used by: ``graph/nodes.py`` → ``fallacy_node`` (gemini-2.5-pro)

The response is requested as structured JSON conforming to the
``FallacyResult`` schema with bilingual metadata, severity Literal,
confidence score, and constructive suggestions.
"""

from __future__ import annotations

_FALLACY_PROMPT_EN = """\
You are a formal logic expert specialising in debate analysis. Analyse the following argument for logical fallacies.

**Debate topic**: {topic}
**Argument to analyse**:
{argument}

**Instructions**:
- Identify ALL logical fallacies present (ad hominem, straw man, false dichotomy, slippery slope, appeal to authority, hasty generalisation, circular reasoning, red herring, tu quoque, equivocation, etc.).
- For each fallacy found, output a JSON object with these EXACT fields:
  - "fallacy_type": the canonical English name of the fallacy
  - "fallacy_name_vi": the Vietnamese name of the fallacy
  - "severity": one of "minor", "moderate", or "major"
  - "offending_excerpt": the exact phrase or sentence containing the fallacy
  - "explanation": one or two sentences explaining why this is a fallacy in this context
  - "suggestion": a constructive suggestion for how to fix the argument
  - "confidence": a float 0.0–1.0 indicating your confidence in this detection

- If NO fallacies are found, return an empty list.

Respond ONLY with valid JSON in this exact format:
{{
  "fallacies": [
    {{
      "fallacy_type": "...",
      "fallacy_name_vi": "...",
      "severity": "minor|moderate|major",
      "offending_excerpt": "...",
      "explanation": "...",
      "suggestion": "...",
      "confidence": 0.0
    }}
  ]
}}\
"""

_FALLACY_PROMPT_VI = """\
Bạn là chuyên gia logic hình thức chuyên về phân tích tranh luận. Hãy phân tích lập luận sau để tìm các ngụy biện logic.

**Chủ đề tranh luận**: {topic}
**Lập luận cần phân tích**:
{argument}

**Hướng dẫn**:
- Xác định TẤT CẢ các ngụy biện logic có trong bài (tấn công cá nhân, người rơm, lưỡng phân sai, dốc trơn, kêu gọi quyền uy, khái quát vội, lập luận vòng tròn, cá trích đỏ, tu quoque, mập mờ ngữ nghĩa, v.v.).
- Với mỗi ngụy biện tìm thấy, output một JSON object với các trường CHÍNH XÁC sau:
  - "fallacy_type": tên chuẩn bằng tiếng Anh (ví dụ: "Ad Hominem", "Straw Man", "False Dilemma")
  - "fallacy_name_vi": tên ngụy biện bằng TIẾNG VIỆT (ví dụ: "Tấn công cá nhân", "Người rơm", "Lưỡng phân sai")
  - "severity": một trong "minor", "moderate", hoặc "major"
  - "offending_excerpt": đoạn trích chính xác trong bài của người dùng chứa ngụy biện
  - "explanation": một hoặc hai câu giải thích rõ ràng HOÀN TOÀN BẰNG TIẾNG VIỆT tại sao đây là ngụy biện
  - "suggestion": gợi ý cụ thể HOÀN TOÀN BẰNG TIẾNG VIỆT để khắc phục lập luận
  - "confidence": float từ 0.0–1.0 cho mức độ tự tin

- Nếu KHÔNG tìm thấy ngụy biện, trả về danh sách rỗng.

Chỉ trả lời bằng JSON hợp lệ theo đúng định dạng này:
{{
  "fallacies": [
    {{
      "fallacy_type": "...",
      "fallacy_name_vi": "...",
      "severity": "minor|moderate|major",
      "offending_excerpt": "...",
      "explanation": "...",
      "suggestion": "...",
      "confidence": 0.0
    }}
  ]
}}\
"""


def build_fallacy_detection_prompt(
    argument: str,
    topic: str,
    language: str,
) -> str:
    """Return the full fallacy detection prompt for the given language.

    Args:
        argument: The user's argument text to analyse.
        topic: The debate topic for context.
        language: Session language (``"en"``, ``"vi"``, or ``"bilingual"``).

    Returns:
        A fully rendered prompt string requesting JSON output.
    """
    template = _FALLACY_PROMPT_VI if language == "vi" else _FALLACY_PROMPT_EN
    return template.format(topic=topic, argument=argument)
