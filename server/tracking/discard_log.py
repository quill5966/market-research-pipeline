"""Discard logging — writes a JSON record of every article dropped
during dedup or grouping to logs/{pipeline_run_id}.discards.json.

Sibling to the token usage log; separate file so the two have
independent consumers and sizes.
"""

import json
from datetime import datetime
from pathlib import Path

from models import DiscardedArticle


STAGES = (
    "dedup_url",
    "dedup_title",
    "dedup_snippet",
    "group_no_content",
    "group_llm_irrelevant",
)


def write_discard_log(
    pipeline_run_id: str,
    discards: list[DiscardedArticle],
    log_dir: str,
) -> str:
    """Write the discard log for a pipeline run.

    Args:
        pipeline_run_id: Pipeline run identifier (matches token log).
        discards: All articles dropped across dedup + grouping stages.
        log_dir: Directory to write the log to.

    Returns:
        Path to the written file.
    """
    bucketed: dict[str, list[dict]] = {stage: [] for stage in STAGES}
    for d in discards:
        bucketed.setdefault(d.stage, []).append(d.model_dump())

    payload = {
        "run_id": pipeline_run_id,
        "written_at": datetime.now().isoformat(),
        "totals": {stage: len(items) for stage, items in bucketed.items()},
        "total_discarded": len(discards),
        "discards": bucketed,
    }

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    out_file = log_path / f"{pipeline_run_id}.discards.json"
    out_file.write_text(json.dumps(payload, indent=2, default=str))
    return str(out_file)
