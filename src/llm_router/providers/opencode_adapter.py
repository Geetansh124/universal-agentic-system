"""OpenCode and open-source coding LLM adapter."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from ..models import FailoverReason, KeyStatus, LLMResponse, ProviderConfig
from .openai_adapter import OpenAIAdapter


class OpenCodeAdapter(OpenAIAdapter):
    """
    Adapter for OpenCode and open-weights code generation models
    (e.g., DeepSeek-Coder, Qwen2.5-Coder, StarCoder) via Together AI,
    HuggingFace, OpenRouter, or local servers.
    """

    DEFAULT_BASE_URL = "https://api.together.xyz/v1"
    DEFAULT_MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct"

    def __init__(self, config: ProviderConfig):
        if not config.base_url:
            config.base_url = self.DEFAULT_BASE_URL
        if not config.model:
            config.model = self.DEFAULT_MODEL
        super().__init__(config)

    def check_exhaustion_signals(
        self, status_code: int, response_text: str
    ) -> Optional[Tuple[FailoverReason, str, Optional[float]]]:
        """Detect quota limits, GPU worker limits, and rate limits on open model hosts."""
        text_lower = response_text.lower()
        if status_code == 429:
            return (
                FailoverReason.RATE_LIMIT,
                f"OpenCode provider rate limit exceeded: {response_text[:300]}",
                None,
            )
        if any(term in text_lower for term in ["out of capacity", "gpu unavailable", "credits exhausted", "rate limit"]):
            return (
                FailoverReason.QUOTA_EXHAUSTED,
                f"OpenCode provider capacity/quota exhausted: {response_text[:300]}",
                None,
            )
        return super().check_exhaustion_signals(status_code, response_text)

    def parse_response(self, response_data: Dict[str, Any], key_status: KeyStatus) -> LLMResponse:
        resp = super().parse_response(response_data, key_status)
        resp.provider_name = self.config.name
        return resp
