# AGENTS.md — Market Research Pipeline

> Context file for LLM coding assistants. Keep this updated with every code change.

## Rules
Do not run automated tests.
Always create an implementation plan before making changes, get the plan reviewed, and only make changes after getting the plan approved.


## Project Overview

A full-stack web app that searches the web for news related to a user-specified product (short name + free-text product context), deduplicates and synthesizes the results with LLM calls, and produces a structured PM brief rendered in the UI (and exportable as markdown).

- **Server** — FastAPI app that exposes a small `/api/runs` surface and runs the pipeline as a background thread.
- **Client** — Vite + React (TypeScript) app that submits run requests, polls for stage progress, and renders the finished brief.
- **Pipeline** — Search → Dedup → Group → Extract → Synthesize → Agent Review, with token tracking on every LLM call. The reviewer can trigger a bounded corrective pass (coverage-gap re-search or synthesis-gap rewrite).

## Tech Stack

**Server (Python 3.12+)**
- **FastAPI** (`fastapi`, `uvicorn`) — HTTP API + ASGI server
- **Anthropic SDK** (`anthropic`) — Claude for all LLM calls. Default pipeline model is `claude-sonnet-4-6`; the New Run screen's "Suggest search terms" button uses a cheaper model (`claude-haiku-4-5-20251001` by default) via `SUGGESTION_MODEL`.
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
├── render.yaml                # Render deployment config (server + client)
├── .venv/                     # Python venv at repo root (gitignored)
├── mockups/                   # Static HTML mockups (design reference)
├── server/                    # FastAPI backend
│   ├── server.py              # FastAPI app, CORS, passcode dependency, concurrency semaphore, in-memory run store, endpoints
│   ├── main.py                # Pipeline orchestrator (execute_pipeline)
│   ├── config.py              # ServerConfig + RunConfig + load_server_config / build_run_config
│   ├── models.py              # All Pydantic models (Run, Brief, SearchResult, etc.)
│   ├── requirements.txt
│   ├── runtime.txt            # Python version pin for Render (python-3.12.7)
│   ├── .env.local             # API keys (gitignored)
│   ├── .env.example
│   ├── agent/
│   │   ├── client.py          # AgentClient — Anthropic SDK wrapper + token budget
│   │   ├── json_utils.py      # parse_llm_json — strips code fences, trailing commas
│   │   ├── grouper.py         # LLM: group results by story
│   │   ├── extractor.py       # LLM: per-article structured extraction
│   │   ├── synthesizer.py     # LLM: generate PM brief markdown
│   │   └── reviewer.py        # LLM: judge brief, propose corrective re-search/rewrite
│   ├── prompts/               # system / grouping / extraction / synthesis / search_terms / review builders
│   ├── services/              # search.py (Tavily) + dedup.py
│   ├── tagging/               # vocabulary.py — closed filter_tag vocabulary
│   ├── tracking/              # token_tracker.py (usage+cost) + discard_log.py + review_log.py
│   ├── templates/             # pm_brief.py — brief template text
│   ├── scripts/               # Diagnostic scripts (inspect_tavily.py)
│   ├── output/                # Generated briefs (gitignored)
│   └── logs/                  # Per-run JSON: {pipeline_run_id}_pipelinerun.json (usage)
│                              #             + {pipeline_run_id}_pipelinerun.discards.json
│                              #             + {pipeline_run_id}_pipelinerun.review.json (agent review trail)
│                              #             + {timestamp}_{product}_searchterm.json (per Suggest call)
└── client/                    # Vite + React (TypeScript) frontend
    ├── index.html
    ├── package.json
    ├── vite.config.ts
    ├── eslint.config.js
    ├── tsconfig.json / tsconfig.app.json / tsconfig.node.json
    ├── public/                # favicon.svg, icons.svg
    └── src/
        ├── App.tsx            # Root + react-router routes (/, /runs/:id, /runs/:id/brief)
        ├── main.tsx
        ├── index.css          # Design system (tokens + component styles)
        ├── constants.ts       # Default form values (domains, thresholds)
        ├── api/client.ts      # Typed fetch wrapper for /api/runs + passcode helpers
        ├── types/models.ts    # TypeScript mirrors of server Pydantic models
        ├── assets/            # Static assets (hero.png, vite.svg)
        ├── components/        # AppBar, PasscodeGate, PillInput, TagChip, StoryCard, PipelineStageList
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
  6. Agent: Review → LLM judges brief; may loop back to a corrective
                    re-search (steps 1-5 on the union) or re-synthesis,
                    capped at MAX_REVIEW_ITERATIONS, budget replenished  (tokens)
  7. Output       → Write brief md to output/{pipeline_run_id}.md  (deterministic)
  8. Logs         → Write logs/{pipeline_run_id}_pipelinerun.json (token usage),
                    logs/{pipeline_run_id}_pipelinerun.discards.json (dropped articles),
                    logs/{pipeline_run_id}_pipelinerun.review.json (review trail) (deterministic)

Separately, POST /api/search-terms/suggest is a small synchronous Haiku call
that runs *before* any pipeline. It writes its own
logs/{timestamp}_{product}_searchterm.json with the same StepUsage shape.

The Run object (in the in-memory `runs` dict in server.py) is mutated
in-place by the background thread, so GET /api/runs/:id reflects live
stage progress as the client polls.
```

## API Surface

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/auth/check` | ✅ | Validates the supplied passcode and returns `{"ok": true}`. Used by the UI's `PasscodeGate` before storing the value in `sessionStorage`. |
| `POST` | `/api/search-terms/suggest` | ✅ | Body: `SuggestSearchTermsRequest` (`product_name`, `product_context`). Synchronous Haiku call (default `claude-haiku-4-5-20251001`); returns `{"suggested_terms": string[]}`. Writes its own `logs/{timestamp}_{product}_searchterm.json`. Returns `502` with a sanitized message on parse or upstream failure. |
| `POST` | `/api/runs` | ✅ | Body: `RunRequest`. Creates a `Run`, kicks off `execute_pipeline` in a background thread, returns `{"id": "<uuid>"}`. Returns `429` if `MAX_CONCURRENT_RUNS` is saturated. |
| `GET`  | `/api/runs/{id}` | ✅ | Returns the live `Run` (status, stages, brief, error). Client polls this. |
| `GET`  | `/api/runs/{id}/export` | ✅ | Returns `brief.raw_markdown` as a `text/markdown` attachment. 400 if not complete. |
| `GET`  | `/api/health` | — | `{"status": "ok"}`. Intentionally public so Render's health probe works. |

All auth-required endpoints use the `require_passcode` FastAPI dependency in `server.py`, which constant-time-compares `Authorization: Bearer <passcode>` against `ServerConfig.app_passcode` via `hmac.compare_digest`. On mismatch the response is `401` with `WWW-Authenticate: Bearer`.

CORS origins come from `ALLOWED_ORIGINS` (comma-separated, default `http://localhost:5173`). `server.py` **rejects `*` at startup** — list each origin explicitly. `allow_methods` is narrowed to `GET, POST, OPTIONS` and `allow_headers` to `Authorization, Content-Type`.

### Concurrency cap
- `MAX_CONCURRENT_RUNS` (default 3) is a module-level `threading.Semaphore` in `server.py`. `POST /api/runs` does a non-blocking `acquire()`; over-cap submits get a `429`. The slot is released in a `finally` from a wrapper around `execute_pipeline`, so failures and success both free it.
- Slots count **currently-running** pipelines, not historical ones — the `runs` dict still grows unbounded; reset by restarting the process.

## Key Patterns & Conventions

### Config (two layers)
- **`ServerConfig`** (server-level) — `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`, `APP_PASSCODE`, `MODEL`, `TOKEN_BUDGET`, `SUGGESTION_MODEL`, `MAX_CONCURRENT_RUNS`, `MAX_REVIEW_ITERATIONS`, `OUTPUT_DIR`, `LOG_DIR`. Loaded from `.env.local` (falls back to `.env`) at startup by `load_server_config()`. The three required values are the two API keys and `APP_PASSCODE` (min 8 chars). Everything else has a default. `SUGGESTION_MODEL` (default `claude-haiku-4-5-20251001`) is the small/cheap model used by `POST /api/search-terms/suggest`; it must have an entry in `MODEL_PRICING`. `MAX_REVIEW_ITERATIONS` (default `1`, must be ≥ 0; `0` disables the agent review loop) caps corrective passes — it flows into `RunConfig` so the orchestrator can read it per run. The reviewer reuses the pipeline `MODEL` (no separate review model).
- **`ALLOWED_ORIGINS`** is read directly from the environment in `server.py` (not part of the Pydantic `ServerConfig`). Comma-separated list of CORS origins; defaults to `http://localhost:5173`. `*` is rejected at startup.
- **`RunConfig`** (per-run) — built by `build_run_config(server, request)` for each `POST /api/runs`. Merges server-level values (incl. `max_review_iterations`) with the UI-supplied `RunRequest` fields: `product_name`, `product_context`, `search_terms`, `include_domains`, `exclude_domains`, `max_results_per_term`, `max_article_chars`, `dedup_title_similarity`, `dedup_snippet_similarity`.
- **Per-run things now come from the UI form**, not env vars. Do not re-add `DOMAIN_DESCRIPTION` / `SEARCH_TERMS` to `ServerConfig`.
- `output/` and `logs/` directories are auto-created on `load_server_config()`.
- Pydantic validators enforce types and ranges (token budget > 0, similarities in `[0, 1]`, `APP_PASSCODE` ≥ 8 chars, `include_domains`/`exclude_domains` ≤ 50 entries each, etc.).

### Auth (shared passcode)
- Single shared secret model — **not real auth**, just a gate to keep random scanners off the API. Stored as `APP_PASSCODE` in env, never per-user.
- Server side: `require_passcode(request)` in `server.py` is a FastAPI `Depends` that reads `Authorization: Bearer <passcode>` and compares against `ServerConfig.app_passcode` via `hmac.compare_digest`. Applied to every endpoint except `/api/health`. Don't add new endpoints without it.
- Client side: passcode lives in `sessionStorage` under key `app_passcode` (see `client/src/api/client.ts`). The `PasscodeGate` component (`client/src/components/PasscodeGate.tsx`) wraps `<BrowserRouter>` in `App.tsx` and blocks rendering until the passcode validates via `POST /api/auth/check`. All API calls send the `Authorization` header automatically.
- 401 recovery: `handleResponse` in `client.ts` clears the stored passcode and calls `window.location.reload()` on any 401 — this is what recovers cleanly after the server-side passcode is rotated.
- Sign-out: `AppBar` has a button that clears `sessionStorage` and reloads, which re-mounts the gate.
- To rotate: change `APP_PASSCODE` on the server and tell trusted users. No client-side change needed.

### Error sanitization
- The catch-all in `main.py:execute_pipeline` logs the full traceback via `logging.exception(...)` and assigns a generic `"Pipeline run failed. Check server logs for details."` to `Run.error`. Do not echo raw exception strings back to the client — library internals and external API response bodies have leaked through that path before. `TokenBudgetExceeded` is exempt because its message describes an expected operational limit.

### LLM Calls
- **All LLM calls go through `AgentClient.call()`** — never instantiate `anthropic.Anthropic()` directly.
- `AgentClient.__init__(anthropic_api_key, model, tracker)` takes the api key + model identifier directly (not a `RunConfig`) so the same wrapper serves both pipeline calls (model from `RunConfig.model`) and the non-pipeline suggest call (model from `ServerConfig.suggestion_model`).
- Each call requires a `step_name` string for token tracking (e.g., `"grouping"`, `"extraction_1"`, `"suggest_search_terms"`).
- Budget enforcement: `chars ÷ 4` estimation before the call; actual `response.usage` recorded after.
- `TokenBudgetExceeded` raised pre-call if the estimate would exceed the remaining budget — orchestrator marks the active stage failed and bails.
- Rate limit: single retry with 30s backoff on `RateLimitError`.
- Temperature defaults to `0.0` (deterministic) for all pipeline steps.

### Token Tracking & Cost
- The Anthropic API does **not** return cost — only `input_tokens` / `output_tokens`. Cost is computed locally from the `MODEL_PRICING` dict in `tracking/token_tracker.py`.
- When adding a new model, **add its pricing to `MODEL_PRICING`** — the tracker raises `KeyError` on unknown models.
- Current pricing: Sonnet 4.6 `$3.00 / M` input, `$15.00 / M` output. Haiku 4.5 (`claude-haiku-4-5-20251001`) `$1.00 / M` input, `$5.00 / M` output.
- `pipeline_run_id` (distinct from the API-level `Run.id` UUID) format: `{ISO timestamp}_{sanitized product_name}`, second-precision.
- **Log file naming (two suffixes).** Pipeline runs write `logs/{pipeline_run_id}_pipelinerun.json` and `logs/{pipeline_run_id}_pipelinerun.discards.json`. Each `POST /api/search-terms/suggest` writes `logs/{timestamp}_{sanitized_product_name}_searchterm.json`. The shared `{timestamp}_{product}` prefix means a searchterm log and the pipelinerun log from the same session sort adjacent in `ls`; the suffix tells you which is which. Suggest calls are intentionally **not** merged into the eventual Run log — each log file stands on its own.
- The suggest call's token tracker is given a per-call budget (~50k) since it is not part of `TOKEN_BUDGET`, and `tracker.save()` is called in a `finally` so a failed/garbled call still leaves a cost record on disk.
- **Truncation telemetry.** Every `StepUsage` records `stop_reason` from the Anthropic response. `stop_reason == "max_tokens"` means the call hit its output cap and was truncated — `AgentClient.call()` prints a runtime warning naming the step + cap, and `TokenTracker.print_summary()` flags the row with `⚠ max_tokens`. Grep `logs/*.json` for `"stop_reason": "max_tokens"` to audit truncation after the fact.

### Discard logging
- `tracking/discard_log.py:write_discard_log()` writes `logs/{pipeline_run_id}_pipelinerun.discards.json` after the grouping stage (the `_pipelinerun` suffix is supplied by the caller in `main.py` for naming consistency with the token usage log). Bucketed by stage: `dedup_url`, `dedup_title`, `dedup_snippet`, `group_no_content`, `group_llm_irrelevant`.
- Inputs: `stats.discarded` from `services/dedup.py` + `grouping_result.discarded` from `agent/grouper.py`. Sibling to the token usage log; independent file so the two have separate consumers and sizes.

### JSON Parsing
- Any LLM response expected as JSON must be parsed via `agent/json_utils.py:parse_llm_json()`. Handles code fences, preamble text, trailing commas.

### Data Models
- All shared data structures are Pydantic models in `server/models.py`. Groups:
  - Token tracking: `StepUsage`, `RunLog`
  - Search & dedup: `SearchResult`, `DiscardedArticle`, `DedupStats`
  - Agent steps: `GroupedStory`, `GroupingResult`, `ThematicTag`, `ExtractionNote`
  - API: `RunRequest`, `SuggestSearchTermsRequest`, `SuggestSearchTermsResponse`, `Stage`, `Run` (has `review_iterations`)
  - Agent review: `ReviewVerdict`
  - Brief: `Highlight`, `Story`, `ActionItem`, `Source`, `Section`, `Brief`
- TypeScript counterparts in `client/src/types/models.ts` should be kept in sync when server models change. The Suggest request/response shapes are inlined in `client/src/api/client.ts:suggestSearchTerms()` — no shared TS interface exists for them yet.

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
- **Prompts:** `prompts/system.py` builds the shared system prompt from `product_name` (short label, used in prompt grammar) and `product_context` (multi-line block describing mission, target customer, current bets, PM responsibility). Every agent step inherits this system prompt — including the non-pipeline `prompts/search_terms.py`. Each step has its own user-message builder in `prompts/`.
- **Search-term suggestion (`prompts/search_terms.py`, endpoint in `server.py`):** Non-pipeline, synchronous Haiku call powering the "Suggest search terms" button on the New Run screen. Asks the LLM for 4–5 short (≤60 char) lowercase web-search queries; response shape `{"suggested_terms": [...]}` parsed via `parse_llm_json()`. Server-side cleanup trims, lowercases, dedupes, drops empties, caps at 10. Failure mode is a sanitized 502 — the UI keeps the form usable for manual entry. Runs before any `RunConfig` exists, which is why `AgentClient.__init__` takes the api key + model directly rather than a `RunConfig`.
- **Grouping (`agent/grouper.py`):** Filters out results with no `raw_content` before prompting (those become `group_no_content` discards). Groups by story arc, selects best source per group (cap ~15). Results the LLM judges irrelevant become `group_llm_irrelevant` discards. Output validated as `GroupingResult` via `parse_llm_json()`; `grouping_result.discarded` is merged with dedup discards by the orchestrator and persisted via `write_discard_log`.
- **Extraction (`agent/extractor.py`):** Processes articles **one at a time** (not batched) to keep context small. Each call gets a unique `step_name` (`extraction_1`, `extraction_2`, ...) and uses `max_tokens=10000`. Accepts a `progress_callback(completed, total)` so the orchestrator can update stage detail live. Gracefully skips on parse failure or `TokenBudgetExceeded` and returns partial results. After parsing each note, `filter_tags` are intersected with `tagging/vocabulary.py:FILTER_TAG_VOCABULARY` — unknown tags are dropped.
- **Synthesis (`agent/synthesizer.py`):** Emits a structured `Brief` **JSON** object (validated against the Pydantic `Brief` model). Uses `max_tokens=10000`. The server then renders markdown server-side via `templates/pm_brief.py:render_brief_markdown()` from the structured brief and writes it to `output/{pipeline_run_id}.md`; the same string is also stored on `Run.brief.raw_markdown`.
- **Synthesis prompt — PM action items bias.** The synthesis prompt biases action items toward four categories (treat as suggestions, not strict tags): **customer/user research questions**, **roadmap considerations**, **competitive responses**, **positioning & messaging**. Each item must be grounded in `product_context` and name a specific product area, competitor, segment, or customer cohort — no generic "monitor the landscape" advice. UI surfaces these under the heading "Ideas for PM Next Steps".
- **Intentionally absent sections.** "Watchlist", "Outlook", and "One thing to watch" were removed from the schema and prompts. The brief should end with its last thematic cluster. Do **not** re-introduce them without an explicit product decision; the synthesis prompt and `templates/pm_brief.py` actively discourage them. The review prompt also forbids the reviewer from suggesting them in `resynthesis_guidance`.
- **Agent review (`agent/reviewer.py`, `prompts/review.py`):** After the first synthesis, a single LLM call (pipeline model, `step_name=review_{n}`, `max_tokens=4000`) judges the brief against `product_context`. It is fed the brief markdown + structured highlights/action_items, a digest of the extraction notes, and the discard log (to counter self-evaluation bias). Output validated as `ReviewVerdict` via `parse_llm_json()`. The discriminating rule: a weakness whose material is **absent from the notes** is a `coverage_gap` (re-search); material **present in the notes but missing/buried** is a `synthesis_gap` (rewrite). On parse/validation failure it returns `None` → orchestrator ships the current brief (never blocks on a broken judge). For `coverage_gap`, the reviewer's `suggested_search_terms` are difference-filtered (`filter_new_terms`) against all terms searched so far — token-set Jaccard ≥ 0.6 (reusing `dedup._tokenize`/`_word_overlap`) drops exact and near-duplicate terms so the re-search explores new query space.
- **`ReviewVerdict` invariant.** `verdict` is `sufficient` | `insufficient`. Two validators **reconcile rather than raise**: a before-validator coerces `"none"`/`""`/`null` → `None`; a model-validator guarantees `sufficient`→`failure_mode is None` (and clears stray corrective fields), and `insufficient`→`failure_mode` is `coverage_gap` or `synthesis_gap` (inferred from `suggested_search_terms`/`resynthesis_guidance` when the LLM left it blank; downgraded to `sufficient` if there's nothing actionable). So a merely-inconsistent verdict never throws.
- **Corrective loop (`main.py`).** Capped at `MAX_REVIEW_ITERATIONS` (default 1) corrective passes. Before each review iteration the token budget is **replenished** by the original budget (`tracker.replenish_budget`) so the loop never terminates on overrun; usage/cost still accumulate into the one `_pipelinerun.json` (steps `grouping`, `extraction_*`, `synthesis`, `review_*` from every pass). `coverage_gap` → re-search new terms → merge-dedup new survivors into the kept set (cross-iteration URL + snippet dedup) → re-group the **union** → extract only uncached articles (cache keyed by `ExtractionNote.source_url`, which the extractor sets authoritatively to the fed URL) → re-synthesize on the union. `synthesis_gap` → re-synthesize the same notes with `resynthesis_guidance`, no new search. Other termination conditions: verdict `sufficient`, zero usable new terms, or zero new articles from the re-search. Each iteration's verdict + action + termination reason is persisted via `tracking/review_log.py:write_review_log` to `logs/{pipeline_run_id}_pipelinerun.review.json`.

### Tags: two distinct vocabularies
- **`thematic_tags`** (`models.ThematicTag`, on `ExtractionNote`): free-form section labels the LLM assigns during extraction. Synthesis uses them to cluster notes into brief `Section`s.
- **`filter_tags`** (`list[str]`, on `ExtractionNote` and `Story`): **closed vocabulary** from `tagging/vocabulary.py`. Default set: `competitive`, `acquisition`, `funding`, `product-launch`, `pricing`, `partnership`, `regulatory`, `security`, `leadership`, `earnings`, `open-source`, `standards`, `customer-signal`, `analyst`. Overridable via the `FILTER_TAG_VOCABULARY` env var (comma-separated). The extractor strips any LLM-supplied tag not in the vocabulary.

### Pipeline ↔ API integration
- `runs: dict[str, Run]` in `server.py` is an in-memory store — it does **not** persist across restarts. If you need durability, this is the seam to add it.
- `execute_pipeline` runs in a daemon `Thread`. It mutates `Run.status`, `Run.stages[*].status/detail/elapsed_ms`, `Run.brief`, and `Run.error` directly — those mutations are what the client sees via polling.
- Stage names are fixed: `["search", "dedup", "group", "extract", "synthesize", "review"]` (see `STAGE_NAMES`). The `Stage.name` Literal in `models.py` must match. On a corrective pass the search/dedup/group/extract/synthesize stages flip `done`→`active` again with a `· round N` suffix in their detail; `Run.review_iterations` counts corrective passes taken (UI label for the review stage is "Agent review brief").
- The structured `Brief` fields (`highlights`, `executive_summary`, `sections`, `action_items`, `sources`) are the source of truth for the rendered UI — `BriefScreen.tsx` walks them directly. `Brief.raw_markdown` is a server-rendered export of the same structured data (via `render_brief_markdown()`), used for the `/api/runs/:id/export` endpoint and as a fallback when the structured fields are empty.

## Running the Project

From the repo root, with two terminals:

```bash
# Terminal 1 — Server
python3 -m venv .venv
source .venv/bin/activate
pip install -r server/requirements.txt
cp server/.env.example server/.env.local   # then fill in API keys + APP_PASSCODE
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
