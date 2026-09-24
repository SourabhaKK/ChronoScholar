# ChronoScholar — Testing Strategy

## Approach: Test-Driven Development (TDD)

**Rule: No implementation file is created until its test file is written and failing.**

Cycle per component:
1. Write failing test (RED)
2. Confirm it fails for the right reason (not import error — actual logic failure)
3. Write minimum implementation to pass (GREEN)
4. Refactor without breaking tests (REFACTOR)
5. Repeat

## Test Execution

```bash
# All tests
pytest tests/ -v --cov=app --cov-report=term-missing

# Unit tests only (fast — run constantly during development)
pytest tests/ -v -m "not integration and not benchmark"

# Integration tests
pytest tests/ -v -m integration

# Benchmark tests (manual only — not in CI)
pytest tests/ -v -m benchmark
```

All tests must pass with:
- Zero network calls
- Zero real API keys set
- Cold start (no pre-existing database files)

## Mock Boundaries (always mocked — no exceptions)

```python
# Everything behind these boundaries is mocked
cognee.add()
cognee.cognify()
cognee.search()
arxiv.Search()                    # arxiv library
httpx.Client.post()               # Groq API
google.generativeai.GenerativeModel.generate_content()  # Gemini
time.sleep()                      # rate limiting
mlflow.log_metric()
mlflow.log_param()
```

## Test Markers

```python
# Unit test (default — no marker needed)
def test_something(): ...

# Integration test
@pytest.mark.integration
def test_components_wired_together(): ...

# Benchmark test (manual only)
@pytest.mark.benchmark
def test_precision_on_ground_truth(): ...
```

Register markers in pyproject.toml:
```toml
[tool.pytest.ini_options]
markers = [
    "integration: integration tests using multi-component fixtures",
    "benchmark: ground truth benchmark tests, run manually only",
]
```

## conftest.py — All Shared Fixtures

All fixtures live in tests/conftest.py exclusively.

```python
import pytest
import json
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime
from app.schemas.paper import Paper
from app.schemas.contradiction import ContradictionPair
from app.config import Settings


# ─── Settings ────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_settings():
    return Settings(
        llm_provider="groq",
        groq_api_key="test-groq-key",
        gemini_api_key="test-gemini-key",
        cognee_db_path="/tmp/test_cognee.db",
        contradiction_confidence_threshold=0.7,
        arxiv_request_delay=0.0,  # No delay in tests
    )


# ─── Sample Papers ────────────────────────────────────────────────────────────

@pytest.fixture
def paper_mem0():
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


@pytest.fixture
def paper_zep():
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
def paper_cognee():
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
def paper_unrelated():
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
def five_paper_corpus(paper_mem0, paper_zep, paper_cognee, paper_unrelated):
    """Mini corpus for integration tests."""
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
def mock_llm_service():
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


# ─── Cognee Service Mock ──────────────────────────────────────────────────────

@pytest.fixture
def mock_cognee_service():
    service = AsyncMock()
    service.get_stats.return_value = {
        "paper_count": 5,
        "entity_count": 35,
        "edge_count": 89,
    }
    service.graph_loaded = True
    return service


# ─── arXiv Mock ───────────────────────────────────────────────────────────────

@pytest.fixture
def mock_arxiv_result(paper_mem0):
    result = MagicMock()
    result.entry_id = "http://arxiv.org/abs/2504.19413v1"
    result.title = paper_mem0.title
    result.summary = paper_mem0.abstract
    result.published = datetime(2025, 4, 1)
    result.authors = [MagicMock(name="Prateek Chhikara")]
    result.categories = ["cs.AI", "cs.LG"]
    return result


# ─── Network Blocker ─────────────────────────────────────────────────────────

@pytest.fixture
def block_network(monkeypatch):
    """Raises on any real network call — confirms tests are truly offline."""
    import socket
    original_connect = socket.socket.connect
    def blocked_connect(self, addr):
        raise RuntimeError(f"Network call blocked in tests: {addr}")
    monkeypatch.setattr(socket.socket, "connect", blocked_connect)


# ─── FastAPI Test Client ──────────────────────────────────────────────────────

@pytest.fixture
def test_client(mock_cognee_service, mock_llm_service):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app()
    app.state.cognee_service = mock_cognee_service
    app.state.contradiction_service = MagicMock()
    return TestClient(app)
```

---

## Test Specifications Per Component

### tests/test_config.py

```python
def test_config_loads_llm_provider_from_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    from app.config import Settings
    assert Settings().llm_provider == "groq"

def test_config_loads_gemini_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    from app.config import Settings
    assert Settings().llm_provider == "gemini"

def test_config_rejects_invalid_llm_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    from app.config import Settings
    with pytest.raises(ValueError):
        Settings()

def test_config_contradiction_threshold_defaults_to_valid_range():
    from app.config import Settings
    s = Settings()
    assert 0.0 <= s.contradiction_confidence_threshold <= 1.0

def test_config_rejects_threshold_above_one(monkeypatch):
    monkeypatch.setenv("CONTRADICTION_CONFIDENCE_THRESHOLD", "1.5")
    from app.config import Settings
    with pytest.raises(ValueError):
        Settings()

def test_config_rejects_negative_threshold(monkeypatch):
    monkeypatch.setenv("CONTRADICTION_CONFIDENCE_THRESHOLD", "-0.1")
    from app.config import Settings
    with pytest.raises(ValueError):
        Settings()
```

### tests/test_llm_service.py

```python
def test_complete_returns_string_on_groq_success(mock_settings, mock_groq_client):
    mock_groq_client.return_value = "test response"
    from app.services.llm_service import LLMService
    service = LLMService(settings=mock_settings)
    assert isinstance(service.complete("test prompt"), str)

def test_complete_retries_on_transient_connection_error(mock_settings, mock_groq_client):
    mock_groq_client.side_effect = [ConnectionError(), ConnectionError(), "success"]
    from app.services.llm_service import LLMService
    service = LLMService(settings=mock_settings)
    result = service.complete("test prompt")
    assert result == "success"
    assert mock_groq_client.call_count == 3

def test_complete_falls_back_to_gemini_on_rate_limit(
        mock_settings, mock_groq_client, mock_gemini_client):
    mock_groq_client.side_effect = RateLimitError("429")
    mock_gemini_client.return_value = "gemini response"
    from app.services.llm_service import LLMService
    service = LLMService(settings=mock_settings)
    assert service.complete("test prompt") == "gemini response"

def test_complete_returns_fallback_string_when_all_providers_fail(
        mock_settings, mock_groq_client, mock_gemini_client):
    mock_groq_client.side_effect = RateLimitError("429")
    mock_gemini_client.side_effect = RateLimitError("429")
    from app.services.llm_service import LLMService
    service = LLMService(settings=mock_settings)
    result = service.complete("test prompt", fallback="safe default")
    assert result == "safe default"

def test_complete_fallback_requires_zero_network_calls(
        mock_settings, mock_groq_client, mock_gemini_client, block_network):
    mock_groq_client.side_effect = Exception("provider error")
    mock_gemini_client.side_effect = Exception("provider error")
    from app.services.llm_service import LLMService
    service = LLMService(settings=mock_settings)
    result = service.complete("test prompt", fallback="default")
    assert result == "default"

def test_provider_switches_to_gemini_via_env_variable(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    from app.services.llm_service import LLMService
    from app.config import Settings
    service = LLMService(settings=Settings())
    assert service.primary_provider == "gemini"

def test_exponential_backoff_delays_between_retries(
        mock_settings, mock_groq_client, mock_sleep):
    mock_groq_client.side_effect = [ConnectionError(), ConnectionError(), "ok"]
    from app.services.llm_service import LLMService
    LLMService(settings=mock_settings).complete("test")
    assert mock_sleep.call_count >= 1
    # First delay >= 1 second, second >= 2 seconds
    delays = [call.args[0] for call in mock_sleep.call_args_list]
    assert delays[1] >= delays[0]
```

### tests/test_arxiv_service.py

```python
def test_fetch_returns_list_of_paper_objects(arxiv_service, mock_arxiv_search):
    mock_arxiv_search.return_value = [mock_arxiv_result()]
    papers = arxiv_service.fetch("agent memory", max_results=1)
    assert len(papers) == 1
    assert hasattr(papers[0], "paper_id")

def test_fetch_extracts_clean_paper_id(arxiv_service, mock_arxiv_result):
    from app.services.arxiv_service import ArxivService
    # ID must be clean: no URL, no "arxiv:", just "XXXX.XXXXX"
    paper = ArxivService._parse_result(mock_arxiv_result)
    assert "arxiv.org" not in paper.paper_id
    assert "http" not in paper.paper_id
    assert paper.paper_id == "2504.19413"

def test_fetch_respects_max_results_limit(arxiv_service, mock_arxiv_search, mock_arxiv_result):
    mock_arxiv_search.return_value = [mock_arxiv_result] * 20
    papers = arxiv_service.fetch("test", max_results=5)
    assert len(papers) <= 5

def test_fetch_returns_empty_list_for_no_results(arxiv_service, mock_arxiv_search):
    mock_arxiv_search.return_value = []
    papers = arxiv_service.fetch("xyznonexistent123abc")
    assert papers == []
    assert isinstance(papers, list)

def test_fetch_calls_sleep_between_requests(arxiv_service, mock_arxiv_search, mock_sleep):
    mock_arxiv_search.return_value = [mock_arxiv_result] * 5
    arxiv_service.fetch("test", max_results=5)
    assert mock_sleep.called

def test_fetch_by_id_returns_single_paper(arxiv_service, mock_arxiv_search, mock_arxiv_result):
    mock_arxiv_search.return_value = [mock_arxiv_result]
    paper = arxiv_service.fetch_by_id("2504.19413")
    assert paper is not None
    assert paper.paper_id == "2504.19413"

def test_fetch_by_id_returns_none_for_invalid_id(arxiv_service, mock_arxiv_search):
    mock_arxiv_search.return_value = []
    paper = arxiv_service.fetch_by_id("0000.00000")
    assert paper is None
```

### tests/test_contradiction_service.py

```python
def test_detect_returns_contradiction_for_known_conflicting_papers(
        contradiction_service, mock_llm_service, paper_mem0, paper_zep):
    result = contradiction_service.detect(paper_mem0, paper_zep)
    assert result.label == "contradicts"
    assert result.confidence > 0.0

def test_detect_result_matches_contradiction_pair_schema(
        contradiction_service, mock_llm_service, paper_mem0, paper_zep):
    result = contradiction_service.detect(paper_mem0, paper_zep)
    from app.schemas.contradiction import ContradictionPair
    assert isinstance(result, ContradictionPair)
    assert result.label in {"contradicts", "supports", "extends", "unrelated"}
    assert 0.0 <= result.confidence <= 1.0

def test_detect_never_returns_empty_explanation(
        contradiction_service, mock_llm_service, paper_mem0, paper_zep):
    result = contradiction_service.detect(paper_mem0, paper_zep)
    assert result.explanation is not None
    assert len(result.explanation.strip()) > 0

def test_detect_never_returns_empty_claims(
        contradiction_service, mock_llm_service, paper_mem0, paper_zep):
    result = contradiction_service.detect(paper_mem0, paper_zep)
    assert len(result.claim_a.strip()) > 0
    assert len(result.claim_b.strip()) > 0

def test_detect_falls_back_when_llm_returns_invalid_json(
        contradiction_service, mock_llm_service, paper_mem0, paper_zep):
    mock_llm_service.complete.return_value = "I cannot determine the relationship."
    result = contradiction_service.detect(paper_mem0, paper_zep)
    assert result.detection_method == "fallback"
    assert result.label == "unrelated"
    assert result.confidence == 0.0

def test_detect_falls_back_when_llm_returns_wrong_schema(
        contradiction_service, mock_llm_service, paper_mem0, paper_zep):
    mock_llm_service.complete.return_value = '{"wrong_field": "value"}'
    result = contradiction_service.detect(paper_mem0, paper_zep)
    assert result.detection_method == "fallback"

def test_detect_falls_back_when_llm_raises(
        contradiction_service, mock_llm_service, paper_mem0, paper_zep):
    mock_llm_service.complete.side_effect = Exception("LLM unavailable")
    result = contradiction_service.detect(paper_mem0, paper_zep)
    assert result.detection_method == "fallback"

def test_detect_returns_unrelated_for_clearly_different_papers(
        contradiction_service, mock_llm_service, paper_mem0, paper_unrelated):
    mock_llm_service.complete.return_value = json.dumps({
        "label": "unrelated",
        "confidence": 0.95,
        "claim_a": "Selective memory achieves 66.9% on LoCoMo",
        "claim_b": "Survey of transformer architectures from 2017-2023",
        "explanation": "These papers address completely different topics.",
    })
    result = contradiction_service.detect(paper_mem0, paper_unrelated)
    assert result.label == "unrelated"

def test_detect_batch_returns_all_pairs(
        contradiction_service, mock_llm_service, five_paper_corpus):
    results = contradiction_service.detect_batch(five_paper_corpus)
    expected_pairs = len(five_paper_corpus) * (len(five_paper_corpus) - 1) // 2
    assert len(results) == expected_pairs

def test_detect_uses_prompt_from_prompts_module(
        contradiction_service, mock_llm_service, paper_mem0, paper_zep):
    contradiction_service.detect(paper_mem0, paper_zep)
    call_args = mock_llm_service.complete.call_args[0][0]
    # Prompt must include both paper IDs and both abstracts
    assert paper_mem0.paper_id in call_args
    assert paper_zep.paper_id in call_args
```

### tests/test_api_routes.py

```python
def test_health_returns_200_always(test_client):
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_ready_returns_200_when_graph_loaded(test_client):
    response = test_client.get("/ready")
    assert response.status_code == 200
    assert response.json()["ready"] is True

def test_ingest_returns_202_with_run_id(test_client):
    response = test_client.post("/ingest", json={
        "query": "agent memory", "max_papers": 5
    })
    assert response.status_code == 202
    assert "run_id" in response.json()
    assert response.json()["status"] == "running"

def test_ingest_rejects_max_papers_above_100(test_client):
    response = test_client.post("/ingest", json={
        "query": "test", "max_papers": 101
    })
    assert response.status_code == 422

def test_ingest_rejects_empty_query(test_client):
    response = test_client.post("/ingest", json={
        "query": "", "max_papers": 10
    })
    assert response.status_code == 422

def test_ingest_status_returns_404_for_unknown_run_id(test_client):
    response = test_client.get("/ingest/status/nonexistent-run-id")
    assert response.status_code == 404

def test_query_returns_answer_with_sources(test_client, mock_cognee_service):
    mock_cognee_service.search.return_value = {
        "answer": "Based on papers...",
        "sources": [],
        "latency_ms": 500,
    }
    response = test_client.post("/query", json={
        "question": "What is graph memory?",
        "search_mode": "GRAPH_COMPLETION",
    })
    assert response.status_code == 200
    assert "answer" in response.json()

def test_query_rejects_invalid_search_mode(test_client):
    response = test_client.post("/query", json={
        "question": "test", "search_mode": "INVALID_MODE"
    })
    assert response.status_code == 422

def test_detect_returns_contradiction_pair(test_client):
    response = test_client.post("/detect", json={
        "paper_id_a": "2504.19413",
        "paper_id_b": "2501.13956",
    })
    assert response.status_code == 200
    body = response.json()
    assert "label" in body
    assert "confidence" in body
    assert "explanation" in body

def test_detect_rejects_same_paper_id_twice(test_client):
    response = test_client.post("/detect", json={
        "paper_id_a": "2504.19413",
        "paper_id_b": "2504.19413",
    })
    assert response.status_code == 422

def test_contradictions_returns_paginated_list(test_client):
    response = test_client.get("/contradictions?limit=10&offset=0")
    assert response.status_code == 200
    body = response.json()
    assert "total" in body
    assert "contradictions" in body
    assert isinstance(body["contradictions"], list)

def test_contradictions_filters_by_min_confidence(test_client):
    response = test_client.get("/contradictions?min_confidence=0.9")
    assert response.status_code == 200

def test_all_error_responses_have_detail_field(test_client):
    response = test_client.get("/ingest/status/fake-id")
    assert "detail" in response.json()
```

---

## CI Pipeline (GitHub Actions)

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.11"}
      - run: pip install uv && uv sync
      - run: ruff check app/ tests/
      - run: mypy app/ --ignore-missing-imports
      - run: pytest tests/ -v -m "not benchmark" --cov=app --cov-fail-under=70
      - run: docker build -t chronoscholar .
```
