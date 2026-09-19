"""Unit tests for Universal Agentic Platform Web API."""

import pytest
from fastapi.testclient import TestClient
from src.web.server import app, reload_router
from src.llm_router.models import LLMResponse


@pytest.fixture
def client():
    return TestClient(app)


def test_get_agents(client):
    res = client.get("/api/agents")
    assert res.status_code == 200
    agents = res.json()
    assert len(agents) >= 5
    ids = [a["id"] for a in agents]
    assert "chief-architect" in ids
    assert "full-stack-coder" in ids
    assert "security-auditor" in ids


def test_get_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert "total_providers" in data
    assert "providers" in data


def test_get_providers(client):
    res = client.get("/api/providers")
    assert res.status_code == 200
    providers = res.json()
    assert isinstance(providers, list)
    for p in providers:
        assert "name" in p
        assert "api_keys_masked" in p


def test_add_and_delete_provider(client):
    test_provider = {
        "name": "test-groq-api",
        "provider_type": "openai_compatible",
        "model": "llama-3.3-70b-versatile",
        "api_keys": ["gsk_TEST_KEY_123456789"],
        "priority": 5,
        "base_url": "https://api.groq.com/openai/v1",
        "enabled": True,
    }

    # 1. Add Provider
    add_res = client.post("/api/providers", json=test_provider)
    assert add_res.status_code == 200
    assert add_res.json()["status"] == "success"

    # Verify provider is in list
    list_res = client.get("/api/providers")
    names = [p["name"] for p in list_res.json()]
    assert "test-groq-api" in names

    # 2. Delete Provider
    del_res = client.delete("/api/providers/test-groq-api")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"

    # Verify deleted
    list_res2 = client.get("/api/providers")
    names2 = [p["name"] for p in list_res2.json()]
    assert "test-groq-api" not in names2


def test_chat_endpoint(client, monkeypatch):
    # Mock router response to avoid real network call during test
    from src.web import server

    class MockRouter:
        failover_history = []

        def generate(self, req):
            return LLMResponse(
                content="Mocked response for testing",
                model="mock-model",
                provider_name="mock-provider",
                key_identifier="mock-key",
            )

    monkeypatch.setattr(server, "get_router", lambda: MockRouter())

    payload = {
        "messages": [{"role": "user", "content": "Hello from unit test"}],
        "agent_id": "chief-architect",
    }
    res = client.post("/api/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["content"] == "Mocked response for testing"
    assert data["provider_name"] == "mock-provider"
    assert data["agent"]["id"] == "chief-architect"
