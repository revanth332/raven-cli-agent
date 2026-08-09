from textual.widgets import Static

class ThinkingMessage(Static):
    """A message bubble that shows a typewriter animation until updated."""
    FULL_TEXT = "Thinking..."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.char_index = 0
        self.direction = 1
        self._timer = None
        self._is_thinking = True

    def on_mount(self) -> None:
        self._timer = self.set_interval(0.1, self.tick)

    def tick(self) -> None:
        if not self._is_thinking:
            return
            
        self.char_index += self.direction
        if self.char_index >= len(self.FULL_TEXT):
            self.char_index = len(self.FULL_TEXT)
            self.direction = -1
        elif self.char_index <= 0:
            self.char_index = 0
            self.direction = 1
            
        super().update(f"● {self.FULL_TEXT[:self.char_index]}")

    def update(self, renderable="") -> None:
        if self._is_thinking:
            self._is_thinking = False
            if self._timer:
                self._timer.pause()
        super().update(renderable)

    def reset_thinking(self) -> None:
        """Resets the state back to thinking and restarts the typewriter animation."""
        self._is_thinking = True
        self.char_index = 0
        self.direction = 1
        if self._timer:
            self._timer.resume()
        super().update("● ")

