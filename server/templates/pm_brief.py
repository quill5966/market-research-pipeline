"""PM Brief JSON schema + markdown renderer.

The synthesizer emits a structured `Brief` JSON object (the schema below
is injected into its prompt). `render_brief_markdown()` walks that
structured object to produce the markdown export served by
GET /api/runs/:id/export.

Format philosophy: optimized for scanning. A reader should be able to
skim the top in under a minute, read any TL;DR in ~10 seconds, and
finish the whole brief in 5–10 minutes. Word caps are soft targets;
readability beats hitting the cap exactly. Never abbreviate words to
fit a cap — cut a clause or rewrite the sentence instead.
"""

from models import Brief

BRIEF_JSON_SCHEMA = """{
  "title": "string — the domain description (becomes the brief title)",
  "date": "YYYY-MM-DD — the run date",
  "source_count": "int — number of unique source domains across all sections",
  "story_count": "int — number of stories across all list-type sections",
  "search_term_count": "int — number of search terms in this run",
  "raw_markdown": "string — leave as empty string; the server renders this",
  "highlights": [
    {
      "rank": "int 1-3",
      "headline": "string — ≤10 words naming the actor + the move",
      "why_matters": "string — ≤12 words on consequence for the PM",
      "pointer_section": "string — exact title of the section this is detailed in"
    }
  ],
  "executive_summary": "string — exactly two sentences, ≤60 words total. Sentence 1 names the dominant theme. Sentence 2 states its consequence for a PM. No semicolons or embedded lists.",
  "sections": [
    {
      "type": "list | summary | callout | quote",
      "title": "string — section heading (e.g., 'Competitor Moves', 'Market & Macro', 'Customer & Buyer Signals', 'Technology & Ecosystem')",
      "content_md": "string OR null — markdown prose for type=summary/callout/quote, or an optional lede for type=list. Null if not used.",
      "stories": [
        {
          "id": "string — stable hash/slug derived from source_url",
          "headline": "string — ≤10 words: actor + move",
          "tldr": "string — ≤25 words. What happened, with the single most important number/date/entity.",
          "pm_angle": "string — ≤20 words. Implication for positioning, roadmap, or stance.",
          "supporting": "string OR null — optional ≤80-word paragraph ONLY when a non-obvious mechanism, quote, or detail materially changes the TL;DR.",
          "source_domain": "string — e.g., 'reuters.com'",
          "source_url": "string — full URL",
          "additional_coverage": ["other source domains covering the same story"],
          "filter_tags": ["tags copied from the extraction note(s) that informed this story"]
        }
      ],
      "source_urls": ["all source URLs cited in this section"]
    }
  ],
  "action_items": [
    {
      "rank": "int starting at 1",
      "text": "string — one imperative sentence ≤20 words",
      "pointer_section": "string — exact title of the triggering section",
      "pointer_story_id": "string OR null — the triggering story id if applicable"
    }
  ],
  "sources": [
    {
      "domain": "string",
      "url": "string",
      "referenced_in": ["section titles where this URL appears"]
    }
  ]
}"""


SECTION_GUIDANCE = """Section types and when to use each:

- `list`: a cluster of 1–N stories surfaced as discrete entries. The workhorse for Competitor Moves, Market & Macro, Customer & Buyer Signals, Technology & Ecosystem, or any other thematic cluster. Each story has headline / TL;DR / PM angle / optional supporting / filter_tags. Use this whenever the material justifies discrete cards.
- `summary`: a short prose paragraph (≤80 words) that frames a mid-brief transition between thematic clusters. Use sparingly.
- `callout`: a set-apart attention block (1–3 sentences). Use only for a single high-importance insight that punches above neighboring list entries.
- `quote`: a single pull quote with attribution on its own line (format: `"…" — Name, Title (source.com)`). Use only when one quote frames the period better than any TL;DR.

Section order is reading order — put the highest-impact section first. Omit any section type you have no material for. Do NOT add forward-looking "Outlook", "One thing to watch", or "Watchlist" sections — the brief should end with its last thematic cluster.
"""


def _render_story_md(story) -> str:
    """Render a single Story as markdown."""
    lines = [f"### {story.headline}"]
    lines.append(f"**TL;DR:** {story.tldr}")
    lines.append(f"**PM angle:** {story.pm_angle}")
    if story.supporting:
        lines.append("")
        lines.append(story.supporting)
    lines.append("")
    coverage = ""
    if story.additional_coverage:
        coverage = f" · also: {', '.join(story.additional_coverage)}"
    lines.append(f"*Source: {story.source_domain} — {story.source_url}{coverage}*")
    if story.filter_tags:
        lines.append(f"*Tags: {', '.join(story.filter_tags)}*")
    return "\n".join(lines)


def render_brief_markdown(brief: Brief) -> str:
    """Render the structured Brief as markdown for export."""
    parts: list[str] = []

    # Header
    parts.append(f"# {brief.title}")
    parts.append(f"*{brief.date} · {brief.story_count} stories · {brief.source_count} sources · {brief.search_term_count} search terms*")
    parts.append("")

    # Highlights
    if brief.highlights:
        parts.append("## Top Highlights")
        for h in sorted(brief.highlights, key=lambda x: x.rank):
            parts.append(f"{h.rank}. **{h.headline}** — {h.why_matters} → see {h.pointer_section}")
        parts.append("")

    # Executive summary
    if brief.executive_summary:
        parts.append("## Executive Summary")
        parts.append(f"> {brief.executive_summary}")
        parts.append("")

    # Sections
    for section in brief.sections:
        parts.append(f"## {section.title}")
        if section.content_md:
            parts.append(section.content_md)
            parts.append("")
        if section.type == "list":
            for story in section.stories:
                parts.append(_render_story_md(story))
                parts.append("")
        # summary/callout/quote already rendered via content_md above
        parts.append("")

    # Action items
    if brief.action_items:
        parts.append("## Ideas for PM Next Steps")
        for item in sorted(brief.action_items, key=lambda x: x.rank):
            parts.append(f"{item.rank}. {item.text} ({item.pointer_section})")
        parts.append("")

    # Sources
    if brief.sources:
        parts.append("## Sources")
        for src in brief.sources:
            refs = f" — {', '.join(src.referenced_in)}" if src.referenced_in else ""
            parts.append(f"- [{src.domain}]({src.url}){refs}")
        parts.append("")

    return "\n".join(parts).rstrip() + "\n"
