"""Shared data models for the PM News Agent pipeline.

Defines Pydantic models used across pipeline components for
structured data exchange and JSON serialization.
"""

from datetime import datetime

from pydantic import BaseModel


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


# --- Phase 3: Agent Step Models ---


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
    """Category-specific extraction details."""

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
    thematic_tags: list[ThematicTag]
    pm_relevant_gaps: list[str]
    group_label: str  # From the grouping step (for synthesis cross-ref)
