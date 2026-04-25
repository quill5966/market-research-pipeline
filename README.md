# Market News Agent

An agentic pipeline that acts as your daily/weekly/monthly market news researcher. Optimized on token usage, it searches for news related to your product domain and synthesizes the results into a structured **PM brief**. 

Built with **Claude** LLM reasoning and **Tavily** for web search. Designed for manual, on-demand runs — point it at any product domain and get a curated research brief in seconds.

## How It Works

```
Search → Deduplicate → Group by Story → Extract Notes → Synthesize Brief
```

1. **Search** — Runs [Tavily](https://tavily.com/) advanced news search across your configured terms, pulling full article content where available.
2. **Deduplicate** — Three-stage dedup (exact URL → domain-title clustering → cross-domain snippet similarity) removes redundant coverage before the LLM process.
3. **Group** — LLM clusters results by story arc and selects the best source per group.
4. **Extract** — LLM extracts structured notes from each article (key facts, competitive signals, product implications).
5. **Synthesize** — LLM generates a polished PM brief from all extraction notes and includes source URLs.

Output lands in `output/` as a timestamped markdown file. Token usage and cost are logged to `logs/`. Errors during the run are logged in `logs/debug/`.

## Quick Start

### Prerequisites

- **Python 3.12+**
- An [Anthropic API key](https://console.anthropic.com/)
- A [Tavily API key](https://tavily.com/)

### Setup

```bash
# Clone the repo
git clone https://github.com/<your-username>/market-research-pipeline.git
cd market-research-pipeline

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure your environment
cp .env.example .env.local
```

Edit `.env.local` with your API keys and domain configuration:

```env
# Required — API keys
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...

# Required — What to research, see example terms
DOMAIN_DESCRIPTION="Enterprise identity and access management (IAM)"
SEARCH_TERMS="enterprise SSO,identity management,zero trust authentication"
```

### Run

```bash
python main.py
```

You'll see live progress in the terminal:

```
🚀 PM News Agent — Run: 2026-04-24T14-30-00_enterprise-identity-and-access
   Domain: Enterprise identity and access management (IAM)
   Search terms: enterprise SSO, identity management, zero trust authentication
   Model:  claude-sonnet-4-6
   Budget: 50,000 input tokens

🔍 Searching for: enterprise SSO (5 results)
🔍 Searching for: identity management (5 results)
...
📊 Final: 12 articles ready for processing
...
✅ Brief written to output/2026-04-24T14-30-00_enterprise-identity-and-access.md
```

## Configuration

All configuration is done through environment variables in `.env.local`. See [`.env.example`](.env.example) for the full template.

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ | — | Anthropic API key |
| `TAVILY_API_KEY` | ✅ | — | Tavily API key |
| `DOMAIN_DESCRIPTION` | ✅ | — | Product domain to research |
| `SEARCH_TERMS` | ✅ | — | Comma-separated search queries |
| `MODEL` | | `claude-sonnet-4-6` | Anthropic model ID |
| `TOKEN_BUDGET` | | `50000` | Max input tokens per run |
| `MAX_RESULTS_PER_TERM` | | `5` | Tavily results per search term |
| `MAX_ARTICLE_CHARS` | | `6000` | Truncation limit for article content |
| `DEDUP_TITLE_SIMILARITY` | | `0.6` | Jaccard threshold for title dedup |
| `DEDUP_SNIPPET_SIMILARITY` | | `0.8` | Jaccard threshold for snippet dedup |
| `INCLUDE_DOMAINS` | | *(none)* | Comma-separated allowlist of domains |
| `EXCLUDE_DOMAINS` | | *(none)* | Comma-separated blocklist of domains |
| `OUTPUT_DIR` | | `output` | Directory for generated briefs |
| `LOG_DIR` | | `logs` | Directory for token usage logs |

## Project Structure

```
market-research-pipeline/
├── main.py                 # Pipeline orchestrator (entry point)
├── config.py               # Config loading + Pydantic validation
├── models.py               # Shared Pydantic data models
├── agent/
│   ├── client.py           # Anthropic SDK wrapper with token budget enforcement
│   ├── json_utils.py       # Robust JSON parsing from LLM output
│   ├── grouper.py          # LLM step: group search results by story
│   ├── extractor.py        # LLM step: per-article structured extraction
│   └── synthesizer.py      # LLM step: generate PM brief
├── prompts/
│   ├── system.py           # Shared system prompt with domain context
│   ├── grouping.py         # Prompt for the grouping step
│   ├── extraction.py       # Prompt for the extraction step
│   └── synthesis.py        # Prompt for the synthesis step
├── services/
│   ├── search.py           # Tavily advanced search wrapper
│   └── dedup.py            # URL + title + snippet deduplication
├── tracking/
│   └── token_tracker.py    # Per-step token usage + cost logging
├── templates/
│   └── pm_brief.py         # Brief template definition
├── output/                 # Generated briefs (gitignored)
└── logs/                   # Token usage JSON logs (gitignored)
```

## Cost & Token Tracking

Every run produces a JSON log in `logs/` with a per-step breakdown of token usage and estimated cost. The pipeline enforces a configurable `TOKEN_BUDGET` — if a step would exceed the budget, it raises an exception and saves partial results.

Current pricing (Claude Sonnet 4.6): **$3.00 / M input tokens**, **$15.00 / M output tokens**.

A typical run with 5 search terms costs roughly **$0.05–$0.15** depending on article count and content length.

## License

This project is for personal/internal use. No license has been specified.
