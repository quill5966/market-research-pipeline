"""PM News Agent — Pipeline Orchestrator

Orchestrates the full market research pipeline:
1. Load config
2. Initialize tracking and LLM client
3. Search + Dedup (Phase 2)
4. Grouping, Extraction, Synthesis (Phase 3)
5. Write output
"""

import re
import time
from datetime import datetime
from pathlib import Path

from config import RunConfig
from tracking.token_tracker import TokenTracker
from tracking.discard_log import write_discard_log
from agent.client import AgentClient, TokenBudgetExceeded
from agent.grouper import group_results
from agent.extractor import extract_articles
from agent.synthesizer import synthesize_brief
from services.search import search
from services.dedup import deduplicate
from models import Run, Stage
from templates.pm_brief import render_brief_markdown


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


def _update_stage(
    run: Run, stage_name: str, status: str, detail: str, start_time: float | None = None
) -> None:
    """Update a stage's status and detail in the Run object.

    Since the Run object is shared with the API handler (in-memory dict),
    GET requests reflect live progress.
    """
    for stage in run.stages:
        if stage.name == stage_name:
            stage.status = status
            stage.detail = detail
            if start_time is not None and status == "done":
                stage.elapsed_ms = int((time.time() - start_time) * 1000)
            break


def execute_pipeline(run: Run, config: RunConfig) -> None:
    """Run the full pipeline, updating run.stages in-place for progress.

    This function is designed to be called in a background thread.
    It mutates the Run object directly so the polling endpoint
    reflects live stage progress.

    Args:
        run: The Run object to update (shared with API handler).
        config: Per-run configuration (server config + user request merged).
    """
    try:
        run.status = "running"
        pipeline_run_id = generate_run_id(config.product_name)
        log_run_id = f"{pipeline_run_id}_pipelinerun"

        # Initialize tracking
        tracker = TokenTracker(
            run_id=log_run_id,
            domain=config.product_name,
            model=config.model,
            token_budget=config.token_budget,
            log_dir=config.log_dir,
        )

        # Initialize LLM client
        client = AgentClient(config.anthropic_api_key, config.model, tracker)

        # --- Stage 1: Search ---
        t0 = time.time()
        _update_stage(run, "search", "active", "Searching...")
        raw_results = search(config)
        _update_stage(
            run, "search", "done",
            f"{len(raw_results)} results across {len(config.search_terms)} terms · Tavily advanced",
            t0,
        )

        # --- Stage 2: Dedup ---
        t0 = time.time()
        _update_stage(run, "dedup", "active", "Deduplicating...")
        deduped, stats = deduplicate(
            raw_results,
            title_threshold=config.dedup_title_similarity,
            snippet_threshold=config.dedup_snippet_similarity,
        )
        _update_stage(
            run, "dedup", "done",
            f"{stats.raw_count} → {len(deduped)} unique articles · {stats.removed_total} removed",
            t0,
        )

        # --- Stage 3: Group ---
        t0 = time.time()
        _update_stage(run, "group", "active", "Grouping by story...")
        grouping_result = group_results(client, deduped, config.product_name, config.product_context)
        _update_stage(
            run, "group", "done",
            f"{len(grouping_result.groups)} distinct stories identified",
            t0,
        )

        # Persist discard log (dedup + grouping) for post-hoc review.
        write_discard_log(
            pipeline_run_id=log_run_id,
            discards=stats.discarded + grouping_result.discarded,
            log_dir=config.log_dir,
        )

        # --- Stage 4: Extract ---
        t0 = time.time()
        _update_stage(run, "extract", "active", "Extracting notes...")

        # Use a progress callback to update the stage detail
        def on_extract_progress(completed: int, total: int):
            _update_stage(
                run, "extract", "active",
                f"{completed} of {total} articles analyzed · running",
            )

        notes = extract_articles(
            client, grouping_result, deduped, config.product_name, config.product_context,
            progress_callback=on_extract_progress,
        )
        _update_stage(
            run, "extract", "done",
            f"{len(notes)} notes extracted",
            t0,
        )

        if not notes:
            run.error = "No extraction notes produced — cannot synthesize brief."
            run.status = "failed"
            _update_stage(run, "synthesize", "failed", "Skipped — no extraction notes")
            tracker.save()
            return

        # --- Stage 5: Synthesize ---
        t0 = time.time()
        _update_stage(run, "synthesize", "active", "Generating brief...")
        run_date = datetime.now().strftime("%Y-%m-%d")

        brief = synthesize_brief(client, notes, config.product_name, config.product_context, run_date)

        if brief:
            # Override LLM-supplied counts with deterministic values
            brief.title = config.product_name
            brief.date = run_date
            brief.source_count = len({sr.source_domain for sr in deduped})
            brief.story_count = sum(len(s.stories) for s in brief.sections)
            brief.search_term_count = len(config.search_terms)

            # Render markdown server-side from the structured brief
            brief.raw_markdown = render_brief_markdown(brief)

            # Write markdown export to output/
            output_path = Path(config.output_dir) / f"{pipeline_run_id}.md"
            output_path.write_text(brief.raw_markdown)

            run.brief = brief

            _update_stage(
                run, "synthesize", "done",
                f"Brief generated · {len(brief.sections)} sections · {brief.story_count} stories",
                t0,
            )
            run.status = "complete"
        else:
            run.error = "Synthesizer produced empty or unparseable output."
            run.status = "failed"
            _update_stage(run, "synthesize", "failed", "Empty or unparseable output")

        # Save token usage log
        tracker.save()
        tracker.print_summary()

    except TokenBudgetExceeded as e:
        # Budget messages are safe — they describe an expected operational
        # limit, not server internals.
        run.error = str(e)
        run.status = "failed"
        for stage in run.stages:
            if stage.status == "active":
                stage.status = "failed"
                stage.detail = "Token budget exceeded"
                break

    except Exception as e:
        # Log the real traceback server-side; show a generic message to the
        # client so library internals / file paths / API response bodies don't
        # leak through the API.
        import logging
        logging.exception("Pipeline run %s failed", run.id)
        run.error = "Pipeline run failed. Check server logs for details."
        run.status = "failed"
        for stage in run.stages:
            if stage.status == "active":
                stage.status = "failed"
                stage.detail = "Internal error"
                break
