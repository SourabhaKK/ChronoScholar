# All shared fixtures live here exclusively — see TESTING_STRATEGY.md
import time
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from app.config import Settings
from app.schemas.paper import Paper

# ─── Settings ────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_settings():
    return Settings(
        llm_provider="groq",
        groq_api_key="test-groq-key",
        gemini_api_key="test-gemini-key",
        cognee_db_path="/tmp/test_cognee.db",
        contradiction_confidence_threshold=0.7,
        arxiv_request_delay=0.0,
    )


# ─── LLM Provider Clients ─────────────────────────────────────────────────────

@pytest.fixture
def mock_groq_client(monkeypatch):
    from app.services import llm_service
    mock = MagicMock()
    monkeypatch.setattr(llm_service, "groq_complete", mock)
    return mock


@pytest.fixture
def mock_gemini_client(monkeypatch):
    from app.services import llm_service
    mock = MagicMock()
    monkeypatch.setattr(llm_service, "gemini_complete", mock)
    return mock


# ─── Sleep / Network ──────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_sleep(monkeypatch):
    """Patches time.sleep globally so no test incurs real retry/backoff delays."""
    mock = MagicMock()
    monkeypatch.setattr(time, "sleep", mock)
    return mock


@pytest.fixture
def block_network(monkeypatch):
    """Raises on any real network call — confirms tests are truly offline."""
    import socket

    def blocked_connect(self, addr):
        raise RuntimeError(f"Network call blocked in tests: {addr}")

    monkeypatch.setattr(socket.socket, "connect", blocked_connect)


# ─── Sample Papers ────────────────────────────────────────────────────────────

@pytest.fixture
def paper_mem0() -> Paper:
    return Paper(
        paper_id="2504.19413",
        title="Mem0: Building production-ready AI agents with scalable long-term memory",
        abstract=(
            "We present Mem0, a memory framework for AI agents. "
            "Our evaluation on LoCoMo benchmark shows graph memory adds minimal "
            "value over vector memory. Selective memory achieves 66.9% accuracy "
            "with 0.71s median latency and approximately 1,800 tokens per conversation."
        ),
        published_date="2025-04",
        authors=["Prateek Chhikara", "Dev Khant"],
        categories=["cs.AI", "cs.LG"],
        arxiv_url="https://arxiv.org/abs/2504.19413",
    )


# ─── arXiv Mocks ─────────────────────────────────────────────────────────────

@pytest.fixture
def mock_arxiv_result(paper_mem0: Paper) -> MagicMock:
    result = MagicMock()
    result.entry_id = "http://arxiv.org/abs/2504.19413v1"
    result.title = paper_mem0.title
    result.summary = paper_mem0.abstract
    result.published = datetime(2025, 4, 1)
    result.authors = [MagicMock(name="Prateek Chhikara")]
    result.categories = ["cs.AI", "cs.LG"]
    return result


@pytest.fixture
def mock_arxiv_search(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Patches arxiv.Search; returns the .results mock so tests can set return_value."""
    import arxiv

    mock_search_cls = MagicMock()
    monkeypatch.setattr(arxiv, "Search", mock_search_cls)
    return mock_search_cls.return_value.results


@pytest.fixture
def arxiv_service(mock_settings: Settings) -> "ArxivService":  # type: ignore[name-defined]
    from app.services.arxiv_service import ArxivService

    return ArxivService(request_delay=mock_settings.arxiv_request_delay)
