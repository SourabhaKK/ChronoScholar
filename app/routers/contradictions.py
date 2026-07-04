import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_arxiv_service, get_cognee_service, get_contradiction_service, get_run_store
from app.schemas.contradiction import (
    ChronoScholarResult,
    CompareRequest,
    CompareResponse,
    ContradictionPair,
    ContradictionResponse,
    DetectRequest,
    FlatRagResult,
)
from app.services.arxiv_service import ArxivService
from app.services.cognee_service import CogneeService
from app.services.contradiction_service import ContradictionService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/detect", response_model=ContradictionPair)
async def detect(
    body: DetectRequest,
    contradiction_svc: ContradictionService = Depends(get_contradiction_service),  # noqa: B008
    arxiv_svc: ArxivService = Depends(get_arxiv_service),  # noqa: B008
    run_store: dict = Depends(get_run_store),  # noqa: B008
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
    run_store: dict = Depends(get_run_store),  # noqa: B008
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


@router.post("/compare", response_model=CompareResponse)
async def compare(
    body: CompareRequest,
    cognee_svc: CogneeService = Depends(get_cognee_service),  # noqa: B008
    contradiction_svc: ContradictionService = Depends(get_contradiction_service),  # noqa: B008
    arxiv_svc: ArxivService = Depends(get_arxiv_service),  # noqa: B008
) -> CompareResponse:
    """Side-by-side: single-paper RAG (SUMMARIES) vs ChronoScholar (GRAPH_COMPLETION + detect)."""
    paper_a = arxiv_svc.fetch_by_id(body.paper_id_a)
    paper_b = arxiv_svc.fetch_by_id(body.paper_id_b)
    if paper_a is None:
        raise HTTPException(status_code=404, detail=f"Paper {body.paper_id_a} not found on arXiv.")
    if paper_b is None:
        raise HTTPException(status_code=404, detail=f"Paper {body.paper_id_b} not found on arXiv.")

    # ── Flat RAG: SUMMARIES search, single-paper context ─────────────────────
    flat_answer = f"{paper_a.title}: {paper_a.abstract[:400]}"
    if cognee_svc.graph_loaded:
        try:
            flat_result = await cognee_svc.search(body.question, mode="SUMMARIES")
            raw = flat_result.get("answer", "")
            if raw:
                flat_answer = raw.strip("[]'\"")
        except Exception as exc:
            logger.warning("SUMMARIES search failed in /compare: %s", exc)

    flat_rag = FlatRagResult(
        answer=flat_answer,
        source_paper_id=paper_a.paper_id,
        source_title=paper_a.title,
    )

    # ── ChronoScholar: GRAPH_COMPLETION + contradiction detection ─────────────
    cs_answer = ""
    if cognee_svc.graph_loaded:
        try:
            cs_result = await cognee_svc.search(body.question, mode="GRAPH_COMPLETION")
            raw = cs_result.get("answer", "")
            if raw:
                cs_answer = raw.strip("[]'\"")
        except Exception as exc:
            logger.warning("GRAPH_COMPLETION search failed in /compare: %s", exc)

    if not cs_answer:
        cs_answer = (
            f"Paper A ({paper_a.paper_id}): {paper_a.abstract[:300]}… "
            f"Paper B ({paper_b.paper_id}): {paper_b.abstract[:300]}…"
        )

    contradiction = contradiction_svc.detect(paper_a, paper_b)

    return CompareResponse(
        flat_rag=flat_rag,
        chronoscholar=ChronoScholarResult(answer=cs_answer, contradiction=contradiction),
    )
