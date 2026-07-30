"""
Unified Ultra-Fast LLM Factory Module for MedAssist AI.

Primary LLM Engine: NVIDIA NIM API (z-ai/glm-5.2) via OpenAI-compatible client.
Fallback Engines: Google Gemini 2.5 Flash / OpenAI models.
"""

import os
from functools import lru_cache
from typing import Optional

from langchain_core.language_models import BaseChatModel
from app.core.settings import settings
from app.utils.logger import get_logger

logger = get_logger("core.llm")


@lru_cache(maxsize=4)
def get_llm(model_name: Optional[str] = None, temperature: float = 0.2) -> Optional[BaseChatModel]:
    """
    Returns a cached LLM instance.
    Primary engine: Google Gemini 2.5 Flash (optimized for ultra-low latency).
    Fallback engine: NVIDIA NIM (z-ai/glm-5.2).
    """
    # 1. NVIDIA NIM Integration (Primary)
    nvidia_key = os.environ.get("NVIDIA_API_KEY") or settings.nvidia_api_key
    nvidia_base = (
        os.environ.get("NVIDIA_BASE_URL") 
        or getattr(settings, "nvidia_base_url", "") 
        or "https://integrate.api.nvidia.com/v1"
    )
    nvidia_model = model_name or settings.nvidia_model

    if nvidia_key and nvidia_key.startswith("nvapi-"):
        try:
            from langchain_openai import ChatOpenAI
            logger.info("Initializing NVIDIA NIM LLM: %s via %s", nvidia_model, nvidia_base)
            model_kwargs = {}
            if settings.llm_enable_thinking:
                model_kwargs = {
                    "extra_body": {
                        "chat_template_kwargs": {"enable_thinking": True},
                        "reasoning_budget": settings.llm_reasoning_budget,
                    }
                }
            return ChatOpenAI(
                base_url=nvidia_base,
                api_key=nvidia_key,
                model=nvidia_model,
                temperature=temperature,
                top_p=0.95,
                max_tokens=settings.llm_max_tokens,
                timeout=settings.llm_timeout_seconds,
                max_retries=1,
                model_kwargs=model_kwargs,
            )
        except Exception as err:
            logger.warning("Failed to initialize NVIDIA NIM ChatOpenAI: %s", err)

    # 2. Google Gemini Fallback
    gemini_key = (
        os.environ.get("GEMINI_API_KEY") 
        or os.environ.get("GOOGLE_API_KEY") 
        or getattr(settings, "gemini_api_key", "")
    )

    if gemini_key and not gemini_key.startswith("nvapi-"):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            target_model = getattr(settings, "gemini_model", "gemini-2.5-flash")
            logger.info("Initializing Google Gemini fallback model: %s", target_model)
            return ChatGoogleGenerativeAI(
                model=target_model,
                google_api_key=gemini_key,
                temperature=temperature,
                max_retries=1,
            )
        except Exception as err:
            logger.warning("Failed to initialize ChatGoogleGenerativeAI: %s", err)

    return None
