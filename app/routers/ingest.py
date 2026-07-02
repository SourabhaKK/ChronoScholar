import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.dependencies import get_cognee_service, get_run_store
from app.schemas.paper import IngestResponse, IngestStatusResponse, PaperIngestRequest
from app.services.arxiv_service import ArxivService
from app.services.cognee_service import CogneeService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/ingest", response_model=IngestResponse, status_code=202)
async def ingest(
    body: PaperIngestRequest,
    background_tasks: BackgroundTasks,
    cognee_svc: CogneeService = Depends(get_cognee_service),
    run_store: dict = Depends(get_run_store),
) -> IngestResponse:
    run_id = str(uuid4())
    run_store[run_id] = {
        "run_id": run_id,
        "status": "running",
        "progress_percent": 0,
        "papers_fetched": 0,
        "papers_total": body.max_papers,
        "message": "Fetching papers from arXiv...",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
    }
    background_tasks.add_task(
        _run_ingestion_task, body, run_id, run_store, cognee_svc
    )
    return IngestResponse(
        run_id=run_id,
        status="running",
        message=f"Ingestion started. Poll /ingest/status/{run_id} for progress.",
    )


async def _run_ingestion_task(
    body: PaperIngestRequest,
    run_id: str,
    run_store: dict,
    cognee_svc: CogneeService,
) -> None:
    try:
        arxiv_svc = ArxivService()
        papers = arxiv_svc.fetch(
            body.query, max_results=body.max_papers, domain_tag=body.domain_tag
        )
        run_store[run_id]["papers_fetched"] = len(papers)
        run_store[run_id]["papers_total"] = len(papers)
        await cognee_svc.run_ingestion(papers, run_id, run_store)
        run_store[run_id].update({
            "status": "complete",
            "progress_percent": 100,
            "message": "Ingestion complete.",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as exc:
        logger.error("Ingestion task failed for run %s: %s", run_id, exc)
        run_store[run_id].update({
            "status": "failed",
            "message": str(exc),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })


@router.get("/ingest/status/{run_id}", response_model=IngestStatusResponse)
async def ingest_status(
    run_id: str,
    run_store: dict = Depends(get_run_store),
) -> IngestStatusResponse:
    if run_id not in run_store:
        raise HTTPException(status_code=404, detail="Run ID not found.")
    data = run_store[run_id]
    return IngestStatusResponse(
        run_id=data["run_id"],
        status=data["status"],
        progress_percent=data.get("progress_percent", 0),
        papers_fetched=data.get("papers_fetched", 0),
        papers_total=data.get("papers_total", 0),
        message=data.get("message", ""),
        started_at=data.get("started_at", ""),
        completed_at=data.get("completed_at"),
    )
