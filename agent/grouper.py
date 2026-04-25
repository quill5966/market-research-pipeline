"""Grouping step — LLM groups search results by story.

Receives deduped search results, filters out those without raw_content,
asks the LLM to group by underlying story/event, and selects the best
source per group for extraction.
"""

from agent.client import AgentClient
from agent.json_utils import parse_llm_json
from models import GroupingResult, SearchResult
from prompts.grouping import build_grouping_prompt
from prompts.system import build_system_prompt


def group_results(
    client: AgentClient,
    results: list[SearchResult],
    domain_description: str,
) -> GroupingResult:
    """Group search results by story and select best sources.

    Filters out results without raw_content before prompting the LLM,
    since those articles can't be extracted downstream.

    Args:
        client: AgentClient for LLM calls.
        results: Deduped search results from Phase 2.
        domain_description: The product domain being researched.

    Returns:
        GroupingResult with selected groups and discard count.

    Raises:
        ValueError: If LLM response cannot be parsed as valid JSON.
        TokenBudgetExceeded: If the call would exceed the token budget.
    """
    # Filter out results with no raw_content
    with_content = [r for r in results if r.raw_content]
    dropped = len(results) - len(with_content)

    if dropped > 0:
        print(f"🔍 Grouper: filtered out {dropped} results with no article content")

    if not with_content:
        print("⚠️  No results with article content available — skipping grouping.")
        return GroupingResult(groups=[], discarded_count=len(results))

    print(f"🔍 Grouper: processing {len(with_content)} results with article content...")

    # Build prompts
    system_prompt = build_system_prompt(domain_description)
    user_message = build_grouping_prompt(with_content, domain_description)

    # Make LLM call
    raw_response = client.call(
        step_name="grouping",
        messages=[{"role": "user", "content": user_message}],
        system=system_prompt,
        max_tokens=2048,
    )

    # Parse and validate
    try:
        parsed = parse_llm_json(raw_response)
        result = GroupingResult(**parsed)
    except (ValueError, TypeError) as e:
        print(f"❌ Grouper: failed to parse LLM response")
        print(f"   Raw response preview: {raw_response[:300]}...")
        raise ValueError(f"Grouping step failed to parse LLM response: {e}") from e

    # Summary
    print(f"✅ Grouper: {len(result.groups)} story groups identified, "
          f"{result.discarded_count} results discarded as irrelevant")
    for i, group in enumerate(result.groups, 1):
        print(f"   {i:2d}. [{group.group_label}] → {group.selected_title[:60]}")

    return result
