# All shared fixtures live here exclusively — see TESTING_STRATEGY.md
import json
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.config import Settings
from app.schemas.contradiction import ContradictionPair
from app.schemas.paper import Paper

# ─── Settings ────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_settings():
    return Settings(
        app_llm_provider="groq",
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
    """Patches arxiv.Client.results at class level; return_value controls what results() yields."""
    import arxiv

    mock_results = MagicMock()
    monkeypatch.setattr(arxiv.Client, "results", mock_results)
    return mock_results


@pytest.fixture
def arxiv_service(mock_settings: Settings) -> "ArxivService":  # type: ignore[name-defined]
    from app.services.arxiv_service import ArxivService

    return ArxivService(request_delay=mock_settings.arxiv_request_delay)


@pytest.fixture
def paper_zep() -> Paper:
    return Paper(
        paper_id="2501.13956",
        title="Zep: A temporal knowledge graph architecture for agent memory",
        abstract=(
            "We introduce Graphiti, a temporal knowledge graph engine for agent memory. "
            "Our system achieves 94.8% accuracy on the DMR benchmark and demonstrates "
            "18.5% improvement on LongMemEval over vector-only approaches. "
            "Graph-based memory shows significant advantages for temporal and multi-hop queries."
        ),
        published_date="2025-01",
        authors=["Preston Rasmussen", "Pavlo Paliychuk"],
        categories=["cs.AI"],
        arxiv_url="https://arxiv.org/abs/2501.13956",
    )


@pytest.fixture
def paper_cognee() -> Paper:
    return Paper(
        paper_id="2505.24478",
        title="Optimizing the Interface Between Knowledge Graphs and LLMs for Complex Reasoning",
        abstract=(
            "We present Cognee, a graph-RAG system achieving 92.5% accuracy on multi-hop "
            "queries compared to 60% for flat RAG baselines. Our hybrid graph-vector "
            "architecture demonstrates substantial improvements for complex reasoning tasks."
        ),
        published_date="2025-05",
        authors=["Vasilije Markovic", "Lazar Obradovic"],
        categories=["cs.AI", "cs.IR"],
        arxiv_url="https://arxiv.org/abs/2505.24478",
    )


@pytest.fixture
def paper_unrelated() -> Paper:
    return Paper(
        paper_id="2312.00001",
        title="A survey of transformer architectures",
        abstract=(
            "We survey transformer architectures from 2017 to 2023, "
            "covering attention mechanisms, positional encodings, and "
            "scaling laws for large language models."
        ),
        published_date="2023-12",
        authors=["Test Author"],
        categories=["cs.LG"],
        arxiv_url="https://arxiv.org/abs/2312.00001",
    )


@pytest.fixture
def five_paper_corpus(paper_mem0: Paper, paper_zep: Paper, paper_cognee: Paper, paper_unrelated: Paper) -> list[Paper]:
    paper_extra = Paper(
        paper_id="2502.00001",
        title="Graph-based Agent Memory: Taxonomy and Applications",
        abstract="We survey graph-based memory architectures for AI agents.",
        published_date="2025-02",
        authors=["Survey Author"],
        categories=["cs.AI"],
        arxiv_url="https://arxiv.org/abs/2502.00001",
    )
    return [paper_mem0, paper_zep, paper_cognee, paper_unrelated, paper_extra]


# ─── LLM Service Mock ─────────────────────────────────────────────────────────

@pytest.fixture
def mock_llm_service() -> MagicMock:
    service = MagicMock()
    service.complete.return_value = json.dumps({
        "label": "contradicts",
        "confidence": 0.87,
        "claim_a": "Graph memory adds minimal value over vector memory",
        "claim_b": "Temporal graph achieves 18.5% improvement over vectors",
        "explanation": (
            "Paper A reports minimal gains from graph memory on LoCoMo. "
            "Paper B demonstrates substantial improvements on LongMemEval."
        ),
    })
    return service


# ─── Contradiction Service ────────────────────────────────────────────────────

@pytest.fixture
def contradiction_service(mock_llm_service: MagicMock) -> "ContradictionService":  # type: ignore[name-defined]
    from app.services.contradiction_service import ContradictionService

    return ContradictionService(llm_service=mock_llm_service)


# ─── Cognee Mocks ─────────────────────────────────────────────────────────────

@pytest.fixture
def mock_cognee_add(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    import cognee

    mock = AsyncMock()
    monkeypatch.setattr(cognee, "add", mock)
    return mock


@pytest.fixture
def mock_cognee_cognify(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    import cognee

    mock = AsyncMock()
    monkeypatch.setattr(cognee, "cognify", mock)
    return mock


@pytest.fixture
def mock_cognee_search(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    import cognee

    mock = AsyncMock()
    monkeypatch.setattr(cognee, "search", mock)
    return mock


@pytest.fixture
def cognee_service(mock_settings: Settings) -> "CogneeService":  # type: ignore[name-defined]
    from app.services.cognee_service import CogneeService

    return CogneeService(settings=mock_settings)


# ─── API-level mocks ──────────────────────────────────────────────────────────

@pytest.fixture
def mock_cognee_service() -> AsyncMock:
    service = AsyncMock()
    # get_stats is a sync method on the real service — override with MagicMock
    service.get_stats = MagicMock(return_value={
        "paper_count": 5,
        "entity_count": 35,
        "edge_count": 89,
    })
    service.graph_loaded = True
    return service


@pytest.fixture
def mock_contradiction_service() -> MagicMock:
    service = MagicMock()
    service.detect.return_value = ContradictionPair(
        pair_id=str(uuid4()),
        paper_id_a="2504.19413",
        paper_id_b="2501.13956",
        label="contradicts",
        confidence=0.87,
        claim_a="Graph memory adds minimal value over vector memory",
        claim_b="Temporal graph achieves 18.5% improvement over vectors",
        explanation=(
            "Paper A minimises the value of graph memory. "
            "Paper B demonstrates substantial improvements."
        ),
        detection_method="llm",
        detected_at=datetime.now(timezone.utc).isoformat(),
    )
    return service


@pytest.fixture
def test_client(mock_cognee_service: AsyncMock, mock_contradiction_service: MagicMock):
    from fastapi.testclient import TestClient
    from app.main import create_app

    app = create_app()
    app.state.cognee_service = mock_cognee_service
    app.state.contradiction_service = mock_contradiction_service
    app.state.arxiv_service = MagicMock()
    app.state.run_store = {"contradictions": []}
    return TestClient(app, raise_server_exceptions=True)
