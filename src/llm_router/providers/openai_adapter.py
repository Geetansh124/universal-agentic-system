"""OpenAI and OpenAI-compatible adapter (OpenAI, Groq, DeepSeek, Mistral, OpenRouter, Ollama)."""

from __future__ import annotations

import json
from typing import Any, Dict, Tuple

from ..models import KeyStatus, LLMRequest, LLMResponse, ProviderConfig
from .base import BaseLLMAdapter


class OpenAIAdapter(BaseLLMAdapter):
    """Adapter for OpenAI and compatible REST endpoints."""

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.base_url = (config.base_url or "https://api.openai.com/v1").rstrip("/")

    def build_request_payload_with_key(self, request: LLMRequest, api_key: str) -> Tuple[str, Dict[str, str], bytes]:
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Universal-Agentic-System/1.0",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        headers.update(self.config.headers)

        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        for m in request.messages:
            messages.append(m.to_dict())

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
        choices = response_data.get("choices", [])
        if not choices:
            raise ValueError("No choices returned from OpenAI-compatible provider.")

        message = choices[0].get("message", {})
        content = message.get("content", "")

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
