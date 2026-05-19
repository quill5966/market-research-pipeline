# Market News Agent

A full-stack web application that acts as your on-demand market news researcher. Searches for news related to your product domain, deduplicates and synthesizes the results using LLM reasoning, and produces a structured **PM brief** rendered in an editorial-grade UI.

Built with **Claude** for LLM reasoning, **Tavily** for web search, **FastAPI** for the backend, and **React + Vite** for the client.

## How It Works

```
Search → Deduplicate → Group by Story → Extract Notes → Synthesize Brief
```

1. **Search** — Runs [Tavily](https://tavily.com/) advanced news search across your terms, pulling full article content where available.
2. **Deduplicate** — Three-stage dedup (exact URL → domain-title clustering → cross-domain snippet similarity) removes redundant coverage.
3. **Group** — LLM clusters results by story arc and selects the best source per group.
4. **Extract** — LLM extracts structured notes from each article (key facts, competitive signals, product implications).
5. **Synthesize** — LLM generates a polished PM brief from all extraction notes with source citations.

The pipeline runs as a background task on the server. The client polls for real-time stage progress and renders the finished brief.

## Quick Start

### Prerequisites

- **Python 3.12+** and **Node.js 18+**
- An [Anthropic API key](https://console.anthropic.com/)
- A [Tavily API key](https://tavily.com/)

### Setup

```bash
# Clone the repo
git clone https://github.com/<your-username>/market-research-pipeline.git
cd market-research-pipeline

# Server — Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r server/requirements.txt

# Server — API keys and passcode
cp server/.env.example server/.env.local
# Edit server/.env.local: fill in ANTHROPIC_API_KEY, TAVILY_API_KEY, and APP_PASSCODE.
# Generate a strong passcode with: openssl rand -base64 24

# Client — Node dependencies
cd client && npm install && cd ..
```

### Run

Open two terminals from the project root:

```bash
# Terminal 1 — Server (API on port 8000)
cd server && source ../.venv/bin/activate && uvicorn server:app --reload --port 8000

# Terminal 2 — Client (UI on port 5173)
cd client && npm run dev
```

Open **http://localhost:5173** to access the app. You'll be prompted for the
`APP_PASSCODE` you set in `server/.env.local`; it's cached in `sessionStorage`
and forgotten when you close the browser tab.

## Configuration

Server-level configuration lives in `server/.env.local`. Per-run parameters — product name, product context (mission / target customer / current bets / PM role), search terms, and include/exclude domain filters — are submitted through the UI form.

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ | — | Anthropic API key |
| `TAVILY_API_KEY` | ✅ | — | Tavily API key |
| `APP_PASSCODE` | ✅ | — | Shared passcode that gates the UI and API (≥8 chars; use ≥16 random chars in production) |
| `MODEL` | | `claude-sonnet-4-6` | Anthropic model ID |
| `TOKEN_BUDGET` | | `200000` | Max input tokens per run |
| `MAX_CONCURRENT_RUNS` | | `3` | Max simultaneous pipeline runs across the server (extra POSTs get a 429) |
| `ALLOWED_ORIGINS` | | `http://localhost:5173` | Comma-separated CORS origins. `*` is rejected at startup |
| `OUTPUT_DIR` | | `output` | Directory for generated briefs |
| `LOG_DIR` | | `logs` | Directory for token usage logs |
| `VITE_API_BASE_URL` | | `http://localhost:8000` | Client-side env var — backend URL for API calls. Set in `client/.env` or as a build-time env var on Render |

## Security

The app is gated by a single shared passcode (`APP_PASSCODE`). The client sends
it on every request as `Authorization: Bearer <passcode>` and the server
constant-time-compares against the env value. This is **not** real auth — it's
a "keep random scanners off the API" gate. To revoke access, rotate
`APP_PASSCODE` on the server and tell trusted users the new value.

Other hardening already in place:
- `MAX_CONCURRENT_RUNS` caps how many pipelines can run at once; over-cap
  submits get a `429`.
- CORS rejects `*` origins at startup; methods/headers are narrowed.
- Pipeline errors surface a generic message to the client; full tracebacks
  stay in the server log.
- `include_domains`/`exclude_domains` are bounded to 50 entries each.

## Project Structure

```
market-research-pipeline/
├── AGENTS.md                   # LLM coding assistant context
├── CLAUDE.md                   # Points to AGENTS.md
├── README.md
├── render.yaml                 # Render deployment config (server + client)
├── .venv/                      # Python virtual environment (gitignored)
├── server/                     # FastAPI backend
│   ├── server.py               # FastAPI app + API endpoints
│   ├── main.py                 # Pipeline orchestrator
│   ├── config.py               # ServerConfig + RunConfig (Pydantic)
│   ├── models.py               # All data models (Run, Brief, Story, etc.)
│   ├── requirements.txt
│   ├── runtime.txt             # Python version pin for Render
│   ├── .env.local              # API keys (gitignored)
│   ├── .env.example
│   ├── agent/
│   │   ├── client.py           # Anthropic SDK wrapper + token budget
│   │   ├── json_utils.py       # JSON parsing from LLM output
│   │   ├── grouper.py          # LLM: group results by story
│   │   ├── extractor.py        # LLM: per-article structured extraction
│   │   └── synthesizer.py      # LLM: generate PM brief
│   ├── prompts/                # Prompt builders per pipeline step
│   ├── services/               # Search + dedup
│   ├── tagging/                # Closed vocabulary for filter_tags
│   ├── tracking/               # Token usage + cost + discard logging
│   ├── templates/              # Brief template
│   ├── scripts/                # Diagnostic scripts (inspect_tavily.py)
│   ├── output/                 # Generated briefs (gitignored)
│   └── logs/                   # Per-run JSON: token usage + discarded articles (gitignored)
└── client/                     # Vite + React (TypeScript) frontend
    ├── index.html
    ├── package.json
    ├── vite.config.ts
    ├── eslint.config.js
    ├── tsconfig.json / tsconfig.app.json / tsconfig.node.json
    ├── public/                 # favicon.svg, icons.svg
    └── src/
        ├── App.tsx             # Root component + routing
        ├── main.tsx            # Entry point
        ├── index.css           # Design system (tokens, components)
        ├── constants.ts        # Default form values (domains, thresholds)
        ├── api/client.ts       # Typed fetch wrapper for /api/runs
        ├── types/models.ts     # TypeScript interfaces (mirrors server models)
        ├── assets/             # Static assets (hero.png, vite.svg)
        ├── components/         # AppBar, PasscodeGate, PillInput, TagChip, StoryCard, PipelineStageList
        └── screens/            # NewRunScreen, PipelineScreen, BriefScreen
```

## API Endpoints

All endpoints except `/api/health` require `Authorization: Bearer <APP_PASSCODE>`.

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/auth/check` | ✅ | Validate the passcode without side effects (used by the UI gate) |
| `POST` | `/api/runs` | ✅ | Start a new pipeline run. Returns `429` if `MAX_CONCURRENT_RUNS` is saturated |
| `GET` | `/api/runs/:id` | ✅ | Get run status, stages, and brief |
| `GET` | `/api/runs/:id/export` | ✅ | Download brief as markdown |
| `GET` | `/api/health` | — | Health check (public, for Render) |

## Cost & Token Tracking

Every run produces a JSON log in `server/logs/` with a per-step breakdown of token usage and estimated cost. Each step also records the Anthropic `stop_reason`, so output truncation (`max_tokens` hits) is visible after the fact — grep for `"stop_reason": "max_tokens"`. A sibling `{run_id}.discards.json` captures articles dropped during dedup and grouping. The pipeline enforces a configurable `TOKEN_BUDGET` — if a step would exceed the budget, it raises an exception and saves partial results.

Current pricing (Claude Sonnet 4.6): **$3.00 / M input tokens**, **$15.00 / M output tokens**.

A typical run with 10 search terms costs roughly **$0.25–$0.50** depending on article count and content length.

## Deployment

The repo includes a `render.yaml` [Blueprint](https://render.com/docs/infrastructure-as-code) that deploys both services to Render:

- **`market-research-server`** — Python web service running FastAPI via uvicorn. Set `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`, `APP_PASSCODE`, and `ALLOWED_ORIGINS` as env vars in the Render dashboard.
- **`market-research-client`** — Static site built with `npm run build`. Set `VITE_API_BASE_URL` to the server's public URL.

The server exposes `/api/health` (no auth) for Render's health probe. `runtime.txt` pins the Python version.

## License

This project is for personal/internal use. No license has been specified.
