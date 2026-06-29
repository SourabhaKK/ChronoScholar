from typing import Literal

from pydantic import BaseModel, Field

SearchMode = Literal["GRAPH_COMPLETION", "SEMANTIC", "HYBRID"]


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    search_mode: SearchMode = "GRAPH_COMPLETION"
    max_results: int = Field(default=5, ge=1, le=20)


class SourceCitation(BaseModel):
    paper_id: str
    title: str
    published_date: str
    relevance_score: float
    excerpt: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceCitation]
    search_mode_used: SearchMode
    latency_ms: int
    graph_ready: bool
