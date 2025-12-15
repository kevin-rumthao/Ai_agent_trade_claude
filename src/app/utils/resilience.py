from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from app.config import settings
import logging

logger = logging.getLogger(__name__)

def is_retryable_exception(exception: Exception) -> bool:
    """Check if exception is worth retrying."""
    # Don't retry on ValueError (user error/bad input)
    if isinstance(exception, ValueError):
        return False
    # Don't retry on ImportError or SyntaxError
    if isinstance(exception, (ImportError, SyntaxError)):
        return False
    # Provide a log message for the retry
    logger.warning(f"Retrying on exception: {type(exception).__name__}: {exception}")
    return True

def api_retry_policy():
    """Create a tenacity retry decorator based on settings."""
    return retry(
        stop=stop_after_attempt(settings.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=settings.RETRY_DELAY_MIN, max=settings.RETRY_DELAY_MAX),
        retry=retry_if_exception(is_retryable_exception),
        reraise=True
    )
