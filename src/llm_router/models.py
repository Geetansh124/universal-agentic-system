"""Data models for Universal LLM Router."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import time


class ProviderType(str, Enum):
    """Supported provider types."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    NVIDIA = "nvidia"
    OPENCODE = "opencode"
    TOGETHER = "together"
    PERPLEXITY = "perplexity"
    COHERE = "cohere"
    OPENAI_COMPATIBLE = "openai_compatible"  # Groq, DeepSeek, Mistral, Ollama, OpenRouter, etc.


PROVIDER_DEFAULT_URLS: Dict[ProviderType, str] = {
    ProviderType.OPENAI: "https://api.openai.com/v1",
    ProviderType.ANTHROPIC: "https://api.anthropic.com/v1",
    ProviderType.GEMINI: "https://generativelanguage.googleapis.com/v1beta",
    ProviderType.NVIDIA: "https://integrate.api.nvidia.com/v1",
    ProviderType.OPENCODE: "https://api.together.xyz/v1",
    ProviderType.TOGETHER: "https://api.together.xyz/v1",
    ProviderType.PERPLEXITY: "https://api.perplexity.ai",
    ProviderType.COHERE: "https://api.cohere.com/v2",
}

PROVIDER_DEFAULT_MODELS: Dict[ProviderType, str] = {
    ProviderType.OPENAI: "gpt-4o-mini",
    ProviderType.ANTHROPIC: "claude-3-5-haiku-20241022",
    ProviderType.GEMINI: "gemini-2.5-flash",
    ProviderType.NVIDIA: "meta/llama-3.3-70b-instruct",
    ProviderType.OPENCODE: "Qwen/Qwen2.5-Coder-32B-Instruct",
    ProviderType.TOGETHER: "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    ProviderType.PERPLEXITY: "sonar",
    ProviderType.COHERE: "command-r-plus-08-2024",
}


class FailoverReason(str, Enum):
    """Reasons for triggering a failover shift."""
    RATE_LIMIT = "rate_limit_429"
    QUOTA_EXHAUSTED = "quota_exhausted"
    AUTH_ERROR = "auth_error_401_403"
    SERVER_ERROR = "server_error_5xx"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    INVALID_RESPONSE = "invalid_response"


@dataclass
class Message:
    """Represents a chat message."""
    role: str  # 'system', 'user', 'assistant'
    content: str

    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class LLMRequest:
    """Normalized LLM request."""
    messages: List[Message]
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2048
    system_prompt: Optional[str] = None
    extra_params: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        """Validate input boundaries."""
        if not self.messages:
            raise ValueError("LLMRequest must contain at least one message.")
        for msg in self.messages:
            if not isinstance(msg.content, str) or not msg.content.strip():
                raise ValueError("Message content cannot be empty or non-string.")
        if not (0.0 <= self.temperature <= 2.0):
            raise ValueError(f"Temperature must be between 0.0 and 2.0, got {self.temperature}.")
        if self.max_tokens <= 0:
            raise ValueError(f"max_tokens must be greater than 0, got {self.max_tokens}.")


@dataclass
class LLMResponse:
    """Normalized LLM response."""
    content: str
    model: str
    provider_name: str
    key_identifier: str
    usage: Dict[str, int] = field(default_factory=dict)
    raw_response: Optional[Dict[str, Any]] = None
    latency_ms: float = 0.0


@dataclass
class ProviderConfig:
    """Configuration for a specific LLM provider."""
    name: str
    provider_type: ProviderType
    model: str
    api_keys: List[str]  # Multiple keys supported for rotation
    priority: int = 1  # Lower number = higher priority
    base_url: Optional[str] = None
    timeout_seconds: float = 30.0
    cooldown_seconds: float = 60.0  # Cooldown time after exhaustion
    headers: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True

    def validate(self) -> None:
        """Validate provider configuration at boundary."""
        if not self.name or not self.name.strip():
            raise ValueError("ProviderConfig name cannot be empty.")
        if not self.api_keys and self.provider_type != ProviderType.OPENAI_COMPATIBLE:
            raise ValueError(f"Provider '{self.name}' must have at least one api_key.")
        if self.timeout_seconds <= 0:
            raise ValueError(f"Provider '{self.name}' timeout must be positive.")
        if self.cooldown_seconds < 0:
            raise ValueError(f"Provider '{self.name}' cooldown cannot be negative.")


@dataclass
class KeyStatus:
    """Tracks state of an individual API key."""
    key: str
    is_exhausted: bool = False
    exhausted_until: float = 0.0
    last_reason: Optional[FailoverReason] = None
    last_error_message: Optional[str] = None
    consecutive_failures: int = 0
    total_calls: int = 0
    successful_calls: int = 0

    @property
    def masked_key(self) -> str:
        """Return masked key for safe logging."""
        if not self.key or len(self.key) <= 8:
            return "***"
        return f"{self.key[:4]}...{self.key[-4:]}"

    def is_available(self, current_time: Optional[float] = None) -> bool:
        """Check if key is available or cooldown has passed."""
        now = current_time if current_time is not None else time.time()
        if not self.is_exhausted:
            return True
        return now >= self.exhausted_until

    def mark_exhausted(self, cooldown_seconds: float, reason: FailoverReason, error_message: str) -> None:
        self.is_exhausted = True
        self.exhausted_until = time.time() + cooldown_seconds
        self.last_reason = reason
        self.last_error_message = error_message
        self.consecutive_failures += 1

    def mark_success(self) -> None:
        self.is_exhausted = False
        self.exhausted_until = 0.0
        self.consecutive_failures = 0
        self.successful_calls += 1


@dataclass
class FailoverEvent:
    """Records a failover shift event."""
    timestamp: float
    from_provider: str
    from_key_masked: str
    to_provider: Optional[str]
    to_key_masked: Optional[str]
    reason: FailoverReason
    error_message: str
