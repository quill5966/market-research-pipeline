"""Configuration loading and validation for the Market Research Pipeline.

Two config layers:
- ServerConfig: loaded once at startup from .env.local (API keys, model, budget, paths)
- RunConfig: built per-request by merging ServerConfig with RunRequest from the UI form
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, field_validator


class ServerConfig(BaseModel):
    """Server-level configuration loaded from .env.local at startup.

    Contains values that are fixed for the server instance:
    API keys, model selection, token budget, and output paths.
    """

    # API keys
    anthropic_api_key: str
    tavily_api_key: str

    # Shared-secret gate for the app (sent by the client as Authorization: Bearer <passcode>)
    app_passcode: str

    # LLM fallback if not set in env variables
    model: str = "claude-sonnet-4-6"
    token_budget: int = 200_000

    # Smaller/cheaper model used to suggest search terms on the New Run screen
    # before the pipeline runs. Must also have an entry in MODEL_PRICING.
    suggestion_model: str = "claude-haiku-4-5-20251001"

    # Output paths
    output_dir: str = "output"
    log_dir: str = "logs"

    # Concurrency limit: max simultaneously-running pipeline runs across the server
    max_concurrent_runs: int = 3

    # Max corrective passes the agent reviewer may trigger per run (0 disables
    # the review loop). Each corrective pass gets a freshly replenished budget.
    max_review_iterations: int = 1

    @field_validator("app_passcode")
    @classmethod
    def passcode_must_be_strong_enough(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("APP_PASSCODE must be at least 8 characters")
        return v

    @field_validator("max_concurrent_runs")
    @classmethod
    def max_concurrent_runs_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"MAX_CONCURRENT_RUNS must be positive, got {v}")
        return v

    @field_validator("max_review_iterations")
    @classmethod
    def max_review_iterations_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError(f"MAX_REVIEW_ITERATIONS must be >= 0, got {v}")
        return v

    @field_validator("token_budget")
    @classmethod
    def token_budget_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"TOKEN_BUDGET must be a positive integer, got {v}")
        return v


class RunConfig(BaseModel):
    """Per-run configuration built by merging ServerConfig with RunRequest.

    Contains everything the pipeline needs to execute a single run.
    """

    # From ServerConfig
    anthropic_api_key: str
    tavily_api_key: str
    model: str
    token_budget: int
    output_dir: str
    log_dir: str
    max_review_iterations: int

    # From RunRequest (user-supplied via UI form)
    product_name: str
    product_context: str
    search_terms: list[str]
    include_domains: list[str] = []
    exclude_domains: list[str] = []
    max_results_per_term: int
    max_article_chars: int
    dedup_title_similarity: float
    dedup_snippet_similarity: float

    @field_validator("max_article_chars")
    @classmethod
    def max_article_chars_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"max_article_chars must be a positive integer, got {v}")
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
            raise ValueError("search_terms must contain at least one term")
        return v


def load_server_config(env_path: str | None = None) -> ServerConfig:
    """Load server config from .env.local or .env file.

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
        "APP_PASSCODE": "Shared passcode that gates the UI/API (min 8 chars)",
    }

    # Exact placeholder values to reject (from .env.example)
    PLACEHOLDERS = {"sk-ant-...", "tvly-...", "change-me"}

    missing = []
    for key, description in required_keys.items():
        value = os.getenv(key)
        if not value or value in PLACEHOLDERS:
            missing.append(f"  {key}: {description}")

    if missing:
        raise ValueError(
            "Missing required config values in .env file:\n"
            + "\n".join(missing)
            + "\n\nCopy .env.example to .env.local and fill in the values."
        )

    config = ServerConfig(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        tavily_api_key=os.getenv("TAVILY_API_KEY", ""),
        app_passcode=os.getenv("APP_PASSCODE", ""),
        model=os.getenv("MODEL", "claude-sonnet-4-6"),
        token_budget=int(os.getenv("TOKEN_BUDGET", "200000")),
        suggestion_model=os.getenv("SUGGESTION_MODEL", "claude-haiku-4-5-20251001"),
        output_dir=os.getenv("OUTPUT_DIR", "output"),
        log_dir=os.getenv("LOG_DIR", "logs"),
        max_concurrent_runs=int(os.getenv("MAX_CONCURRENT_RUNS", "3")),
        max_review_iterations=int(os.getenv("MAX_REVIEW_ITERATIONS", "1")),
    )

    # Ensure output directories exist
    Path(config.output_dir).mkdir(parents=True, exist_ok=True)
    Path(config.log_dir).mkdir(parents=True, exist_ok=True)

    return config


def build_run_config(server: ServerConfig, request) -> RunConfig:
    """Merge ServerConfig with a RunRequest to produce a RunConfig.

    Args:
        server: Server-level config (API keys, model, budget, paths).
        request: RunRequest from the API (domain, terms, thresholds).

    Returns:
        A complete RunConfig for the pipeline to execute.
    """
    return RunConfig(
        # From server
        anthropic_api_key=server.anthropic_api_key,
        tavily_api_key=server.tavily_api_key,
        model=server.model,
        token_budget=server.token_budget,
        output_dir=server.output_dir,
        log_dir=server.log_dir,
        max_review_iterations=server.max_review_iterations,
        # From request
        product_name=request.product_name,
        product_context=request.product_context,
        search_terms=request.search_terms,
        include_domains=request.include_domains,
        exclude_domains=request.exclude_domains,
        max_results_per_term=request.max_results_per_term,
        max_article_chars=request.max_article_chars,
        dedup_title_similarity=request.dedup_title_similarity,
        dedup_snippet_similarity=request.dedup_snippet_similarity,
    )
