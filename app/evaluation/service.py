from functools import lru_cache

from app.core.config import get_settings, read_openai_api_key
from app.evaluation.openai_provider import OpenAIEvaluationProvider
from app.evaluation.provider import EvaluationProvider, EvaluationProviderError


@lru_cache
def get_evaluation_provider() -> EvaluationProvider:
    try:
        settings = get_settings()
        api_key = read_openai_api_key(settings)
        if not api_key:
            raise EvaluationProviderError(
                "provider_not_configured", "Die AI-Bewertung ist nicht konfiguriert.", 503
            )
        return OpenAIEvaluationProvider(
            api_key=api_key, model=settings.openai_model,
            reasoning_effort=settings.openai_reasoning_effort,
            timeout=settings.evaluation_timeout_seconds, max_retries=settings.evaluation_max_retries,
            max_input_chars=settings.evaluation_max_input_chars,
            max_output_tokens=settings.evaluation_max_output_tokens,
            rate_limit_per_minute=settings.evaluation_rate_limit_per_minute,
        )
    except EvaluationProviderError:
        raise
    except Exception as exc:
        # Initialization details may contain environment values or local paths; keep them private.
        raise EvaluationProviderError(
            "provider_not_configured", "Die AI-Bewertung ist nicht konfiguriert.", 503
        ) from exc
