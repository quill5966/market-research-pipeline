"""Prompt builder for the synthesis step.

Asks the LLM to emit a structured Brief JSON object from extraction notes.
The schema is defined in templates/pm_brief.py and is injected into the prompt.
"""

from models import ExtractionNote
from tagging.vocabulary import FILTER_TAG_VOCABULARY


def build_synthesis_prompt(
    notes: list[ExtractionNote],
    domain_description: str,
    brief_schema: str,
    section_guidance: str,
    run_date: str,
) -> str:
    """Build the user message for the synthesis step.

    Args:
        notes: All extraction notes from the extraction step.
        domain_description: The product domain being researched.
        brief_schema: The BRIEF_JSON_SCHEMA string describing the target JSON shape.
        section_guidance: The SECTION_GUIDANCE string describing section types.
        run_date: Current date string (YYYY-MM-DD) for the brief header.

    Returns:
        A formatted user message string.
    """
    notes_json = "[\n"
    for i, note in enumerate(notes):
        notes_json += note.model_dump_json(indent=2)
        if i < len(notes) - 1:
            notes_json += ","
        notes_json += "\n"
    notes_json += "]"

    vocab_list = ", ".join(FILTER_TAG_VOCABULARY)

    return f"""You have {len(notes)} structured extraction notes from recent news articles about {domain_description}. Synthesize them into a complete PM brief, emitted as a JSON object matching the schema below.

TARGET SCHEMA:
{brief_schema}

SECTION TYPES:
{section_guidance}

SYNTHESIS INSTRUCTIONS:

1. **Cluster, then choose a section type.** Group articles by their `thematic_tags` and by any cross-cutting themes you observe. For each cluster, choose a section `title` and `type`. Conventional titles ("Competitor Moves", "Market & Macro", "Customer & Buyer Signals", "Technology & Ecosystem") map naturally to the thematic categories, but you may coin a new title when a cluster is AGENT-IDENTIFIED. Order sections by PM impact (highest first). Omit any section you have no material for.

2. **Compressed entry structure (mandatory for list-type stories).** Each story leads with `tldr` (≤25 words) and `pm_angle` (≤20 words). Include `supporting` (≤80 words) ONLY when a non-obvious mechanism, quote, or detail materially changes how a PM should read the TL;DR. Most entries should NOT need it. When two articles cover the same event, fold them into a single story and list the other domains in `additional_coverage`.

3. **Analytical overlay.** Every `pm_angle` must go beyond restating the fact:
   - Competitor Moves: how does this change our competitive position?
   - Market & Macro: tailwind or headwind, and on what time horizon?
   - Customer & Buyer: does this shift evaluation criteria we should respond to?
   - Technology & Ecosystem: integration opportunity or compatibility risk?

4. **Length discipline.** Word caps are soft targets — going over by 10–20% is fine when the alternative is awkward writing. The full brief should read in 5–10 minutes (target: under 1,500 words total). If approaching a cap, cut adjectives, hedging, and framing language before cutting facts. Specificity (numbers, dates, named entities) survives; commentary gets trimmed. **Never** abbreviate or truncate words to fit (do not write "vuln" for "vulnerability", "auth" for "authentication", "infra" for "infrastructure"). Domain-native initialisms (CVE, IAM, SSO, MFA, API) are fine.

5. **Highlights and executive summary go LAST.** After all sections are complete:
   - **highlights:** three entries ranked 1–3. Each names the most consequential items this scan period. `pointer_section` must exactly match a section `title` you used.
   - **executive_summary:** exactly two sentences, ≤60 words total. Sentence 1 names the dominant theme; sentence 2 states its consequence for a PM. No semicolons, no parentheticals, no embedded lists. This is a frame, not a digest.

6. **PM action items.** 2–5 items. Each item is one imperative sentence ≤20 words, with `pointer_section` matching the triggering section title and `pointer_story_id` set to the triggering story's id when applicable. Generic advice like "monitor the competitive landscape" is NOT acceptable.

7. **Watchlist.** One line per item (≤25 words). Surface PM-relevant gaps from the extraction notes when they represent meaningful blind spots.

8. **Sources.** Populate the global `sources` list with every URL referenced by any story or watchlist item. Set `referenced_in` to the section title(s) where the URL appears. Per-section `source_urls` repeats those URLs grouped by section.

FILTER TAGS (closed vocabulary):
The allowed filter_tags vocabulary is: {vocab_list}

For each story you create, set `filter_tags` to the union of the `filter_tags` arrays of the extraction note(s) that informed it. Do not invent new tags. Do not propagate any value that is not in the vocabulary above. When a story merges multiple notes, deduplicate the union.

OUTPUT FORMAT:
Respond with a single JSON object matching the schema. Do NOT wrap it in code fences. Do NOT include any prose before or after the JSON. Set `raw_markdown` to an empty string — the server renders it.

Replace the placeholder `title` with "{domain_description}" and `date` with "{run_date}".

EXTRACTION NOTES:
{notes_json}"""
