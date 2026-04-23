"""PM News Agent — Pipeline Orchestrator

Orchestrates the full market research pipeline:
1. Load config
2. Initialize tracking and LLM client
3. Search + Dedup (Phase 2)
4. Grouping, Extraction, Synthesis (Phase 3)
5. Format output (Phase 4)
"""

import re
from datetime import datetime

from config import load_config
from tracking.token_tracker import TokenTracker
from agent.client import AgentClient
from services.search import search
from services.dedup import deduplicate


def generate_run_id(domain: str) -> str:
    """Generate a unique run ID from timestamp + sanitized domain.

    Format: {ISO timestamp}_{sanitized domain}
    Example: 2026-04-22T19-30-00_identity-mgmt

    The second-precision timestamp guarantees uniqueness across
    multiple manual runs with the same domain/terms.
    """
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    sanitized = re.sub(r"[^a-z0-9-]", "", domain.lower().replace(" ", "-"))[:30]
    return f"{timestamp}_{sanitized}"


def main():
    # Load config
    config = load_config()

    # Initialize tracking
    run_id = generate_run_id(config.domain_description)
    tracker = TokenTracker(
        run_id=run_id,
        domain=config.domain_description,
        model=config.model,
        token_budget=config.token_budget,
        log_dir=config.log_dir,
    )

    # Initialize LLM client (used in Phase 3)
    client = AgentClient(config=config, tracker=tracker)

    print(f"🚀 PM News Agent — Run: {run_id}")
    print(f"   Domain: {config.domain_description}")
    print(f"   Search terms: {', '.join(config.search_terms)}")
    print(f"   Model:  {config.model}")
    print(f"   Budget: {config.token_budget:,} input tokens")
    print()

    # --- Phase 2: Search & Dedup ---
    raw_results = search(config)
    print()

    deduped, stats = deduplicate(
        raw_results,
        title_threshold=config.dedup_title_similarity,
        snippet_threshold=config.dedup_snippet_similarity,
    )

    # Show deduped results summary
    print(f"\n📊 Final: {len(deduped)} articles ready for processing")
    content_count = sum(1 for r in deduped if r.raw_content)
    print(f"   {content_count} with full article content, {len(deduped) - content_count} snippet-only")

    for i, r in enumerate(deduped, 1):
        content_status = "✅" if r.raw_content else "⚠️ no content"
        print(f"   {i:2d}. [{r.source_domain}] {r.title[:70]} ({content_status})")

    # TODO Phase 3: Grouping, Extraction, Synthesis
    # TODO Phase 4: Formatter, CLI, polish

    # Save logs
    log_path = tracker.save()
    tracker.print_summary()


if __name__ == "__main__":
    main()

