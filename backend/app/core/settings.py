from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "MedAssist AI"
    app_env: str = "development"
    debug: bool = True
    # Secrets must be supplied through the environment or backend/.env.
    secret_key: str = ""
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # JWT
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Database
    mongodb_url: str = "mongodb://localhost:27017"

    # ChromaDB
    chroma_host: str = "chromadb"
    chroma_port: int = 8000
    chroma_collection: str = "medassist_docs"

    # NVIDIA NIM AI Model Integration
    nvidia_api_key: str = ""
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "z-ai/glm-5.2"
    llm_max_tokens: int = 2048
    llm_timeout_seconds: float = 30.0
    llm_enable_thinking: bool = False
    llm_reasoning_budget: int = 2048

    # OpenAI & Gemini AI Models
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    gemini_api_key: str = ""
    google_api_key: str = ""
    gemini_maps_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # Google Maps Platform (Places API, Geocoding API, Distance Matrix API)
    # Get from: console.cloud.google.com → APIs & Services → Credentials
    google_maps_api_key: str = ""

    # Optional Twilio WhatsApp delivery.
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_number: str = "whatsapp:+14155238886"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def validate_runtime_settings() -> None:
    """Fail early instead of serving JWTs signed with a known default secret."""
    if not settings.secret_key:
        raise RuntimeError(
            "SECRET_KEY is required. Copy backend/.env.example to backend/.env "
            "and configure a strong, unique value."
        )
