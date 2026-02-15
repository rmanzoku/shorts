"""Shared utilities: retry logic, helpers."""

import functools
import time

import click


def retry_on_rate_limit(max_retries: int = 3, base_delay: float = 5.0):
    """Decorator that retries API calls on rate limit errors with exponential backoff.

    Handles both OpenAI and Google Gemini API errors.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        raise
                    if _is_retryable(e):
                        delay = base_delay * (2**attempt)
                        click.echo(f"Rate limited / server error. Retrying in {delay:.0f}s...")
                        time.sleep(delay)
                    else:
                        raise

        return wrapper

    return decorator


def _is_retryable(exc: Exception) -> bool:
    """Check if an exception is retryable (rate limit or server error)."""
    # OpenAI errors
    try:
        from openai import APIError, RateLimitError

        if isinstance(exc, RateLimitError):
            return True
        if isinstance(exc, APIError) and exc.status_code and exc.status_code >= 500:
            return True
    except ImportError:
        pass

    # Google Gemini errors
    try:
        from google.genai.errors import APIError as GeminiAPIError
        from google.genai.errors import ServerError

        if isinstance(exc, ServerError):
            return True
        if isinstance(exc, GeminiAPIError) and hasattr(exc, "code") and exc.code == 429:
            return True
    except ImportError:
        pass

    return False
