import pytest
from pydantic import ValidationError


def test_paper_schema_accepts_valid_data():
    from app.schemas.paper import Paper
    paper = Paper(
        paper_id="2504.19413",
        title="Mem0: Building production-ready AI agents",
        abstract="We present Mem0, a memory framework for AI agents.",
        published_date="2025-04",
        authors=["Prateek Chhikara"],
        categories=["cs.AI"],
        arxiv_url="https://arxiv.org/abs/2504.19413",
    )
    assert paper.paper_id == "2504.19413"


def test_paper_schema_rejects_empty_paper_id():
    from app.schemas.paper import Paper
    with pytest.raises(ValidationError):
        Paper(
            paper_id="",
            title="Title",
            abstract="Abstract",
            published_date="2025-04",
            authors=["Author"],
            categories=["cs.AI"],
            arxiv_url="https://arxiv.org/abs/2504.19413",
        )


def test_ingest_request_rejects_max_papers_above_100():
    from app.schemas.paper import PaperIngestRequest
    with pytest.raises(ValidationError):
        PaperIngestRequest(query="agent memory", max_papers=101)


def test_ingest_request_rejects_zero_max_papers():
    from app.schemas.paper import PaperIngestRequest
    with pytest.raises(ValidationError):
        PaperIngestRequest(query="agent memory", max_papers=0)


def test_query_request_rejects_empty_question():
    from app.schemas.query import QueryRequest
    with pytest.raises(ValidationError):
        QueryRequest(question="")


def test_query_request_rejects_invalid_search_mode():
    from app.schemas.query import QueryRequest
    with pytest.raises(ValidationError):
        QueryRequest(question="What is graph memory?", search_mode="INVALID_MODE")


def test_contradiction_pair_rejects_confidence_above_one():
    from app.schemas.contradiction import ContradictionPair
    with pytest.raises(ValidationError):
        ContradictionPair(
            pair_id="7f3c9a1e-8b2d-4e5f-a6c7-d8e9f0a1b2c3",
            paper_id_a="2504.19413",
            paper_id_b="2501.13956",
            label="contradicts",
            confidence=1.5,
            claim_a="Claim A",
            claim_b="Claim B",
            explanation="Explanation",
            detection_method="llm",
            detected_at="2026-06-29T10:27:15.443Z",
        )


def test_contradiction_pair_rejects_invalid_label():
    from app.schemas.contradiction import ContradictionPair
    with pytest.raises(ValidationError):
        ContradictionPair(
            pair_id="7f3c9a1e-8b2d-4e5f-a6c7-d8e9f0a1b2c3",
            paper_id_a="2504.19413",
            paper_id_b="2501.13956",
            label="invalid_label",
            confidence=0.8,
            claim_a="Claim A",
            claim_b="Claim B",
            explanation="Explanation",
            detection_method="llm",
            detected_at="2026-06-29T10:27:15.443Z",
        )


def test_detect_request_rejects_identical_paper_ids():
    from app.schemas.contradiction import DetectRequest
    with pytest.raises(ValidationError):
        DetectRequest(paper_id_a="2504.19413", paper_id_b="2504.19413")


def test_ingest_status_response_accepts_all_status_values():
    from app.schemas.paper import IngestStatusResponse
    for status in ("pending", "running", "complete", "failed"):
        response = IngestStatusResponse(
            run_id="550e8400-e29b-41d4-a716-446655440000",
            status=status,
            progress_percent=0,
            papers_fetched=0,
            papers_total=50,
            message="...",
            started_at="2026-06-29T10:23:45.123Z",
            completed_at=None,
        )
        assert response.status == status
