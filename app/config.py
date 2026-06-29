from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_provider: str = "groq"
    groq_model: str = "llama-3.1-8b-instant"
    gemini_model: str = "gemini-1.5-flash"
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
