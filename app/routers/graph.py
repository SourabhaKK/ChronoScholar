from fastapi import APIRouter

router = APIRouter()


@router.get("/graph/visualise")
async def graph_visualise():
    ...


@router.get("/graph/stats")
async def graph_stats():
    ...
