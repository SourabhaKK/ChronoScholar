import asyncio
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.dependencies import (
    get_arxiv_service,
    get_cognee_service,
    get_compare_cache,
    get_contradiction_service,
    get_run_store,
)
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
    """Side-by-side: single-paper RAG (CHUNKS) vs ChronoScholar (GRAPH_COMPLETION + detect).

    arXiv fetches run in parallel (no graph DB access).
    Cognee CHUNKS and GRAPH_COMPLETION run sequentially to avoid Windows
    file lock contention on the single-file LadybugDB graph.
    detect() fires into the thread pool immediately after arXiv fetches and
    runs concurrently with the Cognee searches (uses Groq only, not the graph DB).
    """
    cache_key = f"{body.paper_id_a}:{body.paper_id_b}"
    if cache_key in cache:
        return cache[cache_key]

    # Phase 1: fetch both papers concurrently (blocking IO → thread pool, no graph DB)
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

    # Phase 2: detect() fires into thread pool immediately (Groq LLM only — no Ladybug lock).
    # Cognee searches run sequentially to prevent Windows Error 33 file lock contention.
    logger.info("compare: starting detect for pair %s/%s", body.paper_id_a, body.paper_id_b)
    detect_future = loop.run_in_executor(
        None, lambda: contradiction_svc.detect(paper_a, paper_b)
    )

    # CHUNKS first (flat RAG simulation — single retrieved segment, simulates single-paper RAG)
    logger.info("compare: starting flat_rag search for %s", body.paper_id_a)
    flat_answer: str
    if not cognee_svc.graph_loaded:
        flat_answer = f"{paper_a.title}: {paper_a.abstract[:400]}"
    else:
        try:
            res = await cognee_svc.search(body.question, mode="CHUNKS")
            raw = res.get("answer", "")
            flat_answer = raw.strip("[]'\"") if raw else f"{paper_a.title}: {paper_a.abstract[:400]}"
        except Exception as exc:
            logger.warning("CHUNKS search failed in /compare: %s", exc)
            flat_answer = f"{paper_a.title}: {paper_a.abstract[:400]}"

    # GRAPH_COMPLETION second (cross-paper synthesis — ChronoScholar view)
    logger.info("compare: starting graph_completion search")
    cs_answer: str
    if not cognee_svc.graph_loaded:
        cs_answer = (
            f"Paper A ({paper_a.paper_id}): {paper_a.abstract[:300]}… "
            f"Paper B ({paper_b.paper_id}): {paper_b.abstract[:300]}…"
        )
    else:
        try:
            res = await cognee_svc.search(body.question, mode="GRAPH_COMPLETION")
            raw = res.get("answer", "")
            cs_answer = raw.strip("[]'\"") if raw else (
                f"Paper A ({paper_a.paper_id}): {paper_a.abstract[:300]}… "
                f"Paper B ({paper_b.paper_id}): {paper_b.abstract[:300]}…"
            )
        except Exception as exc:
            logger.warning("GRAPH_COMPLETION search failed in /compare: %s", exc)
            cs_answer = (
                f"Paper A ({paper_a.paper_id}): {paper_a.abstract[:300]}… "
                f"Paper B ({paper_b.paper_id}): {paper_b.abstract[:300]}…"
            )

    # Collect detect result (likely already done while Cognee searches ran)
    contradiction = await detect_future

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
    # Only cache when graph synthesis produced substantively more content than flat RAG.
    # Similar lengths indicate both fell back to abstract snippets — don't cache, allow retry.
    flat_len = len(result.flat_rag.answer)
    cs_len = len(result.chronoscholar.answer)
    if cs_len > flat_len * 1.5:
        cache[cache_key] = result
        logger.info(
            "compare: result cached (cs_len=%d > flat_len=%d * 1.5)", cs_len, flat_len
        )
    else:
        logger.warning(
            "compare: result NOT cached — answers too similar "
            "(cs_len=%d, flat_len=%d), graph fallback suspected",
            cs_len, flat_len,
        )
    return result
