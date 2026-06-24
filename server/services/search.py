"""Tavily search wrapper for the PM News Agent pipeline.

Runs Tavily advanced search for each configured search term,
normalizes results into SearchResult models, and returns
the combined (undeduped) result list.
"""

from statistics import median
from urllib.parse import urlparse

from tavily import TavilyClient

from config import RunConfig
from models import SearchResult


def search(config: RunConfig, terms: list[str] | None = None) -> list[SearchResult]:
    """Run Tavily advanced search for the given terms.

    Makes one API call per search term with topic="news",
    search_depth="advanced", and include_raw_content=True.
    Results are combined into a single list (undeduped).

    Args:
        config: Pipeline configuration with Tavily API key and search terms.
        terms: Explicit term list to search. Defaults to config.search_terms.
               The agent reviewer passes corrective terms here on a re-search.

    Returns:
        Combined list of SearchResult objects across all terms.
    """
    client = TavilyClient(api_key=config.tavily_api_key)
    search_terms = terms if terms is not None else config.search_terms
    all_results: list[SearchResult] = []
    original_lengths: list[int] = []  # raw_content lengths before truncation
    truncated_count = 0

    for term in search_terms:
        response = client.search(
            query=term,
            search_depth="advanced",
            topic="news",
            time_range="week",
            include_raw_content=True,
            include_answer=False,
            max_results=config.max_results_per_term,
            include_domains=config.include_domains or None,
            exclude_domains=config.exclude_domains or None,
        )

        results = response.get("results", [])

        for r in results:
            # Extract source domain from URL, stripping www. prefix
            parsed = urlparse(r.get("url", ""))
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]

            # Normalize raw_content — treat empty string as None
            raw_content = r.get("raw_content") or None

            # Track original length + truncation against config.max_article_chars
            if raw_content:
                original_lengths.append(len(raw_content))
                if len(raw_content) > config.max_article_chars:
                    original_len = len(raw_content)
                    raw_content = raw_content[: config.max_article_chars]
                    truncated_count += 1
                    print(
                        f"✂  Truncated: {r.get('url', '')} — "
                        f"\"{r.get('title', '')}\" "
                        f"({original_len:,} → {config.max_article_chars:,} chars)"
                    )

            result = SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("content", ""),
                raw_content=raw_content,
                score=r.get("score", 0.0),
                source_domain=domain,
                search_term=term,
            )
            all_results.append(result)

        print(f"🔍 '{term}': {len(results)} results")

    print(f"\n📦 Total raw results: {len(all_results)}")

    # Article-length summary — flags whether max_article_chars is biting on this run.
    if original_lengths:
        med_k = median(original_lengths) / 1000
        max_k = max(original_lengths) / 1000
        cap_k = config.max_article_chars / 1000
        print(
            f"📏 raw_content: {len(original_lengths)} articles with content · "
            f"{truncated_count} truncated to {cap_k:.0f}k chars "
            f"(originals: {med_k:.1f}k median, {max_k:.1f}k max)"
        )

    return all_results
