import time
import asyncio
from typing import Callable, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception, RetryCallState
from app.config import settings
import logging
from functools import wraps

logger = logging.getLogger(__name__)

class CircuitBreakerOpenException(Exception):
    """Raised when the circuit breaker is open."""
    pass

class CircuitBreaker:
    """Simple circuit breaker pattern."""
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"  # CLOSED, OPEN

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        logger.warning(f"Circuit Breaker recorded failure {self.failures}/{self.failure_threshold}")
        if self.failures >= self.failure_threshold:
            if self.state == "CLOSED":
                logger.critical(f"Circuit Breaker OPENED after {self.failures} failures")
                self.state = "OPEN"

    def record_success(self):
        if self.state == "OPEN":
            logger.info("Circuit Breaker CLOSED (recovered)")
        elif self.failures > 0:
            logger.info("Circuit Breaker failure count reset")
            
        self.state = "CLOSED"
        self.failures = 0

    def check(self):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                # Allow one trial (in a real half-open impl, we'd limit concurrency here)
                pass
            else:
                remaining = int(self.recovery_timeout - (time.time() - self.last_failure_time))
                raise CircuitBreakerOpenException(f"Circuit breaker is OPEN. Retrying in {remaining}s")

# Global circuit breaker instance for API calls
api_circuit_breaker = CircuitBreaker()

def is_retryable_exception(exception: Exception) -> bool:
    """Check if exception is worth retrying."""
    # Don't retry on ValueError (user error/bad input)
    if isinstance(exception, ValueError):
        return False
    # Don't retry on ImportError or SyntaxError
    if isinstance(exception, (ImportError, SyntaxError)):
        return False
    # Don't retry on CircuitBreakerOpenException (let it propagate immediately)
    if isinstance(exception, CircuitBreakerOpenException):
        return False
        
    # Provide a log message for the retry
    # logger.warning(f"Retrying on exception: {type(exception).__name__}: {exception}")
    return True

def before_sleep_log(retry_state: RetryCallState):
    """Log when a retry is about to happen."""
    if retry_state.outcome:
         exception = retry_state.outcome.exception()
         logger.warning(
            f"Retrying {retry_state.fn.__name__} due to {type(exception).__name__}: {exception}. "
            f"Next attempt in {retry_state.next_action.sleep}s... "
            f"(Attempt {retry_state.attempt_number})"
        )

def retry_error_callback(retry_state: RetryCallState):
    """Callback when retries are exhausted."""
    exception = retry_state.outcome.exception()
    logger.critical(f"GIVE UP: {retry_state.fn.__name__} failed after {retry_state.attempt_number} attempts. Last error: {exception}")
    # Record failure to circuit breaker
    api_circuit_breaker.record_failure()
    # Return the exception to be raised
    raise exception

def api_retry_policy():
    """Create a tenacity retry decorator based on settings with circuit breaker integration."""
    
    # The retry decorator from tenacity
    tenacity_decorator = retry(
        stop=stop_after_attempt(settings.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=settings.RETRY_DELAY_MIN, max=settings.RETRY_DELAY_MAX),
        retry=retry_if_exception(is_retryable_exception),
        before_sleep=before_sleep_log,
        retry_error_callback=retry_error_callback,
        reraise=True
    )

    def decorator(func: Callable) -> Callable:
        # Wrap the function to check circuit breaker first AND record success
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 1. Check Circuit Breaker BEFORE even trying
            api_circuit_breaker.check()
            
            # 2. Execute with Retry Logic
            # Note: We need to apply the tenacity retry logic to the actual execution
            # But we can't just call func() because we want to retry if func() fails.
            # So we wrap the execution in the tenacity_decorator
            
            @tenacity_decorator
            async def _execute_with_retries():
                return await func(*args, **kwargs)
                
            result = await _execute_with_retries()
            
            # 3. If we get here, it was successful
            api_circuit_breaker.record_success()
            return result
            
        return wrapper
        
    return decorator
