# PM News Agent — MVP Implementation Plan

## Overview

An agentic workflow that searches the web for news related to a specific product domain, deduplicates and synthesizes the results, and produces a structured PM brief as markdown output. The agent uses an LLM to evaluate relevance, group related stories, compress articles into structured notes, and generate a final brief using a configurable template.

## Architecture

```
Config (.env)
  ├── LLM API key (static for testing)
  ├── Search API key
  ├── Domain description
  └── Search terms list

Pipeline
  1. Search Service      → takes terms, calls search API, returns structured results
  2. Dedup Layer          → URL dedup + snippet similarity filtering
  3. Agent: Grouping      → LLM receives snippets, groups by story, picks best sources
  4. Fetch Service        → retrieves full article text for selected URLs
  5. Agent: Extraction   → LLM reads each article, produces structured extraction note
  6. Agent: Synthesis     → LLM generates PM brief from notes using template
  7. Formatter            → renders brief as markdown
  8. Token Tracker        → logs per-step and total token usage to JSON

Steps 1, 2, 4, 7, 8 are deterministic (no token cost).
Steps 3, 5, 6 are LLM calls (token cost tracked per step).
```

## Project Structure

```
pm-news-agent/
├── .env                          # API keys, config
├── config.py                     # Load and validate config
├── main.py                       # Orchestrates the full pipeline
├── services/
│   ├── search.py                 # Search API wrapper
│   ├── dedup.py                  # URL + snippet deduplication
│   └── fetcher.py                # Full article content extraction
├── agent/
│   ├── client.py                 # Anthropic SDK wrapper (Sonnet 4.6)
│   ├── grouper.py                # Step 3: snippet grouping/prioritization
│   ├── extractor.py              # Step 5: per-article structured extraction
│   └── synthesizer.py            # Step 6: final PM brief generation
├── prompts/
│   ├── system.py                 # Base system prompt with domain context
│   ├── grouping.py               # Prompt for snippet grouping step
│   ├── extraction.py             # Prompt for article extraction step
│   └── synthesis.py              # Prompt for final brief generation
├── templates/
│   └── pm_brief.py               # Brief template definition
├── tracking/
│   └── token_tracker.py          # Per-step token usage + cost logging
├── output/                       # Generated briefs land here
└── logs/                         # Token usage logs per run
```

## Implementation Phases

### Phase 1: Foundation

**Goal:** Project skeleton, config loading, token tracker, and LLM client wrapper.

**Tasks:**

Set up the project directory and virtual environment. Create the `.env` file with placeholder values for LLM API key, search API key, domain description, and a comma-separated list of search terms.

Build `config.py` to load and validate all config values from `.env`. It should fail with clear error messages if required values are missing.

Build `tracking/token_tracker.py` — the `TokenTracker` class that accumulates token usage across pipeline steps, calculates estimated cost based on Sonnet 4.6 pricing ($3/$15 per million input/output tokens), and writes a JSON summary to the `logs/` directory at the end of each run. Include a `run_id` based on timestamp + domain name for easy identification.

Build `agent/client.py` — a thin wrapper around the Anthropic SDK that initializes the client from the env API key, exposes a method to call `messages.create` with arbitrary messages and tools, and accepts a `TokenTracker` instance so every call is automatically recorded. The model is fixed to `claude-sonnet-4-6` for MVP.

Add a token budget mechanism: a configurable max input token threshold per run. Before each LLM call, the wrapper checks accumulated usage against the budget and raises an exception if the next call would exceed it. Default budget: 50,000 input tokens.

**Verification:** Run a single test LLM call with a trivial prompt. Confirm the token tracker logs usage correctly and the JSON output is written to `logs/`.

---

### Phase 2: Search and Dedup

**Goal:** A working search pipeline that takes terms, retrieves results, and deduplicates them before the LLM sees anything.

**Tasks:**

Build `services/search.py` — a function that accepts a list of search terms, calls the search API (pick one: Tavily, Serper, or Brave), and returns a list of structured result objects with fields: `title`, `url`, `snippet`, `date`, `source_domain`. Each term is searched independently and results are combined into a single list.

Build `services/dedup.py` with three dedup stages:

1. Exact URL dedup: track seen URLs, discard duplicates.
2. Domain clustering: if multiple results from the same domain have similar titles (simple word overlap threshold, e.g., 60%+), keep only the highest-ranked one.
3. Snippet similarity: compute pairwise word overlap between snippets from different domains. If two snippets share 80%+ of their words, flag one as a likely syndicated duplicate and keep the one from the higher-authority source (prefer original reporting domains over aggregators).

The dedup layer should log how many results were removed at each stage so you can tune thresholds during testing.

Build `services/fetcher.py` — a function that takes a URL and returns the extracted article text. Use a library like `newspaper3k`, `trafilatura`, or `httpx` + `readability-lxml` for content extraction. Strip navigation, ads, and boilerplate. Return the clean text plus a metadata dict (title, author, publish date if available). Add a configurable max character limit per article (default: 6,000 characters, roughly 1,500-2,000 tokens) to prevent long articles from dominating the token budget.

**Verification:** Run the search service with 3-5 test terms related to a domain you care about. Inspect the raw results, then the deduped results. Confirm duplicates are removed and the fetcher returns clean article text. Check that the character limit truncates long articles.

---

### Phase 3: Agent Steps (Grouping, Summarization, Synthesis)

**Goal:** The three LLM-powered pipeline steps that turn raw search results into a PM brief.

**Tasks:**

Define prompts in the `prompts/` directory. Each prompt file exports a function that takes dynamic context (domain description, data) and returns a formatted prompt string. Keep system prompts separate from user messages.

**Step 3 — Grouping (`agent/grouper.py`):**

Input to the LLM: a system prompt with the domain context, plus a user message containing the deduped search results as a list of (title, snippet, source, date) tuples. No full article text at this stage — snippets only.

Instructions: group results by underlying story or event, discard results clearly irrelevant to the domain, rank groups by likely relevance to a PM in this domain, and for each group select the single best source to fetch in full.

Expected output: a structured list of selected URLs with a brief rationale for each selection and group label. Ask the model to respond in JSON.

**Step 5 — Extraction (`agent/extractor.py`):**

Process selected articles one at a time in a loop. For each article:

Input: system prompt with domain context + the fetched article text (truncated to character limit) + structured extraction instructions.

Instructions: extract information while preserving specificity, and pre-classify the article's relevance to the brief's thematic sections. The prompt should emphasize preservation of concrete details over compression, and orient the extraction toward what the synthesis step will need:

```
Extract the following from this article. Preserve specific numbers,
dates, quotes, and named entities. Do not generalize or interpret —
report what the article says.

CORE EXTRACTION:
- Headline: factual, concise
- Source, date, author
- What happened: 3-5 sentences covering the core facts
- Specific data points: numbers, percentages, dollar amounts, dates,
  timelines mentioned (list all, even if they seem minor)
- Direct quotes: any notable statements from named individuals
  (preserve exact wording and attribute by name and title)
- Companies and products mentioned: with context for each
  (what role they play in the story, whether they are a competitor,
  partner, customer, or ecosystem player in the [domain] space)

THEMATIC CLASSIFICATION:
Which of the following categories does this article inform? Select all
that apply and provide category-specific details for each:

- competitor_moves: if yes, extract product/feature names, pricing,
  availability dates, target market segment, and how this changes the
  competitor's positioning relative to [domain]
- market_macro: if yes, extract the specific trend or force, any
  quantitative evidence (market size, growth rates, funding amounts),
  and the time horizon (is this happening now or projected)
- customer_buyer: if yes, extract buyer segment, evaluation criteria
  mentioned, adoption numbers, named customers, and any stated
  reasons for choosing or leaving a vendor
- technology_ecosystem: if yes, extract the specific technology,
  standard, or platform change, which players are involved, and
  the expected timeline for impact
- watchlist: if the article contains early signals, unconfirmed
  reports, or tangential-but-notable information that doesn't
  clearly fit the above categories

PM-RELEVANT GAPS:
What questions would a PM in [domain] want answered that this article
does not address? Focus on gaps that affect competitive positioning,
roadmap decisions, or market understanding. Examples: "No pricing
disclosed for the new tier" or "Article doesn't clarify whether this
applies to enterprise or SMB customers."
```

Expected output: a structured note in JSON, roughly 400-600 tokens. Longer than a summary, but preserves the concrete material the synthesis step needs for thematic narrative construction. The full article text is then discarded from context.

This step is where most tokens are consumed. The one-at-a-time approach prevents context window bloat.

**Step 6 — Synthesis (`agent/synthesizer.py`):**

Input: system prompt with domain context + the PM brief template + all structured notes from step 5 concatenated.

The synthesis step performs three distinct operations in sequence:

1. **Classification review:** Use the thematic classifications from the extraction notes as a starting point, but re-evaluate them. A single article may inform multiple sections. An article the extractor tagged as `competitor_moves` might also contain a `market_macro` insight buried in a quote. The synthesizer should not blindly accept the extractor's classification — it should read across all notes and assign material to sections based on its own judgment.

2. **Cross-source narrative construction:** For each section that has supporting material, write a cohesive narrative that draws from multiple extractions where applicable. Do not list articles sequentially — weave their facts, data points, and quotes into a single analytical story. When two articles cover the same event, synthesize them into one entry, noting where they agree and where they add different details. When articles cover different events that form a pattern (e.g., three competitors all releasing similar features), call out the pattern explicitly.

3. **Analytical overlay:** For each section entry, go beyond reporting what happened. Connect the information to what it means for a PM in [domain]:
   - In Competitor Moves: how does this change the competitive landscape? Does it validate our direction or challenge it?
   - In Market & Macro: is this a headwind or tailwind? What's the time horizon for impact?
   - In Customer & Buyer: does this suggest shifting evaluation criteria we should respond to?
   - In Technology & Ecosystem: does this create an integration opportunity or a compatibility risk?

Additional synthesis rules:
- Write the Executive Summary last, after all sections are complete. It should surface the single most consequential item from the entire brief.
- PM Action Items must reference specific entries from the sections above. Each action item should name the section and the specific event or data point that motivates it. Generic advice like "monitor the competitive landscape" is not acceptable.
- Surface PM-relevant gaps from the extraction notes in the Watchlist section when they represent meaningful blind spots.
- Omit any section where the material is too vague or low-confidence to support a concrete narrative. An empty section is better than a speculative one.
- The agent may add a section not in the template if it identifies a theme that doesn't fit the predefined categories. Label these as "AGENT-IDENTIFIED" with a brief rationale for why it was added.

Expected output: the complete PM brief as structured markdown.

Define the brief template in `templates/pm_brief.py`:

```
MARKET PULSE: [DOMAIN]
Date: [run date]

--- EXECUTIVE SUMMARY ---
2-3 sentences. The single most important takeaway from this scan,
written so a PM who reads nothing else still walks away informed.

--- COMPETITOR MOVES ---
New product launches, feature releases, pricing changes, partnerships,
or strategic pivots by named competitors. Each entry should include:
  - What happened (specific facts, dates, numbers)
  - Which competitor and product
  - Why it matters (direct implications for our positioning or roadmap)
  - Source attribution
Only include if supported by extracted material. Omit section if no
competitor activity was found.

--- MARKET & MACRO TRENDS ---
Broader forces shaping the domain: regulatory changes, shifts in buyer
behavior, emerging technology standards, macroeconomic factors affecting
the market (funding climate, M&A activity, enterprise spending trends).
Focus on what's actionable — trends a PM could bring to a planning
conversation. Source attribution for each claim.
Only include if supported by extracted material. Omit section if nothing
found.

--- CUSTOMER & BUYER SIGNALS ---
Changes in how buyers evaluate, purchase, or use products in this space:
analyst reports, survey data, adoption metrics, public customer wins or
losses by competitors, shifts in procurement criteria. Source attribution.
Only include if supported by extracted material. Omit section if nothing
found.

--- TECHNOLOGY & ECOSYSTEM ---
Standards body decisions, open source project developments, platform
changes by major ecosystem players (cloud providers, infrastructure
vendors), integration or API announcements that affect the domain's
technical landscape. Source attribution.
Only include if supported by extracted material. Omit section if nothing
found.

--- WATCHLIST ---
Items that don't fit the above sections but a PM should be aware of:
early-stage signals, rumors with credible sourcing, or open questions
surfaced during extraction that warrant monitoring. Brief format —
one or two sentences per item with source.
Only include if material exists. Omit section if nothing found.

--- PM ACTION ITEMS ---
Specific, concrete next steps suggested by the material above. Not
generic advice — each item should tie directly to something in the
brief. Examples: "Review our pricing against [competitor]'s new tier
announced on [date]" or "Flag [regulation] for legal review before
Q3 planning." 2-5 items maximum.

--- SOURCES ---
All URLs referenced in the brief, grouped by section.
```

The synthesizer should apply these additional rules:
- When multiple articles cover the same event, synthesize them into a single narrative entry rather than listing each separately.
- Reference specific data points and quotes from the extractions to support claims.
- If a section would contain only vague or low-confidence material, omit it entirely.
- The agent may add a section not in the template if it identifies a theme that doesn't fit the predefined categories. Label these as "AGENT-IDENTIFIED" with a brief rationale for why it was added.

**Verification:** Run the full pipeline end to end. Inspect the output brief for coherence, relevance, and formatting. Check the token tracker log to see per-step costs. Run it 2-3 times with the same inputs to assess output consistency.

---

### Phase 4: Output and Polish

**Goal:** Clean markdown output, run summaries, and quality-of-life improvements for testing iteration.

**Tasks:**

Build the formatter that takes the synthesizer's output and writes it as a markdown file to `output/`, named with the run timestamp and domain (e.g., `2026-04-22_identity-mgmt.md`). Include a metadata header in the file: run date, domain, search terms used, number of articles processed, total token cost.

Add a CLI entry point in `main.py` that accepts optional overrides: `--budget` (max input tokens), `--terms` (override search terms from command line), `--dry-run` (run search and dedup only, show what would be processed, no LLM calls). The dry-run mode is useful for tuning search terms and dedup thresholds without burning tokens.

Add a run summary printed to stdout at the end of each run: total tokens used, estimated cost, number of articles processed, number deduplicated, output file path. This gives you immediate feedback without opening the log file.

Build a simple log analysis script (`scripts/analyze_logs.py`) that reads all JSON logs from `logs/` and prints a table of runs with date, domain, token counts, cost, and step-by-step breakdown. This helps you spot trends across testing iterations — are prompt changes making things cheaper or more expensive.

**Verification:** Run the full pipeline 5 times, varying search terms. Confirm output files are written correctly, logs accumulate, and the analysis script produces a readable summary.

---

## Config Reference

```env
# .env

# LLM
ANTHROPIC_API_KEY=sk-ant-...
MODEL=claude-sonnet-4-6
TOKEN_BUDGET=50000                    # max input tokens per run

# Search
SEARCH_API_KEY=...                    # Tavily, Serper, or Brave key
SEARCH_PROVIDER=tavily                # which search API to use

# Domain
DOMAIN_DESCRIPTION="Enterprise identity and access management (IAM)"
SEARCH_TERMS="enterprise SSO,identity management,zero trust authentication,CIAM platform,passwordless enterprise"

# Dedup thresholds
DEDUP_TITLE_SIMILARITY=0.6
DEDUP_SNIPPET_SIMILARITY=0.8

# Fetcher
MAX_ARTICLE_CHARS=6000                # truncate articles beyond this length

# Output
OUTPUT_DIR=output
LOG_DIR=logs
```

## Cost Estimates

Per-run estimates assuming 5 search terms, ~30 raw results deduped to ~10-15 articles, using extraction with thematic classification (~500-700 token outputs per article):

| Scenario | Model | Est. Input Tokens | Est. Output Tokens | Est. Cost |
|---|---|---|---|---|
| Optimized (dedup + truncation) | Sonnet 4.6 | ~35,000 | ~12,000 | ~$0.29 |
| Unoptimized (30 full articles) | Sonnet 4.6 | ~140,000 | ~25,000 | ~$0.80 |

Testing budget for 2 weeks of active development (10-15 runs/day): $80-120. Use the `--dry-run` flag heavily during early iteration to tune search terms and dedup without burning tokens.

## Key Risks and Mitigations

**Search result quality varies by provider and term specificity.** Mitigation: the `--dry-run` flag lets you evaluate search results without LLM cost. Spend time upfront tuning terms.

**Article extraction can fail or return garbage.** Some sites block automated fetching, return cookie walls, or have non-standard layouts. Mitigation: the fetcher should return a confidence indicator (e.g., did extraction return reasonable-length text). The agent should skip articles with extraction failures rather than trying to summarize HTML noise.

**LLM output format inconsistency.** The grouper and summarizer ask for JSON, but models sometimes wrap it in markdown code fences or add preamble. Mitigation: add a parsing utility that strips code fences and attempts JSON parse with a fallback to re-prompting once.

**Token budget exceeded mid-run.** If the budget check triggers during summarization, some articles won't be processed. Mitigation: the budget mechanism should log which articles were skipped so you can decide if the budget needs to be raised or if fewer articles should be selected in the grouping step.

## Post-MVP Considerations (Out of Scope)

These are noted for future reference but are explicitly excluded from MVP:

- User-facing web UI with API key input
- Email delivery (Resend/SendGrid integration)
- Credential management for paywalled sources
- Scheduled/recurring runs
- Trend detection across historical runs
- PM tool integrations (Jira, Linear, Notion)
- Agent-generated search terms (user provides terms in MVP)
- Multi-agent architecture
