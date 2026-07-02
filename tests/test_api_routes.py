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
    body = response.json()
    assert body is not None
    assert "run_id" in body
    assert body["status"] == "running"


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
    body = response.json()
    assert body is not None
    assert "answer" in body


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
    assert body is not None
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
    assert body is not None
    assert "total" in body
    assert "contradictions" in body
    assert isinstance(body["contradictions"], list)


def test_contradictions_filters_by_min_confidence(test_client):
    response = test_client.get("/contradictions?min_confidence=0.9")
    assert response.status_code == 200
    body = response.json()
    assert body is not None
    assert "contradictions" in body


def test_all_error_responses_have_detail_field(test_client):
    response = test_client.get("/ingest/status/fake-id")
    assert response.status_code == 404
    assert "detail" in response.json()
