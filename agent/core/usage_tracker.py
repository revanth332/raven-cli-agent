"""
Thread-safe session usage and cost tracker with daily breakdowns and HTML visualization dashboard.
"""

from threading import Lock
from pathlib import Path
from datetime import datetime
import json
from typing import Dict, Any, Optional

from agent.core.pricing import calculate_cost, get_model_pricing
from agent.core.usage_html_template import USAGE_REPORT_TEMPLATE


class UsageTracker:
    def __init__(self, persistence_file: Optional[Path] = None):
        self._lock = Lock()
        
        # Turn metrics (latest request)
        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0
        self.last_cost = 0.0
        
        # Cumulative session metrics
        self.session_prompt_tokens = 0
        self.session_completion_tokens = 0
        self.session_cost = 0.0
        self.total_requests = 0
        
        # Daily usage analytics: { "YYYY-MM-DD": { "<model_name>": { "prompt_tokens": int, "completion_tokens": int, "tokens": int, "requests": int, "cost": float } } }
        self.daily_usage: Dict[str, Dict[str, Dict[str, Any]]] = {}

        # Context window tracking
        self.current_context_tokens = 0
        self.max_context_limit = 128000
        
        # Persistence setup
        if persistence_file is None:
            home = Path.home() / ".raven"
            home.mkdir(parents=True, exist_ok=True)
            self.persistence_file = home / "usage_history.json"
        else:
            self.persistence_file = persistence_file

        self.js_data_file = self.persistence_file.parent / "usage_data.js"
        self.html_dashboard_file = self.persistence_file.parent / "usage_report.html"

        self.load_history()
        self.ensure_dashboard_html()

    def record_turn(self, prompt_tokens: int, completion_tokens: int, model_name: str) -> Dict[str, Any]:
        """
        Records usage for a completed turn/request, updates session totals and daily breakdowns.
        """
        turn_cost = calculate_cost(prompt_tokens, completion_tokens, model_name)
        today = datetime.now().strftime("%Y-%m-%d")
        total_turn_tokens = prompt_tokens + completion_tokens
        
        with self._lock:
            self.last_prompt_tokens = prompt_tokens
            self.last_completion_tokens = completion_tokens
            self.last_cost = turn_cost
            
            self.session_prompt_tokens += prompt_tokens
            self.session_completion_tokens += completion_tokens
            self.session_cost += turn_cost
            self.total_requests += 1

            # Daily model aggregation
            if today not in self.daily_usage:
                self.daily_usage[today] = {}
            if model_name not in self.daily_usage[today]:
                self.daily_usage[today][model_name] = {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "tokens": 0,
                    "requests": 0,
                    "cost": 0.0,
                }
            
            rec = self.daily_usage[today][model_name]
            rec["prompt_tokens"] += prompt_tokens
            rec["completion_tokens"] += completion_tokens
            rec["tokens"] += total_turn_tokens
            rec["requests"] += 1
            rec["cost"] = round(rec["cost"] + turn_cost, 6)
            
        self.save_history()
        return self.get_summary(model_name)

    def update_context(self, context_tokens: int, model_name: str):
        """
        Updates current active context window usage.
        """
        pricing = get_model_pricing(model_name)
        with self._lock:
            self.current_context_tokens = context_tokens
            self.max_context_limit = pricing.get("context_limit", 128000)

    def get_summary(self, model_name: str = "gpt-4o") -> Dict[str, Any]:
        """
        Returns snapshot of current usage, costs, and context fill ratio.
        """
        pricing = get_model_pricing(model_name)
        limit = pricing.get("context_limit", 128000)
        
        with self._lock:
            context_pct = min(100.0, (self.current_context_tokens / max(1, limit)) * 100.0)
            return {
                "last_prompt_tokens": self.last_prompt_tokens,
                "last_completion_tokens": self.last_completion_tokens,
                "last_cost": round(self.last_cost, 6),
                "session_prompt_tokens": self.session_prompt_tokens,
                "session_completion_tokens": self.session_completion_tokens,
                "session_cost": round(self.session_cost, 6),
                "total_requests": self.total_requests,
                "current_context_tokens": self.current_context_tokens,
                "max_context_limit": limit,
                "context_percent": round(context_pct, 1),
            }

    def ensure_dashboard_html(self) -> Path:
        """
        Generates or refreshes usage_report.html on disk.
        """
        try:
            self.html_dashboard_file.parent.mkdir(parents=True, exist_ok=True)
            self.html_dashboard_file.write_text(USAGE_REPORT_TEMPLATE, encoding="utf-8")
        except Exception:
            pass
        return self.html_dashboard_file

    def get_dashboard_path(self) -> Path:
        """Returns the absolute path to usage_report.html."""
        self.ensure_dashboard_html()
        return self.html_dashboard_file

    def save_history(self):
        """
        Persists cumulative metrics and daily usage to disk, and updates usage_data.js.
        """
        with self._lock:
            data = {
                "session_prompt_tokens": self.session_prompt_tokens,
                "session_completion_tokens": self.session_completion_tokens,
                "session_cost": round(self.session_cost, 6),
                "total_requests": self.total_requests,
                "daily_usage": self.daily_usage,
            }
            daily_snapshot = dict(self.daily_usage)

        try:
            self.persistence_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.persistence_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            # Write usage_data.js for instant zero-CORS browser loading
            js_content = f"window.USAGE_DATA = {json.dumps(daily_snapshot, indent=2)};\n"
            with open(self.js_data_file, "w", encoding="utf-8") as f:
                f.write(js_content)
        except Exception:
            pass

    def load_history(self):
        """
        Loads persistent cumulative usage metrics and daily breakdowns from disk.
        """
        if not self.persistence_file.exists():
            return
            
        try:
            with open(self.persistence_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                with self._lock:
                    self.session_prompt_tokens = data.get("session_prompt_tokens", 0)
                    self.session_completion_tokens = data.get("session_completion_tokens", 0)
                    self.session_cost = data.get("session_cost", 0.0)
                    self.total_requests = data.get("total_requests", 0)
                    self.daily_usage = data.get("daily_usage", {})
        except Exception:
            pass
