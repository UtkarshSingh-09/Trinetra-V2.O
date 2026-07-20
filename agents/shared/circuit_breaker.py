import time
import logging
from functools import wraps

logger = logging.getLogger("trinetra.circuit-breaker")

class CircuitBreakerError(Exception):
    """Raised when a call is blocked because the circuit breaker is open."""
    pass

class CircuitBreaker:
    """
    Lightweight state-machine circuit breaker for external agent API integration.
    Supports three states: CLOSED, OPEN, and HALF-OPEN.
    """
    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN
        self.failure_count = 0
        self.last_failure_time = 0.0

    def call(self, func, *args, **kwargs):
        """Execute the wrapped function under the state machine constraints."""
        current_time = time.time()
        
        # Check if the circuit breaker can transition from OPEN to HALF-OPEN
        if self.state == "OPEN":
            if current_time - self.last_failure_time > self.recovery_timeout:
                logger.info(f"⚡ Circuit Breaker [{self.name}] transitioning from OPEN to HALF-OPEN.")
                self.state = "HALF-OPEN"
            else:
                raise CircuitBreakerError(
                    f"Call blocked: Circuit Breaker [{self.name}] is OPEN. "
                    f"Remaining cooling time: {self.recovery_timeout - (current_time - self.last_failure_time):.1f}s"
                )

        try:
            result = func(*args, **kwargs)
            
            # If the trial call in HALF-OPEN succeeds, close the circuit
            if self.state == "HALF-OPEN":
                logger.info(f"⚡ Circuit Breaker [{self.name}] trial call succeeded. Transitioning to CLOSED.")
                self.state = "CLOSED"
                self.failure_count = 0
                
            return result
        except Exception as e:
            self._handle_failure(current_time)
            raise e

    def _handle_failure(self, current_time: float):
        self.failure_count += 1
        self.last_failure_time = current_time
        logger.warning(
            f"⚠️ Circuit Breaker [{self.name}] recorded a failure. "
            f"Failure count: {self.failure_count}/{self.failure_threshold}. Current state: {self.state}"
        )
        
        if self.state in ["CLOSED", "HALF-OPEN"] and self.failure_count >= self.failure_threshold:
            logger.error(
                f"🚨 Circuit Breaker [{self.name}] tripped! Transitioning to OPEN for {self.recovery_timeout}s."
            )
            self.state = "OPEN"

    def decorator(self):
        """Return a decorator to easily wrap functions."""
        def wrapper_decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return self.call(func, *args, **kwargs)
            return wrapper
        return wrapper_decorator
