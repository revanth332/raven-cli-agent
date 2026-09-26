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


def compute_percentile(sorted_samples: list, p: float) -> float:
    """
    Computes the p-th percentile (0.0 to 1.0) of a sorted list of numeric values.
    Returns 0.0 if sorted_samples is empty.
    """
    if not sorted_samples:
        return 0.0
    n = len(sorted_samples)
    if n == 1:
        return float(sorted_samples[0])
    k = (n - 1) * p
    f = int(k)
    c = f + 1
    if c >= n:
        return float(sorted_samples[-1])
    d = k - f
    return round(float(sorted_samples[f] + d * (sorted_samples[c] - sorted_samples[f])), 1)


class UsageTracker:
    def __init__(self, persistence_file: Optional[Path] = None):
        self._lock = Lock()
        
        # Turn metrics (latest request)
        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0
        self.last_cost = 0.0
        self.last_duration_ms = 0.0
        self.last_ttft_ms: Optional[float] = None
        
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

    def record_turn(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model_name: str,
        duration_ms: float = 0.0,
        ttft_ms: Optional[float] = None,
        status: str = "success",       # "success" | "error"
        error_code: Optional[str] = None  # "429", "500", "503", "TIMEOUT", "CONTEXT_EXCEEDED", "AUTH_ERROR"
    ) -> Dict[str, Any]:
        """
        Records usage and latency/failure telemetry for a turn/request,
        updates session totals and daily breakdowns.
        """
        turn_cost = calculate_cost(prompt_tokens, completion_tokens, model_name)
        today = datetime.now().strftime("%Y-%m-%d")
        total_turn_tokens = prompt_tokens + completion_tokens
        
        with self._lock:
            self.last_prompt_tokens = prompt_tokens
            self.last_completion_tokens = completion_tokens
            self.last_cost = turn_cost
            self.last_duration_ms = duration_ms
            self.last_ttft_ms = ttft_ms
            
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
                    "latency": {
                        "samples_ms": [],
                        "avg_ms": 0.0,
                        "p50_ms": 0.0,
                        "p95_ms": 0.0,
                        "avg_ttft_ms": 0.0,
                        "ttft_samples_ms": [],
                        "points": []
                    },
                    "reliability": {
                        "success_count": 0,
                        "failure_count": 0,
                        "failure_reasons": {}
                    }
                }
            
            rec = self.daily_usage[today][model_name]
            rec["prompt_tokens"] += prompt_tokens
            rec["completion_tokens"] += completion_tokens
            rec["tokens"] += total_turn_tokens
            rec["requests"] += 1
            rec["cost"] = round(rec["cost"] + turn_cost, 6)

            # Ensure latency structure exists (e.g., if loaded from legacy history)
            lat = rec.setdefault("latency", {
                "samples_ms": [],
                "avg_ms": 0.0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
                "avg_ttft_ms": 0.0,
                "ttft_samples_ms": [],
                "points": []
            })
            samples = lat.setdefault("samples_ms", [])
            points = lat.setdefault("points", [])
            ttft_samples = lat.setdefault("ttft_samples_ms", [])

            if duration_ms > 0:
                samples.append(round(duration_ms, 2))
                if len(samples) > 100:
                    samples[:] = samples[-100:]
                lat["avg_ms"] = round(sum(samples) / len(samples), 1)
                sorted_samples = sorted(samples)
                lat["p50_ms"] = compute_percentile(sorted_samples, 0.50)
                lat["p95_ms"] = compute_percentile(sorted_samples, 0.95)

                points.append({
                    "tokens": completion_tokens,
                    "duration_ms": round(duration_ms, 2)
                })
                if len(points) > 100:
                    points[:] = points[-100:]

            if ttft_ms is not None and ttft_ms > 0:
                ttft_samples.append(round(ttft_ms, 2))
                if len(ttft_samples) > 100:
                    ttft_samples[:] = ttft_samples[-100:]
                lat["avg_ttft_ms"] = round(sum(ttft_samples) / len(ttft_samples), 1)

            # Reliability tracking
            rel = rec.setdefault("reliability", {
                "success_count": 0,
                "failure_count": 0,
                "failure_reasons": {}
            })
            if status == "error":
                rel["failure_count"] = rel.get("failure_count", 0) + 1
                reasons = rel.setdefault("failure_reasons", {})
                code_key = str(error_code) if error_code else "UNKNOWN"
                reasons[code_key] = reasons.get(code_key, 0) + 1
            else:
                rel["success_count"] = rel.get("success_count", 0) + 1
            
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
        Returns snapshot of current usage, costs, context fill ratio, and turn latency.
        """
        pricing = get_model_pricing(model_name)
        limit = pricing.get("context_limit", 128000)
        
        with self._lock:
            context_pct = min(100.0, (self.current_context_tokens / max(1, limit)) * 100.0)
            return {
                "last_prompt_tokens": self.last_prompt_tokens,
                "last_completion_tokens": self.last_completion_tokens,
                "last_cost": round(self.last_cost, 6),
                "last_duration_ms": round(self.last_duration_ms, 2),
                "last_ttft_ms": round(self.last_ttft_ms, 2) if self.last_ttft_ms is not None else None,
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
        Loads persistent cumulative usage metrics and daily breakdowns from disk,
        normalizing legacy records missing latency or reliability structures.
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

                    # Ensure backward compatibility for legacy records missing latency/reliability
                    for day, models in self.daily_usage.items():
                        if not isinstance(models, dict):
                            continue
                        for m_name, m_rec in models.items():
                            if not isinstance(m_rec, dict):
                                continue
                            if "latency" not in m_rec or not isinstance(m_rec["latency"], dict):
                                m_rec["latency"] = {
                                    "samples_ms": [],
                                    "avg_ms": 0.0,
                                    "p50_ms": 0.0,
                                    "p95_ms": 0.0,
                                    "avg_ttft_ms": 0.0,
                                    "ttft_samples_ms": [],
                                    "points": [],
                                }
                            else:
                                lat = m_rec["latency"]
                                lat.setdefault("samples_ms", [])
                                lat.setdefault("avg_ms", 0.0)
                                lat.setdefault("p50_ms", 0.0)
                                lat.setdefault("p95_ms", 0.0)
                                lat.setdefault("avg_ttft_ms", 0.0)
                                lat.setdefault("ttft_samples_ms", [])
                                lat.setdefault("points", [])

                            if "reliability" not in m_rec or not isinstance(m_rec["reliability"], dict):
                                m_rec["reliability"] = {
                                    "success_count": m_rec.get("requests", 0),
                                    "failure_count": 0,
                                    "failure_reasons": {},
                                }
                            else:
                                rel = m_rec["reliability"]
                                rel.setdefault("success_count", m_rec.get("requests", 0))
                                rel.setdefault("failure_count", 0)
                                rel.setdefault("failure_reasons", {})
        except Exception:
            pass
