import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from app.dependencies import get_cognee_service
from app.services.cognee_service import CogneeService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/graph/visualise", response_class=HTMLResponse)
async def graph_visualise(
    cognee_svc: CogneeService = Depends(get_cognee_service),  # noqa: B008
) -> HTMLResponse:
    if not cognee_svc.graph_loaded:
        raise HTTPException(status_code=503, detail="Knowledge graph not ready.")
    html = await cognee_svc.get_graph_html()
    return HTMLResponse(content=html)


@router.get("/graph/stats")
async def graph_stats(
    cognee_svc: CogneeService = Depends(get_cognee_service),  # noqa: B008
) -> dict:
    return cognee_svc.get_stats()
