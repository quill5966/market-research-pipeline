"""Prompt builder for the grouping step.

Formats deduped search results into a user message that asks the LLM
to group them by underlying story, filter irrelevant results, and
select the best source per group.
"""

from models import SearchResult


def build_grouping_prompt(
    results: list[SearchResult],
    domain_description: str,
) -> str:
    """Build the user message for the grouping step.

    Only results with raw_content should be passed in — no-content
    results should be filtered out before calling this function.

    Args:
        results: Deduped search results (with raw_content available).
        domain_description: The product domain being researched.

    Returns:
        A formatted user message string.
    """
    # Format results as a numbered list
    result_lines = []
    for i, r in enumerate(results, 1):
        result_lines.append(
            f"{i}. Title: {r.title}\n"
            f"   Source: {r.source_domain}\n"
            f"   URL: {r.url}\n"
            f"   Snippet: {r.snippet}"
        )

    results_block = "\n\n".join(result_lines)

    return f"""Below are {len(results)} search results related to {domain_description}. Each result includes a title, source domain, URL, and snippet.

Your task:
1. **Group** these results by underlying story or event. Multiple articles covering the same news should be in one group.
2. **Discard** any results that are clearly irrelevant to {domain_description}. Count how many you discard.
3. **Rank** the groups by likely relevance to a product manager working in {domain_description}. Most important groups first.
4. **Select** the single best source per group — prefer original reporting over aggregation, and sources known for depth and accuracy.
5. **Limit** your output to at most 15 groups. If you have more than 15 relevant groups, keep only the top 15 by PM relevance.

Respond with a JSON object matching this exact schema:
{{
  "groups": [
    {{
      "group_label": "Short descriptive label for this story",
      "selected_url": "URL of the best source to read in full",
      "selected_title": "Title of the selected source",
      "rationale": "One sentence explaining why this source was chosen over others in the group",
      "related_urls": ["other", "urls", "in", "this", "group"]
    }}
  ],
  "discarded_count": 3
}}

SEARCH RESULTS:

{results_block}"""
