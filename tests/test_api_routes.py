def test_health_returns_200_always():
    pass


def test_ready_returns_200_when_graph_loaded():
    pass


def test_ingest_returns_202_with_run_id():
    pass


def test_ingest_rejects_max_papers_above_100():
    pass


def test_ingest_rejects_empty_query():
    pass


def test_ingest_status_returns_404_for_unknown_run_id():
    pass


def test_query_returns_answer_with_sources():
    pass


def test_query_rejects_invalid_search_mode():
    pass


def test_detect_returns_contradiction_pair():
    pass


def test_detect_rejects_same_paper_id_twice():
    pass


def test_contradictions_returns_paginated_list():
    pass


def test_contradictions_filters_by_min_confidence():
    pass


def test_all_error_responses_have_detail_field():
    pass
