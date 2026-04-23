"""Configuration loading and validation for the PM News Agent pipeline.

Loads config from .env file, validates required keys, and exposes
a typed Config object for use across the pipeline.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, field_validator


class Config(BaseModel):
    """Validated pipeline configuration."""

    # LLM
    anthropic_api_key: str
    model: str = "claude-sonnet-4-6"
    token_budget: int = 50_000

    # Search (Tavily)
    tavily_api_key: str
    max_results_per_term: int = 5
    include_domains: list[str] = []
    exclude_domains: list[str] = []

    # Domain
    domain_description: str
    search_terms: list[str]

    # Dedup (Phase 2)
    dedup_title_similarity: float = 0.6
    dedup_snippet_similarity: float = 0.8

    # Content
    max_article_chars: int = 6000

    # Output
    output_dir: str = "output"
    log_dir: str = "logs"

    @field_validator("token_budget")
    @classmethod
    def token_budget_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"TOKEN_BUDGET must be a positive integer, got {v}")
        return v

    @field_validator("max_article_chars")
    @classmethod
    def max_article_chars_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"MAX_ARTICLE_CHARS must be a positive integer, got {v}")
        return v

    @field_validator("dedup_title_similarity", "dedup_snippet_similarity")
    @classmethod
    def similarity_must_be_in_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Similarity threshold must be between 0.0 and 1.0, got {v}")
        return v

    @field_validator("search_terms")
    @classmethod
    def search_terms_must_not_be_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("SEARCH_TERMS must contain at least one term")
        return v


def load_config(env_path: str | None = None) -> Config:
    """Load config from .env.local or .env file.

    Checks .env.local first (for local overrides with real secrets),
    then falls back to .env. An explicit env_path overrides both.

    Raises ValueError with clear messages if required keys are missing
    or invalid.
    """
    if env_path:
        load_dotenv(env_path)
    else:
        # .env.local takes priority over .env
        local_path = Path(".env.local")
        if local_path.exists():
            load_dotenv(local_path)
        else:
            load_dotenv(".env")

    # Check required keys with clear error messages
    required_keys = {
        "ANTHROPIC_API_KEY": "Your Anthropic API key (starts with sk-ant-...)",
        "TAVILY_API_KEY": "Your Tavily API key (starts with tvly-...)",
        "DOMAIN_DESCRIPTION": "A description of the product domain to research",
        "SEARCH_TERMS": "Comma-separated list of search terms",
    }

    # Exact placeholder values to reject (from .env.example)
    PLACEHOLDERS = {"sk-ant-...", "tvly-..."}

    missing = []
    for key, description in required_keys.items():
        value = os.getenv(key)
        if not value or value in PLACEHOLDERS:
            missing.append(f"  {key}: {description}")

    if missing:
        raise ValueError(
            "Missing required config values in .env file:\n"
            + "\n".join(missing)
            + "\n\nCopy .env.example to .env and fill in the values."
        )

    # Parse comma-separated list values
    raw_terms = os.getenv("SEARCH_TERMS", "")
    search_terms = [t.strip() for t in raw_terms.split(",") if t.strip()]

    raw_include = os.getenv("INCLUDE_DOMAINS", "")
    include_domains = [d.strip() for d in raw_include.split(",") if d.strip()]

    raw_exclude = os.getenv("EXCLUDE_DOMAINS", "")
    exclude_domains = [d.strip() for d in raw_exclude.split(",") if d.strip()]

    # Build config
    config = Config(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        model=os.getenv("MODEL", "claude-sonnet-4-6"),
        token_budget=int(os.getenv("TOKEN_BUDGET", "50000")),
        tavily_api_key=os.getenv("TAVILY_API_KEY", ""),
        max_results_per_term=int(os.getenv("MAX_RESULTS_PER_TERM", "5")),
        include_domains=include_domains,
        exclude_domains=exclude_domains,
        domain_description=os.getenv("DOMAIN_DESCRIPTION", ""),
        search_terms=search_terms,
        dedup_title_similarity=float(os.getenv("DEDUP_TITLE_SIMILARITY", "0.6")),
        dedup_snippet_similarity=float(os.getenv("DEDUP_SNIPPET_SIMILARITY", "0.8")),
        max_article_chars=int(os.getenv("MAX_ARTICLE_CHARS", "6000")),
        output_dir=os.getenv("OUTPUT_DIR", "output"),
        log_dir=os.getenv("LOG_DIR", "logs"),
    )

    # Ensure output directories exist
    Path(config.output_dir).mkdir(parents=True, exist_ok=True)
    Path(config.log_dir).mkdir(parents=True, exist_ok=True)

    return config
