"""
core/tray.py
System tray icon for the voice assistant.

Why this exists: running fully invisible in the background is bad UX —
you can't tell if it's alive, and the only way to stop it is Task Manager.
This gives you a small icon near the clock with:
  - a color that shows state (gray = idle/listening, orange = paused)
  - a right-click menu: Pause/Resume, Quit

Requires: pip install pystray pillow
"""

"""
core/tray.py
System tray icon for the voice assistant.

Features
--------
✓ Green icon = Listening
✓ Orange icon = Paused
✓ Right-click menu:
    - Pause / Resume
    - Quit

The tray icon shares state with the assistant thread through the
AssistantState object.
"""

from PIL import Image, ImageDraw
import pystray


class AssistantState:
    """
    Shared state between the tray thread and the assistant thread.
    """

    def __init__(self):
        self.running = True
        self.paused = False
        self.icon = None


state = AssistantState()


def _make_dot(color: str) -> Image.Image:
    """
    Creates a simple colored circular tray icon.
    Replace this later with your own .ico if desired.
    """
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((6, 6, 58, 58), fill=color)
    return img


# Green = running
_ICON_IDLE = _make_dot("#4CAF50")

# Orange = paused
_ICON_PAUSED = _make_dot("#FF9800")


def _on_toggle_pause(icon, item):
    """
    Pause / Resume the assistant.
    """
    state.paused = not state.paused

    if state.paused:
        icon.icon = _ICON_PAUSED
        icon.title = "Rakesh Assistant (Paused)"
    else:
        icon.icon = _ICON_IDLE
        icon.title = "Rakesh Assistant (Listening)"


def _on_quit(icon, item):
    """
    Stop the assistant completely.
    """
    state.running = False
    icon.stop()


def _pause_label(item):
    """
    Dynamic menu label.
    """
    return "Resume" if state.paused else "Pause"


def run_tray():
    """
    Runs the system tray.

    This MUST execute on the main thread.
    """

    menu = pystray.Menu(
        pystray.MenuItem(_pause_label, _on_toggle_pause),
        pystray.MenuItem("Quit", _on_quit),
    )

    icon = pystray.Icon(
        "rakesh_assistant",
        _ICON_IDLE,
        "Rakesh Assistant (Listening)",
        menu,
    )

    # Save a reference so other modules (like main.py)
    # can stop the tray programmatically.
    state.icon = icon

    icon.run()