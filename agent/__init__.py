import sys

_default_excepthook = sys.excepthook


def _silent_keyboard_interrupt_hook(exc_type, exc_value, exc_traceback):
    """Suppress noisy Python tracebacks when Ctrl+C is pressed during startup/imports."""
    if issubclass(exc_type, KeyboardInterrupt):
        return
    _default_excepthook(exc_type, exc_value, exc_traceback)


sys.excepthook = _silent_keyboard_interrupt_hook
