"""PM Brief template definition.

Contains the template string that defines the structure and section
headings for the final PM brief output. Injected into the synthesis
prompt so the LLM knows the target format.

Format philosophy: optimized for scanning. A reader should be able to
skim the top of the brief in under a minute and know the most important
items, read any single entry's TL;DR in ~10 seconds, and finish the
entire brief in 5-10 minutes. Word caps are soft targets — readability
beats hitting the cap exactly. Never abbreviate or truncate words to
fit a cap; cut a clause or rewrite the sentence instead.
"""

PM_BRIEF_TEMPLATE = """MARKET PULSE: [DOMAIN]
Date: [run date]

--- TOP 3 HIGHLIGHTS ---
Three single-line bullets naming the three most consequential items
this scan period. Each line: a short headline, an em-dash, a <12-word
"why it matters" clause, then "→ see [Section name]". Order by PM
impact, highest first.
Example shape:
1. [Headline] — [why it matters in <12 words] → see [Section]
2. [Headline] — [why it matters in <12 words] → see [Section]
3. [Headline] — [why it matters in <12 words] → see [Section]

--- EXECUTIVE SUMMARY ---
≤60 words total. Exactly two sentences:
  - Sentence 1: name the single dominant theme of the scan period.
  - Sentence 2: state its consequence for a PM in this domain.
No lists, no semicolons, no parenthetical asides, no embedded clauses.
This is a frame, not a digest — the Top 3 Highlights does the digesting.

--- COMPETITOR MOVES ---
Product launches, feature releases, pricing changes, partnerships, or
strategic pivots by named competitors.

For each entry, use this exact structure:
  ### [Headline ≤10 words: name the actor + the move]
  **TL;DR:** ≤25 words. What happened, including the single most
  important number, date, or named entity. No hedging.
  **PM angle:** ≤20 words. The implication for our positioning,
  roadmap, or competitive stance.

  [Optional supporting paragraph, ≤80 words. Include ONLY when there
  is a non-obvious mechanism, quote, or detail that materially changes
  how a PM should read the TL;DR. Most entries should not need this.]

  *Source: domain.com — URL*

Omit the section if no competitor activity was found.

--- MARKET & MACRO TRENDS ---
Regulatory changes, buyer-behavior shifts, emerging tech standards,
macroeconomic factors. Same per-entry structure as Competitor Moves
(headline / TL;DR / PM angle / optional ≤80-word paragraph / source).
For PM angle in this section: is this a tailwind or headwind, and on
what time horizon?
Omit the section if nothing found.

--- CUSTOMER & BUYER SIGNALS ---
Analyst reports, survey data, adoption metrics, public customer wins
or losses, shifts in procurement criteria. Same per-entry structure.
For PM angle: does this suggest shifting evaluation criteria we should
respond to?
Omit the section if nothing found.

--- TECHNOLOGY & ECOSYSTEM ---
Standards-body decisions, open source developments, platform changes,
integration/API announcements. Same per-entry structure.
For PM angle: integration opportunity or compatibility risk?
Omit the section if nothing found.

--- WATCHLIST ---
Bulleted list. One line per item, ≤25 words each. Format:
  - **[Topic]:** [the signal in <20 words] (*source: domain.com*)
No prose blocks. No multi-sentence items. Omit the section if empty.

--- PM ACTION ITEMS ---
2-5 items. Each item: one imperative sentence, ≤20 words, ending with
a parenthetical pointer to the section/entry that motivates it.
Example: "Review our pricing against Acme's new tier (Competitor Moves: Acme launches Pro plan)."
No generic advice — every item must trace to a specific entry above.

--- SOURCES ---
All URLs referenced in the brief, grouped by section.
"""
