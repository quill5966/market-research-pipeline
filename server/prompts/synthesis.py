"""Prompt builder for the synthesis step.

Formats all extraction notes and the brief template into a user message
that asks the LLM to synthesize a cohesive PM brief.
"""

from models import ExtractionNote


def build_synthesis_prompt(
    notes: list[ExtractionNote],
    domain_description: str,
    brief_template: str,
    run_date: str,
) -> str:
    """Build the user message for the synthesis step.

    Args:
        notes: All extraction notes from the extraction step.
        domain_description: The product domain being researched.
        brief_template: The PM brief template string.
        run_date: Current date string (YYYY-MM-DD) for the brief header.

    Returns:
        A formatted user message string.
    """
    # Serialize notes as JSON for the LLM
    notes_json = "[\n"
    for i, note in enumerate(notes):
        notes_json += note.model_dump_json(indent=2)
        if i < len(notes) - 1:
            notes_json += ","
        notes_json += "\n"
    notes_json += "]"

    return f"""You have {len(notes)} structured extraction notes from recent news articles about {domain_description}. Your task is to synthesize these into a complete PM brief.

BRIEF TEMPLATE:
{brief_template}

Replace [DOMAIN] with "{domain_description}" and [run date] with "{run_date}".

SYNTHESIS INSTRUCTIONS:

1. **Classification review:** Use the thematic classifications from the extraction notes as a starting point, but re-evaluate them. A single article may inform multiple sections. An article tagged as "competitor_moves" might also contain a "market_macro" insight buried in a quote. Read across all notes and assign material to sections based on your own judgment.

2. **Compressed entry structure (mandatory).** Each section entry must lead with a one-line **TL;DR:** (≤25 words) and a one-line **PM angle:** (≤20 words). After those two lines, include a supporting paragraph of ≤80 words ONLY when a non-obvious mechanism, quote, or detail materially changes how a PM should read the TL;DR. Most entries should NOT need the paragraph. Do not write multi-paragraph prose blocks. Cross-source synthesis still applies — when two articles cover the same event, fold them into a single entry — but compress the synthesis into the TL;DR/angle/optional-paragraph structure, not into expanded narrative.

3. **Analytical overlay:** Every entry's PM angle must go beyond restating the fact. Connect to what it means for a PM in {domain_description}:
   - Competitor Moves: how does this change our competitive position?
   - Market & Macro: tailwind or headwind, and on what time horizon?
   - Customer & Buyer: does this shift evaluation criteria we should respond to?
   - Technology & Ecosystem: integration opportunity or compatibility risk?

4. **Length discipline.** Word caps in the template are soft targets, not hard limits — going over by 10–20% is fine when the alternative is awkward writing. The full brief should read in 5–10 minutes (target: under 1,500 words total). If you are approaching a cap, cut adjectives, hedging, and framing language before cutting facts. Specificity (numbers, dates, named entities) survives; commentary gets trimmed. **Never** abbreviate or truncate words to fit a cap (e.g., do not write "vuln" for "vulnerability", "auth" for "authentication", "infra" for "infrastructure"). Use full words and complete sentences — drop a clause or rewrite the sentence instead. Standard initialisms that are domain-native (CVE, IAM, SSO, MFA, API) are fine.

ADDITIONAL RULES:
- Write the Top 3 Highlights and Executive Summary LAST, after all sections are complete.
  - **Top 3 Highlights:** three single-line bullets naming the most consequential items this scan period. Each line ends with `→ see [Section name]` pointing to where it is detailed below. Order by PM impact.
  - **Executive Summary:** ≤60 words, exactly two sentences. Sentence 1 names the dominant theme of the scan period; sentence 2 states its consequence for a PM. No semicolons, no parentheticals, no embedded lists. This is a frame, not a digest — the Top 3 Highlights does the digesting.
- PM Action Items must reference specific entries from the sections above. Each item is one imperative sentence, ≤20 words, ending with a parenthetical pointer to the triggering section/entry. Generic advice like "monitor the competitive landscape" is NOT acceptable.
- Watchlist must be a bulleted list, one line per item (≤25 words). No prose blocks.
- Surface PM-relevant gaps from the extraction notes in the Watchlist when they represent meaningful blind spots.
- Omit any section where the material is too vague or low-confidence to support a concrete entry. An empty section is better than a speculative one.
- You may add a section not in the template if you identify a theme that doesn't fit the predefined categories. Label these as "AGENT-IDENTIFIED" with a brief rationale, and follow the same TL;DR/PM-angle structure.
- Reference specific data points and quotes from the extractions to support claims.
- Include source attribution (source domain + URL) for all factual claims.

Output the complete PM brief as markdown. Do NOT wrap the output in code fences — output raw markdown directly.

EXTRACTION NOTES:
{notes_json}"""
