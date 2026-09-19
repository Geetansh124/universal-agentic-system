---
name: universal-llm-router
description: Universal LLM Router with multi-provider automatic failover across NVIDIA NIM, OpenRouter, Google Gemini, OpenAI, and more. Use this skill whenever routing LLM prompts, running chat sessions with automatic failover, or querying models through the universal router.
---

# Universal LLM Router Skill

## Overview
The Universal LLM Router (`src.llm_router`) provides a unified, resilient interface to multiple LLM providers with automatic real-time failover and multi-key rotation.

## Active Configuration
- **Primary (Priority 1)**: NVIDIA NIM (`meta/llama-3.3-70b-instruct`)
- **Fallback (Priority 2)**: OpenRouter (`meta-llama/llama-3.3-70b-instruct`)
- **Standby (Priority 3)**: Google Gemini (`gemini-2.5-flash`)

## System Commands (Global)
From any terminal, folder, or Antigravity workspace:
- `llm-router --chat`: Launch interactive multi-turn chat with live failover alerts.
- `llm-router --prompt "<query>"`: Run a single prompt and return response.
- `llm-router --health`: View real-time provider and key status.
- `llm-router --simulate-failover`: Run automated failover demonstration.

## Programmatic Usage
```python
from src.llm_router.router import UniversalLLMRouter
from src.llm_router.models import LLMRequest, Message

router = UniversalLLMRouter.from_config_file("config/llm_router_config.json")
response = router.prompt("Explain quantum computing")
print(response)
```
