"""Universal LLM Router with Automatic Failover and Multi-Provider Shifting."""

from .exceptions import (
    AllProvidersExhaustedError,
    ConfigurationError,
    LLMRoutingError,
    ProviderExhaustedError,
)
from .models import (
    FailoverEvent,
    FailoverReason,
    KeyStatus,
    LLMRequest,
    LLMResponse,
    Message,
    ProviderConfig,
    ProviderType,
)
from .router import UniversalLLMRouter

__all__ = [
    "UniversalLLMRouter",
    "ProviderConfig",
    "ProviderType",
    "FailoverReason",
    "FailoverEvent",
    "KeyStatus",
    "LLMRequest",
    "LLMResponse",
    "Message",
    "LLMRoutingError",
    "ProviderExhaustedError",
    "AllProvidersExhaustedError",
    "ConfigurationError",
]
