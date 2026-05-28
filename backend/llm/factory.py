from backend.llm.protocol import LLMProvider
from backend.llm.groq_adapter import GroqAdapter
from backend.llm.cerebras_adapter import CerebrasAdapter
from backend.llm.gemini_adapter import GeminiAdapter


def get_filter_provider(settings: dict) -> LLMProvider:
    provider = settings.get("llm_filter_provider", "groq")
    if provider == "groq":
        return GroqAdapter(api_key=settings.get("groq_api_key", ""))
    if provider == "cerebras":
        return CerebrasAdapter(api_key=settings.get("cerebras_api_key", ""))
    if provider == "gemini":
        return GeminiAdapter(api_key=settings.get("gemini_api_key", ""))
    raise ValueError(f"Unknown filter provider: {provider}")


def get_summarize_provider(settings: dict) -> LLMProvider:
    provider = settings.get("llm_summarize_provider", "cerebras")
    if provider == "cerebras":
        return CerebrasAdapter(api_key=settings.get("cerebras_api_key", ""))
    if provider == "groq":
        return GroqAdapter(api_key=settings.get("groq_api_key", ""))
    if provider == "gemini":
        return GeminiAdapter(api_key=settings.get("gemini_api_key", ""))
    raise ValueError(f"Unknown summarize provider: {provider}")
