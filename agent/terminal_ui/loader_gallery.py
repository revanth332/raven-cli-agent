from typing import Dict, Any, List
import copy

from rich.text import Text
from rich.markup import escape
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Static, Input
from textual.binding import Binding

try:
    from rich._spinners import SPINNERS as RICH_SPINNERS
except Exception:
    RICH_SPINNERS = {}

CUSTOM_SPINNERS: Dict[str, Dict[str, Any]] = {
    "brailleSnake": {
        "interval": 80,
        "frames": [
            "⠁⠂⠄⡀⢀⠠⠐⠈",
            "⠈⠁⠂⠄⡀⢀⠠⠐",
            "⠐⠈⠁⠂⠄⡀⢀⠠",
            "⠠⠐⠈⠁⠂⠄⡀⢀",
            "⢀⠠⠐⠈⠁⠂⠄⡀",
            "⡀⢀⠠⠐⠈⠁⠂⠄",
            "⠄⡀⢀⠠⠐⠈⠁⠂",
            "⠂⠄⡀⢀⠠⠐⠈⠁",
        ],
    },
    "bouncingBall": {
        "interval": 80,
        "frames": [
            "( ●    )",
            "(  ●   )",
            "(   ●  )",
            "(    ● )",
            "(     ●)",
            "(    ● )",
            "(   ●  )",
            "(  ●   )",
            "( ●    )",
            "(●     )",
        ],
    },
    "point": {
        "interval": 125,
        "frames": [
            "∙∙∙",
            "●∙∙",
            "∙●∙",
            "∙∙●",
            "∙∙∙",
        ],
    },
}

ALL_SPINNERS: Dict[str, Dict[str, Any]] = copy.deepcopy(CUSTOM_SPINNERS)


class LiveSpinnerWidget(Static):
    """An animated widget rendering a specific spinner's frame sequence at its native interval."""
    
    def __init__(self, spinner_name: str, spinner_spec: Dict[str, Any], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.spinner_name = spinner_name
        self.spinner_spec = spinner_spec
        raw_frames = spinner_spec.get("frames", ["."])
        if isinstance(raw_frames, str):
            self.frames = list(raw_frames)
        else:
            self.frames = list(raw_frames)
        self.interval_ms = spinner_spec.get("interval", 100)
        self.frame_idx = 0
        self._timer = None

    def on_mount(self) -> None:
        interval_sec = max(0.015, self.interval_ms / 1000.0)
        self._timer = self.set_interval(interval_sec, self.advance_frame)
        self.advance_frame()

    def advance_frame(self) -> None:
        if not self.frames:
            return
        frame = self.frames[self.frame_idx % len(self.frames)]
        self.frame_idx += 1
        self.update(Text(str(frame), style="bold #22D3EE"))


class SpinnerCard(Vertical):
    """A visual card displaying spinner information and a live animation preview."""
    
    def __init__(self, name: str, spec: Dict[str, Any], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_class("spinner_card")
        self.spinner_name = name
        self.spinner_spec = spec

    def compose(self) -> ComposeResult:
        interval = self.spinner_spec.get("interval", 100)
        frames_count = len(self.spinner_spec.get("frames", []))
        
        with Horizontal(classes="card_header"):
            yield Static(self.spinner_name, classes="spinner_name")
            yield Static(f"{interval}ms", classes="spinner_interval")
        
        with Container(classes="spinner_preview_box"):
            yield LiveSpinnerWidget(self.spinner_name, self.spinner_spec, classes="spinner_live_text")
            
        yield Static(f"{frames_count} frames", classes="spinner_meta")


class LoaderGalleryApp(App):
    """Interactive TUI Gallery displaying all available terminal loaders and spinners."""
    
    CSS_PATH = "styles/loader_gallery.tcss"
    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("escape", "clear_or_quit", "Clear / Quit", show=True),
        Binding("/", "focus_search", "Search", show=True),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.search_debounce_timer = None
        self.current_filter = ""

    def compose(self) -> ComposeResult:
        total_count = len(ALL_SPINNERS)
        with Horizontal(id="header_bar"):
            yield Static(f"⚡ Raven Spinner Gallery ({total_count} Styles)", id="header_title")
            yield Static(Text("/ Search  •  q/ESC Exit", style="#94A3B8"), id="header_hint")

        with Container(id="search_container"):
            yield Input(placeholder="Search spinners (brailleSnake, bouncingBall, point)...", id="search_input")

        with ScrollableContainer(id="gallery_container"):
            with Container(id="spinner_grid"):
                for name, spec in sorted(ALL_SPINNERS.items()):
                    yield SpinnerCard(name, spec)

        yield Static("Raven CLI • Press [bold cyan]Q[/bold cyan] to return to terminal", id="footer_bar")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input with debouncing."""
        if event.input.id == "search_input":
            if self.search_debounce_timer is not None:
                self.search_debounce_timer.stop()
            self.search_debounce_timer = self.set_timer(0.25, lambda: self.apply_filter(event.value))

    def apply_filter(self, query: str) -> None:
        """Filters the mounted spinner cards based on search query."""
        self.current_filter = query.strip().lower()
        gallery_grid = self.query_one("#spinner_grid")
        gallery_grid.remove_children()
        
        filtered = [
            (name, spec) for name, spec in sorted(ALL_SPINNERS.items())
            if not self.current_filter or self.current_filter in name.lower()
        ]
        
        for name, spec in filtered:
            gallery_grid.mount(SpinnerCard(name, spec))

    def action_focus_search(self) -> None:
        search_input = self.query_one("#search_input", Input)
        search_input.focus()

    def action_clear_or_quit(self) -> None:
        search_input = self.query_one("#search_input", Input)
        if search_input.has_focus or search_input.value:
            search_input.value = ""
            self.apply_filter("")
            self.set_focus(None)
        else:
            self.exit()


def run_loader_gallery() -> None:
    """Entrypoint to launch the Loader Gallery Textual App."""
    app = LoaderGalleryApp()
    app.run()
