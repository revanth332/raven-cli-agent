"""
Sidebar component for displaying token, context, and cost consumption metrics in Textual TUI.
"""

from textual.containers import Vertical
from textual.widgets import Static
from rich.panel import Panel
from rich.text import Text
from rich.console import Group
from typing import Dict, Any


class ConsumptionSidebar(Vertical):
    """
    TUI Sidebar widget displaying real-time token usage, context fill ratio, and session cost analytics.
    """

    DEFAULT_CSS = """
    ConsumptionSidebar {
        width: 32;
        min-width: 28;
        max-width: 38;
        height: 100%;
        background: #14171f;
        border-left: heavy #22D3EE;
        padding: 1 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.metrics_static = Static(id="sidebar_metrics")

    def compose(self):
        yield self.metrics_static

    def on_mount(self):
        self.update_metrics()

    def update_metrics(self, metrics: Dict[str, Any] | None = None):
        """
        Updates the sidebar with fresh usage, context, and cost metrics.
        """
        if metrics is None:
            metrics = {
                "last_prompt_tokens": 0,
                "last_completion_tokens": 0,
                "last_cost": 0.0,
                "session_prompt_tokens": 0,
                "session_completion_tokens": 0,
                "session_cost": 0.0,
                "total_requests": 0,
                "current_context_tokens": 0,
                "max_context_limit": 128000,
                "context_percent": 0.0,
            }

        last_prompt = metrics.get("last_prompt_tokens", 0)
        last_completion = metrics.get("last_completion_tokens", 0)
        last_cost = metrics.get("last_cost", 0.0)

        session_prompt = metrics.get("session_prompt_tokens", 0)
        session_completion = metrics.get("session_completion_tokens", 0)
        session_tokens = session_prompt + session_completion
        session_cost = metrics.get("session_cost", 0.0)
        total_reqs = metrics.get("total_requests", 0)

        curr_context = metrics.get("current_context_tokens", 0)
        max_context = metrics.get("max_context_limit", 128000)
        context_pct = metrics.get("context_percent", 0.0)

        # Build Context Progress Bar
        bar_length = 16
        filled_length = int(round((bar_length * context_pct) / 100.0))
        filled_length = min(bar_length, max(0, filled_length))
        empty_length = bar_length - filled_length

        if context_pct > 80:
            bar_color = "red"
        elif context_pct > 50:
            bar_color = "yellow"
        else:
            bar_color = "cyan"

        bar_str = f"[{bar_color}]" + "█" * filled_length + f"[dim white]" + "░" * empty_length + f"[/dim white][/{bar_color}]"

        content = Text()
        content.append("📊 METRICS & COST\n", style="bold cyan")
        content.append("───────────────\n", style="dim grey")

        # Context Section
        content.append("🧠 Context Fill:\n", style="bold white")
        content.append(f"{curr_context:,} / {max_context:,} tkn\n", style="dim white")

        # Render context bar using markup format in static
        text_markup = (
            f"[bold cyan]📊 CONSUMPTION METRICS[/bold cyan]\n"
            f"[dim #475569]────────────────────────────[/dim #475569]\n\n"
            f"[bold #F8FAFC]🧠 Context Fill:[/bold #F8FAFC] {context_pct:.1f}%\n"
            f"{bar_str}\n"
            f"[dim #94A3B8]{curr_context:,} / {max_context:,} tokens[/dim #94A3B8]\n\n"
            f"[dim #475569]────────────────────────────[/dim #475569]\n\n"
            f"[bold #F8FAFC]⚡ Last Turn:[/bold #F8FAFC]\n"
            f"  [dim #94A3B8]Prompt:[/dim #94A3B8] {last_prompt:,}\n"
            f"  [dim #94A3B8]Completion:[/dim #94A3B8] {last_completion:,}\n"
            f"  [dim #94A3B8]Cost:[/dim #94A3B8] [bold #10B981]${last_cost:.4f}[/bold #10B981]\n\n"
            f"[dim #475569]────────────────────────────[/dim #475569]\n\n"
            f"[bold #F8FAFC]📈 Session Totals:[/bold #F8FAFC]\n"
            f"  [dim #94A3B8]Requests:[/dim #94A3B8] {total_reqs}\n"
            f"  [dim #94A3B8]Total Tokens:[/dim #94A3B8] {session_tokens:,}\n"
            f"  [dim #94A3B8]Total Cost:[/dim #94A3B8] [bold #10B981]${session_cost:.4f}[/bold #10B981]\n"
        )

        try:
            self.metrics_static.update(text_markup)
        except Exception:
            pass
