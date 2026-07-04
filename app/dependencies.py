from fastapi import Request

from app.services.arxiv_service import ArxivService
from app.services.cognee_service import CogneeService
from app.services.contradiction_service import ContradictionService


def get_cognee_service(request: Request) -> CogneeService:
    return request.app.state.cognee_service


def get_contradiction_service(request: Request) -> ContradictionService:
    return request.app.state.contradiction_service


def get_arxiv_service(request: Request) -> ArxivService:
    return request.app.state.arxiv_service


def get_run_store(request: Request) -> dict:
    return request.app.state.run_store


def get_compare_cache(request: Request) -> dict:
    return request.app.state.compare_cache
