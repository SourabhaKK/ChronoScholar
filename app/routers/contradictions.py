from fastapi import APIRouter

router = APIRouter()


@router.get("/contradictions")
async def list_contradictions():
    ...


@router.post("/detect")
async def detect(body=None):
    ...
