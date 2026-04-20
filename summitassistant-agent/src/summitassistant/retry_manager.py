"""Retry logic with exponential backoff."""

import asyncio
from typing import Callable, Any, Tuple, Type
import logging

logger = logging.getLogger(__name__)


class RetryManager:
    """Implements exponential backoff retry logic."""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        """Initialize retry manager.
        
        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds for exponential backoff
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        logger.info(f"RetryManager initialized with max_retries={max_retries}")

    async def execute_with_retry(
        self,
        operation: Callable,
        retryable_exceptions: Tuple[Type[Exception], ...]
    ) -> Any:
        """Execute operation with exponential backoff retry.
        
        Args:
            operation: Async callable to execute
            retryable_exceptions: Tuple of exception types to retry on
            
        Returns:
            Result of the operation
            
        Raises:
            Exception: If all retries are exhausted
        """
        for attempt in range(self.max_retries + 1):
            try:
                return await operation()
            except retryable_exceptions as e:
                if attempt == self.max_retries:
                    logger.error(f"All {self.max_retries} retries exhausted: {e}")
                    raise
                
                delay = self.base_delay * (2 ** attempt)
                logger.warning(
                    f"Retry {attempt + 1}/{self.max_retries} after {delay}s: {e}"
                )
                await asyncio.sleep(delay)
