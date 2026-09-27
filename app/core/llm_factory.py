import requests
from functools import lru_cache
from langchain_groq import ChatGroq
from app.core.config import settings
from app.utils.logger import logger

def get_available_groq_models(api_key: str) -> list[str]:
    """Queries Groq API for currently active model IDs."""
    if not api_key:
        return []
    try:
        url = "https://api.groq.com/openai/v1/models"
        headers = {"Authorization": f"Bearer {api_key}"}
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            models = [m["id"] for m in data.get("data", [])]
            logger.info(f"Groq API Active Models found: {models}")
            return models
        else:
            logger.warning(f"Groq models API returned status {res.status_code}: {res.text}")
    except Exception as e:
        logger.warning(f"Could not query Groq models API: {e}")
    return []

@lru_cache(maxsize=4)
def get_llm(temperature: float = 0.0, model_name: str = None) -> ChatGroq:
    """
    Centralized factory for initializing and caching ChatGroq instances.
    Auto-detects active Groq models if the requested model returns 404.
    """
    api_key = settings.GROQ_API_KEY
    if not api_key:
        logger.warning("GROQ_API_KEY is missing in settings!")

    requested_model = model_name or settings.GROQ_MODEL or "llama3-8b-8192"
    selected_model = requested_model

    # Auto-validate model availability against Groq API
    active_models = get_available_groq_models(api_key)
    if active_models:
        if requested_model in active_models:
            selected_model = requested_model
        else:
            # Fallback preference order for Groq chat LLMs
            preferred_order = [
                "llama-3.3-70b-versatile",
                "llama3-8b-8192",
                "llama3-70b-8192",
                "llama-3.1-8b-instant",
                "mixtral-8x7b-32768",
                "qwen/qwen3.6-27b",
                "openai/gpt-oss-120b",
                "openai/gpt-oss-20b",
                "groq/compound",
                "gemma2-9b-it"
            ]
            matched = [m for m in preferred_order if m in active_models]
            if matched:
                selected_model = matched[0]
            else:
                # Exclude guard/whisper/audio models
                chat_models = [m for m in active_models if not any(x in m for x in ["guard", "whisper", "orpheus"])]
                selected_model = chat_models[0] if chat_models else active_models[0]
            logger.info(f"Requested model '{requested_model}' not found in Groq active list. Auto-selected '{selected_model}'")

    logger.info(f"Initializing ChatGroq LLM client [model: {selected_model}, temp: {temperature}]")
    return ChatGroq(
        groq_api_key=api_key,
        model_name=selected_model,
        temperature=temperature
    )
