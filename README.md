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

# Server — API keys
cp server/.env.example server/.env.local
# Edit server/.env.local with your real API keys

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

Open **http://localhost:5173** to access the app.

## Configuration

Server-level configuration lives in `server/.env.local`. Per-run parameters — product name, product context (mission / target customer / current bets / PM role), search terms, and include/exclude domain filters — are submitted through the UI form.

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ | — | Anthropic API key |
| `TAVILY_API_KEY` | ✅ | — | Tavily API key |
| `MODEL` | | `claude-sonnet-4-6` | Anthropic model ID |
| `TOKEN_BUDGET` | | `50000` | Max input tokens per run |
| `OUTPUT_DIR` | | `output` | Directory for generated briefs |
| `LOG_DIR` | | `logs` | Directory for token usage logs |

## Project Structure

```
market-research-pipeline/
├── AGENTS.md                   # LLM coding assistant context
├── README.md
├── .venv/                      # Python virtual environment (gitignored)
├── server/                     # FastAPI backend
│   ├── server.py               # FastAPI app + API endpoints
│   ├── main.py                 # Pipeline orchestrator
│   ├── config.py               # ServerConfig + RunConfig (Pydantic)
│   ├── models.py               # All data models (Run, Brief, Story, etc.)
│   ├── requirements.txt
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
│   ├── output/                 # Generated briefs (gitignored)
│   └── logs/                   # Per-run JSON: token usage + discarded articles (gitignored)
└── client/                     # Vite + React (TypeScript) frontend
    ├── index.html
    ├── package.json
    ├── src/
    │   ├── App.tsx             # Root component + routing
    │   ├── main.tsx            # Entry point
    │   ├── index.css           # Design system (tokens, components)
    │   ├── api/client.ts       # Typed fetch wrapper for /api/runs
    │   ├── types/models.ts     # TypeScript interfaces (mirrors server models)
    │   ├── components/         # AppBar, PillInput, TagChip, StoryCard, PipelineStageList
    │   └── screens/            # NewRunScreen, PipelineScreen, BriefScreen
    └── node_modules/           # (gitignored)
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/runs` | Start a new pipeline run |
| `GET` | `/api/runs/:id` | Get run status, stages, and brief |
| `GET` | `/api/runs/:id/export` | Download brief as markdown |
| `GET` | `/api/health` | Health check |

## Cost & Token Tracking

Every run produces a JSON log in `server/logs/` with a per-step breakdown of token usage and estimated cost. Each step also records the Anthropic `stop_reason`, so output truncation (`max_tokens` hits) is visible after the fact — grep for `"stop_reason": "max_tokens"`. A sibling `{run_id}.discards.json` captures articles dropped during dedup and grouping. The pipeline enforces a configurable `TOKEN_BUDGET` — if a step would exceed the budget, it raises an exception and saves partial results.

Current pricing (Claude Sonnet 4.6): **$3.00 / M input tokens**, **$15.00 / M output tokens**.

A typical run with 5 search terms costs roughly **$0.05–$0.15** depending on article count and content length.

## License

This project is for personal/internal use. No license has been specified.
