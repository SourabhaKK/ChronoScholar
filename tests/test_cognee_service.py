from unittest.mock import AsyncMock


def test_cognee_service_initialises_with_graph_loaded_false(cognee_service) -> None:
    assert cognee_service.graph_loaded is False


async def test_run_ingestion_calls_add_then_cognify_for_each_batch(
    cognee_service,
    mock_cognee_add: AsyncMock,
    mock_cognee_cognify: AsyncMock,
    five_paper_corpus,
) -> None:
    await cognee_service.run_ingestion(five_paper_corpus, "test-run-id", {})
    assert mock_cognee_add.called
    assert mock_cognee_cognify.called


async def test_run_ingestion_sets_graph_loaded_true_after_completion(
    cognee_service,
    mock_cognee_add: AsyncMock,
    mock_cognee_cognify: AsyncMock,
    five_paper_corpus,
) -> None:
    await cognee_service.run_ingestion(five_paper_corpus, "test-run-id", {})
    assert cognee_service.graph_loaded is True


async def test_run_ingestion_updates_run_store_progress_during_execution(
    cognee_service,
    mock_cognee_add: AsyncMock,
    mock_cognee_cognify: AsyncMock,
    five_paper_corpus,
) -> None:
    run_store: dict = {"test-run-id": {"progress_percent": 0}}
    await cognee_service.run_ingestion(five_paper_corpus, "test-run-id", run_store)
    assert run_store["test-run-id"]["progress_percent"] > 0


async def test_search_calls_cognee_search_with_correct_search_type(
    cognee_service,
    mock_cognee_search: AsyncMock,
) -> None:
    mock_cognee_search.return_value = []
    await cognee_service.search("What is graph memory?", mode="GRAPH_COMPLETION")
    assert mock_cognee_search.called


async def test_get_stats_returns_dict_with_required_keys(cognee_service) -> None:
    stats = await cognee_service.get_stats()
    assert "paper_count" in stats
    assert "entity_count" in stats
    assert "edge_count" in stats


async def test_run_ingestion_handles_empty_paper_list_gracefully(
    cognee_service,
    mock_cognee_add: AsyncMock,
    mock_cognee_cognify: AsyncMock,
) -> None:
    result = await cognee_service.run_ingestion([], "test-run-id", {})
    assert result is not None
