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
    from app.services.llm_service import LLMService, RateLimitError
    mock_groq_client.side_effect = RateLimitError("429")
    mock_gemini_client.return_value = "gemini response"
    service = LLMService(settings=mock_settings)
    assert service.complete("test prompt") == "gemini response"


def test_complete_returns_fallback_string_when_all_providers_fail(
        mock_settings, mock_groq_client, mock_gemini_client):
    from app.services.llm_service import LLMService, RateLimitError
    mock_groq_client.side_effect = RateLimitError("429")
    mock_gemini_client.side_effect = RateLimitError("429")
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
    delays = [call.args[0] for call in mock_sleep.call_args_list]
    assert delays[1] >= delays[0]
