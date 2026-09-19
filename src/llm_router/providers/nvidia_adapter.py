"""NVIDIA NIM and AI Foundation API adapter."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from ..models import FailoverReason, KeyStatus, LLMResponse, ProviderConfig
from .openai_adapter import OpenAIAdapter


class NvidiaAdapter(OpenAIAdapter):
    """
    Adapter for NVIDIA NIM and AI Foundation REST endpoints.
    Default endpoint: https://integrate.api.nvidia.com/v1
    """

    DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"

    def __init__(self, config: ProviderConfig):
        # Fall back to official NVIDIA API base URL if not explicitly provided
        if not config.base_url:
            config.base_url = self.DEFAULT_BASE_URL
        super().__init__(config)

    def check_exhaustion_signals(
        self, status_code: int, response_text: str
    ) -> Optional[Tuple[FailoverReason, str, Optional[float]]]:
        """Check for NVIDIA-specific quota exhaustion and rate limiting."""
        text_lower = response_text.lower()

        # NVIDIA specific exhaustion indicators
        nvidia_quota_signals = [
            "credit",
            "credits depleted",
            "quota exceeded",
            "rate limit",
            "too many requests",
            "nvcf-rate-limit",
            "usage limit reached",
            "insufficient funds",
        ]
        if status_code == 429 or any(sig in text_lower for sig in nvidia_quota_signals):
            return (
                FailoverReason.QUOTA_EXHAUSTED,
                f"NVIDIA NIM quota/rate limit exhausted (HTTP {status_code}): {response_text[:300]}",
                None,
            )

        return super().check_exhaustion_signals(status_code, response_text)

    def parse_response(self, response_data: Dict[str, Any], key_status: KeyStatus) -> LLMResponse:
        resp = super().parse_response(response_data, key_status)
        resp.provider_name = self.config.name
        return resp
