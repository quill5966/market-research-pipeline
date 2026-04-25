"""PM Brief template definition.

Contains the template string that defines the structure and section
headings for the final PM brief output. Injected into the synthesis
prompt so the LLM knows the target format.
"""

PM_BRIEF_TEMPLATE = """MARKET PULSE: [DOMAIN]
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
"""
