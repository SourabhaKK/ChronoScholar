from typing import Literal

from pydantic import BaseModel, Field

IngestStatus = Literal["pending", "running", "complete", "failed"]


class Paper(BaseModel):
    paper_id: str = Field(min_length=1)
    title: str
    abstract: str
    published_date: str
    authors: list[str]
    categories: list[str]
    arxiv_url: str


class PaperIngestRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    max_papers: int = Field(default=50, ge=1, le=100)
    domain_tag: str | None = None


class IngestResponse(BaseModel):
    run_id: str
    status: IngestStatus
    message: str


class IngestStatusResponse(BaseModel):
    run_id: str
    status: IngestStatus
    progress_percent: int = Field(ge=0, le=100)
    papers_fetched: int
    papers_total: int
    entities_created: int | None = None
    edges_created: int | None = None
    contradiction_pairs_detected: int | None = None
    cognify_duration_seconds: float | None = None
    message: str
    started_at: str
    completed_at: str | None = None
