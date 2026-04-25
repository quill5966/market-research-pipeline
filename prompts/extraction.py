"""Prompt builder for the extraction step.

Formats a single article's full text into a user message that asks
the LLM to extract structured information with thematic classification.
"""


def build_extraction_prompt(
    article_text: str,
    title: str,
    source: str,
    url: str,
    domain_description: str,
    group_label: str,
) -> str:
    """Build the user message for a single article extraction.

    Args:
        article_text: Full article text (raw_content from SearchResult).
        title: Article title.
        source: Source domain (e.g., "reuters.com").
        url: Article URL.
        domain_description: The product domain being researched.
        group_label: Story group label from the grouping step.

    Returns:
        A formatted user message string.
    """
    return f"""Extract structured information from the following article. This article was grouped under the story: "{group_label}"

ARTICLE METADATA:
- Title: {title}
- Source: {source}
- URL: {url}

ARTICLE TEXT:
{article_text}

---

Extract the following from this article. Preserve specific numbers, dates, quotes, and named entities. Do not generalize or interpret — report what the article says.

CORE EXTRACTION:
- headline: A factual, concise headline
- source: The source domain
- source_url: The article URL
- date: Publication date if mentioned (null if not found)
- author: Author name if mentioned (null if not found)
- what_happened: 3-5 sentences covering the core facts
- data_points: List all specific numbers, percentages, dollar amounts, dates, timelines mentioned (even if they seem minor)
- quotes: Any notable direct quotes from named individuals (preserve exact wording and attribute by name and title)
- companies_and_products: List of companies and products mentioned, with context for each (what role they play in the story, whether they are a competitor, partner, customer, or ecosystem player in the {domain_description} space)

THEMATIC CLASSIFICATION:
Which of the following categories does this article inform? Select all that apply and provide category-specific details for each:

- competitor_moves: if yes, extract product/feature names, pricing, availability dates, target market segment, and how this changes the competitor's positioning relative to {domain_description}
- market_macro: if yes, extract the specific trend or force, any quantitative evidence (market size, growth rates, funding amounts), and the time horizon (is this happening now or projected)
- customer_buyer: if yes, extract buyer segment, evaluation criteria mentioned, adoption numbers, named customers, and any stated reasons for choosing or leaving a vendor
- technology_ecosystem: if yes, extract the specific technology, standard, or platform change, which players are involved, and the expected timeline for impact
- watchlist: if the article contains early signals, unconfirmed reports, or tangential-but-notable information that doesn't clearly fit the above categories

PM-RELEVANT GAPS:
What questions would a PM in {domain_description} want answered that this article does not address? Focus on gaps that affect competitive positioning, roadmap decisions, or market understanding.

Respond with a JSON object matching this schema:
{{
  "headline": "...",
  "source": "{source}",
  "source_url": "{url}",
  "date": "YYYY-MM-DD or null",
  "author": "Name or null",
  "what_happened": "3-5 sentences...",
  "data_points": ["point 1", "point 2"],
  "quotes": ["'Quote text' — Speaker Name, Title"],
  "companies_and_products": ["Company X (competitor, launched new feature Y)"],
  "thematic_tags": [
    {{"category": "competitor_moves", "details": "..."}},
    {{"category": "market_macro", "details": "..."}}
  ],
  "pm_relevant_gaps": ["gap 1", "gap 2"],
  "group_label": "{group_label}"
}}"""
