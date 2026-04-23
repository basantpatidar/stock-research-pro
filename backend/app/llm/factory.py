from langchain_core.language_models import BaseChatModel
from app.config import Settings

# Free-tier requests-per-second for each provider (sourced from provider docs)
_FREE_TIER_RPS = {
    "gemini":    4 / 60,   # 5 RPM limit → stay at 4
    "groq":     25 / 60,   # 30 RPM limit → stay at 25
    "cerebras": 25 / 60,   # 30 RPM limit → stay at 25
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


def get_llm(settings: Settings) -> BaseChatModel:
    """
    Returns a LangChain BaseChatModel for the configured provider.
    LangGraph receives this and never knows which provider is behind it.
    Swap MODEL_TYPE in .env — zero code changes needed anywhere else.
    Set LLM_TIER=free to enable conservative rate limiting; LLM_TIER=paid to disable it.
    """
    provider = settings.model_type.lower()

    match provider:

        case "groq":
            from langchain_groq import ChatGroq
            return ChatGroq(
                model=settings.model_name,
                api_key=settings.groq_api_key,
                temperature=0.1,
                max_retries=3,
                rate_limiter=_rate_limiter("groq", settings),
            )

        case "ollama":
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=settings.ollama_model,
                temperature=0.1,
            )

        case "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=settings.model_name,
                google_api_key=settings.gemini_api_key,
                temperature=0.1,
                max_retries=1,  # daily quota won't clear on retry — fail fast
                rate_limiter=_rate_limiter("gemini", settings),
            )

        case "claude":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=settings.model_name,
                api_key=settings.anthropic_api_key,
                temperature=0.1,
                max_retries=3,
            )

        case "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=settings.model_name,
                api_key=settings.openai_api_key,
                temperature=0.1,
                max_retries=3,
            )

        case "openrouter":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=settings.model_name,
                base_url="https://openrouter.ai/api/v1",
                api_key=settings.openrouter_api_key,
                temperature=0.1,
                max_retries=3,
                rate_limiter=_rate_limiter("openrouter", settings),
            )

        case "cerebras":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=settings.model_name,
                base_url="https://api.cerebras.ai/v1",
                api_key=settings.cerebras_api_key,
                temperature=0.1,
                max_retries=3,
                rate_limiter=_rate_limiter("cerebras", settings),
            )

        case _:
            raise ValueError(
                f"Unknown model_type: '{settings.model_type}'. "
                f"Valid options: groq, ollama, gemini, claude, openai, openrouter, cerebras"
            )


def _try_build(provider: str, settings: Settings) -> BaseChatModel | None:
    """Build an LLM for provider, return None if key is missing or build fails."""
    try:
        # model_copy avoids mutating the lru_cache'd Settings singleton
        return get_llm(settings.model_copy(update={"model_type": provider}))
    except Exception:
        return None


def get_llm_with_fallback(settings: Settings) -> BaseChatModel:
    """
    Returns a LangChain runnable that falls back at *runtime* — catches 429s,
    quota errors, and timeouts mid-request, not just missing keys at startup.
    Order: configured provider → groq → cerebras → ollama
    """
    candidates = [settings.model_type]
    if "groq" not in candidates and settings.groq_api_key:
        candidates.append("groq")
    if "cerebras" not in candidates and settings.cerebras_api_key:
        candidates.append("cerebras")
    if "ollama" not in candidates:
        candidates.append("ollama")

    built = [llm for p in candidates if (llm := _try_build(p, settings)) is not None]

    if not built:
        raise RuntimeError("All LLM providers failed to initialise")

    primary, *fallbacks = built
    if not fallbacks:
        return primary

    # .with_fallbacks() retries the chain on any exception at invocation time,
    # so a Gemini 429 or quota error automatically switches to the next provider.
    return primary.with_fallbacks(fallbacks)
