import json


def test_detect_returns_contradiction_for_known_conflicting_papers(
    contradiction_service, paper_mem0, paper_zep
) -> None:
    result = contradiction_service.detect(paper_mem0, paper_zep)
    assert result.label == "contradicts"
    assert result.confidence > 0.0


def test_detect_result_matches_contradiction_pair_schema(
    contradiction_service, paper_mem0, paper_zep
) -> None:
    from app.schemas.contradiction import ContradictionPair

    result = contradiction_service.detect(paper_mem0, paper_zep)
    assert isinstance(result, ContradictionPair)
    assert result.label in {"contradicts", "supports", "extends", "unrelated"}
    assert 0.0 <= result.confidence <= 1.0


def test_detect_never_returns_empty_explanation(
    contradiction_service, paper_mem0, paper_zep
) -> None:
    result = contradiction_service.detect(paper_mem0, paper_zep)
    assert result.explanation is not None
    assert len(result.explanation.strip()) > 0


def test_detect_never_returns_empty_claims(
    contradiction_service, paper_mem0, paper_zep
) -> None:
    result = contradiction_service.detect(paper_mem0, paper_zep)
    assert len(result.claim_a.strip()) > 0
    assert len(result.claim_b.strip()) > 0


def test_detect_falls_back_when_llm_returns_invalid_json(
    contradiction_service, mock_llm_service, paper_mem0, paper_zep
) -> None:
    mock_llm_service.complete.return_value = "I cannot determine the relationship."
    result = contradiction_service.detect(paper_mem0, paper_zep)
    assert result.detection_method == "fallback"
    assert result.label == "unrelated"
    assert result.confidence == 0.0


def test_detect_falls_back_when_llm_returns_wrong_schema(
    contradiction_service, mock_llm_service, paper_mem0, paper_zep
) -> None:
    mock_llm_service.complete.return_value = '{"wrong_field": "value"}'
    result = contradiction_service.detect(paper_mem0, paper_zep)
    assert result.detection_method == "fallback"


def test_detect_falls_back_when_llm_raises(
    contradiction_service, mock_llm_service, paper_mem0, paper_zep
) -> None:
    mock_llm_service.complete.side_effect = Exception("LLM unavailable")
    result = contradiction_service.detect(paper_mem0, paper_zep)
    assert result.detection_method == "fallback"


def test_detect_returns_unrelated_for_clearly_different_papers(
    contradiction_service, mock_llm_service, paper_mem0, paper_unrelated
) -> None:
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
    contradiction_service, five_paper_corpus
) -> None:
    results = contradiction_service.detect_batch(five_paper_corpus)
    expected_pairs = len(five_paper_corpus) * (len(five_paper_corpus) - 1) // 2
    assert len(results) == expected_pairs


def test_detect_uses_prompt_from_prompts_module(
    contradiction_service, mock_llm_service, paper_mem0, paper_zep
) -> None:
    contradiction_service.detect(paper_mem0, paper_zep)
    call_args = mock_llm_service.complete.call_args[0][0]
    assert paper_mem0.paper_id in call_args
    assert paper_zep.paper_id in call_args
