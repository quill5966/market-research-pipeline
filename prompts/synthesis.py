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

2. **Cross-source narrative construction:** For each section that has supporting material, write a cohesive narrative that draws from multiple extractions where applicable. Do NOT list articles sequentially — weave their facts, data points, and quotes into a single analytical story. When two articles cover the same event, synthesize them into one entry, noting where they agree and where they add different details. When articles cover different events that form a pattern (e.g., three competitors all releasing similar features), call out the pattern explicitly.

3. **Analytical overlay:** For each section entry, go beyond reporting what happened. Connect the information to what it means for a PM in {domain_description}:
   - In Competitor Moves: how does this change the competitive landscape? Does it validate our direction or challenge it?
   - In Market & Macro: is this a headwind or tailwind? What's the time horizon for impact?
   - In Customer & Buyer: does this suggest shifting evaluation criteria we should respond to?
   - In Technology & Ecosystem: does this create an integration opportunity or a compatibility risk?

ADDITIONAL RULES:
- Write the Executive Summary LAST, after all sections are complete. It should surface the single most consequential item from the entire brief.
- PM Action Items must reference specific entries from the sections above. Each action item should name the section and the specific event or data point that motivates it. Generic advice like "monitor the competitive landscape" is NOT acceptable.
- Surface PM-relevant gaps from the extraction notes in the Watchlist section when they represent meaningful blind spots.
- Omit any section where the material is too vague or low-confidence to support a concrete narrative. An empty section is better than a speculative one.
- You may add a section not in the template if you identify a theme that doesn't fit the predefined categories. Label these as "AGENT-IDENTIFIED" with a brief rationale for why it was added.
- When multiple articles cover the same event, synthesize them into a single narrative entry rather than listing each separately.
- Reference specific data points and quotes from the extractions to support claims.
- Include source attribution (source domain + URL) for all factual claims.

Output the complete PM brief as markdown. Do NOT wrap the output in code fences — output raw markdown directly.

EXTRACTION NOTES:
{notes_json}"""
