"""
Dynamic Provider-Scoped Model Discovery and Caching Subsystem.
Queries remote provider endpoints (OpenRouter, Ollama, Groq, OpenAI) and enriches
pricing, context limits, and multimodal vision capabilities.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, List, Optional

from agent.core.pricing import register_dynamic_model_pricing
from agent.core.vision import register_dynamic_vision_model, is_model_vision_capable

logger = logging.getLogger(__name__)

CACHE_DIR = Path.home() / ".raven" / "cache"
DEFAULT_CACHE_TTL = 86400  # 24 hours in seconds


def _slugify(text: str) -> str:
    """Creates a filesystem-safe slug from a string."""
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", text.strip().lower())


class ModelFetcher:
    """Handles fetching, caching, and registering model metadata from LLM providers."""

    def __init__(self, cache_dir: Optional[Path] = None, ttl_seconds: int = DEFAULT_CACHE_TTL) -> None:
        self.cache_dir = cache_dir or CACHE_DIR
        self.ttl_seconds = ttl_seconds

    def _get_cache_path(self, preset_name: str) -> Path:
        slug = _slugify(preset_name)
        return self.cache_dir / f"models_{slug}.json"

    def _read_cache(self, preset_name: str) -> Optional[dict]:
        cache_path = self._get_cache_path(preset_name)
        if not cache_path.exists():
            return None
        try:
            content = cache_path.read_text(encoding="utf-8")
            data = json.loads(content)
            if isinstance(data, dict) and "models" in data and isinstance(data["models"], list):
                return data
        except Exception as e:
            logger.debug(f"Failed to read model cache for {preset_name}: {e}")
        return None

    def _write_cache(self, preset_name: str, models: List[Dict[str, Any]]) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path = self._get_cache_path(preset_name)
            payload = {
                "preset_name": preset_name,
                "fetched_at": time.time(),
                "ttl_seconds": self.ttl_seconds,
                "models": models,
            }
            cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to write model cache for {preset_name}: {e}")

    def _register_metadata(self, models: List[Dict[str, Any]]) -> None:
        """Populates dynamic registries for pricing and vision capabilities."""
        for m in models:
            model_id = m.get("id")
            if not model_id:
                continue
            input_cost = m.get("input_cost_per_1m", 0.0)
            output_cost = m.get("output_cost_per_1m", 0.0)
            context_limit = m.get("context_limit", 128000)
            if input_cost > 0 or output_cost > 0 or context_limit != 128000:
                register_dynamic_model_pricing(
                    model_name=model_id,
                    input_cost_per_1m=input_cost,
                    output_cost_per_1m=output_cost,
                    context_limit=context_limit,
                )
            if m.get("vision"):
                register_dynamic_vision_model(model_id, True)

    def fetch_models(
        self,
        preset_name: str,
        preset_config: Dict[str, Any],
        force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Fetches models for the given provider preset.
        Uses cached responses if valid; otherwise performs network discovery with fallback.
        """
        # 1. Check disk cache if not forcing refresh
        cached_data = self._read_cache(preset_name)
        if cached_data and not force_refresh:
            fetched_at = cached_data.get("fetched_at", 0)
            ttl = cached_data.get("ttl_seconds", self.ttl_seconds)
            if time.time() - fetched_at < ttl:
                models = cached_data.get("models", [])
                self._register_metadata(models)
                return models

        # 2. Network Discovery
        provider_type = preset_config.get("provider_type", "openai")
        use_vertex = bool(preset_config.get("use_vertex_ai") or provider_type == "vertex")
        base_url = preset_config.get("base_url") or ""
        api_key = preset_config.get("api_key") or ""

        discovered_models: List[Dict[str, Any]] = []
        try:
            if use_vertex:
                discovered_models = self._fetch_vertex_models(preset_config)
            elif "openrouter.ai" in base_url.lower():
                discovered_models = self._fetch_openrouter_models(api_key, base_url)
            elif "11434" in base_url or "ollama" in preset_name.lower():
                discovered_models = self._fetch_ollama_models(base_url)
            else:
                discovered_models = self._fetch_openai_compatible_models(base_url, api_key)

            if discovered_models:
                self._write_cache(preset_name, discovered_models)
                self._register_metadata(discovered_models)
                return discovered_models
        except Exception as e:
            logger.warning(f"Live model discovery failed for '{preset_name}': {e}")

        # 3. Fallback: Return cached data if present (even if expired)
        if cached_data and cached_data.get("models"):
            models = cached_data["models"]
            self._register_metadata(models)
            return models

        # 4. Final Fallback: Return models defined in preset config
        preset_models = preset_config.get("models", [])
        if not preset_models:
            default_m = preset_config.get("default_model")
            preset_models = [default_m] if default_m else []

        fallback_list = []
        for mid in preset_models:
            if isinstance(mid, str) and mid.strip():
                fallback_list.append({
                    "id": mid.strip(),
                    "name": mid.strip(),
                    "context_limit": 128000,
                    "input_cost_per_1m": 0.0,
                    "output_cost_per_1m": 0.0,
                    "vision": is_model_vision_capable(mid.strip()),
                })
        return fallback_list

    def _fetch_vertex_models(self, preset_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        configured = preset_config.get("models") or [
            "google/gemini-2.5-flash",
            "google/gemini-2.5-pro",
            "google/gemini-3-flash-preview",
            "google/gemini-3.1-pro-preview",
        ]
        results = []
        for mid in configured:
            results.append({
                "id": mid,
                "name": mid.split("/")[-1].replace("-", " ").title(),
                "context_limit": 1048576,
                "input_cost_per_1m": 0.75 if "flash" in mid else 2.00,
                "output_cost_per_1m": 3.75 if "flash" in mid else 12.00,
                "vision": True,
            })
        return results

    def _fetch_openrouter_models(self, api_key: str, base_url: str) -> List[Dict[str, Any]]:
        url = "https://openrouter.ai/api/v1/models"
        req = urllib.request.Request(url, headers={"User-Agent": "Raven-CLI-Agent/1.0"})
        if api_key:
            req.add_header("Authorization", f"Bearer {api_key}")

        with urllib.request.urlopen(req, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))

        data = payload.get("data", [])
        models: List[Dict[str, Any]] = []
        for item in data:
            mid = item.get("id")
            if not mid:
                continue
            name = item.get("name") or mid
            context_length = int(item.get("context_length") or 128000)
            pricing = item.get("pricing") or {}
            prompt_cost = float(pricing.get("prompt") or 0.0) * 1_000_000
            completion_cost = float(pricing.get("completion") or 0.0) * 1_000_000

            architecture = item.get("architecture") or {}
            modality = str(architecture.get("modality", "")).lower()
            vision = "image" in modality or is_model_vision_capable(mid)

            models.append({
                "id": mid,
                "name": name,
                "context_limit": context_length,
                "input_cost_per_1m": round(prompt_cost, 4),
                "output_cost_per_1m": round(completion_cost, 4),
                "vision": vision,
            })
        return models

    def _fetch_ollama_models(self, base_url: str) -> List[Dict[str, Any]]:
        # e.g., http://localhost:11434/v1 -> http://localhost:11434/api/tags
        root_url = re.sub(r"/v1/?$", "", base_url.strip()) if base_url else "http://localhost:11434"
        url = f"{root_url.rstrip('/')}/api/tags"

        req = urllib.request.Request(url, headers={"User-Agent": "Raven-CLI-Agent/1.0"})
        with urllib.request.urlopen(req, timeout=4) as response:
            payload = json.loads(response.read().decode("utf-8"))

        data = payload.get("models", [])
        models: List[Dict[str, Any]] = []
        for item in data:
            mid = item.get("name")
            if not mid:
                continue
            models.append({
                "id": mid,
                "name": mid,
                "context_limit": 128000,
                "input_cost_per_1m": 0.0,
                "output_cost_per_1m": 0.0,
                "vision": is_model_vision_capable(mid),
            })
        return models

    def _fetch_openai_compatible_models(self, base_url: str, api_key: str) -> List[Dict[str, Any]]:
        if not base_url:
            return []
        url = f"{base_url.rstrip('/')}/models"
        req = urllib.request.Request(url, headers={"User-Agent": "Raven-CLI-Agent/1.0"})
        if api_key:
            req.add_header("Authorization", f"Bearer {api_key}")

        with urllib.request.urlopen(req, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))

        data = payload.get("data", [])
        models: List[Dict[str, Any]] = []
        for item in data:
            mid = item.get("id")
            if not mid:
                continue
            models.append({
                "id": mid,
                "name": mid,
                "context_limit": 128000,
                "input_cost_per_1m": 0.0,
                "output_cost_per_1m": 0.0,
                "vision": is_model_vision_capable(mid),
            })
        return models


_default_fetcher = ModelFetcher()


def fetch_models(
    preset_name: str,
    preset_config: Dict[str, Any],
    force_refresh: bool = False
) -> List[Dict[str, Any]]:
    return _default_fetcher.fetch_models(preset_name, preset_config, force_refresh=force_refresh)
