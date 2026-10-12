"""
Sidebar component for displaying session, context tokens, cost, and active model status in Textual TUI.
"""

from pathlib import Path
from typing import Dict, Any, Optional
from textual.containers import Vertical
from textual.widgets import Static

_SIDEBAR_CSS = (Path(__file__).parent / "styles" / "sidebar.tcss").read_text(encoding="utf-8")


class ConsumptionSidebar(Vertical):
    """
    TUI Sidebar widget displaying session title, context token usage, cost, LSP status, and active model.
    """

    DEFAULT_CSS = _SIDEBAR_CSS

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.top_static = Static(id="sidebar_top")
        self.spacer = Static(id="sidebar_spacer")
        self.bottom_static = Static(id="sidebar_bottom")
        self.metrics_static = self.top_static
        self.session_name = "Greeting"
        self.project_name = "New Project"
        self.model_name: Optional[str] = None

    def compose(self):
        yield self.top_static
        yield self.spacer
        yield self.bottom_static

    def on_mount(self):
        from agent.utils import get_active_project_name
        proj = get_active_project_name() or Path.cwd().name
        self.project_name = proj
        self.update_metrics()

    def _format_cwd(self) -> str:
        try:
            cwd = Path.cwd().resolve()
            home = Path.home().resolve()
            try:
                rel = cwd.relative_to(home)
                path_str = f"/~\\{rel}" if rel.parts else "/~"
            except ValueError:
                path_str = str(cwd)
        except Exception:
            path_str = str(Path.cwd())

        if len(path_str) > 32:
            path_str = path_str[:30] + ".."
        return path_str

    def update_metrics(
        self,
        metrics: Optional[Dict[str, Any]] = None,
        session_name: Optional[str] = None,
        project_name: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        """
        Updates the sidebar with session context, tokens, cost, and Raven status info.
        """
        if session_name is not None:
            self.session_name = session_name
        if project_name is not None:
            self.project_name = project_name
        if model_name is not None:
            self.model_name = model_name

        if metrics is None:
            metrics = {
                "session_cost": 0.0,
                "current_context_tokens": 0,
                "context_percent": 0.0,
            }

        curr_context = metrics.get("current_context_tokens", 0)
        context_pct = metrics.get("context_percent", 0.0)
        session_cost = metrics.get("session_cost", 0.0)

        s_name = self.session_name or "Greeting"
        clean_session = s_name if len(s_name) <= 32 else s_name[:30] + ".."

        top_markup = (
            f"[bold #F8FAFC]{clean_session}[/bold #F8FAFC]\n\n"
            f"[bold #F8FAFC]Context[/bold #F8FAFC]\n"
            f"[#94A3B8]{curr_context:,} tokens[/#94A3B8]\n"
            f"[#94A3B8]{int(round(context_pct))}% used[/#94A3B8]\n"
            f"[#94A3B8]${session_cost:.2f} spent[/#94A3B8]"
        )

        cwd_str = self._format_cwd()

        bottom_markup = (
            f"[#94A3B8]{cwd_str}[/#94A3B8]\n\n"
            f"[#10B981]•[/#10B981] [bold #F8FAFC]Raven[/bold #F8FAFC]"
        )

        try:
            self.top_static.update(top_markup)
            self.bottom_static.update(bottom_markup)
        except Exception:
            pass
