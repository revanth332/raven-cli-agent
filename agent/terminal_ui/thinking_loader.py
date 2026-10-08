import time
from textual.widgets import Static

class ThinkingMessage(Static):
    """A message bubble that shows a clean point spinner animation and elapsed timer."""
    FULL_TEXT = "Thinking..."
    SPINNER_FRAMES = [
        "∙∙∙",
        "●∙∙",
        "∙●∙",
        "∙∙●",
        "∙∙∙",
    ]

    def __init__(self, text: str = "Thinking...", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.FULL_TEXT = text
        self.start_time = time.time()
        self.frame_index = 0
        self._timer = None
        self._is_thinking = True

    def on_mount(self) -> None:
        # 125ms interval matching the "point" spinner spec
        self._timer = self.set_interval(0.125, self.tick)

    def tick(self) -> None:
        if not self._is_thinking:
            return
            
        elapsed = time.time() - self.start_time
        frame = self.SPINNER_FRAMES[self.frame_index % len(self.SPINNER_FRAMES)]
        self.frame_index += 1
        
        super().update(f"[bold cyan]{frame}[/bold cyan] {self.FULL_TEXT} [dim]({elapsed:.1f}s)[/dim]")

    def update(self, renderable="") -> None:
        if self._is_thinking:
            self._is_thinking = False
            if self._timer:
                self._timer.pause()
        super().update(renderable)

    def set_text(self, text: str):
        """Dynamically updates the full animation text without resetting the elapsed timer."""
        self.FULL_TEXT = text

    def reset_thinking(self) -> None:
        """Resets the state back to thinking and restarts the animation, keeping the overall elapsed timer."""
        self._is_thinking = True
        if self._timer:
            self._timer.resume()
        elapsed = time.time() - self.start_time
        frame = self.SPINNER_FRAMES[self.frame_index % len(self.SPINNER_FRAMES)]
        super().update(f"[bold cyan]{frame}[/bold cyan] {self.FULL_TEXT} [dim]({elapsed:.1f}s)[/dim]")

