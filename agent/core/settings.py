from dotenv import load_dotenv
from pathlib import Path
import json
import os

load_dotenv()

class Settings:
    SCHEMA = {
        "RAVEN_BASE_URL": (None, "str", ["RAVEN_BASE_URL", "BASE_URL"]),
        "RAVEN_API_KEY": (None, "str", ["RAVEN_API_KEY", "API_KEY"]),
        "RAVEN_MODEL": ("google/gemini-3-flash-preview", "str", ["RAVEN_MODEL", "MODEL"]),
        "RAVEN_SMALL_MODEL": (None, "str", ["RAVEN_SMALL_MODEL", "SMALL_MODEL"]),
        "RAVEN_EMBEDDING_MODEL": (None, "str", ["RAVEN_EMBEDDING_MODEL", "EMBEDDING_MODEL"]),
        "RAVEN_USE_VERTEX_AI": (False, "bool", ["RAVEN_USE_VERTEX_AI", "USE_VERTEX_AI"]),
        "RAVEN_AUTO_APPROVE": (False, "bool", ["RAVEN_AUTO_APPROVE", "AUTO_APPROVE"]),
        "RAVEN_AGENT_SOFT_TURNS": (25, "int", ["RAVEN_AGENT_SOFT_TURNS", "AGENT_SOFT_TURNS"]),
        "RAVEN_AGENT_HARD_TURNS": (40, "int", ["RAVEN_AGENT_HARD_TURNS", "AGENT_HARD_TURNS"]),
        "RAVEN_AGENT_MAX_TOOL_CALLS": (60, "int", ["RAVEN_AGENT_MAX_TOOL_CALLS", "AGENT_MAX_TOOL_CALLS"]),
        "RAVEN_AGENT_MAX_NO_PROGRESS": (3, "int", ["RAVEN_AGENT_MAX_NO_PROGRESS", "AGENT_MAX_NO_PROGRESS"]),
        "RAVEN_AGENT_GRACE_TURNS": (4, "int", ["RAVEN_AGENT_GRACE_TURNS", "AGENT_GRACE_TURNS"]),
    }

    def __init__(self):
        self._known_settings = list(self.SCHEMA.keys())
        self.config_file = Path.home() / ".raven" / "config.json"
        self.config = {}
        self.reload()

    def _coerce(self, value, val_type):
        if value is None:
            return None
        if val_type == "bool":
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in ("true", "1", "yes")
        elif val_type == "int":
            try:
                return int(value)
            except (ValueError, TypeError):
                return value
        elif val_type == "float":
            try:
                return float(value)
            except (ValueError, TypeError):
                return value
        s = str(value).strip()
        if s.lower() in ("none", "null"):
            return None
        return s

    def reload(self):
        """Loads all settings with precedence: ENV > Config file > Default."""
        self.config = {}
        try:
            if self.config_file.exists():
                self.config = json.loads(self.config_file.read_text(encoding="utf-8"))
        except Exception:
            self.config = {}

        if not isinstance(self.config, dict):
            self.config = {}

        for canonical_attr, (default_val, val_type, lookup_keys) in self.SCHEMA.items():
            value = None
            found = False

            # 1. Environment variable check (highest priority)
            for k in lookup_keys:
                if k in os.environ and os.environ[k] is not None:
                    raw = os.environ[k]
                    if str(raw).strip() != "":
                        value = self._coerce(raw, val_type)
                        found = True
                        break

            # 2. Config file check (second priority)
            if not found:
                for k in lookup_keys:
                    if k in self.config and self.config[k] is not None:
                        raw = self.config[k]
                        if str(raw).strip() != "":
                            value = self._coerce(raw, val_type)
                            found = True
                            break

            # 3. Default fallback
            if not found:
                value = default_val

            setattr(self, canonical_attr, value)
            for alias in lookup_keys:
                setattr(self, alias, value)

    def set_config(self, config):
        if not self.config:
            self.config = {}
        for key, value in config.items():
            self.config[key] = value
            matched = False
            for canonical_attr, (default_val, val_type, lookup_keys) in self.SCHEMA.items():
                if key in lookup_keys:
                    coerced_val = self._coerce(value, val_type)
                    setattr(self, canonical_attr, coerced_val)
                    for alias in lookup_keys:
                        setattr(self, alias, coerced_val)
                    matched = True
                    break
            if not matched:
                setattr(self, key, value)
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            self.config_file.write_text(json.dumps(self.config, indent=4), encoding="utf-8")
        except Exception as e:
            raise e


settings = Settings()