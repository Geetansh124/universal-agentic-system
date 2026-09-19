"""Unit tests for Universal LLM Router with automatic failover."""

import time
import unittest
from typing import Any, Dict
from unittest.mock import MagicMock, patch

from src.llm_router.exceptions import (
    AllProvidersExhaustedError,
    ConfigurationError,
    ProviderExhaustedError,
)
from src.llm_router.models import (
    FailoverReason,
    KeyStatus,
    LLMRequest,
    LLMResponse,
    Message,
    ProviderConfig,
    ProviderType,
)
from src.llm_router.providers.base import BaseLLMAdapter
from src.llm_router.router import UniversalLLMRouter


class MockFailingAdapter(BaseLLMAdapter):
    """Adapter that fails a designated number of times before succeeding."""

    def __init__(self, config: ProviderConfig, fail_calls: int = 1, reason: FailoverReason = FailoverReason.QUOTA_EXHAUSTED):
        super().__init__(config)
        self.fail_calls = fail_calls
        self.reason = reason
        self.calls = 0

    def build_request_payload(self, request: LLMRequest):
        return "http://mock", {}, b"{}"

    def parse_response(self, response_data: Dict[str, Any], key_status: KeyStatus) -> LLMResponse:
        return LLMResponse(
            content=f"Success from {self.config.name}",
            model=self.config.model,
            provider_name=self.config.name,
            key_identifier=key_status.masked_key,
        )

    def execute(self, request: LLMRequest, key_status: KeyStatus) -> LLMResponse:
        self.calls += 1
        if self.calls <= self.fail_calls:
            raise ProviderExhaustedError(
                self.config.name,
                self.reason,
                f"Simulated exhaustion ({self.reason.value}) on key {key_status.masked_key}",
                status_code=429,
                retry_after=10.0,
            )
        return self.parse_response({}, key_status)


class TestUniversalLLMRouter(unittest.TestCase):
    """Test suite for UniversalLLMRouter."""

    def test_request_validation(self):
        """Verify boundary input validation on LLMRequest."""
        # Empty messages
        with self.assertRaises(ValueError):
            req = LLMRequest(messages=[])
            req.validate()

        # Empty content
        with self.assertRaises(ValueError):
            req = LLMRequest(messages=[Message(role="user", content="   ")])
            req.validate()

        # Invalid temperature
        with self.assertRaises(ValueError):
            req = LLMRequest(messages=[Message(role="user", content="hi")], temperature=2.5)
            req.validate()

        # Invalid max_tokens
        with self.assertRaises(ValueError):
            req = LLMRequest(messages=[Message(role="user", content="hi")], max_tokens=-10)
            req.validate()

    def test_provider_config_validation(self):
        """Verify boundary input validation on ProviderConfig."""
        with self.assertRaises(ValueError):
            cfg = ProviderConfig(
                name="", provider_type=ProviderType.GEMINI, model="m", api_keys=["k"]
            )
            cfg.validate()

        with self.assertRaises(ValueError):
            cfg = ProviderConfig(
                name="p", provider_type=ProviderType.OPENAI, model="m", api_keys=[],
            )
            cfg.validate()

    def test_single_provider_success(self):
        """Test standard generation with single provider."""
        router = UniversalLLMRouter()
        cfg = ProviderConfig(
            name="gemini",
            provider_type=ProviderType.GEMINI,
            model="gemini-2.5-flash",
            api_keys=["test_key_12345678"],
        )
        router.add_provider(cfg)
        router._adapters["gemini"] = MockFailingAdapter(cfg, fail_calls=0)

        req = LLMRequest(messages=[Message(role="user", content="Hello")])
        resp = router.generate(req)

        self.assertEqual(resp.provider_name, "gemini")
        self.assertIn("Success", resp.content)
        self.assertEqual(len(router.failover_history), 0)

    def test_multi_key_automatic_shift_on_exhaustion(self):
        """Test that when Key 1 is exhausted (429), it automatically shifts to Key 2."""
        router = UniversalLLMRouter()
        cfg = ProviderConfig(
            name="openai",
            provider_type=ProviderType.OPENAI,
            model="gpt-4o-mini",
            api_keys=["key1_12345678", "key2_87654321"],
        )
        router.add_provider(cfg)
        # First call fails on key 1, second call succeeds on key 2
        router._adapters["openai"] = MockFailingAdapter(cfg, fail_calls=1)

        req = LLMRequest(messages=[Message(role="user", content="Generate code")])
        resp = router.generate(req)

        self.assertEqual(resp.provider_name, "openai")
        self.assertEqual(resp.key_identifier, "key2...4321")
        self.assertEqual(len(router.failover_history), 1)
        self.assertEqual(router.failover_history[0].reason, FailoverReason.QUOTA_EXHAUSTED)
        self.assertEqual(router.failover_history[0].from_key_masked, "key1...5678")
        self.assertEqual(router.failover_history[0].to_key_masked, "key2...4321")

    def test_cross_provider_fallback_when_all_keys_exhausted(self):
        """Test that when Provider 1 keys are all exhausted, it shifts to Provider 2."""
        router = UniversalLLMRouter()

        p1_cfg = ProviderConfig(
            name="primary-gemini",
            provider_type=ProviderType.GEMINI,
            model="gemini-2.5-flash",
            api_keys=["gemini_key_11111111"],
            priority=1,
        )
        p2_cfg = ProviderConfig(
            name="secondary-groq",
            provider_type=ProviderType.OPENAI_COMPATIBLE,
            model="llama-3.3-70b-versatile",
            api_keys=["groq_key_22222222"],
            priority=2,
        )
        router.add_provider(p1_cfg)
        router.add_provider(p2_cfg)

        # Gemini fails with rate limit / quota
        router._adapters["primary-gemini"] = MockFailingAdapter(p1_cfg, fail_calls=1)
        # Groq succeeds
        router._adapters["secondary-groq"] = MockFailingAdapter(p2_cfg, fail_calls=0)

        req = LLMRequest(messages=[Message(role="user", content="Research summary")])
        resp = router.generate(req)

        self.assertEqual(resp.provider_name, "secondary-groq")
        self.assertEqual(len(router.failover_history), 1)
        event = router.failover_history[0]
        self.assertEqual(event.from_provider, "primary-gemini")
        self.assertEqual(event.to_provider, "secondary-groq")

    def test_all_providers_exhausted_raises_error(self):
        """Test error raised when all providers in chain are exhausted."""
        router = UniversalLLMRouter()
        p1 = ProviderConfig(name="p1", provider_type=ProviderType.GEMINI, model="m", api_keys=["k1_12345678"], priority=1)
        p2 = ProviderConfig(name="p2", provider_type=ProviderType.OPENAI, model="m", api_keys=["k2_12345678"], priority=2)
        router.add_provider(p1)
        router.add_provider(p2)

        router._adapters["p1"] = MockFailingAdapter(p1, fail_calls=99)
        router._adapters["p2"] = MockFailingAdapter(p2, fail_calls=99)

        req = LLMRequest(messages=[Message(role="user", content="Test")])
        with self.assertRaises(AllProvidersExhaustedError) as ctx:
            router.generate(req)

        self.assertIn("All 2 providers", str(ctx.exception))

    def test_cooldown_expiration_restores_key(self):
        """Test that a key on cooldown is restored once time passes."""
        key_stat = KeyStatus(key="test_key_12345678")
        key_stat.mark_exhausted(cooldown_seconds=1.0, reason=FailoverReason.RATE_LIMIT, error_message="429")

        # In cooldown
        self.assertTrue(key_stat.is_exhausted)
        self.assertFalse(key_stat.is_available(time.time()))

        # After cooldown passes
        future_time = time.time() + 2.0
        self.assertTrue(key_stat.is_available(future_time))

    def test_health_status_reporting(self):
        """Test that get_health_status accurately reports provider states."""
        router = UniversalLLMRouter()
        cfg = ProviderConfig(
            name="gemini",
            provider_type=ProviderType.GEMINI,
            model="gemini-2.5-flash",
            api_keys=["key1_12345678"],
        )
        router.add_provider(cfg)
        status = router.get_health_status()
        self.assertEqual(status["total_providers"], 1)
        self.assertEqual(status["providers"][0]["name"], "gemini")
        self.assertTrue(status["providers"][0]["keys"][0]["available"])

    def test_from_config_file_and_env_expansion(self):
        """Test loading router configuration from file with env var expansion."""
        import os
        os.environ["TEST_LLM_KEY_GEMINI"] = "AIzaSyTest12345"
        try:
            router = UniversalLLMRouter.from_config_file("config/llm_router_config.example.json")
            self.assertEqual(len(router.providers), 5)
            # Find google-gemini provider
            gemini_p = next(p for p in router.providers if p.name == "google-gemini")
            self.assertEqual(gemini_p.model, "gemini-2.5-flash")
        finally:
            os.environ.pop("TEST_LLM_KEY_GEMINI", None)


if __name__ == "__main__":
    unittest.main()
