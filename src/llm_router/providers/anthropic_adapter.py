"""Anthropic Claude adapter."""

from __future__ import annotations

import json
from typing import Any, Dict, Tuple

from ..models import KeyStatus, LLMRequest, LLMResponse, ProviderConfig
from .base import BaseLLMAdapter


class AnthropicAdapter(BaseLLMAdapter):
    """Adapter for Anthropic Claude Messages API."""

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.base_url = (config.base_url or "https://api.anthropic.com/v1").rstrip("/")

    def build_request_payload_with_key(self, request: LLMRequest, api_key: str) -> Tuple[str, Dict[str, str], bytes]:
        url = f"{self.base_url}/messages"

        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "User-Agent": "Universal-Agentic-System/1.0",
        }
        headers.update(self.config.headers)

        messages = []
        for m in request.messages:
            if m.role == "system" and not request.system_prompt:
                # System messages can be captured as top-level system prompt
                pass
            else:
                messages.append({"role": m.role, "content": m.content})

        # Ensure at least one user message
        if not messages and request.messages:
            messages.append({"role": "user", "content": request.messages[0].content})

        payload: Dict[str, Any] = {
            "model": request.model or self.config.model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.system_prompt:
            payload["system"] = request.system_prompt
        payload.update(request.extra_params)

        body_bytes = json.dumps(payload).encode("utf-8")
        return url, headers, body_bytes

    def build_request_payload(self, request: LLMRequest) -> Tuple[str, Dict[str, str], bytes]:
        key = self.config.api_keys[0] if self.config.api_keys else ""
        return self.build_request_payload_with_key(request, key)

    def parse_response(self, response_data: Dict[str, Any], key_status: KeyStatus) -> LLMResponse:
        content_blocks = response_data.get("content", [])
        text_parts = [
            block.get("text", "")
            for block in content_blocks
            if block.get("type") == "text"
        ]
        content = "".join(text_parts)

        usage = response_data.get("usage", {})
        model = response_data.get("model", self.config.model)

        return LLMResponse(
            content=content,
            model=model,
            provider_name=self.config.name,
            key_identifier=key_status.masked_key,
            usage=usage,
            raw_response=response_data,
        )
