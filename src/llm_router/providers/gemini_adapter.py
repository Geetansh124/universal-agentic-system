"""Google Gemini API adapter."""

from __future__ import annotations

import json
from typing import Any, Dict, Tuple

from ..models import KeyStatus, LLMRequest, LLMResponse, ProviderConfig
from .base import BaseLLMAdapter


class GeminiAdapter(BaseLLMAdapter):
    """Adapter for Google Gemini REST API (v1beta)."""

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.base_url = (config.base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")

    def build_request_payload_with_key(self, request: LLMRequest, api_key: str) -> Tuple[str, Dict[str, str], bytes]:
        model = request.model or self.config.model
        # Securely pass API key via x-goog-api-key header
        url = f"{self.base_url}/models/{model}:generateContent"

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
            "User-Agent": "Universal-Agentic-System/1.0",
        }
        headers.update(self.config.headers)

        contents = []
        for m in request.messages:
            role = "user" if m.role in ("user", "system") else "model"
            contents.append({
                "role": role,
                "parts": [{"text": m.content}],
            })

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            },
        }

        if request.system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": request.system_prompt}]
            }

        payload.update(request.extra_params)
        body_bytes = json.dumps(payload).encode("utf-8")
        return url, headers, body_bytes

    def build_request_payload(self, request: LLMRequest) -> Tuple[str, Dict[str, str], bytes]:
        key = self.config.api_keys[0] if self.config.api_keys else ""
        return self.build_request_payload_with_key(request, key)

    def parse_response(self, response_data: Dict[str, Any], key_status: KeyStatus) -> LLMResponse:
        candidates = response_data.get("candidates", [])
        if not candidates:
            # Check prompt feedback or error
            feedback = response_data.get("promptFeedback", {})
            block_reason = feedback.get("blockReason")
            if block_reason:
                raise ValueError(f"Gemini prompt blocked: {block_reason}")
            raise ValueError("No candidates returned from Gemini API.")

        parts = candidates[0].get("content", {}).get("parts", [])
        text_parts = [p.get("text", "") for p in parts if "text" in p]
        content = "".join(text_parts)

        usage_meta = response_data.get("usageMetadata", {})
        usage = {
            "prompt_tokens": usage_meta.get("promptTokenCount", 0),
            "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
            "total_tokens": usage_meta.get("totalTokenCount", 0),
        }

        return LLMResponse(
            content=content,
            model=self.config.model,
            provider_name=self.config.name,
            key_identifier=key_status.masked_key,
            usage=usage,
            raw_response=response_data,
        )
