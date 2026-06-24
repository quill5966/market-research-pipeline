"""Review prompt — the agent reviewer judges a synthesized brief.

Builds the user-message body asking the LLM to assess the brief against the
product context and decide whether a corrective pass is warranted. Pairs with
the shared build_system_prompt() in prompts/system.py (which carries
product_context). The response is parsed into a ReviewVerdict.
"""

from models import Brief, DiscardedArticle, ExtractionNote


def _notes_digest(notes: list[ExtractionNote]) -> str:
    """Compact digest of the extraction notes the brief was built from.

    The reviewer compares this against the brief to decide whether a weakness
    is a coverage gap (material absent here) or a synthesis gap (material
    present here but missing/buried in the brief).
    """
    lines: list[str] = []
    for i, n in enumerate(notes, 1):
        data = "; ".join(n.data_points[:4]) if n.data_points else "—"
        gaps = "; ".join(n.pm_relevant_gaps[:3]) if n.pm_relevant_gaps else "—"
        lines.append(
            f"{i}. [{n.group_label}] {n.headline}\n"
            f"   what_happened: {n.what_happened}\n"
            f"   data_points: {data}\n"
            f"   pm_relevant_gaps: {gaps}"
        )
    return "\n".join(lines) if lines else "(no notes)"


def _discards_digest(discards: list[DiscardedArticle]) -> str:
    """One-line-per-article digest of what the pipeline dropped.

    Surfacing discards counters self-evaluation bias: the reviewer can see what
    was thrown away rather than only judging the confident-looking brief.
    """
    if not discards:
        return "(none)"
    lines = [f"- [{d.stage}] {d.title or d.url}" for d in discards]
    return "\n".join(lines)


def build_review_prompt(
    brief: Brief,
    notes: list[ExtractionNote],
    discards: list[DiscardedArticle],
    product_name: str,
    original_terms: list[str],
) -> str:
    """Build the user message for the review step.

    Args:
        brief: The synthesized brief to assess (uses its rendered markdown
               plus structured highlights/action_items).
        notes: Extraction notes the brief was synthesized from.
        discards: Articles dropped during dedup + grouping (bias check).
        product_name: Short product label being researched.
        original_terms: Search terms already used — new terms must differ.

    Returns:
        A user-message string. The response is expected to be JSON matching
        the ReviewVerdict schema.
    """
    highlights = "\n".join(
        f"{h.rank}. {h.headline} — {h.why_matters}" for h in brief.highlights
    ) or "(none)"
    action_items = "\n".join(f"{a.rank}. {a.text}" for a in brief.action_items) or "(none)"
    terms_list = ", ".join(original_terms) if original_terms else "(none)"

    return f"""You are reviewing a weekly PM brief produced for {product_name} before it is shown to the PM. Your job is to decide whether the brief is good enough to ship, and if not, to diagnose the cause and prescribe a fix. Judge it strictly against the product context in the system prompt.

Score the brief against this rubric, all anchored to the product context:
1. Coverage — are the competitors, customer segments, current bets, and product category named in the product context actually represented?
2. Relevance — do the stories matter to THIS PM, or is it generic industry noise?
3. Recency — is the material current, or stale/thin?
4. Actionability — are the action items specific and grounded (naming a product area, competitor, segment, or cohort), not generic "monitor the landscape" advice?
5. Grounding — does the brief faithfully reflect the extraction notes, with nothing important buried or misstated?

DECISION RULE — for each weakness you identify, ask:
- Is the missing/weak material ABSENT from the extraction notes? → the pipeline never found it → failure_mode = "coverage_gap" (another web search can fix it).
- Is it PRESENT in the notes but missing, buried, or misstated in the brief? → failure_mode = "synthesis_gap" (re-synthesis fixes it, no new search needed).
- If both kinds of weakness exist, prefer "coverage_gap".

VERDICT CONSTRAINT:
- If the brief is good enough, verdict = "sufficient" and failure_mode = null.
- If not, verdict = "insufficient" and failure_mode MUST be "coverage_gap" or "synthesis_gap".

IF failure_mode == "coverage_gap", populate `suggested_search_terms`:
- 2-4 short (≤60 char), lowercase, natural-language news-search queries.
- Each query must target a SPECIFIC gap you identified — name the missing competitor, event, regulation, segment, or technology.
- Do NOT repeat or paraphrase any of the original search terms already used: {terms_list}
- No quotes, boolean operators, site: filters, or dates.

IF failure_mode == "synthesis_gap", populate `resynthesis_guidance`:
- Concrete instructions for re-writing the brief from the SAME notes (e.g. "surface the Okta pricing data point in Competitor Moves; the current draft omits it").
- Do NOT suggest adding a "Watchlist", "Outlook", or "One thing to watch" section — these are intentionally excluded from this product's briefs.

EXISTING BRIEF:

Executive summary: {brief.executive_summary}

Highlights:
{highlights}

Action items:
{action_items}

Full brief markdown:
{brief.raw_markdown}

EXTRACTION NOTES THE BRIEF WAS BUILT FROM:
{_notes_digest(notes)}

ARTICLES THE PIPELINE DISCARDED (for context — do not assume these were wrongly dropped):
{_discards_digest(discards)}

Respond with JSON only — no preamble, no fences:
{{"verdict": "sufficient" | "insufficient", "failure_mode": "coverage_gap" | "synthesis_gap" | null, "rationale": "...", "gaps": ["..."], "suggested_search_terms": ["..."], "resynthesis_guidance": "..." | null}}"""
