"""Market Research Pipeline — FastAPI Server

Serves the API for the market research web application.
Run with: uvicorn server:app --reload --port 8000
"""

import os
from datetime import datetime, timezone
from threading import Thread
from uuid import uuid4

from fastapi import FastAPI, HTTPException
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory run store
runs: dict[str, Run] = {}

# Default pipeline stages
STAGE_NAMES = ["search", "dedup", "group", "extract", "synthesize"]


def _make_stages() -> list[Stage]:
    """Create fresh pipeline stages, all in 'pending' status."""
    return [Stage(name=name) for name in STAGE_NAMES]


@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/api/runs")
def create_run(request: RunRequest) -> dict:
    """Start a new pipeline run.

    Accepts per-run configuration from the UI form, merges with
    server config, and kicks off the pipeline in a background thread.

    Returns: {"id": "<run-uuid>"}
    """
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

    # Execute pipeline in background thread
    thread = Thread(
        target=execute_pipeline,
        args=(run, run_config),
        daemon=True,
    )
    thread.start()

    return {"id": run_id}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> Run:
    """Get run status, stage progress, and results.

    The Run object is updated in-place by the background thread,
    so polling this endpoint reflects live progress.
    """
    if run_id not in runs:
        raise HTTPException(status_code=404, detail="Run not found")
    return runs[run_id]


@app.get("/api/runs/{run_id}/export")
def export_brief(run_id: str):
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
