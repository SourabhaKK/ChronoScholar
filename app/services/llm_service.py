import logging
import time

from app.config import Settings

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Raised when an LLM provider responds with HTTP 429."""


def groq_complete(prompt: str, settings: Settings, system: str = "") -> str:
    """Real Groq SDK call — replaced by the mock_groq_client fixture in tests."""
    from groq import Groq

    from groq.types.chat import ChatCompletionMessageParam

    messages: list[ChatCompletionMessageParam] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    client = Groq(api_key=settings.groq_api_key, timeout=10.0)
    response = client.chat.completions.create(
        model=settings.groq_model,
        messages=messages,
    )
    return response.choices[0].message.content


def gemini_complete(prompt: str, settings: Settings, system: str = "") -> str:
    """Real Gemini SDK call — replaced by the mock_gemini_client fixture in tests."""
    import google.generativeai as genai

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(
        settings.gemini_model,
        system_instruction=system if system else None,
    )
    response = model.generate_content(prompt)
    return response.text


class LLMService:
    MAX_RETRIES = 3
    RATE_LIMIT_RETRIES = 3

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.primary_provider = settings.app_llm_provider
        self.fast_mode = settings.llm_fast_mode

    def complete(self, prompt: str, fallback: str = "", system: str = "") -> str:
        # Tier 1: Primary provider with exponential backoff
        for attempt in range(self.MAX_RETRIES):
            try:
                return self._call_primary(prompt, system)
            except RateLimitError:
                break  # Jump to Tier 2 immediately
            except (ConnectionError, TimeoutError) as exc:
                if attempt < self.MAX_RETRIES - 1:
                    delay = (0.5**attempt) if self.fast_mode else (2**attempt)
                    logger.warning(
                        "Primary provider attempt %d failed, retrying in %ds: %s",
                        attempt + 1, delay, exc,
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        "Primary provider exhausted after %d attempts", self.MAX_RETRIES
                    )
            except Exception as exc:
                logger.error("Primary provider failed with unexpected error: %s", exc)
                break

        # Tier 2: Fallback provider on rate limit
        for attempt in range(self.RATE_LIMIT_RETRIES):
            try:
                return self._call_fallback(prompt, system)
            except RateLimitError:
                delay = (1.0 * (1.5**attempt)) if self.fast_mode else (5 * (2**attempt))
                logger.warning("Fallback provider rate limited, waiting %ds", delay)
                time.sleep(delay)
            except Exception as exc:
                logger.error("Fallback provider failed: %s", exc)
                break

        # Tier 3: Deterministic fallback — zero network calls
        logger.warning("All LLM providers exhausted. Returning deterministic fallback.")
        return fallback

    def _call_primary(self, prompt: str, system: str = "") -> str:
        return groq_complete(prompt, self.settings, system=system)

    def _call_fallback(self, prompt: str, system: str = "") -> str:
        return gemini_complete(prompt, self.settings, system=system)
