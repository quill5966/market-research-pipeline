"""Tavily search wrapper for the PM News Agent pipeline.

Runs Tavily advanced search for each configured search term,
normalizes results into SearchResult models, and returns
the combined (undeduped) result list.
"""

from urllib.parse import urlparse

from tavily import TavilyClient

from config import Config
from models import SearchResult


def search(config: Config) -> list[SearchResult]:
    """Run Tavily advanced search for all configured terms.

    Makes one API call per search term with topic="news",
    search_depth="advanced", and include_raw_content=True.
    Results are combined into a single list (undeduped).

    Args:
        config: Pipeline configuration with Tavily API key and search terms.

    Returns:
        Combined list of SearchResult objects across all terms.
    """
    client = TavilyClient(api_key=config.tavily_api_key)
    all_results: list[SearchResult] = []

    for term in config.search_terms:
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

            # Truncate raw_content to configured limit
            if raw_content and len(raw_content) > config.max_article_chars:
                raw_content = raw_content[: config.max_article_chars]

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
    return all_results
