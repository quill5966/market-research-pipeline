"""Closed vocabulary for per-article filter_tags.

These tags drive UI tag-chip filtering in the brief view. They are distinct
from ExtractionNote.thematic_tags, which drive synthesis-time section routing.
"""

import os

DEFAULT_FILTER_TAG_VOCABULARY: list[str] = [
    "competitive",
    "acquisition",
    "funding",
    "product-launch",
    "pricing",
    "partnership",
    "regulatory",
    "security",
    "leadership",
    "earnings",
    "open-source",
    "standards",
    "customer-signal",
    "analyst",
]


def _load_vocabulary() -> list[str]:
    env_value = os.environ.get("FILTER_TAG_VOCABULARY")
    if not env_value:
        return DEFAULT_FILTER_TAG_VOCABULARY
    overrides = [t.strip() for t in env_value.split(",") if t.strip()]
    return overrides or DEFAULT_FILTER_TAG_VOCABULARY


FILTER_TAG_VOCABULARY: list[str] = _load_vocabulary()
