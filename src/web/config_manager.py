"""Configuration manager for dynamically inserting, updating, and deleting LLM API providers."""

from __future__ import annotations

import json
import os
import shutil
from typing import Any, Dict, List, Optional

from ..llm_router.models import ProviderConfig, ProviderType


class ConfigManager:
    """Manages active LLM provider configurations in config/llm_router_config.json."""

    def __init__(self, config_path: Optional[str] = None):
        if not config_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            local_cfg = os.path.join(base_dir, "config", "llm_router_config.json")
            example_cfg = os.path.join(base_dir, "config", "llm_router_config.example.json")
            if not os.path.exists(local_cfg) and os.path.exists(example_cfg):
                shutil.copyfile(example_cfg, local_cfg)
            config_path = local_cfg

        self.config_path = config_path

    def get_raw_config(self) -> Dict[str, Any]:
        """Read configuration file."""
        if not os.path.exists(self.config_path):
            return {"providers": []}
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_raw_config(self, data: Dict[str, Any]) -> None:
        """Save configuration file."""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def list_providers(self) -> List[Dict[str, Any]]:
        """Return all configured providers with masked keys for security."""
        raw = self.get_raw_config()
        providers = raw.get("providers", [])
        sanitized = []
        for p in providers:
            p_copy = dict(p)
            keys = p_copy.get("api_keys", [])
            p_copy["api_keys_masked"] = [
                f"{k[:4]}...{k[-4:]}" if len(k) > 8 else "***"
                for k in keys
            ]
            # Include key count
            p_copy["key_count"] = len(keys)
            sanitized.append(p_copy)
        return sanitized

    def add_or_update_provider(self, provider_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add or update an API provider in the configuration."""
        name = provider_data.get("name", "").strip()
        if not name:
            raise ValueError("Provider 'name' is required.")

        provider_type_str = provider_data.get("provider_type", "openai_compatible").strip()
        model = provider_data.get("model", "").strip()
        api_keys = provider_data.get("api_keys", [])
        if isinstance(api_keys, str):
            api_keys = [k.strip() for k in api_keys.split(",") if k.strip()]

        priority = int(provider_data.get("priority", 1))
        base_url = provider_data.get("base_url")
        timeout_seconds = float(provider_data.get("timeout_seconds", 30.0))
        cooldown_seconds = float(provider_data.get("cooldown_seconds", 60.0))
        enabled = bool(provider_data.get("enabled", True))

        raw = self.get_raw_config()
        providers = raw.get("providers", [])

        # Check if provider exists
        existing_idx = next((i for i, p in enumerate(providers) if p.get("name") == name), None)

        entry = {
            "name": name,
            "provider_type": provider_type_str,
            "model": model,
            "priority": priority,
            "api_keys": api_keys,
            "timeout_seconds": timeout_seconds,
            "cooldown_seconds": cooldown_seconds,
            "enabled": enabled,
        }
        if base_url:
            entry["base_url"] = base_url

        if existing_idx is not None:
            # If no new keys provided on update, retain existing keys
            if not api_keys and "api_keys" in providers[existing_idx]:
                entry["api_keys"] = providers[existing_idx]["api_keys"]
            providers[existing_idx] = entry
        else:
            providers.append(entry)

        # Sort by priority
        providers.sort(key=lambda x: x.get("priority", 99))
        raw["providers"] = providers
        self.save_raw_config(raw)
        return entry

    def delete_provider(self, name: str) -> bool:
        """Delete an API provider by name."""
        raw = self.get_raw_config()
        providers = raw.get("providers", [])
        new_providers = [p for p in providers if p.get("name") != name]
        if len(new_providers) == len(providers):
            return False
        raw["providers"] = new_providers
        self.save_raw_config(raw)
        return True
