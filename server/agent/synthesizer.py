"""Synthesis step — LLM generates the PM brief from extraction notes.

Takes all structured extraction notes, the brief template, and domain
context, and produces the final markdown PM brief.
"""

from agent.client import AgentClient
from models import ExtractionNote
from prompts.synthesis import build_synthesis_prompt
from prompts.system import build_system_prompt
from templates.pm_brief import PM_BRIEF_TEMPLATE


def synthesize_brief(
    client: AgentClient,
    notes: list[ExtractionNote],
    domain_description: str,
    run_date: str,
) -> str:
    """Synthesize a PM brief from extraction notes.

    Args:
        client: AgentClient for LLM calls.
        notes: Extraction notes from the extraction step.
        domain_description: The product domain being researched.
        run_date: Current date string (YYYY-MM-DD) for the brief header.

    Returns:
        The complete PM brief as a markdown string.

    Raises:
        TokenBudgetExceeded: If the call would exceed the token budget.
    """
    if not notes:
        print("⚠️  No extraction notes — cannot synthesize brief.")
        return ""

    print(f"\n📝 Synthesizer: generating brief from {len(notes)} extraction notes...")

    # Build prompts
    system_prompt = build_system_prompt(domain_description)
    user_message = build_synthesis_prompt(
        notes=notes,
        domain_description=domain_description,
        brief_template=PM_BRIEF_TEMPLATE,
        run_date=run_date,
    )

    # Make LLM call — higher max_tokens for the full brief
    brief = client.call(
        step_name="synthesis",
        messages=[{"role": "user", "content": user_message}],
        system=system_prompt,
        max_tokens=4096,
    )

    print(f"✅ Synthesizer: brief generated ({len(brief):,} chars)")

    return brief
