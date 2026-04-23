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
