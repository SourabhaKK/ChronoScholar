import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_arxiv_service, get_contradiction_service, get_run_store
from app.schemas.contradiction import ContradictionPair, ContradictionResponse, DetectRequest
from app.services.arxiv_service import ArxivService
from app.services.contradiction_service import ContradictionService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/detect", response_model=ContradictionPair)
async def detect(
    body: DetectRequest,
    contradiction_svc: ContradictionService = Depends(get_contradiction_service),
    arxiv_svc: ArxivService = Depends(get_arxiv_service),
    run_store: dict = Depends(get_run_store),
) -> ContradictionPair:
    paper_a = arxiv_svc.fetch_by_id(body.paper_id_a)
    paper_b = arxiv_svc.fetch_by_id(body.paper_id_b)
    if paper_a is None:
        raise HTTPException(
            status_code=404, detail=f"Paper {body.paper_id_a} not found on arXiv."
        )
    if paper_b is None:
        raise HTTPException(
            status_code=404, detail=f"Paper {body.paper_id_b} not found on arXiv."
        )
    result = contradiction_svc.detect(paper_a, paper_b)
    run_store.setdefault("contradictions", []).append(result)
    return result


@router.get("/contradictions", response_model=ContradictionResponse)
async def list_contradictions(
    min_confidence: float = Query(default=0.7, ge=0.0, le=1.0),
    label: Literal["contradicts", "supports", "extends", "unrelated"] | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    run_store: dict = Depends(get_run_store),
) -> ContradictionResponse:
    all_pairs: list[ContradictionPair] = run_store.get("contradictions", [])
    filtered = [p for p in all_pairs if p.confidence >= min_confidence]
    if label is not None:
        filtered = [p for p in filtered if p.label == label]
    page = filtered[offset : offset + limit]
    return ContradictionResponse(
        total=len(filtered),
        returned=len(page),
        offset=offset,
        contradictions=page,
    )
