"""Command-line interface for Universal LLM Router."""

import argparse
import json
import os
import sys
import time
from typing import Any, Dict

from .models import (
    FailoverReason,
    KeyStatus,
    LLMRequest,
    LLMResponse,
    Message,
    ProviderConfig,
    ProviderType,
)
from .providers.base import BaseLLMAdapter
from .router import UniversalLLMRouter


class MockSimulatedAdapter(BaseLLMAdapter):
    """Simulated adapter for demonstration of real-time failover."""

    def __init__(self, config: ProviderConfig, fail_count: int = 1):
        super().__init__(config)
        self.fail_count = fail_count
        self.current_calls = 0

    def build_request_payload(self, request: LLMRequest):
        return "http://mock.endpoint", {}, b"{}"

    def parse_response(self, response_data: Dict[str, Any], key_status: KeyStatus) -> LLMResponse:
        return LLMResponse(
            content=f"Hello from {self.config.name} ({self.config.model})! Failover succeeded.",
            model=self.config.model,
            provider_name=self.config.name,
            key_identifier=key_status.masked_key,
        )

    def execute(self, request: LLMRequest, key_status: KeyStatus) -> LLMResponse:
        from .exceptions import ProviderExhaustedError

        self.current_calls += 1
        if self.current_calls <= self.fail_count:
            # Simulate 429 Too Many Requests / Quota Exhaustion
            raise ProviderExhaustedError(
                self.config.name,
                FailoverReason.QUOTA_EXHAUSTED,
                f"HTTP 429: Quota exceeded on key {key_status.masked_key}. Limit reached.",
                status_code=429,
                retry_after=60.0,
            )
        return self.parse_response({}, key_status)


def run_failover_simulation() -> None:
    """Run an interactive simulation demonstrating automatic shift on exhaustion."""
    print("=" * 70)
    print(" UNIVERSAL AGENTIC SYSTEM: AUTOMATIC FAILOVER DEMONSTRATION")
    print("=" * 70)
    print("Scenario:")
    print("  1. Primary Provider: 'NVIDIA NIM' (priority 1)")
    print("     - Model: meta/llama-3.3-70b-instruct")
    print("     - Encounters HTTP 429 (NVIDIA NIM Quota Exhausted)")
    print("  2. Fallback Provider 1: 'OpenCode Hub' (priority 2)")
    print("     - Model: Qwen/Qwen2.5-Coder-32B-Instruct")
    print("     - Encounters Rate Limit")
    print("  3. Fallback Provider 2: 'Google Gemini' (priority 3)")
    print("     - Automatically takes over and completes the task!")
    print("-" * 70)

    router = UniversalLLMRouter()

    # Provider 1: NVIDIA NIM (Priority 1) -> fails
    nvidia_cfg = ProviderConfig(
        name="nvidia-nim",
        provider_type=ProviderType.NVIDIA,
        model="meta/llama-3.3-70b-instruct",
        api_keys=["nvapi-DUMMY_NVIDIA_KEY_1111"],
        priority=1,
        cooldown_seconds=60.0,
    )
    router.add_provider(nvidia_cfg)
    router._adapters["nvidia-nim"] = MockSimulatedAdapter(nvidia_cfg, fail_count=1)

    # Provider 2: OpenCode (Priority 2) -> fails
    opencode_cfg = ProviderConfig(
        name="opencode-hub",
        provider_type=ProviderType.OPENCODE,
        model="Qwen/Qwen2.5-Coder-32B-Instruct",
        api_keys=["opencode_DUMMY_KEY_2222"],
        priority=2,
        cooldown_seconds=60.0,
    )
    router.add_provider(opencode_cfg)
    router._adapters["opencode-hub"] = MockSimulatedAdapter(opencode_cfg, fail_count=1)

    # Provider 3: Gemini (Priority 3) -> succeeds
    gemini_cfg = ProviderConfig(
        name="google-gemini",
        provider_type=ProviderType.GEMINI,
        model="gemini-2.5-flash",
        api_keys=["AIzaSyDUMMY_GEMINI_KEY_3333"],
        priority=3,
    )
    router.add_provider(gemini_cfg)
    router._adapters["google-gemini"] = MockSimulatedAdapter(gemini_cfg, fail_count=0)

    print("\n[Step 1] Initial Router Status:")
    for p in router.get_health_status()["providers"]:
        print(f"  - Provider: {p['name']} (Priority {p['priority']}), Keys: {len(p['keys'])}")

    print("\n[Step 2] Sending User Request: 'Analyze system architecture'...")
    req = LLMRequest(
        messages=[Message(role="user", content="Analyze system architecture")]
    )

    resp = router.generate(req)

    print("\n[Step 3] Final Response Received:")
    print(f"  Provider Used : {resp.provider_name}")
    print(f"  Model         : {resp.model}")
    print(f"  Key Used      : {resp.key_identifier}")
    print(f"  Result        : {resp.content}")

    print("\n[Step 4] Failover Audit Log:")
    for i, event in enumerate(router.failover_history, 1):
        print(
            f"  {i}. {event.from_provider} [{event.from_key_masked}] EXHAUSTED ({event.reason.value}) "
            f"-> Shifted to: {event.to_provider} [{event.to_key_masked}]"
        )
    print("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(description="Universal LLM Router CLI")
    parser.add_argument("--config", type=str, default="config/llm_router_config.json", help="Path to config file")
    parser.add_argument("--health", action="store_true", help="Print health status of configured providers")
    parser.add_argument("--simulate-failover", action="store_true", help="Run simulated automatic failover demo")
    parser.add_argument("--prompt", type=str, help="Generate completion for a prompt")
    args = parser.parse_args()

    if args.simulate_failover:
        run_failover_simulation()
        return

    config_path = args.config
    if not os.path.exists(config_path):
        example_path = "config/llm_router_config.example.json"
        if os.path.exists(example_path):
            config_path = example_path
        else:
            print(f"Configuration file not found at '{args.config}'. Run with --simulate-failover to test.")
            sys.exit(1)

    try:
        router = UniversalLLMRouter.from_config_file(config_path)
    except Exception as err:
        print(f"Failed to load router config: {err}")
        sys.exit(1)

    if args.health:
        print(json.dumps(router.get_health_status(), indent=2))
        return

    if args.prompt:
        try:
            resp = router.prompt(args.prompt)
            print(resp)
        except Exception as err:
            print(f"Generation error: {err}")
            sys.exit(1)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
