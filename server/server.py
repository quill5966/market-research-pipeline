"""Market Research Pipeline — FastAPI Server

Serves the API for the market research web application.
Run with: uvicorn server:app --reload --port 8000
"""

import hmac
import os
import threading
from datetime import datetime, timezone
from threading import Thread
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from config import build_run_config, load_server_config
from main import execute_pipeline
from models import Brief, Run, RunRequest, Stage

# Load server config at startup
server_config = load_server_config()

app = FastAPI(title="Market Research Pipeline")

allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

# Refuse wildcard origins together with credentials — that combination is
# either rejected by browsers or, worse, accepted permissively by misconfigured
# proxies. Force the operator to enumerate origins explicitly.
if "*" in allowed_origins:
    raise ValueError(
        "ALLOWED_ORIGINS cannot contain '*' — list each origin explicitly "
        "(e.g. 'https://app.example.com,https://staging.example.com')."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# In-memory run store
runs: dict[str, Run] = {}

# Concurrency gate for the pipeline. Counts only currently-running pipelines,
# not historical ones, so the runs dict can grow without throttling new submits.
_run_slots = threading.Semaphore(server_config.max_concurrent_runs)

# Default pipeline stages
STAGE_NAMES = ["search", "dedup", "group", "extract", "synthesize"]


def _make_stages() -> list[Stage]:
    """Create fresh pipeline stages, all in 'pending' status."""
    return [Stage(name=name) for name in STAGE_NAMES]


def require_passcode(request: Request) -> None:
    """Reject any request that doesn't carry the shared passcode.

    Accepts the passcode via `Authorization: Bearer <passcode>`. Uses a
    constant-time compare so a timing attacker can't byte-grind the secret.
    """
    auth = request.headers.get("authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not hmac.compare_digest(token, server_config.app_passcode):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid passcode",
            headers={"WWW-Authenticate": "Bearer"},
        )


@app.get("/api/health")
def health_check():
    """Public health check (used by Render). No auth — exposes no run data."""
    return {"status": "ok"}


@app.post("/api/auth/check")
def auth_check(_: None = Depends(require_passcode)) -> dict:
    """Validate the supplied passcode without performing any side effects.

    Used by the client's passcode gate before storing the value in
    sessionStorage. Returns 200 on success, 401 on failure.
    """
    return {"ok": True}


def _run_pipeline_with_slot(run: Run, run_config) -> None:
    """Wrap execute_pipeline so the semaphore is always released."""
    try:
        execute_pipeline(run, run_config)
    finally:
        _run_slots.release()


@app.post("/api/runs")
def create_run(request: RunRequest, _: None = Depends(require_passcode)) -> dict:
    """Start a new pipeline run.

    Accepts per-run configuration from the UI form, merges with
    server config, and kicks off the pipeline in a background thread.

    Returns: {"id": "<run-uuid>"}
    """
    # Reject when we're already at capacity rather than queueing — a queued
    # run looks identical to a hung run from the UI's perspective.
    if not _run_slots.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Server is busy — too many concurrent runs. Try again in a moment.",
        )

    try:
        run_id = str(uuid4())

        run = Run(
            id=run_id,
            status="queued",
            created_at=datetime.now(timezone.utc),
            request=request,
            stages=_make_stages(),
        )

        runs[run_id] = run

        # Build per-run config by merging server config + request
        run_config = build_run_config(server_config, request)
    except Exception:
        _run_slots.release()
        raise

    # Execute pipeline in background thread — the wrapper releases the slot
    # when the run finishes (success or failure).
    thread = Thread(
        target=_run_pipeline_with_slot,
        args=(run, run_config),
        daemon=True,
    )
    thread.start()

    return {"id": run_id}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str, _: None = Depends(require_passcode)) -> Run:
    """Get run status, stage progress, and results.

    The Run object is updated in-place by the background thread,
    so polling this endpoint reflects live progress.
    """
    if run_id not in runs:
        raise HTTPException(status_code=404, detail="Run not found")
    return runs[run_id]


@app.get("/api/runs/{run_id}/export")
def export_brief(run_id: str, _: None = Depends(require_passcode)):
    """Download the brief as a markdown file.

    Only available when the run is complete and has a brief with
    raw_markdown content.
    """
    if run_id not in runs:
        raise HTTPException(status_code=404, detail="Run not found")

    run = runs[run_id]
    if run.status != "complete" or not run.brief or not run.brief.raw_markdown:
        raise HTTPException(status_code=400, detail="Brief not ready for export")

    return PlainTextResponse(
        content=run.brief.raw_markdown,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="brief-{run_id[:8]}.md"'
        },
    )
