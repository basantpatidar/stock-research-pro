from langchain_core.language_models import BaseChatModel
from app.config import Settings


def get_llm(settings: Settings) -> BaseChatModel:
    """
    Returns a LangChain BaseChatModel for the configured provider.
    LangGraph receives this and never knows which provider is behind it.
    Swap MODEL_TYPE in .env — zero code changes needed anywhere else.
    """
    match settings.model_type.lower():

        case "groq":
            from langchain_groq import ChatGroq
            return ChatGroq(
                model=settings.model_name,
                api_key=settings.groq_api_key,
                temperature=0.1,
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
            )

        case "claude":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=settings.model_name,
                api_key=settings.anthropic_api_key,
                temperature=0.1,
            )

        case "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=settings.model_name,
                api_key=settings.openai_api_key,
                temperature=0.1,
            )

        case "openrouter":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=settings.model_name,
                base_url="https://openrouter.ai/api/v1",
                api_key=settings.openrouter_api_key,
                temperature=0.1,
            )

        case "cerebras":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=settings.model_name,
                base_url="https://api.cerebras.ai/v1",
                api_key=settings.cerebras_api_key,
                temperature=0.1,
            )

        case _:
            raise ValueError(
                f"Unknown model_type: '{settings.model_type}'. "
                f"Valid options: groq, ollama, gemini, claude, openai, openrouter, cerebras"
            )


def get_llm_with_fallback(settings: Settings) -> BaseChatModel:
    """
    Tries providers in order. Falls back if a key is missing.
    Useful for background jobs that must not fail silently.
    Order: configured provider → groq → cerebras → ollama
    """
    providers_to_try = [settings.model_type]

    if "groq" not in providers_to_try and settings.groq_api_key:
        providers_to_try.append("groq")
    if "cerebras" not in providers_to_try and settings.cerebras_api_key:
        providers_to_try.append("cerebras")
    if "ollama" not in providers_to_try:
        providers_to_try.append("ollama")

    last_error = None
    for provider in providers_to_try:
        try:
            original_type = settings.model_type
            settings.model_type = provider
            llm = get_llm(settings)
            settings.model_type = original_type
            return llm
        except Exception as e:
            last_error = e
            continue

    raise RuntimeError(
        f"All LLM providers failed. Last error: {last_error}"
    )
