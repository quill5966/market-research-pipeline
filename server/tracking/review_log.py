"""Review logging — writes a JSON record of every agent-reviewer verdict and
the corrective action it triggered to logs/{pipeline_run_id}.review.json.

Sibling to the token usage and discard logs; separate file so the review trail
(verdict, rationale, new terms, survivor counts, termination reason) is
auditable on its own and the rubric can be tuned post-hoc.
"""

import json
from datetime import datetime
from pathlib import Path

from models import ReviewVerdict


class ReviewEntry:
    """One review iteration: the verdict plus what the orchestrator did with it."""

    def __init__(
        self,
        iteration: int,
        verdict: ReviewVerdict | None,
        action: str,
        new_terms: list[str] | None = None,
        new_articles: int | None = None,
        termination_reason: str | None = None,
    ):
        self.iteration = iteration
        self.verdict = verdict
        self.action = action  # e.g. "ship", "coverage_gap_research", "synthesis_gap_rewrite"
        self.new_terms = new_terms or []
        self.new_articles = new_articles
        self.termination_reason = termination_reason

    def to_dict(self) -> dict:
        return {
            "iteration": self.iteration,
            "verdict": self.verdict.model_dump() if self.verdict else None,
            "action": self.action,
            "new_terms": self.new_terms,
            "new_articles": self.new_articles,
            "termination_reason": self.termination_reason,
        }


def write_review_log(
    pipeline_run_id: str,
    entries: list[ReviewEntry],
    log_dir: str,
) -> str | None:
    """Write the review log for a pipeline run.

    Args:
        pipeline_run_id: Pipeline run identifier (matches token log naming).
        entries: One ReviewEntry per review iteration.
        log_dir: Directory to write the log to.

    Returns:
        Path to the written file, or None if there were no review iterations.
    """
    if not entries:
        return None

    payload = {
        "run_id": pipeline_run_id,
        "written_at": datetime.now().isoformat(),
        "review_iterations": len(entries),
        "entries": [e.to_dict() for e in entries],
    }

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    out_file = log_path / f"{pipeline_run_id}.review.json"
    out_file.write_text(json.dumps(payload, indent=2, default=str))
    return str(out_file)
