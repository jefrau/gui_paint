"""Manual acceptance for M1: a rectangle that toggles inside the 3D viewport.

This step needs a Blender window, so it is deliberately not part of tests/run.sh.
Run it from an interactive session:

    blender --python tests/manual_m1.py

What to look for:

1. a red rectangle appears in the bottom-left corner of the 3D viewport;
2. every two seconds it disappears and comes back, repeatedly;
3. quitting Blender leaves nothing registered.

Run `stop()` from Blender's Python console to end the toggle early and check that
the rectangle is gone.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bpy

from gui_paint_modules import Surface

RECT = {"x": 20.0, "y": 20.0, "w": 160.0, "h": 90.0, "color": (1.0, 0.15, 0.15, 1.0)}

_state = {"surface": None, "enabled": False}


def _find_view3d():
    """Return a 3D viewport area, or None while the UI is not ready yet."""
    screen = bpy.context.screen
    if screen is None:
        return None
    return next((area for area in screen.areas if area.type == "VIEW_3D"), None)


def _paint(canvas):
    """Draw the rectangle the manual step looks for."""
    canvas.rect(RECT["x"], RECT["y"], RECT["w"], RECT["h"], RECT["color"])


def _toggle():
    """Enable or disable the overlay every time the timer fires."""
    area = _find_view3d()
    if area is None:
        return 1.0
    if _state["surface"] is None:
        surface = Surface("SpaceView3D")
        surface.draw = _paint
        _state["surface"] = surface
    if _state["enabled"]:
        _state["surface"].disable()
    else:
        _state["surface"].enable(area)
    _state["enabled"] = not _state["enabled"]
    print(f"gui_paint M1: overlay {'on' if _state['enabled'] else 'off'}")
    return 2.0


def stop():
    """Disable the overlay and drop the timer."""
    if _state["surface"] is not None:
        _state["surface"].disable()
        _state["enabled"] = False
    try:
        bpy.app.timers.unregister(_toggle)
    except ValueError:
        pass
    print("gui_paint M1: stopped, nothing registered")


bpy.app.timers.register(_toggle, first_interval=1.0)
print("gui_paint M1 manual check armed: watch the bottom-left of the 3D viewport.")
