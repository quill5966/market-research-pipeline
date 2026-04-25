"""Extraction step — LLM extracts structured notes per article.

Processes each selected article one at a time, extracting structured
information with thematic classification. Handles budget exceeded
and parse failures gracefully by skipping individual articles.
"""

from agent.client import AgentClient, TokenBudgetExceeded
from agent.json_utils import parse_llm_json
from models import ExtractionNote, GroupingResult, SearchResult
from prompts.extraction import build_extraction_prompt
from prompts.system import build_system_prompt


def extract_articles(
    client: AgentClient,
    groups: GroupingResult,
    results: list[SearchResult],
    domain_description: str,
) -> list[ExtractionNote]:
    """Extract structured notes from each selected article.

    Processes articles one at a time to keep context windows small
    and token tracking granular. Skips articles gracefully on parse
    failures or budget exhaustion.

    Args:
        client: AgentClient for LLM calls.
        groups: GroupingResult from the grouping step.
        results: Deduped search results (used for URL→article lookup).
        domain_description: The product domain being researched.

    Returns:
        List of ExtractionNote objects (may be shorter than groups
        if some articles were skipped).
    """
    if not groups.groups:
        print("⚠️  No groups to extract — skipping extraction step.")
        return []

    # Build URL → SearchResult lookup
    url_lookup: dict[str, SearchResult] = {r.url: r for r in results}

    system_prompt = build_system_prompt(domain_description)
    notes: list[ExtractionNote] = []
    total = len(groups.groups)
    skipped_budget = 0
    skipped_parse = 0
    skipped_no_content = 0

    print(f"\n📝 Extractor: processing {total} articles...")

    for i, group in enumerate(groups.groups):
        # Look up the search result by URL
        sr = url_lookup.get(group.selected_url)
        if not sr or not sr.raw_content:
            print(f"   ⚠️  {i+1}/{total}: Skipping [{group.group_label}] — "
                  f"no article content for {group.selected_url}")
            skipped_no_content += 1
            continue

        # Build extraction prompt
        user_message = build_extraction_prompt(
            article_text=sr.raw_content,
            title=sr.title,
            source=sr.source_domain,
            url=sr.url,
            domain_description=domain_description,
            group_label=group.group_label,
        )

        # Make LLM call (may raise TokenBudgetExceeded)
        try:
            raw_response = client.call(
                step_name=f"extraction_{i+1}",
                messages=[{"role": "user", "content": user_message}],
                system=system_prompt,
                max_tokens=5000,
            )
        except TokenBudgetExceeded as e:
            remaining = total - i
            skipped_budget = remaining
            print(f"\n   ⚠️  Token budget exceeded at article {i+1}/{total}. "
                  f"Skipping remaining {remaining} articles.")
            print(f"   {e}")
            break

        # Parse and validate
        try:
            parsed = parse_llm_json(raw_response)
            note = ExtractionNote(**parsed)
            notes.append(note)
            print(f"   📝 {i+1}/{total}: {note.headline[:60]}")
        except (ValueError, TypeError) as e:
            skipped_parse += 1
            print(f"   ❌ {i+1}/{total}: Parse failed for [{group.group_label}] — {e}")

            # Dump full response to debug file for diagnosis
            from pathlib import Path
            debug_dir = Path("logs/debug")
            debug_dir.mkdir(parents=True, exist_ok=True)
            debug_path = debug_dir / f"extraction_fail_{i+1}.txt"
            debug_path.write_text(raw_response)
            print(f"      Full response dumped to {debug_path}")
            continue

    # Summary
    print(f"\n✅ Extractor: {len(notes)} notes extracted from {total} articles")
    if skipped_no_content:
        print(f"   ⚠️  {skipped_no_content} skipped (no article content)")
    if skipped_parse:
        print(f"   ⚠️  {skipped_parse} skipped (JSON parse failure)")
    if skipped_budget:
        print(f"   ⚠️  {skipped_budget} skipped (token budget exceeded)")

    return notes
