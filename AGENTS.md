# AGENTS.md — Market Research Pipeline

> Context file for LLM coding assistants. Keep this updated with every code change.

## Rules
Do not run automated tests.
Always create an implementation plan before making changes, get the plan reviewed, and only make changes after getting the plan approved.


## Project Overview

A full-stack web app that searches the web for news related to a user-specified product (short name + free-text product context), deduplicates and synthesizes the results with LLM calls, and produces a structured PM brief rendered in the UI (and exportable as markdown).

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
│   ├── tagging/               # vocabulary.py — closed filter_tag vocabulary
│   ├── tracking/              # token_tracker.py (usage+cost) + discard_log.py
│   ├── templates/             # pm_brief.py — brief template text
│   ├── output/                # Generated briefs (gitignored)
│   └── logs/                  # Per-run JSON: {id}.json (usage) + {id}.discards.json
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
  7. Logs         → Write logs/{run_id}.json (token usage) and
                    logs/{run_id}.discards.json (dropped articles) (deterministic)

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
- **`RunConfig`** (per-run) — built by `build_run_config(server, request)` for each `POST /api/runs`. Merges server-level values with the UI-supplied `RunRequest` fields: `product_name`, `product_context`, `search_terms`, `include_domains`, `exclude_domains`, `max_results_per_term`, `max_article_chars`, `dedup_title_similarity`, `dedup_snippet_similarity`.
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
- `pipeline_run_id` (distinct from the API-level `Run.id` UUID) format: `{ISO timestamp}_{sanitized product_name}`, second-precision.
- **Truncation telemetry.** Every `StepUsage` records `stop_reason` from the Anthropic response. `stop_reason == "max_tokens"` means the call hit its output cap and was truncated — `AgentClient.call()` prints a runtime warning naming the step + cap, and `TokenTracker.print_summary()` flags the row with `⚠ max_tokens`. Grep `logs/{run_id}.json` for `"stop_reason": "max_tokens"` to audit truncation after the fact.

### Discard logging
- `tracking/discard_log.py:write_discard_log()` writes `logs/{pipeline_run_id}.discards.json` after the grouping stage. Bucketed by stage: `dedup_url`, `dedup_title`, `dedup_snippet`, `group_no_content`, `group_llm_irrelevant`.
- Inputs: `stats.discarded` from `services/dedup.py` + `grouping_result.discarded` from `agent/grouper.py`. Sibling to the token usage log; independent file so the two have separate consumers and sizes.

### JSON Parsing
- Any LLM response expected as JSON must be parsed via `agent/json_utils.py:parse_llm_json()`. Handles code fences, preamble text, trailing commas.

### Data Models
- All shared data structures are Pydantic models in `server/models.py`. Groups:
  - Token tracking: `StepUsage`, `RunLog`
  - Search & dedup: `SearchResult`, `DiscardedArticle`, `DedupStats`
  - Agent steps: `GroupedStory`, `GroupingResult`, `ThematicTag`, `ExtractionNote`
  - API: `RunRequest`, `Stage`, `Run`
  - Brief: `Highlight`, `Story`, `ActionItem`, `Source`, `Brief`
- TypeScript counterparts in `client/src/types/models.ts` should be kept in sync when server models change.

### Search
- Tavily advanced search: `search_depth="advanced"`, `topic="news"`, `time_range="week"`, `include_raw_content=True`.
- One Tavily API call per search term, results combined.
- Domain filtering via `include_domains` / `exclude_domains` from the RunRequest.
- `raw_content` is truncated to `max_article_chars` (default 6,000).
- Results with no `raw_content` are kept but flagged — downstream steps skip them.
- After the search loop, `services/search.py` prints a `📏 raw_content: …` summary line — total articles with content, count truncated, the cap, and median/max original length. Use it to gauge whether `max_article_chars` is biting on a given run before opening logs.

### Dedup
- Three-stage pipeline: exact URL → domain-title clustering → cross-domain snippet similarity.
- URL normalization strips trailing slashes, `utm_*` params, and fragments.
- Word-overlap (Jaccard) similarity for title and snippet comparisons.
- Tavily `score` used as proxy for source authority in tie-breaking.
- Thresholds come from `RunConfig` (defaults: title `0.6`, snippet `0.8`).

### Agent Steps
- **Prompts:** `prompts/system.py` builds the shared system prompt from `product_name` (short label, used in prompt grammar) and `product_context` (multi-line block describing mission, target customer, current bets, PM responsibility). Every agent step inherits this system prompt. Each step has its own user-message builder in `prompts/`.
- **Grouping (`agent/grouper.py`):** Filters out results with no `raw_content` before prompting (those become `group_no_content` discards). Groups by story arc, selects best source per group (cap ~15). Results the LLM judges irrelevant become `group_llm_irrelevant` discards. Output validated as `GroupingResult` via `parse_llm_json()`; `grouping_result.discarded` is merged with dedup discards by the orchestrator and persisted via `write_discard_log`.
- **Extraction (`agent/extractor.py`):** Processes articles **one at a time** (not batched) to keep context small. Each call gets a unique `step_name` (`extraction_1`, `extraction_2`, ...). Accepts a `progress_callback(completed, total)` so the orchestrator can update stage detail live. Gracefully skips on parse failure or `TokenBudgetExceeded` and returns partial results. After parsing each note, `filter_tags` are intersected with `tagging/vocabulary.py:FILTER_TAG_VOCABULARY` — unknown tags are dropped.
- **Synthesis (`agent/synthesizer.py`):** Emits a structured `Brief` **JSON** object (validated against the Pydantic `Brief` model). Uses `max_tokens=8192`. The server then renders markdown server-side via `templates/pm_brief.py:render_brief_markdown()` from the structured brief and writes it to `output/{pipeline_run_id}.md`; the same string is also stored on `Run.brief.raw_markdown`.
- **Synthesis prompt — PM action items bias.** The synthesis prompt biases action items toward four categories (treat as suggestions, not strict tags): **customer/user research questions**, **roadmap considerations**, **competitive responses**, **positioning & messaging**. Each item must be grounded in `product_context` and name a specific product area, competitor, segment, or customer cohort — no generic "monitor the landscape" advice. UI surfaces these under the heading "Ideas for PM Next Steps".
- **Intentionally absent sections.** "Watchlist", "Outlook", and "One thing to watch" were removed from the schema and prompts. The brief should end with its last thematic cluster. Do **not** re-introduce them without an explicit product decision; the synthesis prompt and `templates/pm_brief.py` actively discourage them.

### Tags: two distinct vocabularies
- **`thematic_tags`** (`models.ThematicTag`, on `ExtractionNote`): free-form section labels the LLM assigns during extraction. Synthesis uses them to cluster notes into brief `Section`s.
- **`filter_tags`** (`list[str]`, on `ExtractionNote` and `Story`): **closed vocabulary** from `tagging/vocabulary.py`. Default set: `competitive`, `acquisition`, `funding`, `product-launch`, `pricing`, `partnership`, `regulatory`, `security`, `leadership`, `earnings`, `open-source`, `standards`, `customer-signal`, `analyst`. Overridable via the `FILTER_TAG_VOCABULARY` env var (comma-separated). The extractor strips any LLM-supplied tag not in the vocabulary.

### Pipeline ↔ API integration
- `runs: dict[str, Run]` in `server.py` is an in-memory store — it does **not** persist across restarts. If you need durability, this is the seam to add it.
- `execute_pipeline` runs in a daemon `Thread`. It mutates `Run.status`, `Run.stages[*].status/detail/elapsed_ms`, `Run.brief`, and `Run.error` directly — those mutations are what the client sees via polling.
- Stage names are fixed: `["search", "dedup", "group", "extract", "synthesize"]` (see `STAGE_NAMES`). The `Stage.name` Literal in `models.py` must match.
- The structured `Brief` fields (`highlights`, `executive_summary`, `sections`, `action_items`, `sources`) are the source of truth for the rendered UI — `BriefScreen.tsx` walks them directly. `Brief.raw_markdown` is a server-rendered export of the same structured data (via `render_brief_markdown()`), used for the `/api/runs/:id/export` endpoint and as a fallback when the structured fields are empty.

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
