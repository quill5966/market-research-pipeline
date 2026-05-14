"""Shared data models for the Market Research Pipeline.

Defines Pydantic models used across pipeline components for
structured data exchange and JSON serialization.

Model groups:
- Token tracking: StepUsage, RunLog
- Search & dedup: SearchResult, DedupStats
- Agent steps: GroupedStory, GroupingResult, ThematicTag, ExtractionNote
- API: RunRequest, Stage, Run
- Brief: Highlight, Story, WatchlistItem, ActionItem, Source, Brief
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator


# --- Token tracking models ---


class StepUsage(BaseModel):
    """Token usage for a single pipeline step."""

    step_name: str  # e.g., "grouping", "extraction_article_3"
    input_tokens: int
    output_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    timestamp: datetime


class RunLog(BaseModel):
    """Complete token usage log for a pipeline run."""

    run_id: str  # e.g., "2026-04-22T19-30-00_identity-mgmt"
    domain: str
    model: str
    token_budget: int
    pricing: dict[str, float]  # {"input_per_million": 3.00, "output_per_million": 15.00}
    steps: list[StepUsage]
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    budget_remaining: int
    started_at: datetime
    completed_at: datetime | None = None


# --- Search & dedup models ---


class SearchResult(BaseModel):
    """A single search result from Tavily."""

    title: str
    url: str
    snippet: str  # Tavily 'content' field
    raw_content: str | None = None  # Full article text (None if extraction failed)
    score: float  # Tavily relevance score (0-1)
    source_domain: str  # Extracted from URL (e.g., "reuters.com")
    search_term: str  # Which search term produced this result


class DedupStats(BaseModel):
    """Statistics from the deduplication pipeline."""

    raw_count: int
    after_url_dedup: int
    after_domain_title_dedup: int
    after_snippet_dedup: int
    removed_total: int


# --- Agent step models ---


class GroupedStory(BaseModel):
    """A group of related search results identified by the grouper."""

    group_label: str  # Human-readable story label
    selected_url: str  # Best source URL to process
    selected_title: str  # Title of the selected source
    rationale: str  # Why this source was chosen
    related_urls: list[str] = []  # Other URLs in this group (not processed)


class GroupingResult(BaseModel):
    """Full output from the grouping step."""

    groups: list[GroupedStory]
    discarded_count: int  # Number of results deemed irrelevant


class ThematicTag(BaseModel):
    """Category-specific extraction details (for section routing)."""

    category: str  # e.g., "competitor_moves", "market_macro"
    details: str  # Category-specific details


class ExtractionNote(BaseModel):
    """Structured extraction from a single article."""

    headline: str
    source: str
    source_url: str
    date: str | None = None
    author: str | None = None
    what_happened: str  # 3-5 sentence summary of core facts
    data_points: list[str]  # Specific numbers, dates, percentages
    quotes: list[str]  # Direct quotes with attribution
    companies_and_products: list[str]  # With context for each
    thematic_tags: list[ThematicTag]  # Coarse categories for section routing
    filter_tags: list[str] = []  # Fine-grained tags from closed vocabulary for UI filtering
    pm_relevant_gaps: list[str]
    group_label: str  # From the grouping step (for synthesis cross-ref)


# --- API models ---


class RunRequest(BaseModel):
    """Request body for POST /api/runs — submitted from the UI form."""

    domain_description: str  # required, 10-500 chars
    search_terms: list[str]  # required, 1-10 items
    include_domains: list[str] = []  # optional
    exclude_domains: list[str] = []  # optional
    # Advanced options — client is the source of truth, so these are required.
    max_results_per_term: int
    max_article_chars: int
    dedup_title_similarity: float
    dedup_snippet_similarity: float
    # Note: token_budget is NOT here — it's server config only

    @field_validator("domain_description")
    @classmethod
    def domain_description_length(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 10:
            raise ValueError("domain_description must be at least 10 characters")
        if len(v) > 500:
            raise ValueError("domain_description must be at most 500 characters")
        return v

    @field_validator("search_terms")
    @classmethod
    def search_terms_not_empty(cls, v: list[str]) -> list[str]:
        v = [t.strip() for t in v if t.strip()]
        if not v:
            raise ValueError("At least one search term is required")
        if len(v) > 10:
            raise ValueError("At most 10 search terms allowed")
        return v


class Stage(BaseModel):
    """Pipeline stage progress (part of a Run)."""

    name: Literal["search", "dedup", "group", "extract", "synthesize"]
    status: Literal["pending", "active", "done", "failed"] = "pending"
    detail: str = "Waiting"
    elapsed_ms: int | None = None


class Run(BaseModel):
    """Full run state — returned by GET /api/runs/:id."""

    id: str  # UUID
    status: Literal["queued", "running", "complete", "failed"] = "queued"
    created_at: datetime
    request: RunRequest  # Echo of original request
    stages: list[Stage]
    brief: "Brief | None" = None  # Populated when status == "complete"
    error: str | None = None  # Populated when status == "failed"


# --- Structured brief models ---


class Highlight(BaseModel):
    """Top highlight entry in the brief."""

    rank: int  # 1, 2, or 3
    headline: str
    why_matters: str
    pointer_section: str  # Which section to navigate to


class Story(BaseModel):
    """A single story entry within a brief section."""

    id: str  # Stable hash of source URL, for tag-filter routing
    headline: str
    tldr: str
    pm_angle: str
    supporting: str | None = None  # Optional ≤80-word paragraph
    source_domain: str
    source_url: str
    additional_coverage: list[str] = []  # Other domains covering same story
    filter_tags: list[str] = []  # From closed vocabulary — powers UI filtering


class WatchlistItem(BaseModel):
    """Watchlist entry in the brief."""

    topic: str  # Bolded prefix
    signal: str  # The body
    source_domain: str


class ActionItem(BaseModel):
    """PM action item in the brief."""

    rank: int
    text: str
    pointer_section: str  # Which section motivates this
    pointer_story_id: str | None = None  # For filter-following


class Source(BaseModel):
    """Source citation in the brief."""

    domain: str
    url: str
    referenced_in: list[str]  # Section titles where this URL appears


class Section(BaseModel):
    """A section of the brief — the synthesizer chooses the type and title per run."""

    type: Literal["summary", "list", "callout", "quote"]
    title: str  # Section heading (e.g., "Competitor Moves", "Outlook")
    content_md: str | None = None  # Prose body for summary/callout/quote (and optional lede for list)
    stories: list[Story] = []  # Populated only for type == "list"
    source_urls: list[str] = []  # Consolidated source URLs for this section


class Brief(BaseModel):
    """The synthesized PM brief — the main deliverable."""

    title: str  # e.g., "Enterprise identity and access management"
    date: str  # Run date string
    source_count: int
    story_count: int
    search_term_count: int
    raw_markdown: str  # Rendered markdown blob for export
    highlights: list[Highlight]
    executive_summary: str
    sections: list[Section]  # Ordered; synthesizer decides which sections exist
    watchlist: list[WatchlistItem]
    action_items: list[ActionItem]
    sources: list[Source]
