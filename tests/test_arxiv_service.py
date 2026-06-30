from unittest.mock import MagicMock


def test_fetch_returns_list_of_paper_objects(
    arxiv_service,
    mock_arxiv_search: MagicMock,
    mock_arxiv_result: MagicMock,
) -> None:
    mock_arxiv_search.return_value = [mock_arxiv_result]
    papers = arxiv_service.fetch("agent memory", max_results=1)
    assert len(papers) == 1
    assert hasattr(papers[0], "paper_id")


def test_fetch_extracts_clean_paper_id(
    mock_arxiv_result: MagicMock,
) -> None:
    from app.services.arxiv_service import ArxivService

    paper = ArxivService._parse_result(mock_arxiv_result)
    assert "arxiv.org" not in paper.paper_id
    assert "http" not in paper.paper_id
    assert paper.paper_id == "2504.19413"


def test_fetch_respects_max_results_limit(
    arxiv_service,
    mock_arxiv_search: MagicMock,
    mock_arxiv_result: MagicMock,
) -> None:
    mock_arxiv_search.return_value = [mock_arxiv_result] * 20
    papers = arxiv_service.fetch("test", max_results=5)
    assert len(papers) <= 5


def test_fetch_returns_empty_list_for_no_results(
    arxiv_service,
    mock_arxiv_search: MagicMock,
) -> None:
    mock_arxiv_search.return_value = []
    papers = arxiv_service.fetch("xyznonexistent123abc")
    assert papers == []
    assert isinstance(papers, list)


def test_fetch_calls_sleep_between_requests(
    arxiv_service,
    mock_arxiv_search: MagicMock,
    mock_arxiv_result: MagicMock,
    mock_sleep: MagicMock,
) -> None:
    mock_arxiv_search.return_value = [mock_arxiv_result] * 5
    arxiv_service.fetch("test", max_results=5)
    assert mock_sleep.called


def test_fetch_by_id_returns_single_paper(
    arxiv_service,
    mock_arxiv_search: MagicMock,
    mock_arxiv_result: MagicMock,
) -> None:
    mock_arxiv_search.return_value = [mock_arxiv_result]
    paper = arxiv_service.fetch_by_id("2504.19413")
    assert paper is not None
    assert paper.paper_id == "2504.19413"


def test_fetch_by_id_returns_none_for_invalid_id(
    arxiv_service,
    mock_arxiv_search: MagicMock,
) -> None:
    mock_arxiv_search.return_value = []
    paper = arxiv_service.fetch_by_id("0000.00000")
    assert paper is None
    assert mock_arxiv_search.called
