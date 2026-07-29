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
    secret_key: str = "dev-secret-key-replace-in-production"
    api_v1_prefix: str = "/api/v1"

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
    nvidia_api_key: str = "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"
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "z-ai/glm-5.2"

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


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
