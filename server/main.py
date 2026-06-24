"""PM News Agent — Pipeline Orchestrator

Orchestrates the full market research pipeline:
1. Load config
2. Initialize tracking and LLM client
3. Search + Dedup (Phase 2)
4. Grouping, Extraction, Synthesis (Phase 3)
5. Agent review + bounded corrective re-search / re-synthesis (Phase 4)
6. Write output
"""

import re
import time
from datetime import datetime
from pathlib import Path

from config import RunConfig
from tracking.token_tracker import TokenTracker
from tracking.discard_log import write_discard_log
from tracking.review_log import ReviewEntry, write_review_log
from agent.client import AgentClient, TokenBudgetExceeded
from agent.grouper import group_results
from agent.extractor import extract_articles
from agent.synthesizer import synthesize_brief
from agent.reviewer import review_brief
from services.search import search
from services.dedup import deduplicate, _normalize_url, _word_overlap
from models import DiscardedArticle, ExtractionNote, GroupingResult, Run, SearchResult
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

    After the first synthesis, an agent reviewer judges the brief against the
    product context. On an "insufficient" verdict it triggers a bounded
    corrective pass — a coverage-gap re-search (synthesizing on the deduped
    union of prior + new results) or a synthesis-gap rewrite — capped at
    config.max_review_iterations passes, each granted a freshly replenished
    token budget.

    Args:
        run: The Run object to update (shared with API handler).
        config: Per-run configuration (server config + user request merged).
    """
    try:
        run.status = "running"
        pipeline_run_id = generate_run_id(config.product_name)
        log_run_id = f"{pipeline_run_id}_pipelinerun"
        run_date = datetime.now().strftime("%Y-%m-%d")
        original_budget = config.token_budget

        # Initialize tracking + LLM client
        tracker = TokenTracker(
            run_id=log_run_id,
            domain=config.product_name,
            model=config.model,
            token_budget=config.token_budget,
            log_dir=config.log_dir,
        )
        client = AgentClient(config.anthropic_api_key, config.model, tracker)

        # --- Accumulators shared across the initial pass and corrective passes ---
        accumulated_results: list[SearchResult] = []     # deduped kept set (grows on re-search)
        notes_by_url: dict[str, ExtractionNote] = {}      # extraction cache, keyed by source_url
        all_terms: list[str] = list(config.search_terms)  # every term searched so far
        all_dedup_discards: list[DiscardedArticle] = []   # dedup discards across all searches
        current_notes: list[ExtractionNote] = []          # notes feeding the current synthesis
        current_grouping: GroupingResult | None = None     # latest grouping (for discards/counts)
        review_entries: list[ReviewEntry] = []

        def _round_suffix(rnd: int) -> str:
            return f" · round {rnd}" if rnd > 1 else ""

        # --- Stage 1+2: Search + Dedup, merging new results into the kept set ---
        def search_and_dedup(terms: list[str] | None, rnd: int) -> int:
            """Search the given terms, dedup, merge new survivors into the kept
            set, and return the count of genuinely new articles added."""
            t0 = time.time()
            _update_stage(run, "search", "active", f"Searching...{_round_suffix(rnd)}")
            raw = search(config, terms=terms)
            _update_stage(
                run, "search", "done",
                f"{len(raw)} results across {len(terms or config.search_terms)} terms · "
                f"Tavily advanced{_round_suffix(rnd)}",
                t0,
            )

            t0 = time.time()
            _update_stage(run, "dedup", "active", f"Deduplicating...{_round_suffix(rnd)}")
            deduped, stats = deduplicate(
                raw,
                title_threshold=config.dedup_title_similarity,
                snippet_threshold=config.dedup_snippet_similarity,
            )
            all_dedup_discards.extend(stats.discarded)

            # Cross-iteration filter: drop any new article already represented in
            # the kept set (by normalized URL or snippet similarity) so we don't
            # re-extract or re-pay for content we already have.
            seen_urls = {_normalize_url(r.url) for r in accumulated_results}
            survivors: list[SearchResult] = []
            for r in deduped:
                norm = _normalize_url(r.url)
                if norm in seen_urls:
                    continue
                if any(
                    _word_overlap(r.snippet, k.snippet) >= config.dedup_snippet_similarity
                    for k in accumulated_results
                ):
                    continue
                survivors.append(r)
                seen_urls.add(norm)

            accumulated_results.extend(survivors)
            _update_stage(
                run, "dedup", "done",
                f"{stats.raw_count} → {len(accumulated_results)} unique articles"
                f" · {len(survivors)} new{_round_suffix(rnd)}",
                t0,
            )
            return len(survivors)

        # --- Stage 3+4: Group + Extract (extraction cache reuses prior notes) ---
        def group_and_extract(rnd: int) -> bool:
            """Re-group the full kept set and extract only uncached articles.

            Updates current_grouping and current_notes. Returns False if no
            notes are available to synthesize.
            """
            nonlocal current_grouping, current_notes

            t0 = time.time()
            _update_stage(run, "group", "active", f"Grouping by story...{_round_suffix(rnd)}")
            grouping = group_results(
                client, accumulated_results, config.product_name, config.product_context
            )
            current_grouping = grouping
            _update_stage(
                run, "group", "done",
                f"{len(grouping.groups)} distinct stories identified{_round_suffix(rnd)}",
                t0,
            )

            # Extract only the groups whose selected source we haven't seen yet.
            uncached = [g for g in grouping.groups if g.selected_url not in notes_by_url]
            t0 = time.time()
            cached_n = len(grouping.groups) - len(uncached)
            _update_stage(
                run, "extract", "active",
                f"Extracting notes... ({cached_n} reused){_round_suffix(rnd)}",
            )

            if uncached:
                def on_extract_progress(completed: int, total: int):
                    _update_stage(
                        run, "extract", "active",
                        f"{completed} of {total} new articles analyzed · "
                        f"{cached_n} reused{_round_suffix(rnd)}",
                    )

                new_notes = extract_articles(
                    client,
                    GroupingResult(groups=uncached, discarded=[]),
                    accumulated_results,
                    config.product_name,
                    config.product_context,
                    progress_callback=on_extract_progress,
                )
                for n in new_notes:
                    notes_by_url[n.source_url] = n

            # Assemble the notes feeding synthesis, in current grouping order —
            # the deduped union of prior kept notes + newly extracted ones.
            current_notes = [
                notes_by_url[g.selected_url]
                for g in grouping.groups
                if g.selected_url in notes_by_url
            ]
            _update_stage(
                run, "extract", "done",
                f"{len(current_notes)} notes ({cached_n} reused){_round_suffix(rnd)}",
                t0,
            )
            return bool(current_notes)

        # --- Stage 5: Synthesis (+ finalize the Brief) ---
        def run_synthesis(rnd: int, resynthesis_guidance: str | None = None) -> bool:
            """Synthesize current_notes into a Brief and finalize it on the Run.

            Returns True on success, False on empty/unparseable output.
            """
            t0 = time.time()
            detail = (
                f"Re-synthesizing...{_round_suffix(rnd)}"
                if resynthesis_guidance else f"Generating brief...{_round_suffix(rnd)}"
            )
            _update_stage(run, "synthesize", "active", detail)

            brief = synthesize_brief(
                client, current_notes, config.product_name, config.product_context,
                run_date, resynthesis_guidance=resynthesis_guidance,
            )
            if not brief:
                _update_stage(run, "synthesize", "failed", "Empty or unparseable output")
                return False

            # Deterministic fields override LLM-supplied counts.
            brief.title = config.product_name
            brief.date = run_date
            brief.source_count = len({sr.source_domain for sr in accumulated_results})
            brief.story_count = sum(len(s.stories) for s in brief.sections)
            brief.search_term_count = len(all_terms)
            brief.raw_markdown = render_brief_markdown(brief)

            output_path = Path(config.output_dir) / f"{pipeline_run_id}.md"
            output_path.write_text(brief.raw_markdown)
            run.brief = brief

            _update_stage(
                run, "synthesize", "done",
                f"Brief generated · {len(brief.sections)} sections · "
                f"{brief.story_count} stories{_round_suffix(rnd)}",
                t0,
            )
            return True

        # ============================ Initial pass ============================
        search_and_dedup(terms=None, rnd=1)

        if not group_and_extract(rnd=1):
            run.error = "No extraction notes produced — cannot synthesize brief."
            run.status = "failed"
            _update_stage(run, "extract", "failed", "No notes extracted")
            _update_stage(run, "synthesize", "failed", "Skipped — no extraction notes")
            _write_logs(tracker, log_run_id, all_dedup_discards,
                        current_grouping, review_entries, config.log_dir)
            return

        if not run_synthesis(rnd=1):
            run.error = "Synthesizer produced empty or unparseable output."
            run.status = "failed"
            _write_logs(tracker, log_run_id, all_dedup_discards,
                        current_grouping, review_entries, config.log_dir)
            return

        # ===================== Agent review + corrective loop =====================
        if config.max_review_iterations == 0:
            _update_stage(run, "review", "done", "Agent review disabled")
        else:
            t_review = time.time()
            for iteration in range(1, config.max_review_iterations + 1):
                # Each corrective pass (and the review call itself) gets a fresh
                # full budget so the loop never terminates on overrun. Usage and
                # cost keep accumulating into the same log.
                tracker.replenish_budget(original_budget)

                _update_stage(
                    run, "review", "active",
                    f"Agent assessing brief (round {iteration})...",
                )
                discards_for_review = all_dedup_discards + (
                    current_grouping.discarded if current_grouping else []
                )
                verdict = review_brief(
                    client, run.brief, current_notes, discards_for_review,
                    config.product_name, config.product_context, all_terms, iteration,
                )

                # No verdict, or judged sufficient → ship the current brief.
                if verdict is None or verdict.verdict == "sufficient":
                    reason = "sufficient" if verdict else "unparseable_verdict"
                    review_entries.append(
                        ReviewEntry(iteration, verdict, action="ship", termination_reason=reason)
                    )
                    _update_stage(run, "review", "done", "Brief approved by agent reviewer", t_review)
                    break

                rnd = iteration + 1

                if verdict.failure_mode == "synthesis_gap":
                    review_entries.append(
                        ReviewEntry(iteration, verdict, action="synthesis_gap_rewrite")
                    )
                    run.review_iterations = iteration
                    _update_stage(
                        run, "review", "active",
                        f"Insufficient — re-synthesizing (round {rnd})",
                    )
                    if not run_synthesis(rnd, resynthesis_guidance=verdict.resynthesis_guidance):
                        break  # keep the prior brief on synth failure; stop looping
                    continue  # re-review the rewritten brief if iterations remain

                # coverage_gap
                new_terms = verdict.suggested_search_terms
                if not new_terms:
                    review_entries.append(
                        ReviewEntry(iteration, verdict, action="ship",
                                    termination_reason="no_new_terms")
                    )
                    _update_stage(
                        run, "review", "done",
                        "Agent found gaps but no usable new search terms; shipping current brief",
                        t_review,
                    )
                    break

                run.review_iterations = iteration
                _update_stage(
                    run, "review", "active",
                    f"Insufficient — re-searching {len(new_terms)} new terms (round {rnd})",
                )
                new_count = search_and_dedup(terms=new_terms, rnd=rnd)
                all_terms.extend(new_terms)

                if new_count == 0:
                    review_entries.append(
                        ReviewEntry(iteration, verdict, action="ship", new_terms=new_terms,
                                    new_articles=0, termination_reason="no_new_articles")
                    )
                    _update_stage(
                        run, "review", "done",
                        "Re-search found no new articles; shipping current brief",
                        t_review,
                    )
                    break

                review_entries.append(
                    ReviewEntry(iteration, verdict, action="coverage_gap_research",
                                new_terms=new_terms, new_articles=new_count)
                )
                if not group_and_extract(rnd):
                    break
                if not run_synthesis(rnd):
                    break
                # Loop continues to re-review if iterations remain.
            else:
                # Loop ran to completion without an early ship → hit the cap.
                _update_stage(run, "review", "done", "Max review iterations reached", t_review)

        run.status = "complete"

        _write_logs(tracker, log_run_id, all_dedup_discards,
                    current_grouping, review_entries, config.log_dir)

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

    except Exception:
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


def _write_logs(
    tracker: TokenTracker,
    log_run_id: str,
    dedup_discards: list[DiscardedArticle],
    grouping: GroupingResult | None,
    review_entries: list[ReviewEntry],
    log_dir: str,
) -> None:
    """Persist the token usage, discard, and review logs at the end of a run."""
    grouping_discards = grouping.discarded if grouping else []
    write_discard_log(
        pipeline_run_id=log_run_id,
        discards=dedup_discards + grouping_discards,
        log_dir=log_dir,
    )
    write_review_log(
        pipeline_run_id=log_run_id,
        entries=review_entries,
        log_dir=log_dir,
    )
    tracker.save()
    tracker.print_summary()
