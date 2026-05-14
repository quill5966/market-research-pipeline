"""Deduplication pipeline for search results.

Three-stage dedup:
1. Exact URL dedup — remove identical URLs
2. Domain-title clustering — within same domain, merge similar titles
3. Cross-domain snippet similarity — catch syndicated content across domains

Each stage logs removal counts for threshold tuning.
"""

import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from models import DedupStats, DiscardedArticle, SearchResult


def deduplicate(
    results: list[SearchResult],
    title_threshold: float,
    snippet_threshold: float,
) -> tuple[list[SearchResult], DedupStats]:
    """Run the three-stage dedup pipeline.

    Args:
        results: Raw search results (may contain duplicates).
        title_threshold: Jaccard similarity threshold for same-domain
                         title dedup (default 0.6).
        snippet_threshold: Jaccard similarity threshold for cross-domain
                           snippet dedup (default 0.8).

    Returns:
        Tuple of (deduped results sorted by score descending, stats).
    """
    raw_count = len(results)

    # Stage 1: Exact URL dedup
    after_url, url_discards = _dedup_exact_url(results)
    url_removed = len(url_discards)

    # Stage 2: Domain-title clustering
    after_title, title_discards = _dedup_domain_title(after_url, title_threshold)
    title_removed = len(title_discards)

    # Stage 3: Cross-domain snippet similarity
    after_snippet, snippet_discards = _dedup_snippet(after_title, snippet_threshold)
    snippet_removed = len(snippet_discards)

    # Sort by score descending (best results first)
    after_snippet.sort(key=lambda r: r.score, reverse=True)

    stats = DedupStats(
        raw_count=raw_count,
        after_url_dedup=len(after_url),
        after_domain_title_dedup=len(after_title),
        after_snippet_dedup=len(after_snippet),
        removed_total=raw_count - len(after_snippet),
        discarded=url_discards + title_discards + snippet_discards,
    )

    print(
        f"📋 Dedup: {stats.raw_count} raw → "
        f"{stats.after_url_dedup} after URL → "
        f"{stats.after_domain_title_dedup} after domain-title → "
        f"{stats.after_snippet_dedup} after snippet"
    )
    print(
        f"   Removed: {stats.removed_total} total "
        f"({url_removed} exact URL, "
        f"{title_removed} domain-title, "
        f"{snippet_removed} snippet)"
    )

    return after_snippet, stats


def _normalize_url(url: str) -> str:
    """Normalize a URL for dedup comparison.

    Lowercases, strips trailing slash, removes utm_* query params.
    """
    parsed = urlparse(url.lower().rstrip("/"))

    # Remove utm_* and tracking query params
    if parsed.query:
        params = parse_qs(parsed.query)
        filtered = {
            k: v for k, v in params.items()
            if not k.startswith("utm_")
        }
        clean_query = urlencode(filtered, doseq=True)
    else:
        clean_query = ""

    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        clean_query,
        "",  # strip fragment
    ))


def _dedup_exact_url(
    results: list[SearchResult],
) -> tuple[list[SearchResult], list[DiscardedArticle]]:
    """Stage 1: Remove results with identical normalized URLs.

    Keeps the first occurrence (typically highest-scored since
    Tavily returns results in relevance order).
    """
    seen: dict[str, SearchResult] = {}
    deduped: list[SearchResult] = []
    discards: list[DiscardedArticle] = []

    for r in results:
        normalized = _normalize_url(r.url)
        winner = seen.get(normalized)
        if winner is None:
            seen[normalized] = r
            deduped.append(r)
        else:
            discards.append(DiscardedArticle(
                url=r.url,
                title=r.title,
                stage="dedup_url",
                reason="Duplicate normalized URL",
                kept_in_favor_of=winner.url,
            ))

    return deduped, discards


def _dedup_domain_title(
    results: list[SearchResult], threshold: float
) -> tuple[list[SearchResult], list[DiscardedArticle]]:
    """Stage 2: Within each domain, merge results with similar titles.

    Groups results by source_domain. Within each group, compares
    titles pairwise. If two titles exceed the threshold, keeps the
    one with the higher Tavily score.
    """
    # Group by domain
    by_domain: dict[str, list[SearchResult]] = {}
    for r in results:
        by_domain.setdefault(r.source_domain, []).append(r)

    deduped: list[SearchResult] = []
    discards: list[DiscardedArticle] = []

    for domain, group in by_domain.items():
        if len(group) <= 1:
            deduped.extend(group)
            continue

        # Sort by score descending so we keep higher-scored items
        group.sort(key=lambda r: r.score, reverse=True)
        keep: list[SearchResult] = []

        for candidate in group:
            duplicate_of: SearchResult | None = None
            similarity = 0.0
            for kept in keep:
                sim = _word_overlap(candidate.title, kept.title)
                if sim >= threshold:
                    duplicate_of = kept
                    similarity = sim
                    break
            if duplicate_of is None:
                keep.append(candidate)
            else:
                discards.append(DiscardedArticle(
                    url=candidate.url,
                    title=candidate.title,
                    stage="dedup_title",
                    reason=(
                        f"Title Jaccard {similarity:.2f} ≥ {threshold:.2f} "
                        f"within domain {domain}"
                    ),
                    kept_in_favor_of=duplicate_of.url,
                ))

        deduped.extend(keep)

    return deduped, discards


def _dedup_snippet(
    results: list[SearchResult], threshold: float
) -> tuple[list[SearchResult], list[DiscardedArticle]]:
    """Stage 3: Cross-domain snippet similarity.

    Compares snippets pairwise across different domains. If two
    snippets exceed the threshold, keeps the one with the higher
    Tavily score (proxy for source authority).
    """
    # Sort by score descending — higher-scored results are kept
    sorted_results = sorted(results, key=lambda r: r.score, reverse=True)
    keep: list[SearchResult] = []
    discards: list[DiscardedArticle] = []

    for candidate in sorted_results:
        duplicate_of: SearchResult | None = None
        similarity = 0.0
        for kept in keep:
            # Only compare across different domains
            if candidate.source_domain == kept.source_domain:
                continue
            sim = _word_overlap(candidate.snippet, kept.snippet)
            if sim >= threshold:
                duplicate_of = kept
                similarity = sim
                break
        if duplicate_of is None:
            keep.append(candidate)
        else:
            discards.append(DiscardedArticle(
                url=candidate.url,
                title=candidate.title,
                stage="dedup_snippet",
                reason=(
                    f"Snippet Jaccard {similarity:.2f} ≥ {threshold:.2f} "
                    f"across domains ({candidate.source_domain} vs "
                    f"{duplicate_of.source_domain})"
                ),
                kept_in_favor_of=duplicate_of.url,
            ))

    return keep, discards


def _word_overlap(text_a: str, text_b: str) -> float:
    """Jaccard similarity of word sets (case-insensitive).

    Returns |intersection| / |union| of word sets, where words
    are lowercased and stripped of punctuation.

    Returns 0.0 if both texts are empty.
    """
    words_a = _tokenize(text_a)
    words_b = _tokenize(text_b)

    if not words_a and not words_b:
        return 0.0

    intersection = words_a & words_b
    union = words_a | words_b

    return len(intersection) / len(union) if union else 0.0


def _tokenize(text: str) -> set[str]:
    """Tokenize text into a set of lowercased words, stripping punctuation."""
    # Remove punctuation, lowercase, split on whitespace
    cleaned = re.sub(r"[^\w\s]", "", text.lower())
    return set(cleaned.split())
