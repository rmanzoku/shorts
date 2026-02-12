"""Shared utilities: retry logic, helpers."""

import functools
import time

import click
from openai import APIError, RateLimitError


def retry_on_rate_limit(max_retries: int = 3, base_delay: float = 5.0):
    """Decorator that retries API calls on rate limit errors with exponential backoff."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except RateLimitError:
                    if attempt == max_retries:
                        raise
                    delay = base_delay * (2**attempt)
                    click.echo(f"Rate limited. Retrying in {delay:.0f}s...")
                    time.sleep(delay)
                except APIError as e:
                    if attempt == max_retries:
                        raise
                    if e.status_code and e.status_code >= 500:
                        delay = base_delay * (2**attempt)
                        click.echo(f"Server error. Retrying in {delay:.0f}s...")
                        time.sleep(delay)
                    else:
                        raise

        return wrapper

    return decorator
