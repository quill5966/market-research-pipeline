# AGENTS.md — Market Research Pipeline

> Context file for LLM coding assistants. Keep this updated with every code change.

## Rules
Do not run automated tests.
Always create an implementation plan before making changes, get the plan reviewed, and only make changes after getting the plan approved.


## Project Overview

A full-stack web app that searches the web for news related to a user-specified product domain, deduplicates and synthesizes the results with LLM calls, and produces a structured PM brief rendered in the UI (and exportable as markdown).

- **Server** — FastAPI app that exposes a small `/api/runs` surface and runs the pipeline as a background thread.
- **Client** — Vite + React (TypeScript) app that submits run requests, polls for stage progress, and renders the finished brief.
- **Pipeline** — Search → Dedup → Group → Extract → Synthesize, with token tracking on every LLM call.

## Tech Stack

**Server (Python 3.12+)**
- **FastAPI** (`fastapi`, `uvicorn`) — HTTP API + ASGI server
- **Anthropic SDK** (`anthropic`) — Claude (default `claude-sonnet-4-6`) for all LLM calls
- **Pydantic v2** — config validation, data models, request/response schemas
- **python-dotenv** — env file loading (`.env.local` → `.env` priority)
- **Tavily** (`tavily-python`) — advanced web search with `include_raw_content=True` (no separate fetcher needed)

**Client (Node 18+)**
- **React 19** + **react-router-dom 7** — UI + client-side routing
- **Vite 8** — dev server and build (`npm run dev` on port 5173)
- **TypeScript** — types mirror server Pydantic models in `client/src/types/models.ts`

## Project Structure

```
market-research-pipeline/
├── AGENTS.md                  # This file — LLM context
├── CLAUDE.md                  # Points to AGENTS.md
├── README.md                  # User-facing docs (setup + run)
├── .venv/                     # Python venv at repo root (gitignored)
├── mockups/                   # Static HTML mockups (design reference)
├── server/                    # FastAPI backend
│   ├── server.py              # FastAPI app, CORS, in-memory run store, endpoints
│   ├── main.py                # Pipeline orchestrator (execute_pipeline)
│   ├── config.py              # ServerConfig + RunConfig + load_server_config / build_run_config
│   ├── models.py              # All Pydantic models (Run, Brief, SearchResult, etc.)
│   ├── requirements.txt
│   ├── .env.local             # API keys (gitignored)
│   ├── .env.example
│   ├── agent/
│   │   ├── client.py          # AgentClient — Anthropic SDK wrapper + token budget
│   │   ├── json_utils.py      # parse_llm_json — strips code fences, trailing commas
│   │   ├── grouper.py         # LLM: group results by story
│   │   ├── extractor.py       # LLM: per-article structured extraction
│   │   └── synthesizer.py     # LLM: generate PM brief markdown
│   ├── prompts/               # system / grouping / extraction / synthesis builders
│   ├── services/              # search.py (Tavily) + dedup.py
│   ├── tracking/              # token_tracker.py — per-step usage + cost logging
│   ├── templates/             # pm_brief.py — brief template text
│   ├── output/                # Generated briefs (gitignored)
│   └── logs/                  # Per-run token usage JSON (gitignored)
└── client/                    # Vite + React (TypeScript) frontend
    ├── index.html
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── App.tsx            # Root + react-router routes (/, /runs/:id, /runs/:id/brief)
        ├── main.tsx
        ├── index.css          # Design system (tokens + component styles)
        ├── api/client.ts      # Typed fetch wrapper for /api/runs
        ├── types/models.ts    # TypeScript mirrors of server Pydantic models
        ├── components/        # AppBar, PillInput, TagChip, StoryCard, PipelineStageList
        └── screens/           # NewRunScreen, PipelineScreen, BriefScreen
```

## Architecture & Data Flow

```
ServerConfig (.env.local)            ← loaded once at server startup
       +
RunRequest (POST /api/runs body)     ← per-request from UI form
       ↓
RunConfig (merged via build_run_config)
       ↓
Background thread: execute_pipeline(run, config)
  1. Search       → Tavily advanced search, one call per term  (deterministic)
  2. Dedup        → URL → domain-title → snippet similarity     (deterministic)
  3. Agent: Group → LLM groups snippets by story arc            (tokens)
  4. Agent: Extract → LLM extracts notes per article, 1-at-a-time (tokens)
  5. Agent: Synth → LLM generates PM brief markdown             (tokens)
  6. Output       → Write brief md to output/{run_id}.md        (deterministic)
  7. Tracker      → Write JSON usage log to logs/{run_id}.json  (deterministic)

The Run object (in the in-memory `runs` dict in server.py) is mutated
in-place by the background thread, so GET /api/runs/:id reflects live
stage progress as the client polls.
```

## API Surface

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/runs` | Body: `RunRequest`. Creates a `Run`, kicks off `execute_pipeline` in a background thread, returns `{"id": "<uuid>"}`. |
| `GET`  | `/api/runs/{id}` | Returns the live `Run` (status, stages, brief, error). Client polls this. |
| `GET`  | `/api/runs/{id}/export` | Returns `brief.raw_markdown` as a `text/markdown` attachment. 400 if not complete. |
| `GET`  | `/api/health` | `{"status": "ok"}` |

CORS is currently locked to `http://localhost:5173` (Vite dev server) in `server.py`.

## Key Patterns & Conventions

### Config (two layers)
- **`ServerConfig`** (server-level) — `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`, `MODEL`, `TOKEN_BUDGET`, `OUTPUT_DIR`, `LOG_DIR`. Loaded from `.env.local` (falls back to `.env`) at startup by `load_server_config()`. API keys are the only *required* values; everything else has a default.
- **`RunConfig`** (per-run) — built by `build_run_config(server, request)` for each `POST /api/runs`. Merges server-level values with the UI-supplied `RunRequest` fields: `domain_description`, `search_terms`, `include_domains`, `exclude_domains`, `max_results_per_term`, `max_article_chars`, `dedup_title_similarity`, `dedup_snippet_similarity`.
- **Per-run things now come from the UI form**, not env vars. Do not re-add `DOMAIN_DESCRIPTION` / `SEARCH_TERMS` to `ServerConfig`.
- `output/` and `logs/` directories are auto-created on `load_server_config()`.
- Pydantic validators enforce types and ranges (token budget > 0, similarities in `[0, 1]`, etc.).

### LLM Calls
- **All LLM calls go through `AgentClient.call()`** — never instantiate `anthropic.Anthropic()` directly.
- Each call requires a `step_name` string for token tracking (e.g., `"grouping"`, `"extraction_1"`).
- Budget enforcement: `chars ÷ 4` estimation before the call; actual `response.usage` recorded after.
- `TokenBudgetExceeded` raised pre-call if the estimate would exceed the remaining budget — orchestrator marks the active stage failed and bails.
- Rate limit: single retry with 30s backoff on `RateLimitError`.
- Temperature defaults to `0.0` (deterministic) for all pipeline steps.

### Token Tracking & Cost
- The Anthropic API does **not** return cost — only `input_tokens` / `output_tokens`. Cost is computed locally from the `MODEL_PRICING` dict in `tracking/token_tracker.py`.
- When adding a new model, **add its pricing to `MODEL_PRICING`** — the tracker raises `KeyError` on unknown models.
- Current pricing (Sonnet 4.6): `$3.00 / M` input, `$15.00 / M` output.
- Each run produces `logs/{pipeline_run_id}.json` with a per-step breakdown.
- `pipeline_run_id` (distinct from the API-level `Run.id` UUID) format: `{ISO timestamp}_{sanitized-domain}`, second-precision.

### JSON Parsing
- Any LLM response expected as JSON must be parsed via `agent/json_utils.py:parse_llm_json()`. Handles code fences, preamble text, trailing commas.

### Data Models
- All shared data structures are Pydantic models in `server/models.py`. Groups:
  - Token tracking: `StepUsage`, `RunLog`
  - Search & dedup: `SearchResult`, `DedupStats`
  - Agent steps: `GroupedStory`, `GroupingResult`, `ThematicTag`, `ExtractionNote`
  - API: `RunRequest`, `Stage`, `Run`
  - Brief: `Highlight`, `Story`, `WatchlistItem`, `ActionItem`, `Source`, `Brief`
- TypeScript counterparts in `client/src/types/models.ts` should be kept in sync when server models change.

### Search
- Tavily advanced search: `search_depth="advanced"`, `topic="news"`, `time_range="week"`, `include_raw_content=True`.
- One Tavily API call per search term, results combined.
- Domain filtering via `include_domains` / `exclude_domains` from the RunRequest.
- `raw_content` is truncated to `max_article_chars` (default 6,000).
- Results with no `raw_content` are kept but flagged — downstream steps skip them.

### Dedup
- Three-stage pipeline: exact URL → domain-title clustering → cross-domain snippet similarity.
- URL normalization strips trailing slashes, `utm_*` params, and fragments.
- Word-overlap (Jaccard) similarity for title and snippet comparisons.
- Tavily `score` used as proxy for source authority in tie-breaking.
- Thresholds come from `RunConfig` (defaults: title `0.6`, snippet `0.8`).

### Agent Steps
- **Prompts:** `prompts/system.py` builds the shared system prompt for the configured domain. Each step has its own user-message builder in `prompts/`.
- **Grouping (`agent/grouper.py`):** Filters out results with no `raw_content` before prompting. Groups by story arc, selects best source per group (cap ~15). Output validated as `GroupingResult` via `parse_llm_json()`.
- **Extraction (`agent/extractor.py`):** Processes articles **one at a time** (not batched) to keep context small. Each call gets a unique `step_name` (`extraction_1`, `extraction_2`, ...). Accepts a `progress_callback(completed, total)` so the orchestrator can update stage detail live. Gracefully skips on parse failure or `TokenBudgetExceeded` and returns partial results.
- **Synthesis (`agent/synthesizer.py`):** Produces raw **markdown** (not JSON). Uses `max_tokens=4096`. Output is written to `output/{pipeline_run_id}.md` and also stored on the `Run.brief.raw_markdown` field.

### Pipeline ↔ API integration
- `runs: dict[str, Run]` in `server.py` is an in-memory store — it does **not** persist across restarts. If you need durability, this is the seam to add it.
- `execute_pipeline` runs in a daemon `Thread`. It mutates `Run.status`, `Run.stages[*].status/detail/elapsed_ms`, `Run.brief`, and `Run.error` directly — those mutations are what the client sees via polling.
- Stage names are fixed: `["search", "dedup", "group", "extract", "synthesize"]` (see `STAGE_NAMES`). The `Stage.name` Literal in `models.py` must match.
- `Brief.raw_markdown` is currently the source of truth for the rendered brief. The structured `Brief` fields (`highlights`, `sections`, `watchlist`, etc.) are scaffolded but not yet populated by the pipeline (see TODO in `main.py`).

## Running the Project

From the repo root, with two terminals:

```bash
# Terminal 1 — Server
python3 -m venv .venv
source .venv/bin/activate
pip install -r server/requirements.txt
cp server/.env.example server/.env.local   # then fill in API keys
cd server && uvicorn server:app --reload --port 8000

# Terminal 2 — Client
cd client && npm install && npm run dev    # http://localhost:5173
```

There is no CLI entry point anymore. `main.py` is imported by `server.py`; running it standalone is not supported.

## Important Files to Read First

1. `server/config.py` — the two-layer config model (`ServerConfig` + `RunConfig`).
2. `server/server.py` — API endpoints, in-memory run store, background thread launch.
3. `server/main.py` — `execute_pipeline` — how stages are wired and how `Run` is mutated.
4. `server/agent/client.py` — `AgentClient.call()` interface used by all LLM steps.
5. `server/tracking/token_tracker.py` — `MODEL_PRICING` and how usage/cost is recorded.
6. `client/src/api/client.ts` + `client/src/types/models.ts` — the client/server contract.
