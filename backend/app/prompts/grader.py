# backend/app/prompts/grader.py
"""
Prompt builders for post-session grading.

Used by: ``graph/nodes.py`` → ``grader_node`` (gemini-2.5-pro)

Aggregates the full debate transcript and extracted claims to produce
a ``SessionScore`` with four sub-dimensions (0-25 each), letter grade,
bilingual feedback, and a verdict summary.
"""

from __future__ import annotations

from app.models.session import Claim, Turn

_GRADING_PROMPT_EN = """\
You are an expert debate coach and formal logic professor. Grade the following debate session.

**Debate topic**: {topic}
**Difficulty level**: {difficulty}
**User's position**: {user_position}

**Full debate transcript**:
{transcript}

**Extracted claims made by the user across the session**:
{claims_summary}

**Total fallacies committed by the user**: {fallacy_count}

**Grading rubric** (each sub-score is 0-25, total is 0-100):

1. **Argument Depth** (0-25): Sophistication, nuance, and originality of arguments. Did the user go beyond surface-level points?
2. **Logical Consistency** (0-25): Internal consistency across turns. Did they contradict themselves? Were their inferences valid?
3. **Evidence Quality** (0-25): Did they cite evidence, examples, data, or authoritative sources? Were references relevant and accurate?
4. **Rebuttal Effectiveness** (0-25): How well did they address and counter the AI's arguments? Did they engage with the strongest version of opposing points?

**Letter grade mapping**:
- A: 85-100 (Excellent)
- B: 70-84 (Good)
- C: 55-69 (Satisfactory)
- D: 40-54 (Needs Improvement)
- F: 0-39 (Poor)

**Output instructions**:
- Provide 2-4 specific strengths (in English)
- Provide 2-4 specific strengths (in Vietnamese: diễn đạt tự nhiên, chuẩn mực)
- Provide 2-4 areas for improvement (in English)
- Provide 2-4 areas for improvement (in Vietnamese: góp ý chi tiết, mang tính xây dựng)
- Write a one-paragraph verdict in English
- Write a one-paragraph verdict in Vietnamese (nhận xét toàn diện, sâu sắc bằng tiếng Việt)

Respond ONLY with valid JSON in this exact format:
{{
  "argument_depth": 0,
  "logical_consistency": 0,
  "evidence_quality": 0,
  "rebuttal_effectiveness": 0,
  "total": 0,
  "grade": "A|B|C|D|F",
  "fallacies_committed": 0,
  "contradictions_caught": 0,
  "strengths_en": ["..."],
  "strengths_vi": ["..."],
  "improvements_en": ["..."],
  "improvements_vi": ["..."],
  "verdict_en": "...",
  "verdict_vi": "..."
}}\
"""


def _format_transcript(turns: list[Turn]) -> str:
    """Format the turn list into a readable transcript.

    Args:
        turns: Ordered list of debate turns.

    Returns:
        A formatted multi-line string.
    """
    lines: list[str] = []
    for turn in turns:
        prefix = "User" if turn.speaker == "user" else "AI"
        lines.append(f"[Turn {turn.turn_number}] {prefix}: {turn.content}")
    return "\n\n".join(lines) if lines else "No turns recorded."


def _format_claims(claims: list[Claim]) -> str:
    """Format claims into a summary string.

    Args:
        claims: All claims extracted during the session.

    Returns:
        A formatted claims list.
    """
    user_claims = [c for c in claims if c.speaker == "user"]
    if not user_claims:
        return "No claims extracted."

    lines: list[str] = []
    for claim in user_claims:
        lines.append(
            f"- [{claim.claim_type}] {claim.claim_text} "
            f"(entities: {', '.join(claim.key_entities) if claim.key_entities else 'none'})"
        )
    return "\n".join(lines)


def build_grading_prompt(
    topic: str,
    difficulty: str,
    user_position: str,
    turns: list[Turn],
    claims: list[Claim],
    fallacy_count: int,
) -> str:
    """Build the session grading prompt.

    Args:
        topic: The debate topic.
        difficulty: Difficulty level of the session.
        user_position: The stance the user defended.
        turns: Full ordered list of debate turns.
        claims: All claims extracted during the session.
        fallacy_count: Total fallacies committed by the user.

    Returns:
        A fully rendered prompt string requesting JSON output.
    """
    return _GRADING_PROMPT_EN.format(
        topic=topic,
        difficulty=difficulty,
        user_position=user_position,
        transcript=_format_transcript(turns),
        claims_summary=_format_claims(claims),
        fallacy_count=fallacy_count,
    )
