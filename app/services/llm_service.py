class LLMService:
    MAX_RETRIES = 3
    RATE_LIMIT_RETRIES = 3

    def __init__(self, settings):
        ...

    def complete(self, prompt: str, fallback: str = "") -> str:
        ...

    def _call_primary(self, prompt: str) -> str:
        ...

    def _call_fallback(self, prompt: str) -> str:
        ...
