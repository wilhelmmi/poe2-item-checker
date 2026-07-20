from functools import lru_cache

from app.builds.provider import OpenAIBuildProvider
from app.core.config import get_settings, read_openai_api_key
from app.evaluation.provider import EvaluationProviderError


@lru_cache
def get_build_provider() -> OpenAIBuildProvider:
    settings = get_settings()
    api_key = read_openai_api_key(settings)
    if not api_key:
        raise EvaluationProviderError(
            "provider_not_configured", "Die automatische Build-Analyse ist nicht konfiguriert.", 503
        )
    return OpenAIBuildProvider(api_key=api_key, model=settings.openai_model,
        timeout=settings.evaluation_timeout_seconds, max_retries=settings.evaluation_max_retries,
        max_output_tokens=settings.build_analysis_max_output_tokens,
        rate_limit_per_minute=settings.evaluation_rate_limit_per_minute)
