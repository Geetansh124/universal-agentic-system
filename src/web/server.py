"""FastAPI Web Server for Claude Desktop-Style Agentic Platform UI."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..llm_router.models import LLMRequest, Message
from ..llm_router.router import UniversalLLMRouter
from .config_manager import ConfigManager

app = FastAPI(title="Universal Agentic Platform", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Config & Router
config_mgr = ConfigManager()
router_instance: Optional[UniversalLLMRouter] = None


def get_router() -> UniversalLLMRouter:
    global router_instance
    if router_instance is None:
        try:
            router_instance = UniversalLLMRouter.from_config_file(config_mgr.config_path)
        except Exception:
            router_instance = UniversalLLMRouter()
    return router_instance


def reload_router() -> UniversalLLMRouter:
    global router_instance
    router_instance = UniversalLLMRouter.from_config_file(config_mgr.config_path)
    return router_instance


# ---------------------------------------------------------------------------
# Agent Personas Catalog
# ---------------------------------------------------------------------------
AGENT_PERSONAS = [
    {
        "id": "chief-architect",
        "name": "Chief Architect",
        "role": "System Architecture & Resilience",
        "avatar": "🏛️",
        "system_prompt": (
            "You are the Chief System Architect. You specialize in distributed systems, "
            "fault tolerance, multi-provider redundancy, high-scalability architectures, "
            "and clean architectural design patterns. Always provide well-structured, robust solutions."
        ),
    },
    {
        "id": "full-stack-coder",
        "name": "Full-Stack Engineer",
        "role": "Code Implementation & Debugging",
        "avatar": "💻",
        "system_prompt": (
            "You are an expert Full-Stack Software Engineer. You write clean, idiomatic, "
            "production-ready code with unit tests, error handling, and type annotations. "
            "Format code blocks cleanly with appropriate language tags."
        ),
    },
    {
        "id": "security-auditor",
        "name": "Security & Red Team",
        "role": "Security Analysis & Hardening",
        "avatar": "🛡️",
        "system_prompt": (
            "You are a Senior Application Security Engineer and Auditor. You identify security "
            "vulnerabilities (OWASP Top 10, credential leakage, injection, misconfigurations) "
            "and provide defensive hardening strategies with exact remediations."
        ),
    },
    {
        "id": "polar-specialist",
        "name": "Polar Expedition Lead",
        "role": "Autonomous Logistics & Operations",
        "avatar": "❄️",
        "system_prompt": (
            "You are the Lead Operations Specialist for Polar Expedition Logistics. You understand "
            "harsh-environment computing, offline-first architectures, low-bandwidth communications, "
            "and asset tracking under extreme conditions."
        ),
    },
    {
        "id": "research-analyst",
        "name": "Research Analyst",
        "role": "Deep Synthesis & Trade-off Analysis",
        "avatar": "🔬",
        "system_prompt": (
            "You are a Principal AI and Technology Research Analyst. You synthesize complex technical "
            "topics, evaluate trade-offs with rigorous analytical thinking, and cite architectural principles."
        ),
    },
]


# ---------------------------------------------------------------------------
# Request & Response Models
# ---------------------------------------------------------------------------
class ChatMessageModel(BaseModel):
    role: str
    content: str


class ChatRequestModel(BaseModel):
    messages: List[ChatMessageModel]
    agent_id: Optional[str] = "chief-architect"
    system_prompt: Optional[str] = None
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(2048, ge=1, le=8192)


class ProviderInputModel(BaseModel):
    name: str
    provider_type: str
    model: str
    api_keys: List[str]
    priority: int = 1
    base_url: Optional[str] = None
    timeout_seconds: float = 30.0
    cooldown_seconds: float = 60.0
    enabled: bool = True


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------
@app.get("/api/health")
def get_health() -> Dict[str, Any]:
    """Get real-time health status of providers and keys."""
    router = get_router()
    return router.get_health_status()


@app.get("/api/agents")
def get_agents() -> List[Dict[str, Any]]:
    """Return available agent personas."""
    return AGENT_PERSONAS


@app.get("/api/providers")
def get_providers() -> List[Dict[str, Any]]:
    """List all configured providers with masked keys."""
    return config_mgr.list_providers()


@app.post("/api/providers")
def save_provider(payload: ProviderInputModel) -> Dict[str, Any]:
    """Insert or update an API provider and reload the router."""
    try:
        data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        saved = config_mgr.add_or_update_provider(data)
        reload_router()
        return {"status": "success", "provider": saved}
    except Exception as err:
        raise HTTPException(status_code=400, detail=str(err))


@app.delete("/api/providers/{name}")
def delete_provider(name: str) -> Dict[str, Any]:
    """Delete an API provider by name and reload the router."""
    success = config_mgr.delete_provider(name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Provider '{name}' not found.")
    reload_router()
    return {"status": "success", "deleted": name}


@app.post("/api/chat")
def chat(payload: ChatRequestModel) -> Dict[str, Any]:
    """Execute chat conversation across the failover router."""
    router = get_router()

    # Determine system prompt based on agent persona
    system_prompt = payload.system_prompt
    agent_info = next((a for a in AGENT_PERSONAS if a["id"] == payload.agent_id), None)
    if not system_prompt and agent_info:
        system_prompt = agent_info["system_prompt"]

    messages = [Message(role=m.role, content=m.content) for m in payload.messages]

    req = LLMRequest(
        messages=messages,
        system_prompt=system_prompt,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
    )

    prev_failover_count = len(router.failover_history)
    try:
        resp = router.generate(req)
        new_failovers = [
            {
                "from_provider": ev.from_provider,
                "from_key_masked": ev.from_key_masked,
                "to_provider": ev.to_provider,
                "to_key_masked": ev.to_key_masked,
                "reason": ev.reason.value,
                "timestamp": ev.timestamp,
            }
            for ev in router.failover_history[prev_failover_count:]
        ]

        return {
            "content": resp.content,
            "provider_name": resp.provider_name,
            "model": resp.model,
            "key_identifier": resp.key_identifier,
            "usage": resp.usage,
            "failover_events": new_failovers,
            "agent": agent_info,
        }
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


# ---------------------------------------------------------------------------
# Static Assets & Frontend Serving
# ---------------------------------------------------------------------------
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(static_dir, "index.html"))
