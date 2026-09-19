"""Custom exceptions for LLM Router."""

from typing import Optional
from .models import FailoverReason


class LLMRoutingError(Exception):
    """Base exception for routing errors."""
    pass


class ConfigurationError(LLMRoutingError):
    """Raised when configuration is invalid."""
    pass


class ProviderExhaustedError(LLMRoutingError):
    """Raised when a specific provider or key encounters an exhaustion error."""

    def __init__(
        self,
        provider_name: str,
        reason: FailoverReason,
        message: str,
        status_code: Optional[int] = None,
        retry_after: Optional[float] = None,
    ):
        self.provider_name = provider_name
        self.reason = reason
        self.status_code = status_code
        self.retry_after = retry_after
        super().__init__(f"Provider '{provider_name}' exhausted ({reason.value}): {message}")


class AllProvidersExhaustedError(LLMRoutingError):
    """Raised when all configured providers and keys in the fallback pool are exhausted."""

    def __init__(self, message: str = "All providers and API keys in the fallback chain are exhausted."):
        super().__init__(message)
