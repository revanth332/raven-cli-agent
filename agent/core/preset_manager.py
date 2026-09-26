from pathlib import Path
import json
import copy
from agent.core.settings import settings

BUILTIN_PRESETS = {"OpenRouter", "Google Vertex AI", "Local Ollama", "Groq"}

DEFAULT_PRESETS = {
    "OpenRouter": {
        "provider_type": "openai",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": "",
        "default_model": "anthropic/claude-3.7-sonnet",
        "use_vertex_ai": False,
    },
    "Google Vertex AI": {
        "provider_type": "vertex",
        "base_url": None,
        "api_key": None,
        "default_model": "google/gemini-2.5-flash",
        "use_vertex_ai": True,
    },
    "Local Ollama": {
        "provider_type": "openai",
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
        "default_model": "qwen2.5-coder:14b",
        "use_vertex_ai": False,
    },
    "Groq": {
        "provider_type": "openai",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": "",
        "default_model": "llama-3.3-70b-versatile",
        "use_vertex_ai": False,
    },
}


class PresetManager:
    """Manages reading, writing, and switching LLM provider presets in ~/.raven/providers.json."""

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path or (Path.home() / ".raven" / "providers.json")

    def _get_default_structure(self) -> dict:
        presets = copy.deepcopy(DEFAULT_PRESETS)
        current_key = getattr(settings, "RAVEN_API_KEY", None)
        current_base = getattr(settings, "RAVEN_BASE_URL", None)
        current_model = getattr(settings, "RAVEN_MODEL", None)
        use_vertex = getattr(settings, "RAVEN_USE_VERTEX_AI", False)

        if current_key and current_base and "openrouter" in str(current_base).lower():
            presets["OpenRouter"]["api_key"] = current_key
        if current_model:
            if use_vertex:
                presets["Google Vertex AI"]["default_model"] = current_model
            elif current_base and "openrouter" in str(current_base).lower():
                presets["OpenRouter"]["default_model"] = current_model

        active = "Google Vertex AI" if use_vertex else "OpenRouter"
        return {
            "active_preset": active,
            "presets": presets,
        }

    def _save_to_disk(self, data: dict) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load_presets(self) -> dict:
        """Loads presets from providers.json or initializes defaults if not present."""
        if self.config_path.exists():
            try:
                content = self.config_path.read_text(encoding="utf-8")
                data = json.loads(content)
                if isinstance(data, dict) and "presets" in data and isinstance(data["presets"], dict):
                    # Ensure standard built-in presets exist
                    for k, v in DEFAULT_PRESETS.items():
                        if k not in data["presets"]:
                            data["presets"][k] = copy.deepcopy(v)
                    if not data.get("active_preset") or data["active_preset"] not in data["presets"]:
                        use_vertex = getattr(settings, "RAVEN_USE_VERTEX_AI", False)
                        data["active_preset"] = "Google Vertex AI" if use_vertex else "OpenRouter"
                    return data
            except Exception:
                pass

        data = self._get_default_structure()
        try:
            self._save_to_disk(data)
        except Exception:
            pass
        return data

    def save_preset(self, name: str, config: dict, set_as_active: bool = True) -> None:
        """Saves or updates a preset in providers.json."""
        if not name or not name.strip():
            raise ValueError("Preset name cannot be empty")
        name = name.strip()
        data = self.load_presets()

        provider_type = config.get("provider_type")
        use_vertex = bool(config.get("use_vertex_ai") or provider_type == "vertex")

        base_url = config.get("base_url")
        api_key = config.get("api_key")

        preset_data = {
            "provider_type": "vertex" if use_vertex else "openai",
            "base_url": None if use_vertex else (base_url.strip() if isinstance(base_url, str) else base_url),
            "api_key": None if use_vertex else (api_key.strip() if isinstance(api_key, str) else api_key),
            "default_model": config.get("default_model") or (
                "google/gemini-2.5-flash" if use_vertex else "anthropic/claude-3.7-sonnet"
            ),
            "use_vertex_ai": use_vertex,
        }

        data.setdefault("presets", {})[name] = preset_data
        if set_as_active:
            data["active_preset"] = name
        self._save_to_disk(data)

    def delete_preset(self, name: str) -> bool:
        """Deletes a custom preset. Built-in presets cannot be deleted."""
        if name in BUILTIN_PRESETS:
            raise ValueError(f"Cannot delete built-in preset: '{name}'")
        data = self.load_presets()
        if name not in data.get("presets", {}):
            return False
        del data["presets"][name]
        if data.get("active_preset") == name:
            data["active_preset"] = "OpenRouter" if "OpenRouter" in data["presets"] else next(iter(data["presets"].keys()), "")
        self._save_to_disk(data)
        return True

    def get_active_preset(self) -> tuple[str, dict]:
        """Returns (active_preset_name, active_preset_dict)."""
        data = self.load_presets()
        active_name = data.get("active_preset")
        presets = data.get("presets", {})
        if active_name and active_name in presets:
            return active_name, dict(presets[active_name])
        if "OpenRouter" in presets:
            return "OpenRouter", dict(presets["OpenRouter"])
        if presets:
            first_key = next(iter(presets.keys()))
            return first_key, dict(presets[first_key])
        return "OpenRouter", dict(DEFAULT_PRESETS["OpenRouter"])

    def set_active_preset(self, name: str) -> None:
        """Sets active preset name in providers.json."""
        data = self.load_presets()
        if name in data.get("presets", {}):
            data["active_preset"] = name
            self._save_to_disk(data)


_default_manager = PresetManager()


def load_presets() -> dict:
    return _default_manager.load_presets()


def save_preset(name: str, config: dict, set_as_active: bool = True) -> None:
    return _default_manager.save_preset(name, config, set_as_active=set_as_active)


def delete_preset(name: str) -> bool:
    return _default_manager.delete_preset(name)


def get_active_preset() -> tuple[str, dict]:
    return _default_manager.get_active_preset()


def set_active_preset(name: str) -> None:
    return _default_manager.set_active_preset(name)
