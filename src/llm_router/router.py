"""Universal LLM Router with automatic failover, multi-key rotation, and cross-provider shifting."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Type

from .exceptions import (
    AllProvidersExhaustedError,
    ConfigurationError,
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
    PROVIDER_DEFAULT_MODELS,
    PROVIDER_DEFAULT_URLS,
)
from .providers.anthropic_adapter import AnthropicAdapter
from .providers.base import BaseLLMAdapter
from .providers.cohere_adapter import CohereAdapter
from .providers.gemini_adapter import GeminiAdapter
from .providers.nvidia_adapter import NvidiaAdapter
from .providers.opencode_adapter import OpenCodeAdapter
from .providers.openai_adapter import OpenAIAdapter

logger = logging.getLogger("llm_router")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [llm_router] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class UniversalLLMRouter:
    """
    Unified router that executes LLM requests across any provider
    and automatically shifts to fallback keys and providers upon exhaustion.
    """

    ADAPTER_MAP: Dict[ProviderType, Type[BaseLLMAdapter]] = {
        ProviderType.OPENAI: OpenAIAdapter,
        ProviderType.ANTHROPIC: AnthropicAdapter,
        ProviderType.GEMINI: GeminiAdapter,
        ProviderType.NVIDIA: NvidiaAdapter,
        ProviderType.OPENCODE: OpenCodeAdapter,
        ProviderType.TOGETHER: OpenAIAdapter,
        ProviderType.PERPLEXITY: OpenAIAdapter,
        ProviderType.COHERE: CohereAdapter,
        ProviderType.OPENAI_COMPATIBLE: OpenAIAdapter,
    }

    def __init__(self, providers: Optional[List[ProviderConfig]] = None):
        self.providers: List[ProviderConfig] = []
        self._adapters: Dict[str, BaseLLMAdapter] = {}
        self._key_statuses: Dict[str, List[KeyStatus]] = {}
        self.failover_history: List[FailoverEvent] = []

        if providers:
            for p in providers:
                self.add_provider(p)

    def add_provider(self, config: ProviderConfig) -> None:
        """Add a provider configuration to the router."""
        # Auto-populate official default base URL and model if omitted
        if not config.base_url and config.provider_type in PROVIDER_DEFAULT_URLS:
            config.base_url = PROVIDER_DEFAULT_URLS[config.provider_type]
        if not config.model and config.provider_type in PROVIDER_DEFAULT_MODELS:
            config.model = PROVIDER_DEFAULT_MODELS[config.provider_type]

        config.validate()
        adapter_cls = self.ADAPTER_MAP.get(config.provider_type)
        if not adapter_cls:
            raise ConfigurationError(f"Unsupported provider type: {config.provider_type}")

        # Check for duplicate names
        if any(p.name == config.name for p in self.providers):
            raise ConfigurationError(f"Provider with name '{config.name}' already exists.")

        self.providers.append(config)
        # Sort providers by priority (ascending: 1 = top priority)
        self.providers.sort(key=lambda p: p.priority)

        self._adapters[config.name] = adapter_cls(config)
        self._key_statuses[config.name] = [
            KeyStatus(key=key) for key in config.api_keys
        ] if config.api_keys else [KeyStatus(key="")]

    def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Execute request with automatic failover across keys and providers.
        Input validation is enforced at system boundary.
        """
        request.validate()

        if not self.providers:
            raise ConfigurationError("No providers configured in router.")

        now = time.time()
        attempted_reasons: List[str] = []

        # Find next candidate key across all providers
        for p_idx, provider in enumerate(self.providers):
            if not provider.enabled:
                continue

            adapter = self._adapters[provider.name]
            key_statuses = self._key_statuses[provider.name]

            for k_idx, key_status in enumerate(key_statuses):
                # Check cooldown / availability
                if not key_status.is_available(now):
                    cooldown_left = int(key_status.exhausted_until - now)
                    logger.debug(
                        f"Skipping {provider.name} [{key_status.masked_key}]: in cooldown for {cooldown_left}s"
                    )
                    attempted_reasons.append(
                        f"{provider.name}[{key_status.masked_key}] exhausted (cooldown: {cooldown_left}s)"
                    )
                    continue

                # Key is available (or has cooled down)
                if key_status.is_exhausted and now >= key_status.exhausted_until:
                    logger.info(
                        f"Cooldown expired for {provider.name} [{key_status.masked_key}]. Restoring key to active."
                    )
                    key_status.is_exhausted = False

                key_status.total_calls += 1

                try:
                    logger.debug(f"Routing request to {provider.name} ({provider.model}) using key {key_status.masked_key}")
                    response = adapter.execute(request, key_status)
                    key_status.mark_success()
                    return response

                except ProviderExhaustedError as err:
                    cooldown = err.retry_after or provider.cooldown_seconds
                    key_status.mark_exhausted(cooldown, err.reason, str(err))

                    # Determine next shift destination for logging
                    next_dest = self._peek_next_available(p_idx, k_idx + 1)
                    next_provider_name = next_dest[0].name if next_dest else None
                    next_key_masked = next_dest[1].masked_key if next_dest else None

                    event = FailoverEvent(
                        timestamp=time.time(),
                        from_provider=provider.name,
                        from_key_masked=key_status.masked_key,
                        to_provider=next_provider_name,
                        to_key_masked=next_key_masked,
                        reason=err.reason,
                        error_message=str(err),
                    )
                    self.failover_history.append(event)

                    shift_msg = (
                        f"-> SHIFTING to {next_provider_name} [{next_key_masked}]"
                        if next_provider_name
                        else "-> NO MORE ACTIVE PROVIDERS"
                    )
                    logger.warning(
                        f"[AUTOMATIC FAILOVER] Provider '{provider.name}' [{key_status.masked_key}] "
                        f"EXHAUSTED ({err.reason.value}). Cooldown: {cooldown}s. {shift_msg}"
                    )
                    attempted_reasons.append(f"{provider.name}[{key_status.masked_key}]: {str(err)}")
                    continue

                except Exception as err:
                    # Generic unexpected error
                    key_status.mark_exhausted(provider.cooldown_seconds, FailoverReason.INVALID_RESPONSE, str(err))
                    attempted_reasons.append(f"{provider.name}[{key_status.masked_key}]: Unexpected error: {str(err)}")
                    logger.error(f"Error on {provider.name} [{key_status.masked_key}]: {err}")
                    continue

        # All providers and keys failed
        summary = " | ".join(attempted_reasons)
        raise AllProvidersExhaustedError(
            f"All {len(self.providers)} providers and their keys are exhausted or unavailable. "
            f"Failure breakdown: {summary}"
        )

    def _peek_next_available(self, start_p_idx: int, start_k_idx: int) -> Optional[Tuple[ProviderConfig, KeyStatus]]:
        """Find next available provider and key without modifying state."""
        now = time.time()
        for p_idx in range(start_p_idx, len(self.providers)):
            provider = self.providers[p_idx]
            if not provider.enabled:
                continue
            key_statuses = self._key_statuses[provider.name]
            k_start = start_k_idx if p_idx == start_p_idx else 0
            for k_idx in range(k_start, len(key_statuses)):
                k_stat = key_statuses[k_idx]
                if k_stat.is_available(now):
                    return provider, k_stat
        return None

    def prompt(self, user_prompt: str, system_prompt: Optional[str] = None, **kwargs: Any) -> str:
        """Convenience method to generate text from a simple prompt."""
        req = LLMRequest(
            messages=[Message(role="user", content=user_prompt)],
            system_prompt=system_prompt,
            extra_params=kwargs,
        )
        resp = self.generate(req)
        return resp.content

    def get_health_status(self) -> Dict[str, Any]:
        """Return health status of all providers and API keys."""
        now = time.time()
        status_report: Dict[str, Any] = {
            "total_providers": len(self.providers),
            "providers": [],
        }
        for p in self.providers:
            keys_info = []
            for k_stat in self._key_statuses[p.name]:
                cooldown_left = max(0.0, k_stat.exhausted_until - now)
                keys_info.append({
                    "key_masked": k_stat.masked_key,
                    "available": k_stat.is_available(now),
                    "is_exhausted": k_stat.is_exhausted,
                    "cooldown_remaining_sec": round(cooldown_left, 1),
                    "consecutive_failures": k_stat.consecutive_failures,
                    "total_calls": k_stat.total_calls,
                    "successful_calls": k_stat.successful_calls,
                    "last_reason": k_stat.last_reason.value if k_stat.last_reason else None,
                })
            status_report["providers"].append({
                "name": p.name,
                "type": p.provider_type.value,
                "model": p.model,
                "priority": p.priority,
                "enabled": p.enabled,
                "keys": keys_info,
            })
        return status_report

    @classmethod
    def from_config_file(cls, config_path: str) -> "UniversalLLMRouter":
        """Load router configuration from JSON with environment variable expansion."""
        if not os.path.exists(config_path):
            raise ConfigurationError(f"Config file not found: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Expand ${VAR_NAME} or $VAR_NAME
        def replace_env(match: re.Match) -> str:
            var_name = match.group(1) or match.group(2)
            return os.getenv(var_name, "")

        expanded_content = re.sub(r"\$\{([A-Za-z0-9_]+)\}|\$([A-Za-z0-9_]+)", replace_env, content)
        data = json.loads(expanded_content)

        providers: List[ProviderConfig] = []
        for p_data in data.get("providers", []):
            # Filter out empty keys (e.g. unset environment variables)
            raw_keys = p_data.get("api_keys", [])
            valid_keys = [k.strip() for k in raw_keys if k and k.strip()]
            enabled = p_data.get("enabled", True)
            if not valid_keys:
                valid_keys = [f"UNCONFIGURED_{p_data['name'].upper().replace('-', '_')}_KEY"]
                enabled = False

            p_config = ProviderConfig(
                name=p_data["name"],
                provider_type=ProviderType(p_data["provider_type"]),
                model=p_data["model"],
                api_keys=valid_keys,
                priority=p_data.get("priority", 1),
                base_url=p_data.get("base_url"),
                timeout_seconds=float(p_data.get("timeout_seconds", 30.0)),
                cooldown_seconds=float(p_data.get("cooldown_seconds", 60.0)),
                headers=p_data.get("headers", {}),
                enabled=enabled,
            )
            providers.append(p_config)

        return cls(providers)
