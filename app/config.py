from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

VALID_LLM_PROVIDERS = {"groq", "gemini", "ollama", "fallback"}


class Settings(BaseSettings):
    # APP_LLM_PROVIDER controls ChronoScholar's own LLM client (groq/gemini/…).
    # LLM_PROVIDER is reserved for Cognee's internal config (must be a Cognee LLMProvider value).
    app_llm_provider: str = "groq"
    groq_model: str = "llama-3.1-8b-instant"
    gemini_model: str = "gemini-2.5-flash"
    groq_api_key: str = ""
    gemini_api_key: str = ""
    ollama_base_url: str = ""
    cognee_db_path: str = ""
    cognee_vector_db_path: str = ""
    mlflow_tracking_uri: str = ""
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    arxiv_request_delay: float = 3.0
    contradiction_confidence_threshold: float = 0.7
    cognee_batch_size: int = 15
    llm_fast_mode: bool = Field(default=False)

    @field_validator("app_llm_provider")
    @classmethod
    def validate_llm_provider(cls, value: str) -> str:
        if value not in VALID_LLM_PROVIDERS:
            raise ValueError(
                f"app_llm_provider must be one of {sorted(VALID_LLM_PROVIDERS)}, got {value!r}"
            )
        return value

    @field_validator("contradiction_confidence_threshold")
    @classmethod
    def validate_contradiction_confidence_threshold(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError(
                f"contradiction_confidence_threshold must be between 0.0 and 1.0, got {value}"
            )
        return value
