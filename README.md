<div align="center">

<img src="https://shieldcn.dev/header/gradient.svg?title=Universal%20Agentic%20System&subtitle=Multi-provider%20LLM%20routing%20and%20agent%20orchestration&accent=%2306b6d4&mode=dark" alt="Universal Agentic System banner" width="100%" />

![Python](https://shieldcn.dev/badge/python-3.9%2B-3776AB.svg?logo=python&variant=secondary)
![Status](https://shieldcn.dev/badge/status-early-stage-amber.svg?animate=shimmer)
![Stars](https://shieldcn.dev/github/stars/Geetansh124/universal-agentic-system.svg?variant=outline)

**A Python LLM router and agentic-system workspace with provider adapters, failover logic, web configuration, and agent catalogs.**

[Source](https://github.com/Geetansh124/universal-agentic-system) · [Issues](https://github.com/Geetansh124/universal-agentic-system/issues) · [System blueprint](agentic-system-blueprint.md)

</div>

> **Status:** Early-stage project. Review the code, provider settings, and deployment configuration before relying on it. Repository deployment files do not establish a currently running hosted service.

## What it contains

The Python package provides a multi-provider router, request/response models, provider adapters, and CLI entry points (llm-router and universal-llm). The repository also includes a small web configuration server, agent definitions for supported agent environments, tests, and deployment examples.

~~~mermaid
flowchart LR
  U[CLI or Python caller] --> R[LLM router]
  W[Web configuration] --> R
  R --> P[Provider adapters]
  P -->|response| R
  P -->|error or exhausted key| F[Failover handling]
  F --> P
  R --> U
  A[Agent definitions] -. configuration .-> U
~~~

## Quickstart

~~~bash
git clone https://github.com/Geetansh124/universal-agentic-system.git
cd universal-agentic-system
python -m venv .venv
python -m pip install -e .
llm-router --help
~~~

Set the API key for the provider you intend to use. The Docker Compose file references OPENROUTER_API_KEY, NVIDIA_API_KEY, and GEMINI_API_KEY; keep credentials in environment variables and never commit them.

## Repository map

| Path | Purpose |
| --- | --- |
| src/llm_router/ | Router, models, CLI, and provider adapters |
| src/web/ | Web configuration server |
| .agents/, .claude/, .agentic/ | Agent definitions and orchestration configuration |
| tests/ | Project tests |
| agentic-system-blueprint.md | Extended design blueprint |
| Dockerfile, docker-compose.yml, render.yaml | Deployment examples |

## Configuration and limitations

- Live requests require external provider credentials, network access, quotas, and model availability.
- Failover cannot guarantee availability when all configured providers or keys are unavailable.
- Treat deployment manifests as examples; verify secrets, costs, persistence, and service health before deployment.
- Do not send confidential or regulated data without reviewing the selected provider's data handling terms.

## Contributing

Open an issue with a reproducible example, then submit a focused pull request. Include tests for routing or adapter changes.
