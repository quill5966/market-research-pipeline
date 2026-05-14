"""Grouping step — LLM groups search results by story.

Receives deduped search results, filters out those without raw_content,
asks the LLM to group by underlying story/event, and selects the best
source per group for extraction.
"""

from agent.client import AgentClient
from agent.json_utils import parse_llm_json
from models import DiscardedArticle, GroupingResult, SearchResult
from prompts.grouping import build_grouping_prompt
from prompts.system import build_system_prompt


def group_results(
    client: AgentClient,
    results: list[SearchResult],
    product_name: str,
    product_context: str,
) -> GroupingResult:
    """Group search results by story and select best sources.

    Filters out results without raw_content before prompting the LLM,
    since those articles can't be extracted downstream.

    Args:
        client: AgentClient for LLM calls.
        results: Deduped search results from Phase 2.
        product_name: Short product label being researched.
        product_context: Multi-line product context for the system prompt.

    Returns:
        GroupingResult with selected groups and discard count.

    Raises:
        ValueError: If LLM response cannot be parsed as valid JSON.
        TokenBudgetExceeded: If the call would exceed the token budget.
    """
    # Filter out results with no raw_content
    with_content = [r for r in results if r.raw_content]
    no_content = [r for r in results if not r.raw_content]
    no_content_discards = [
        DiscardedArticle(
            url=r.url,
            title=r.title,
            stage="group_no_content",
            reason="No raw_content available from search; cannot extract.",
        )
        for r in no_content
    ]

    if no_content_discards:
        print(f"🔍 Grouper: filtered out {len(no_content_discards)} results with no article content")

    if not with_content:
        print("⚠️  No results with article content available — skipping grouping.")
        return GroupingResult(groups=[], discarded=no_content_discards)

    print(f"🔍 Grouper: processing {len(with_content)} results with article content...")

    # Build prompts
    system_prompt = build_system_prompt(product_name, product_context)
    user_message = build_grouping_prompt(with_content, product_name)

    # Make LLM call
    raw_response = client.call(
        step_name="grouping",
        messages=[{"role": "user", "content": user_message}],
        system=system_prompt,
        max_tokens=2048,
    )

    # Parse and validate. The LLM emits `discarded` as [{url, reason}], which
    # lacks the title/stage required by DiscardedArticle — handle it separately
    # before constructing GroupingResult.
    try:
        parsed = parse_llm_json(raw_response)
        raw_discards = parsed.pop("discarded", []) or []
        result = GroupingResult(**parsed)
    except (ValueError, TypeError) as e:
        print(f"❌ Grouper: failed to parse LLM response")
        print(f"   Raw response preview: {raw_response[:300]}...")
        raise ValueError(f"Grouping step failed to parse LLM response: {e}") from e

    # Enrich LLM-supplied discards with stage label and original title.
    # The LLM only knows URLs; look up titles from the input set.
    title_by_url = {r.url: r.title for r in with_content}
    llm_discards: list[DiscardedArticle] = []
    for d in raw_discards:
        if not isinstance(d, dict) or not d.get("url"):
            continue
        url = d["url"]
        llm_discards.append(DiscardedArticle(
            url=url,
            title=title_by_url.get(url, ""),
            stage="group_llm_irrelevant",
            reason=d.get("reason"),
        ))
    result.discarded = no_content_discards + llm_discards

    # Summary
    print(f"✅ Grouper: {len(result.groups)} story groups identified, "
          f"{len(result.discarded)} results discarded "
          f"({len(no_content_discards)} no content, {len(llm_discards)} irrelevant)")
    for i, group in enumerate(result.groups, 1):
        print(f"   {i:2d}. [{group.group_label}] → {group.selected_title[:60]}")

    return result
