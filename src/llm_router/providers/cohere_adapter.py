"""Cohere V2 Chat API adapter."""

from __future__ import annotations

import json
from typing import Any, Dict, Tuple

from ..models import KeyStatus, LLMRequest, LLMResponse, ProviderConfig
from .base import BaseLLMAdapter


class CohereAdapter(BaseLLMAdapter):
    """Adapter for Cohere V2 Chat API."""

    DEFAULT_BASE_URL = "https://api.cohere.com/v2"

    def __init__(self, config: ProviderConfig):
        if not config.base_url:
            config.base_url = self.DEFAULT_BASE_URL
        super().__init__(config)

    def build_request_payload_with_key(
        self, request: LLMRequest, api_key: str
    ) -> Tuple[str, Dict[str, str], bytes]:
        url = f"{self.config.base_url.rstrip('/')}/chat"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Universal-Agentic-System/1.0",
        }
        headers.update(self.config.headers)

        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        for m in request.messages:
            messages.append({"role": m.role, "content": m.content})

        payload: Dict[str, Any] = {
            "model": request.model or self.config.model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        payload.update(request.extra_params)
        body_bytes = json.dumps(payload).encode("utf-8")
        return url, headers, body_bytes

    def build_request_payload(self, request: LLMRequest) -> Tuple[str, Dict[str, str], bytes]:
        key = self.config.api_keys[0] if self.config.api_keys else ""
        return self.build_request_payload_with_key(request, key)

    def parse_response(self, response_data: Dict[str, Any], key_status: KeyStatus) -> LLMResponse:
        message = response_data.get("message", {})
        content_list = message.get("content", [])
        text = "".join(item.get("text", "") for item in content_list if item.get("type") == "text")

        usage_meta = response_data.get("usage", {}).get("tokens", {})
        usage = {
            "prompt_tokens": usage_meta.get("input_tokens", 0),
            "completion_tokens": usage_meta.get("output_tokens", 0),
            "total_tokens": (usage_meta.get("input_tokens", 0) + usage_meta.get("output_tokens", 0)),
        }

        return LLMResponse(
            content=text,
            model=self.config.model,
            provider_name=self.config.name,
            key_identifier=key_status.masked_key,
            usage=usage,
            raw_response=response_data,
        )
