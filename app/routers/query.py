import logging
import time

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_cognee_service
from app.prompts import QUERY_GROUNDING_PREFIX
from app.schemas.query import QueryRequest, QueryResponse, SourceCitation
from app.services.cognee_service import CogneeService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query(
    body: QueryRequest,
    cognee_svc: CogneeService = Depends(get_cognee_service),  # noqa: B008
) -> QueryResponse:
    if not cognee_svc.graph_loaded:
        raise HTTPException(
            status_code=503,
            detail="Knowledge graph not ready. Ingest papers first.",
        )
    start_ms = int(time.time() * 1000)
    grounded_q = QUERY_GROUNDING_PREFIX.substitute(user_question=body.question)
    result = await cognee_svc.search(grounded_q, mode=body.search_mode)
    latency_ms = int(time.time() * 1000) - start_ms
    sources = [SourceCitation(**s) for s in result.get("sources", [])]
    return QueryResponse(
        answer=result.get("answer", ""),
        sources=sources,
        search_mode_used=body.search_mode,
        latency_ms=latency_ms,
        graph_ready=True,
    )
