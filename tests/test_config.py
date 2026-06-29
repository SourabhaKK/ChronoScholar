import pytest


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
