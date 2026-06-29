from fastapi import APIRouter, BackgroundTasks

router = APIRouter()


@router.post("/ingest", status_code=202)
async def ingest(body, background_tasks: BackgroundTasks):
    ...


@router.get("/ingest/status/{run_id}")
async def ingest_status(run_id: str):
    ...
