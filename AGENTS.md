# AGENTS.md — PM News Agent

> Context file for LLM coding assistants. Keep this updated with every code change.

## Project Overview

An agentic pipeline that searches the web for news related to a specific product domain, deduplicates and synthesizes the results using LLM calls, and produces a structured PM brief as markdown output. Designed for manual, on-demand runs.

**Full MVP spec:** [`pm-news-agent-mvp-plan.md`](./pm-news-agent-mvp-plan.md)

## Tech Stack

- **Python 3.14.4**
- **Anthropic SDK** (`anthropic`) — Claude Sonnet 4.6 for all LLM calls
- **Pydantic v2** — config validation, data models, JSON serialization
- **python-dotenv** — env file loading (`.env.local` → `.env` priority)
- **Tavily** (`tavily-python`) — web search with advanced search + `include_raw_content=True` (replaces the need for a separate article fetcher)

## Project Structure

```
market-research-pipeline/
├── .env.local              # Real API keys (gitignored)
├── .env.example            # Template showing all config keys
├── .gitignore
├── requirements.txt        # Pinned dependencies
├── AGENTS.md               # This file — LLM context
├── CLAUDE.md               # Points to AGENTS.md
├── pm-news-agent-mvp-plan.md # Full MVP specification
├── config.py               # Config loading + Pydantic validation
├── models.py               # Shared data models (StepUsage, RunLog)
├── main.py                 # Pipeline orchestrator (entry point)
├── agent/
│   ├── client.py           # Anthropic SDK wrapper with token budget enforcement
│   └── json_utils.py       # Parses JSON from LLM output (strips code fences, etc.)
├── tracking/
│   └── token_tracker.py    # Per-step token usage + cost logging → JSON
├── output/                 # Generated briefs land here (gitignored)
└── logs/                   # Token usage JSON logs per run (gitignored)
```

### Planned directories (not yet implemented)

```
├── services/
│   ├── search.py           # Tavily search wrapper
│   └── dedup.py            # URL + snippet deduplication
├── agent/
│   ├── grouper.py          # LLM: group search results by story
│   ├── extractor.py        # LLM: per-article structured extraction
│   └── synthesizer.py      # LLM: generate PM brief from extraction notes
├── prompts/
│   ├── system.py           # Base system prompt with domain context
│   ├── grouping.py         # Prompt for snippet grouping step
│   ├── extraction.py       # Prompt for article extraction step
│   └── synthesis.py        # Prompt for final brief generation
└── templates/
    └── pm_brief.py         # Brief template definition
```

## Implementation Status

| Phase | Status | What it covers |
|-------|--------|----------------|
| **Phase 1: Foundation** | ✅ Complete | Config, token tracker, LLM client wrapper, data models |
| **Phase 2: Search & Dedup** | 🔲 Not started | Tavily search, URL/snippet deduplication |
| **Phase 3: Agent Steps** | 🔲 Not started | Grouping, extraction, synthesis LLM steps |
| **Phase 4: Output & Polish** | 🔲 Not started | Markdown formatter, CLI, run summaries |

## Architecture & Data Flow

```
Config (.env.local)
  → load_config() → Config object (Pydantic)
  → TokenTracker (initialized with run_id, model, budget)
  → AgentClient (wraps Anthropic SDK, auto-records tokens)

Pipeline (main.py orchestrates):
  1. Search         → Tavily advanced search, one call per term (deterministic)
  2. Dedup          → URL + title + snippet similarity filtering (deterministic)
  3. Agent: Group   → LLM groups snippets by story, picks best sources (tokens)
  4. Agent: Extract → LLM extracts structured notes per article (tokens)
  5. Agent: Synth   → LLM generates PM brief from all notes (tokens)
  6. Formatter      → Renders markdown to output/ (deterministic)
  7. Token Tracker  → Writes JSON log to logs/ (deterministic)
```

## Key Patterns & Conventions

### Config
- **`config.py`** loads `.env.local` first, falls back to `.env`. Pass explicit path to override.
- Required keys: `ANTHROPIC_API_KEY`, `DOMAIN_DESCRIPTION`, `SEARCH_TERMS`.
- Pydantic validators enforce types and ranges (e.g., `TOKEN_BUDGET > 0`, similarity thresholds in `[0, 1]`).
- `output/` and `logs/` directories are auto-created on config load.

### LLM Calls
- **All LLM calls go through `AgentClient.call()`** — never call `anthropic.Anthropic()` directly.
- Each call requires a `step_name` string for token tracking.
- Budget enforcement: chars÷4 estimation before the call; actual `response.usage` recorded after.
- `TokenBudgetExceeded` exception raised if estimated usage would exceed budget.
- Rate limit: single retry with 30s backoff on `RateLimitError`.
- Temperature defaults to `0.0` (deterministic) for all pipeline steps.

### Token Tracking & Cost
- **The Anthropic API does NOT return cost** — only `input_tokens`/`output_tokens`.
- Cost is calculated locally using the `MODEL_PRICING` dict in `tracking/token_tracker.py`.
- When adding a new model, add its pricing to `MODEL_PRICING`. The tracker raises `KeyError` on unknown models.
- Current pricing (Sonnet 4.6): $3.00/M input, $15.00/M output.
- Each run produces a JSON log in `logs/{run_id}.json` with per-step breakdown.
- `run_id` format: `{timestamp}_{sanitized-domain}` — unique per invocation (second precision).

### JSON Parsing
- LLM responses expected as JSON should be parsed through `agent/json_utils.py:parse_llm_json()`.
- Handles: code fences, preamble text, trailing commas.

### Data Models
- All shared data structures are Pydantic models in `models.py`.
- `StepUsage`: per-LLM-call token/cost record.
- `RunLog`: full run summary with all steps, written to JSON via `.model_dump_json()`.

## Search (Phase 2 — Not Yet Implemented)

Decision: **Tavily advanced search** with `search_depth="advanced"` and `include_raw_content=True`.
- One API call per search term, results combined.
- Returns `title`, `url`, `content` (snippet), `raw_content` (full article text), `score`.
- `raw_content` eliminates the need for a separate fetcher/scraper service.
- Dedup operates on snippets/titles/URLs — before `raw_content` is used downstream.

## Running the Project

```bash
cd pm-news-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copy and fill in your API keys
cp .env.example .env.local
# Edit .env.local with real ANTHROPIC_API_KEY

# Run the pipeline
python main.py
```

## Important Files to Read First

1. `config.py` — understand what config is available and how it's loaded
2. `agent/client.py` — understand the LLM call interface (`AgentClient.call()`)
3. `tracking/token_tracker.py` — understand `MODEL_PRICING` and how costs are tracked
4. `main.py` — see how everything is wired together
