"""Synthesis step — LLM generates the structured PM Brief from extraction notes.

Takes all structured extraction notes and produces a `Brief` Pydantic object.
The markdown export is rendered server-side via `render_brief_markdown()`.
"""

from agent.client import AgentClient
from agent.json_utils import parse_llm_json
from models import Brief, ExtractionNote
from prompts.synthesis import build_synthesis_prompt
from prompts.system import build_system_prompt
from tagging.vocabulary import FILTER_TAG_VOCABULARY
from templates.pm_brief import BRIEF_JSON_SCHEMA, SECTION_GUIDANCE


def synthesize_brief(
    client: AgentClient,
    notes: list[ExtractionNote],
    domain_description: str,
    run_date: str,
) -> Brief | None:
    """Synthesize a structured PM Brief from extraction notes.

    Returns None on empty input or parse failure (orchestrator handles fallback).

    Raises:
        TokenBudgetExceeded: If the call would exceed the token budget.
    """
    if not notes:
        print("⚠️  No extraction notes — cannot synthesize brief.")
        return None

    print(f"\n📝 Synthesizer: generating brief from {len(notes)} extraction notes...")

    system_prompt = build_system_prompt(domain_description)
    user_message = build_synthesis_prompt(
        notes=notes,
        domain_description=domain_description,
        brief_schema=BRIEF_JSON_SCHEMA,
        section_guidance=SECTION_GUIDANCE,
        run_date=run_date,
    )

    raw_response = client.call(
        step_name="synthesis",
        messages=[{"role": "user", "content": user_message}],
        system=system_prompt,
        max_tokens=8192,
    )

    try:
        parsed = parse_llm_json(raw_response)
        brief = Brief(**parsed)
    except (ValueError, TypeError) as e:
        print(f"❌ Synthesizer: JSON parse failed — {e}")
        from pathlib import Path
        debug_dir = Path("logs/debug")
        debug_dir.mkdir(parents=True, exist_ok=True)
        debug_path = debug_dir / "synthesis_fail.txt"
        debug_path.write_text(raw_response)
        print(f"   Full response dumped to {debug_path}")
        return None

    # Belt-and-suspenders: strip any filter_tags outside the vocabulary
    for section in brief.sections:
        for story in section.stories:
            story.filter_tags = [t for t in story.filter_tags if t in FILTER_TAG_VOCABULARY]

    print(f"✅ Synthesizer: brief parsed — {len(brief.sections)} sections, {sum(len(s.stories) for s in brief.sections)} stories")

    return brief
