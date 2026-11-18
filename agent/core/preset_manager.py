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
        "models": [
            "anthropic/claude-3.7-sonnet",
            "google/gemini-2.5-flash",
            "google/gemini-2.5-pro",
            "deepseek/deepseek-r1",
            "meta-llama/llama-3.3-70b-instruct",
            "openrouter/free",
        ],
        "default_image_model": "black-forest-labs/flux-1-schnell",
        "image_models": [
            "black-forest-labs/flux-1-schnell",
            "black-forest-labs/flux-1-dev",
            "stabilityai/stable-diffusion-3-medium",
        ],
    },
    "Google Vertex AI": {
        "provider_type": "vertex",
        "base_url": None,
        "api_key": None,
        "default_model": "google/gemini-2.5-flash",
        "models": [
            "google/gemini-2.5-flash",
            "google/gemini-2.5-pro",
            "google/gemini-3-flash-preview",
            "google/gemini-3.1-pro-preview",
        ],
        "default_image_model": "gemini-3.1-flash-image",
        "image_models": [
            "gemini-3.1-flash-image",
            "gemini-3-pro-image",
            "imagen-3.0-generate-002",
        ],
    },
    "Local Ollama": {
        "provider_type": "openai",
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
        "default_model": "qwen2.5-coder:14b",
        "models": [
            "qwen2.5-coder:14b",
            "deepseek-r1:14b",
            "llama3.3:latest",
        ],
        "default_image_model": "",
        "image_models": [],
    },
    "Groq": {
        "provider_type": "openai",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": "",
        "default_model": "llama-3.3-70b-versatile",
        "models": [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
            "deepseek-r1-distill-llama-70b",
        ],
        "default_image_model": "",
        "image_models": [],
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
        is_vertex_base = bool(current_base and "aiplatform.googleapis.com" in str(current_base).lower())

        if is_vertex_base and current_base:
            presets["Google Vertex AI"]["base_url"] = current_base
        if current_key and current_base and "openrouter" in str(current_base).lower():
            presets["OpenRouter"]["api_key"] = current_key
        if current_model:
            if is_vertex_base:
                presets["Google Vertex AI"]["default_model"] = current_model
            elif current_base and "openrouter" in str(current_base).lower():
                presets["OpenRouter"]["default_model"] = current_model

        active = "Google Vertex AI" if (is_vertex_base or (not current_key and not current_base)) else "OpenRouter"
        image_active = "Google Vertex AI" if "Google Vertex AI" in presets else active
        return {
            "active_preset": active,
            "image_preset": image_active,
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
                    # Ensure standard built-in presets exist and have models list
                    for k, v in DEFAULT_PRESETS.items():
                        if k not in data["presets"]:
                            data["presets"][k] = copy.deepcopy(v)
                        else:
                            # Backfill models list if missing in existing user preset
                            if "models" not in data["presets"][k] or not isinstance(data["presets"][k]["models"], list):
                                data["presets"][k]["models"] = list(v.get("models", []))
                            # Backfill image models and default image model if missing
                            if "image_models" not in data["presets"][k] or not isinstance(data["presets"][k]["image_models"], list):
                                data["presets"][k]["image_models"] = list(v.get("image_models", []))
                            if "default_image_model" not in data["presets"][k]:
                                data["presets"][k]["default_image_model"] = v.get("default_image_model", "")
                    
                    # Ensure custom presets also have a models list and image_models list
                    for k, preset_obj in data["presets"].items():
                        if "models" not in preset_obj or not isinstance(preset_obj["models"], list):
                            default_m = preset_obj.get("default_model")
                            preset_obj["models"] = [default_m] if default_m else []
                        if "image_models" not in preset_obj or not isinstance(preset_obj["image_models"], list):
                            default_im = preset_obj.get("default_image_model")
                            preset_obj["image_models"] = [default_im] if default_im else []
                        if "default_image_model" not in preset_obj:
                            preset_obj["default_image_model"] = preset_obj["image_models"][0] if preset_obj["image_models"] else ""

                    if not data.get("active_preset") or data["active_preset"] not in data["presets"]:
                        data["active_preset"] = "OpenRouter"

                    if not data.get("image_preset") or data["image_preset"] not in data["presets"]:
                        if "Google Vertex AI" in data["presets"]:
                            data["image_preset"] = "Google Vertex AI"
                        elif "OpenRouter" in data["presets"]:
                            data["image_preset"] = "OpenRouter"
                        else:
                            data["image_preset"] = data.get("active_preset", next(iter(data["presets"].keys()), ""))
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
        use_vertex = bool(name == "Google Vertex AI" or provider_type == "vertex")

        base_url = config.get("base_url")
        api_key = config.get("api_key")

        # Existing preset models or fallback to default
        existing_models = []
        existing_image_models = []
        existing_default_image_model = ""
        if name in data.get("presets", {}):
            existing_models = data["presets"][name].get("models", [])
            existing_image_models = data["presets"][name].get("image_models", [])
            existing_default_image_model = data["presets"][name].get("default_image_model", "")
        elif name in DEFAULT_PRESETS:
            existing_models = list(DEFAULT_PRESETS[name].get("models", []))
            existing_image_models = list(DEFAULT_PRESETS[name].get("image_models", []))
            existing_default_image_model = DEFAULT_PRESETS[name].get("default_image_model", "")

        models = config.get("models")
        if models is None or not isinstance(models, list):
            models = existing_models
        
        default_model = config.get("default_model") or (
            "google/gemini-2.5-flash" if use_vertex else "anthropic/claude-3.7-sonnet"
        )
        if default_model and default_model not in models:
            models = [default_model] + [m for m in models if m != default_model]

        image_models = config.get("image_models")
        if image_models is None or not isinstance(image_models, list):
            image_models = existing_image_models

        default_image_model = config.get("default_image_model") or existing_default_image_model or (
            "gemini-3.1-flash-image" if use_vertex else ("black-forest-labs/flux-1-schnell" if "openrouter" in str(base_url).lower() else "")
        )
        if default_image_model and default_image_model not in image_models:
            image_models = [default_image_model] + [m for m in image_models if m != default_image_model]

        preset_data = {
            "provider_type": "vertex" if use_vertex else "openai",
            "base_url": (base_url.strip() if isinstance(base_url, str) and base_url.strip() else None),
            "api_key": None if use_vertex else (api_key.strip() if isinstance(api_key, str) else api_key),
            "default_model": default_model,
            "models": models,
            "default_image_model": default_image_model,
            "image_models": image_models,
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
        if data.get("image_preset") == name:
            if "Google Vertex AI" in data["presets"]:
                data["image_preset"] = "Google Vertex AI"
            elif "OpenRouter" in data["presets"]:
                data["image_preset"] = "OpenRouter"
            else:
                data["image_preset"] = next(iter(data["presets"].keys()), "")
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

    def get_image_preset(self) -> tuple[str, dict]:
        """Returns (image_preset_name, image_preset_dict)."""
        data = self.load_presets()
        image_name = data.get("image_preset")
        presets = data.get("presets", {})
        if image_name and image_name in presets:
            return image_name, dict(presets[image_name])
        if "Google Vertex AI" in presets:
            return "Google Vertex AI", dict(presets["Google Vertex AI"])
        if "OpenRouter" in presets:
            return "OpenRouter", dict(presets["OpenRouter"])
        if presets:
            first_key = next(iter(presets.keys()))
            return first_key, dict(presets[first_key])
        return "Google Vertex AI", dict(DEFAULT_PRESETS["Google Vertex AI"])

    def set_image_preset(self, name: str, default_model: str | None = None) -> None:
        """Sets active image preset name in providers.json, optionally updating default_image_model."""
        data = self.load_presets()
        if name in data.get("presets", {}):
            data["image_preset"] = name
            if default_model and default_model.strip():
                clean_model = default_model.strip()
                data["presets"][name]["default_image_model"] = clean_model
                image_models = data["presets"][name].setdefault("image_models", [])
                if clean_model not in image_models:
                    image_models.append(clean_model)
            self._save_to_disk(data)

    def get_preset_image_models(self, name: str | None = None) -> list[str]:
        """Returns list of configured image models for a preset."""
        data = self.load_presets()
        target = name or data.get("image_preset") or "Google Vertex AI"
        preset = data.get("presets", {}).get(target)
        if preset and "image_models" in preset and isinstance(preset["image_models"], list):
            return list(preset["image_models"])
        if target in DEFAULT_PRESETS:
            return list(DEFAULT_PRESETS[target].get("image_models", []))
        return []

    def add_preset_image_model(self, preset_name: str, model_id: str) -> None:
        """Adds an image model to a preset's image_models list if not present."""
        if not preset_name or not model_id or not model_id.strip():
            return
        model_id = model_id.strip()
        data = self.load_presets()
        if preset_name in data.get("presets", {}):
            models = data["presets"][preset_name].setdefault("image_models", [])
            if model_id not in models:
                models.append(model_id)
                self._save_to_disk(data)

    def remove_preset_image_model(self, preset_name: str, model_id: str) -> bool:
        """Removes an image model from a preset's image_models list."""
        if not preset_name or not model_id:
            return False
        model_id = model_id.strip()
        data = self.load_presets()
        if preset_name in data.get("presets", {}):
            models = data["presets"][preset_name].get("image_models", [])
            if model_id in models:
                models.remove(model_id)
                if data["presets"][preset_name].get("default_image_model") == model_id:
                    data["presets"][preset_name]["default_image_model"] = models[0] if models else ""
                self._save_to_disk(data)
                return True
        return False

    def get_preset_models(self, name: str | None = None) -> list[str]:
        """Returns list of configured favorite/default models for a preset."""
        data = self.load_presets()
        target = name or data.get("active_preset") or "OpenRouter"
        preset = data.get("presets", {}).get(target)
        if preset and "models" in preset and isinstance(preset["models"], list):
            return list(preset["models"])
        if target in DEFAULT_PRESETS:
            return list(DEFAULT_PRESETS[target].get("models", []))
        return []

    def add_preset_model(self, preset_name: str, model_id: str) -> None:
        """Adds a model to a preset's model list if not present."""
        if not preset_name or not model_id or not model_id.strip():
            return
        model_id = model_id.strip()
        data = self.load_presets()
        if preset_name in data.get("presets", {}):
            models = data["presets"][preset_name].setdefault("models", [])
            if model_id not in models:
                models.append(model_id)
                self._save_to_disk(data)

    def remove_preset_model(self, preset_name: str, model_id: str) -> bool:
        """Removes a model from a preset's model list."""
        if not preset_name or not model_id:
            return False
        model_id = model_id.strip()
        data = self.load_presets()
        if preset_name in data.get("presets", {}):
            models = data["presets"][preset_name].get("models", [])
            if model_id in models:
                models.remove(model_id)
                self._save_to_disk(data)
                return True
        return False


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


def get_preset_models(name: str | None = None) -> list[str]:
    return _default_manager.get_preset_models(name)


def add_preset_model(preset_name: str, model_id: str) -> None:
    return _default_manager.add_preset_model(preset_name, model_id)


def remove_preset_model(preset_name: str, model_id: str) -> bool:
    return _default_manager.remove_preset_model(preset_name, model_id)


def get_image_preset() -> tuple[str, dict]:
    return _default_manager.get_image_preset()


def set_image_preset(name: str, default_model: str | None = None) -> None:
    return _default_manager.set_image_preset(name, default_model)


def get_preset_image_models(name: str | None = None) -> list[str]:
    return _default_manager.get_preset_image_models(name)


def add_preset_image_model(preset_name: str, model_id: str) -> None:
    return _default_manager.add_preset_image_model(preset_name, model_id)


def remove_preset_image_model(preset_name: str, model_id: str) -> bool:
    return _default_manager.remove_preset_image_model(preset_name, model_id)
