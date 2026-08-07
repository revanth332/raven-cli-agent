from dotenv import load_dotenv
from pathlib import Path
import json

load_dotenv()

class Settings:
    def __init__(self):
        self.RAVEN_BASE_URL = None
        self.RAVEN_API_KEY = None
        self.RAVEN_MODEL = "google/gemini-3-flash-preview"
        self.RAVEN_USE_VERTEX_AI = False
        self.config_file = Path.home() / ".raven" / "config.json"
        try:
            self.config = json.loads(self.config_file.read_text(encoding="utf-8"))
        except:
            self.config = None
        if self.config:
            self.RAVEN_BASE_URL = self.config.get("RAVEN_BASE_URL")
            self.RAVEN_API_KEY = self.config.get("RAVEN_API_KEY")
            self.RAVEN_MODEL = self.config.get("RAVEN_MODEL")
            self.RAVEN_USE_VERTEX_AI = self.config.get("RAVEN_USE_VERTEX_AI")
    def set_config(self,config):
        if not self.config:
            self.config = {}
        for key,value in config.items():
            self.config[key] = value
        try:
            self.config_file.write_text(json.dumps(self.config),encoding="utf-8")
        except Exception as e:
            raise e


settings = Settings()