"""Review step — the agent reviewer judges a synthesized brief.

Makes a single LLM call (pipeline model) that assesses the brief against the
product context and returns a ReviewVerdict. On a coverage_gap verdict, the
LLM-proposed search terms are filtered so they genuinely differ from the terms
already used — otherwise a second search would just re-fetch the same articles.

Returns None on parse/validation failure so the orchestrator can ship the
current brief rather than block on a broken judge.
"""

from agent.client import AgentClient
from agent.json_utils import parse_llm_json
from models import Brief, DiscardedArticle, ExtractionNote, ReviewVerdict
from prompts.review import build_review_prompt
from prompts.system import build_system_prompt
from services.dedup import _tokenize, _word_overlap

# Jaccard threshold above which a candidate term is considered a duplicate of
# an existing term (reuses the dedup title-similarity default).
NEW_TERM_SIMILARITY_THRESHOLD = 0.6


def _is_duplicate_term(candidate: str, existing: list[str]) -> bool:
    """True if `candidate` is an exact or near-duplicate of any `existing` term.

    Token-set Jaccard subsumes exact match (identical/reordered terms score
    1.0), so a single similarity pass is sufficient.
    """
    cand_tokens = _tokenize(candidate)
    if not cand_tokens:
        return True  # empty after tokenizing — nothing to search
    for term in existing:
        if _word_overlap(candidate, term) >= NEW_TERM_SIMILARITY_THRESHOLD:
            return True
    return False


def filter_new_terms(candidates: list[str], original_terms: list[str]) -> list[str]:
    """Keep only candidate terms that meaningfully differ from prior terms.

    Pass B: drop any candidate too similar to an original term.
    Pass C: dedupe survivors against each other (same similarity logic).
    Trims, lowercases, and drops empties along the way.
    """
    kept: list[str] = []
    for raw in candidates:
        term = raw.strip().lower()
        if not term:
            continue
        if _is_duplicate_term(term, original_terms):
            continue
        if _is_duplicate_term(term, kept):  # Pass C — against already-kept new terms
            continue
        kept.append(term)
    return kept


def review_brief(
    client: AgentClient,
    brief: Brief,
    notes: list[ExtractionNote],
    discards: list[DiscardedArticle],
    product_name: str,
    product_context: str,
    original_terms: list[str],
    iteration: int,
) -> ReviewVerdict | None:
    """Assess a brief and return a ReviewVerdict, or None on failure.

    Args:
        client: AgentClient for the LLM call (pipeline model).
        brief: The synthesized brief to review.
        notes: Extraction notes the brief was built from.
        discards: Articles dropped during dedup + grouping.
        product_name: Short product label being researched.
        product_context: Multi-line product context for the system prompt.
        original_terms: Search terms already used (for difference-filtering).
        iteration: 1-based review iteration, for the token-log step name.

    Returns:
        A reconciled ReviewVerdict, or None if the response could not be
        parsed/validated (orchestrator ships the current brief in that case).

    Raises:
        TokenBudgetExceeded: If the call would exceed the token budget.
    """
    print(f"\n🔎 Reviewer: assessing brief (iteration {iteration})...")

    system_prompt = build_system_prompt(product_name, product_context)
    user_message = build_review_prompt(
        brief=brief,
        notes=notes,
        discards=discards,
        product_name=product_name,
        original_terms=original_terms,
    )

    raw_response = client.call(
        step_name=f"review_{iteration}",
        messages=[{"role": "user", "content": user_message}],
        system=system_prompt,
        max_tokens=4000,
    )

    try:
        parsed = parse_llm_json(raw_response)
        verdict = ReviewVerdict(**parsed)
    except (ValueError, TypeError) as e:
        print(f"❌ Reviewer: failed to parse verdict — {e}")
        from pathlib import Path
        debug_dir = Path("logs/debug")
        debug_dir.mkdir(parents=True, exist_ok=True)
        (debug_dir / f"review_fail_{iteration}.txt").write_text(raw_response)
        return None

    # For coverage gaps, ensure proposed terms differ from what we've searched.
    if verdict.failure_mode == "coverage_gap":
        verdict.suggested_search_terms = filter_new_terms(
            verdict.suggested_search_terms, original_terms
        )

    print(
        f"✅ Reviewer: verdict={verdict.verdict}"
        f"{f', failure_mode={verdict.failure_mode}' if verdict.failure_mode else ''}"
        f" — {verdict.rationale[:120]}"
    )
    if verdict.failure_mode == "coverage_gap":
        print(f"   New search terms: {verdict.suggested_search_terms or '(none survived filter)'}")

    return verdict
