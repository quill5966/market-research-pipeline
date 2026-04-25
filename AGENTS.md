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
├── models.py               # Shared data models (StepUsage, RunLog, agent step models)
├── main.py                 # Pipeline orchestrator (entry point)
├── agent/
│   ├── client.py           # Anthropic SDK wrapper with token budget enforcement
│   ├── json_utils.py       # Parses JSON from LLM output (strips code fences, etc.)
│   ├── grouper.py          # LLM: group search results by story
│   ├── extractor.py        # LLM: per-article structured extraction
│   └── synthesizer.py      # LLM: generate PM brief from extraction notes
├── prompts/
│   ├── system.py           # Base system prompt with domain context
│   ├── grouping.py         # Prompt for snippet grouping step
│   ├── extraction.py       # Prompt for article extraction step
│   └── synthesis.py        # Prompt for final brief generation
├── templates/
│   └── pm_brief.py         # Brief template definition
├── services/
│   ├── search.py           # Tavily advanced search wrapper
│   └── dedup.py            # URL + title + snippet deduplication
├── tracking/
│   └── token_tracker.py    # Per-step token usage + cost logging → JSON
├── output/                 # Generated briefs land here (gitignored)
└── logs/                   # Token usage JSON logs per run (gitignored)
```

## Implementation Status

| Phase | Status | What it covers |
|-------|--------|----------------|
| **Phase 1: Foundation** | ✅ Complete | Config, token tracker, LLM client wrapper, data models |
| **Phase 2: Search & Dedup** | ✅ Complete | Tavily search, URL/title/snippet deduplication |
| **Phase 3: Agent Steps** | ✅ Complete | Grouping, extraction, synthesis LLM steps |
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
- Required keys: `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`, `DOMAIN_DESCRIPTION`, `SEARCH_TERMS`.
- Pydantic validators enforce types and ranges (e.g., `TOKEN_BUDGET > 0`, similarity thresholds in `[0, 1]`, `MAX_ARTICLE_CHARS > 0`).
- `output/` and `logs/` directories are auto-created on config load.
- `INCLUDE_DOMAINS` / `EXCLUDE_DOMAINS`: comma-separated lists for Tavily domain filtering. Configurable per-user in `.env.local`.

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
- `SearchResult`: normalized Tavily search result with `title`, `url`, `snippet`, `raw_content`, `score`, `source_domain`, `search_term`.
- `DedupStats`: removal counts per dedup stage.

### Search (Phase 2)
- **Tavily advanced search** with `search_depth="advanced"`, `topic="news"`, `time_range="week"`, `include_raw_content=True`.
- One API call per search term, results combined.
- Domain filtering via `include_domains` / `exclude_domains` config.
- `raw_content` is truncated to `MAX_ARTICLE_CHARS` (default 6,000).
- Results with no `raw_content` (extraction failures) are kept but flagged — downstream steps skip them.

### Dedup (Phase 2)
- Three-stage pipeline: exact URL → domain-title clustering → cross-domain snippet similarity.
- URL normalization strips trailing slashes, `utm_*` params, and fragments.
- Word-overlap (Jaccard) similarity for title and snippet comparisons.
- Tavily `score` used as proxy for source authority in tie-breaking.
- Configurable thresholds: `DEDUP_TITLE_SIMILARITY` (0.6), `DEDUP_SNIPPET_SIMILARITY` (0.8).

### Agent Steps (Phase 3)
- **Prompt architecture:** System prompt (`prompts/system.py`) is shared across all steps, establishing the LLM's role for the configured domain. Each step has its own user message builder in `prompts/`.
- **Data flow:** Grouping → Extraction → Synthesis. Each step produces structured output consumed by the next.
- **Grouping (`agent/grouper.py`):** Filters out results with no `raw_content` before prompting. Groups by story, selects best source per group (max 15). Output: `GroupingResult` (validated via `parse_llm_json()`).
- **Extraction (`agent/extractor.py`):** Processes articles one at a time (not batched) to keep context small. Each call gets a unique `step_name` (e.g., `extraction_1`). Gracefully skips on parse failure or `TokenBudgetExceeded` — returns partial results.
- **Synthesis (`agent/synthesizer.py`):** Produces raw markdown (not JSON). Uses `max_tokens=4096`. Output is written directly to `output/{run_id}.md`.
- **New data models in `models.py`:** `GroupedStory`, `GroupingResult`, `ThematicTag`, `ExtractionNote`.

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
