"""Base adapter for LLM providers."""

from __future__ import annotations

import abc
import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

from ..exceptions import ProviderExhaustedError
from ..models import FailoverReason, KeyStatus, LLMRequest, LLMResponse, ProviderConfig

logger = logging.getLogger("llm_router")


class BaseLLMAdapter(abc.ABC):
    """Abstract base class for provider adapters."""

    def __init__(self, config: ProviderConfig):
        self.config = config

    @abc.abstractmethod
    def build_request_payload(self, request: LLMRequest) -> Tuple[str, Dict[str, str], bytes]:
        """
        Build URL, headers, and body bytes for the HTTP request.
        Returns: (url, headers, body_bytes)
        """
        pass

    @abc.abstractmethod
    def parse_response(self, response_data: Dict[str, Any], key_status: KeyStatus) -> LLMResponse:
        """Parse raw response JSON into normalized LLMResponse."""
        pass

    def check_exhaustion_signals(self, status_code: int, response_text: str) -> Optional[Tuple[FailoverReason, str, Optional[float]]]:
        """
        Analyze status code and response body for quota/rate limit exhaustion.
        Returns (FailoverReason, message, optional_retry_after) if exhausted, else None.
        """
        text_lower = response_text.lower()

        # 429 Too Many Requests
        if status_code == 429:
            reason = FailoverReason.RATE_LIMIT
            if any(term in text_lower for term in ["quota", "insufficient", "credit", "billing", "exhausted"]):
                reason = FailoverReason.QUOTA_EXHAUSTED
            return reason, f"HTTP 429 Rate limit / quota exceeded: {response_text[:300]}", None

        # 401 or 403 Unauthorized / Quota / Depleted Key
        if status_code in (401, 403):
            if any(term in text_lower for term in ["quota", "credit", "balance", "exhausted", "suspended", "expired"]):
                return FailoverReason.QUOTA_EXHAUSTED, f"HTTP {status_code} Key quota/auth exhausted: {response_text[:300]}", None
            return FailoverReason.AUTH_ERROR, f"HTTP {status_code} Authentication failed: {response_text[:300]}", None

        # 503 / 504 / 529 Server Overloaded
        if status_code in (503, 504, 529):
            return FailoverReason.SERVER_ERROR, f"HTTP {status_code} Provider service overloaded: {response_text[:300]}", None

        # Body-based exhaustion signals regardless of status
        exhaustion_indicators = [
            "resource_exhausted",
            "insufficient_quota",
            "rate_limit_exceeded",
            "exceeded your current quota",
            "overloaded_error",
            "credit balance is too low",
            "model is overloaded",
            "quota exceeded",
        ]
        if any(ind in text_lower for ind in exhaustion_indicators):
            return FailoverReason.QUOTA_EXHAUSTED, f"Exhaustion detected in response: {response_text[:300]}", None

        return None

    def execute(self, request: LLMRequest, key_status: KeyStatus) -> LLMResponse:
        """Execute request using standard urllib."""
        import time
        start_time = time.time()
        url, headers, body_bytes = self.build_request_payload_with_key(request, key_status.key)

        req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                status_code = response.getcode()
                response_bytes = response.read()
                response_text = response_bytes.decode("utf-8")
                
                # Check for 200 OK responses that still report exhaustion in body
                exhaustion = self.check_exhaustion_signals(status_code, response_text)
                if exhaustion:
                    reason, msg, retry_after = exhaustion
                    raise ProviderExhaustedError(self.config.name, reason, msg, status_code, retry_after)

                response_json = json.loads(response_text)
                parsed = self.parse_response(response_json, key_status)
                parsed.latency_ms = (time.time() - start_time) * 1000.0
                return parsed

        except urllib.error.HTTPError as err:
            error_body = ""
            try:
                error_body = err.read().decode("utf-8")
            except Exception:
                pass

            exhaustion = self.check_exhaustion_signals(err.code, error_body)
            if exhaustion:
                reason, msg, retry_after = exhaustion
                # Check for Retry-After header
                try:
                    retry_header = err.headers.get("Retry-After")
                    if retry_header and retry_header.isdigit():
                        retry_after = float(retry_header)
                except Exception:
                    pass
                raise ProviderExhaustedError(self.config.name, reason, msg, err.code, retry_after)
            
            # Non-exhaustion HTTP error
            raise ProviderExhaustedError(
                self.config.name,
                FailoverReason.SERVER_ERROR if err.code >= 500 else FailoverReason.INVALID_RESPONSE,
                f"HTTP {err.code}: {error_body[:300]}",
                err.code,
            )

        except urllib.error.URLError as err:
            err_str = str(err.reason).lower()
            if "timed out" in err_str:
                raise ProviderExhaustedError(
                    self.config.name, FailoverReason.TIMEOUT, f"Request timed out after {self.config.timeout_seconds}s"
                )
            raise ProviderExhaustedError(
                self.config.name, FailoverReason.NETWORK_ERROR, f"Network error: {str(err.reason)}"
            )
        except json.JSONDecodeError as err:
            raise ProviderExhaustedError(
                self.config.name, FailoverReason.INVALID_RESPONSE, f"Failed to parse JSON response: {str(err)}"
            )

    def build_request_payload_with_key(self, request: LLMRequest, api_key: str) -> Tuple[str, Dict[str, str], bytes]:
        """Wrapper to pass key into build_request_payload."""
        # By default, pass key in header or subclass handles it
        return self.build_request_payload(request)
