"""Search-term suggestion prompt.

Builds the user-message body asking the LLM to generate 4-5 short web-search
queries from the product name + product context. Pairs with the shared
build_system_prompt() in prompts/system.py.
"""


def build_search_terms_prompt(product_name: str, product_context: str) -> str:
    """Build the user-message body for the search-term suggestion call.

    The response is expected to be JSON of the shape:
        {"suggested_terms": ["term one", "term two", ...]}

    Args:
        product_name: Short product/company label (e.g., "Acme DB").
        product_context: Multi-line product context block.

    Returns:
        A user-message string.
    """
    return f"""Generate 4-5 web-search queries that a PM at {product_name} should run weekly to stay informed about their market and competitive landscape.

Product context:
{product_context}

Requirements for each query:
- 60 characters or fewer.
- Natural-language search phrase — no quotes, no boolean operators, no site: filters.
- Lowercase.
- Suitable for a news search engine (Tavily) returning recent articles.

Coverage to aim for across the 4-5 queries:
- At least one query naming product category or technology mentioned in the product context.
- At least one query naming top competitor(s) in the product context.
- At least one broader market/trend query (e.g., the buyer's industry, regulatory shifts, customer behavior changes).
- Avoid generic queries like "tech news" or "{product_name} news" — they are too broad to be useful.
- Avoid duplicates and near-duplicates.
- Do not add day, month, year into the search term. 

Respond with JSON only — no preamble, no fences:
{{"suggested_terms": ["...", "...", "...", "...", "..."]}}"""
