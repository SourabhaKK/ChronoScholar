import asyncio
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.dependencies import get_arxiv_service, get_cognee_service, get_contradiction_service, get_run_store, get_compare_cache
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
    request: Request,
    cognee_svc: CogneeService = Depends(get_cognee_service),  # noqa: B008
    contradiction_svc: ContradictionService = Depends(get_contradiction_service),  # noqa: B008
    arxiv_svc: ArxivService = Depends(get_arxiv_service),  # noqa: B008
    cache: dict = Depends(get_compare_cache),  # noqa: B008
) -> CompareResponse:
    """Side-by-side: single-paper RAG (SUMMARIES) vs ChronoScholar (GRAPH_COMPLETION + detect).

    Parallelised: both arXiv fetches run concurrently, then both Cognee searches
    and the LLM detect call run concurrently so wall-clock time ≈ slowest task.
    """
    cache_key = f"{body.paper_id_a}:{body.paper_id_b}"
    if cache_key in cache:
        return cache[cache_key]

    # Phase 1: fetch both papers concurrently (blocking IO → thread pool)
    loop = asyncio.get_event_loop()
    paper_a, paper_b = await asyncio.gather(
        loop.run_in_executor(None, arxiv_svc.fetch_by_id, body.paper_id_a),
        loop.run_in_executor(None, arxiv_svc.fetch_by_id, body.paper_id_b),
    )
    if paper_a is None:
        raise HTTPException(status_code=404, detail=f"Paper {body.paper_id_a} not found on arXiv.")
    if paper_b is None:
        raise HTTPException(status_code=404, detail=f"Paper {body.paper_id_b} not found on arXiv.")
    assert paper_a is not None
    assert paper_b is not None

    # Phase 2: run SUMMARIES search, GRAPH_COMPLETION search, and detect() concurrently.
    async def _flat_search() -> str:
        logger.info("compare: starting flat_rag search for %s", body.paper_id_a)
        if not cognee_svc.graph_loaded:
            return f"{paper_a.title}: {paper_a.abstract[:400]}"
        try:
            res = await cognee_svc.search(body.question, mode="SUMMARIES")
            raw = res.get("answer", "")
            return raw.strip("[]'\"") if raw else f"{paper_a.title}: {paper_a.abstract[:400]}"
        except Exception as exc:
            logger.warning("SUMMARIES search failed in /compare: %s", exc)
            return f"{paper_a.title}: {paper_a.abstract[:400]}"

    async def _graph_search() -> str:
        logger.info("compare: starting graph_completion search")
        if not cognee_svc.graph_loaded:
            return (
                f"Paper A ({paper_a.paper_id}): {paper_a.abstract[:300]}… "
                f"Paper B ({paper_b.paper_id}): {paper_b.abstract[:300]}…"
            )
        try:
            res = await cognee_svc.search(body.question, mode="GRAPH_COMPLETION")
            raw = res.get("answer", "")
            return raw.strip("[]'\"") if raw else (
                f"Paper A ({paper_a.paper_id}): {paper_a.abstract[:300]}… "
                f"Paper B ({paper_b.paper_id}): {paper_b.abstract[:300]}…"
            )
        except Exception as exc:
            logger.warning("GRAPH_COMPLETION search failed in /compare: %s", exc)
            return (
                f"Paper A ({paper_a.paper_id}): {paper_a.abstract[:300]}… "
                f"Paper B ({paper_b.paper_id}): {paper_b.abstract[:300]}…"
            )

    async def _detect() -> ContradictionPair:
        logger.info("compare: starting detect for pair %s/%s", body.paper_id_a, body.paper_id_b)
        return await loop.run_in_executor(None, lambda: contradiction_svc.detect(paper_a, paper_b))

    flat_answer, cs_answer, contradiction = await asyncio.gather(
        _flat_search(), _graph_search(), _detect()
    )
    logger.info("compare: flat_rag answer length: %d", len(flat_answer))
    logger.info("compare: chronoscholar answer length: %d", len(cs_answer))
    logger.info("compare: contradiction label: %s", contradiction.label)
    if len(flat_answer) > 300:
        flat_answer = flat_answer[:297] + "..."

    result = CompareResponse(
        flat_rag=FlatRagResult(
            answer=flat_answer,
            source_paper_id=paper_a.paper_id,
            source_title=paper_a.title,
        ),
        chronoscholar=ChronoScholarResult(answer=cs_answer, contradiction=contradiction),
    )
    cache[cache_key] = result
    return result
