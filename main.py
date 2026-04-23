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

    # Initialize LLM client
    client = AgentClient(config=config, tracker=tracker)

    # Phase 1: Test call to verify foundation
    print(f"🚀 PM News Agent — Phase 1 Foundation Test")
    print(f"   Domain: {config.domain_description}")
    print(f"   Model:  {config.model}")
    print(f"   Budget: {config.token_budget:,} input tokens")
    print()

    response = client.call(
        step_name="test_call",
        system="You are a helpful assistant.",
        messages=[
            {
                "role": "user",
                "content": "Say 'Phase 1 foundation is working.' in exactly those words.",
            }
        ],
        max_tokens=50,
    )
    print(f"✅ LLM Response: {response}")

    # Save logs
    log_path = tracker.save()
    tracker.print_summary()

    # TODO Phase 2: Search + Dedup
    # TODO Phase 3: Grouping, Extraction, Synthesis
    # TODO Phase 4: Formatter, CLI, polish


if __name__ == "__main__":
    main()
