"""JSON parsing utility for LLM responses.

Handles common formatting issues in LLM-generated JSON:
code fences, preamble text, and trailing commas.
"""

import json
import re


def parse_llm_json(text: str) -> dict | list:
    """Parse JSON from LLM output, handling common formatting issues.

    Handles:
    - JSON wrapped in ```json ... ``` code fences
    - Leading/trailing preamble text before/after JSON
    - Trailing commas (common LLM mistake)

    Args:
        text: Raw text from an LLM response that should contain JSON.

    Returns:
        Parsed JSON as a dict or list.

    Raises:
        ValueError: If JSON cannot be parsed after all cleanup attempts.
    """
    # Fast path: try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip markdown code fences
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            # Try fixing trailing commas in fenced content
            cleaned = _fix_trailing_commas(fence_match.group(1))
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass

    # Find JSON by looking for first { or [ and last matching } or ]
    extracted = _extract_json_substring(text)
    if extracted:
        try:
            return json.loads(extracted)
        except json.JSONDecodeError:
            # Try fixing trailing commas
            cleaned = _fix_trailing_commas(extracted)
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass

    # All attempts failed
    preview = text[:200] + ("..." if len(text) > 200 else "")
    raise ValueError(
        f"Could not parse JSON from LLM output. "
        f"Preview of raw text: {preview}"
    )


def _extract_json_substring(text: str) -> str | None:
    """Find the outermost JSON object or array in text."""
    # Find the first { or [
    obj_start = text.find("{")
    arr_start = text.find("[")

    if obj_start == -1 and arr_start == -1:
        return None

    if obj_start == -1:
        start, open_char, close_char = arr_start, "[", "]"
    elif arr_start == -1:
        start, open_char, close_char = obj_start, "{", "}"
    else:
        if obj_start < arr_start:
            start, open_char, close_char = obj_start, "{", "}"
        else:
            start, open_char, close_char = arr_start, "[", "]"

    # Find the matching closing bracket
    end = text.rfind(close_char)
    if end == -1 or end <= start:
        return None

    return text[start : end + 1]


def _fix_trailing_commas(text: str) -> str:
    """Remove trailing commas before closing brackets/braces."""
    return re.sub(r",\s*([}\]])", r"\1", text)
