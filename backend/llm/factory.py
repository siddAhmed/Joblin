from backend.llm.protocol import LLMProvider
from backend.llm.groq_adapter import GroqAdapter
from backend.llm.cerebras_adapter import CerebrasAdapter
from backend.llm.gemini_adapter import GeminiAdapter


def get_filter_provider(settings: dict) -> LLMProvider:
    provider = settings.get("llm_filter_provider", "groq")
    if provider == "groq":
        return GroqAdapter(
            api_key=settings.get("groq_api_key", ""),
            filter_model=settings.get("groq_filter_model", "llama-3.1-8b-instant"),
            summarize_model=settings.get("groq_summarize_model", "llama-3.3-70b-versatile"),
        )
    if provider == "cerebras":
        return CerebrasAdapter(
            api_key=settings.get("cerebras_api_key", ""),
            model=settings.get("cerebras_model", "gpt-oss-120b"),
        )
    if provider == "gemini":
        return GeminiAdapter(
            api_key=settings.get("gemini_api_key", ""),
            filter_model=settings.get("gemini_filter_model", "gemini-3.1-flash-lite"),
            summarize_model=settings.get("gemini_summarize_model", "gemini-3.1-flash-lite"),
        )
    raise ValueError(f"Unknown filter provider: {provider}")


def get_summarize_provider(settings: dict) -> LLMProvider:
    provider = settings.get("llm_summarize_provider", "groq")
    if provider == "cerebras":
        return CerebrasAdapter(
            api_key=settings.get("cerebras_api_key", ""),
            model=settings.get("cerebras_model", "gpt-oss-120b"),
        )
    if provider == "groq":
        return GroqAdapter(
            api_key=settings.get("groq_api_key", ""),
            filter_model=settings.get("groq_filter_model", "llama-3.1-8b-instant"),
            summarize_model=settings.get("groq_summarize_model", "llama-3.3-70b-versatile"),
        )
    if provider == "gemini":
        return GeminiAdapter(
            api_key=settings.get("gemini_api_key", ""),
            filter_model=settings.get("gemini_filter_model", "gemini-2.0-flash-lite"),
            summarize_model=settings.get("gemini_summarize_model", "gemini-2.0-flash-lite"),
        )
    raise ValueError(f"Unknown summarize provider: {provider}")


def get_tailor_provider(settings: dict) -> LLMProvider:
    return get_summarize_provider(settings)
