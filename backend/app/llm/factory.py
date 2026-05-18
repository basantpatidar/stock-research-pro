from langchain_core.language_models import BaseChatModel

from app.config import Settings

# Free-tier requests-per-second for each provider (sourced from provider docs)
_FREE_TIER_RPS = {
    "gemini": 4 / 60,  # 5 RPM limit → stay at 4
    "groq": 25 / 60,  # 30 RPM limit → stay at 25
    "cerebras": 25 / 60,  # 30 RPM limit → stay at 25
    "openrouter": 5 / 60,  # varies by model; conservative default
}


def _rate_limiter(provider: str, settings: Settings):
    """Returns an InMemoryRateLimiter for free tier, None for paid."""
    if settings.llm_tier.lower() != "free":
        return None
    rps = _FREE_TIER_RPS.get(provider)
    if rps is None:
        return None
    from langchain_core.rate_limiters import InMemoryRateLimiter

    return InMemoryRateLimiter(requests_per_second=rps)


def _build_llm(provider: str, model: str, settings: Settings) -> BaseChatModel:
    """
    Instantiates a LangChain BaseChatModel for the given provider + model name.
    Separated from get_llm() so any provider+model combo can be built independently
    of what's in settings.model_type / settings.model_name.
    """
    match provider.lower():

        case "groq":
            from langchain_groq import ChatGroq

            return ChatGroq(
                model=model,
                api_key=settings.groq_api_key,
                temperature=0.1,
                max_retries=3,
                rate_limiter=_rate_limiter("groq", settings),
            )

        case "ollama":
            from langchain_ollama import ChatOllama

            return ChatOllama(
                model=model,
                temperature=0.1,
            )

        case "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI

            return ChatGoogleGenerativeAI(
                model=model,
                google_api_key=settings.gemini_api_key,
                temperature=0.1,
                max_retries=1,  # daily quota won't clear on retry — fail fast
                rate_limiter=_rate_limiter("gemini", settings),
            )

        case "claude":
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model=model,
                api_key=settings.anthropic_api_key,
                temperature=0.1,
                max_retries=3,
            )

        case "openai":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=model,
                api_key=settings.openai_api_key,
                temperature=0.1,
                max_retries=3,
            )

        case "openrouter":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=model,
                base_url="https://openrouter.ai/api/v1",
                api_key=settings.openrouter_api_key,
                temperature=0.1,
                max_retries=3,
                rate_limiter=_rate_limiter("openrouter", settings),
            )

        case "cerebras":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=model,
                base_url="https://api.cerebras.ai/v1",
                api_key=settings.cerebras_api_key,
                temperature=0.1,
                max_retries=3,
                rate_limiter=_rate_limiter("cerebras", settings),
            )

        case _:
            raise ValueError(
                f"Unknown provider: '{provider}'. "
                f"Valid options: groq, ollama, gemini, claude, openai, openrouter, cerebras"
            )


def get_llm(settings: Settings) -> BaseChatModel:
    """Returns the default LLM (model_type / model_name from settings)."""
    return _build_llm(settings.model_type, settings.model_name, settings)


def get_llm_for_task(task: str, settings: Settings) -> BaseChatModel:
    """
    Returns an LLM configured for the given task: "agent", "tier2", or "tier3".
    Falls back to model_type / model_name when no task-specific override is set.

    Two models from the same provider are fine — e.g. tier2=gemini/gemini-2.5-flash
    and tier3=gemini/gemini-2.5-pro both use GEMINI_API_KEY, different model names.

    Example .env overrides:
        LLM_AGENT_TYPE=groq
        LLM_AGENT_MODEL=llama-3.3-70b-versatile
        LLM_TIER2_TYPE=gemini
        LLM_TIER2_MODEL=gemini-2.5-flash
        LLM_TIER3_TYPE=claude
        LLM_TIER3_MODEL=claude-haiku-4-5-20251001
    """
    provider = getattr(settings, f"llm_{task}_type", "") or settings.model_type
    model = getattr(settings, f"llm_{task}_model", "") or settings.model_name
    return _build_llm(provider, model, settings)


def _try_build(provider: str, model: str, settings: Settings) -> BaseChatModel | None:
    """Build an LLM for provider+model, return None if key is missing or build fails."""
    try:
        return _build_llm(provider, model, settings)
    except Exception:
        return None


def get_llm_with_fallback(settings: Settings, task: str = "agent") -> BaseChatModel:
    """
    Returns a LangChain runnable that falls back at *runtime* — catches 429s,
    quota errors, and timeouts mid-request, not just missing keys at startup.

    Uses task-specific config as the primary model (falls back to model_type if unset).
    Fallback chain: task-configured primary → groq → cerebras → ollama
    """
    primary_provider = getattr(settings, f"llm_{task}_type", "") or settings.model_type
    primary_model = getattr(settings, f"llm_{task}_model", "") or settings.model_name

    candidates: list[tuple[str, str]] = [(primary_provider, primary_model)]

    if "groq" != primary_provider and settings.groq_api_key:
        candidates.append(("groq", "llama-3.3-70b-versatile"))
    if "cerebras" != primary_provider and settings.cerebras_api_key:
        candidates.append(("cerebras", "llama3.3-70b"))
    if "ollama" != primary_provider:
        candidates.append(("ollama", settings.ollama_model))

    built = [llm for p, m in candidates if (llm := _try_build(p, m, settings)) is not None]

    if not built:
        raise RuntimeError("All LLM providers failed — no valid model could be constructed.")

    primary, *fallbacks = built
    return primary.with_fallbacks(fallbacks) if fallbacks else primary
