# All shared fixtures live here exclusively — see TESTING_STRATEGY.md
import time
from unittest.mock import MagicMock

import pytest

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
