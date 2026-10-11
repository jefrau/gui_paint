"""Manual acceptance for M3: a toolbar of icon buttons inside the 3D viewport.

This step needs a Blender window, so it is deliberately not part of tests/run.sh.
Run it from an interactive session:

    /opt/blender/blender-4.2.23-linux-x64/blender --python tests/manual_m3.py
    /opt/blender/blender-5.2.2-linux-x64/blender  --python tests/manual_m3.py

What to look for:

1. a dark rounded panel in the bottom-left of the 3D viewport;
2. three buttons inside it, each with an icon on the left and a label after it —
   Select with a triangle, Grab with a square, Move with a cross;
3. the labels are readable and the icons are recognisable at the default scale.

Hit-testing is interactive: from Blender's Python console, call
`manual_m3.probe(x, y)` with a region-local point (origin at the viewport's
bottom-left, y up) and it prints the widget under that point, or `None`.

Run `import manual_m3; manual_m3.stop()` to end it and leave the viewport clean.
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))  # repo root, so gui_paint_modules imports
sys.path.insert(0, str(_HERE))  # tests/, so `import manual_m3` works from the console

# Blender runs this file as `__main__`, so a bare `import manual_m3` from the console
# would build a second, empty module whose _state knows nothing about the armed
# surface. Aliasing the running module under its own name makes the documented console
# commands (probe/stop) act on the one that is actually armed.
sys.modules.setdefault("manual_m3", sys.modules[__name__])

import bpy

from gui_paint_modules import Anchor, Button, Icon, Node, Panel, Scene, Surface, VBox

BUTTONS = (
    ("Select", "select"),
    ("Grab", "grab"),
    ("Move", "move"),
)

_state = {"surface": None}


def build_scene():
    """Return the toolbar: a panel anchored bottom-left with one button per icon."""
    panel = Panel(layout=VBox(gap=2, padding=3), anchor=Anchor.bottom_left(margin=12))
    for label, icon_name in BUTTONS:
        panel.add(Button(label=label, icon=Icon.named(icon_name)))
    root = Node()
    root.add(panel)
    return Scene(root)


def _find_view3d():
    """Return a 3D viewport area, or None while the UI is not ready yet."""
    screen = bpy.context.screen
    if screen is None:
        return None
    return next((area for area in screen.areas if area.type == "VIEW_3D"), None)


def _arm():
    """Enable the scene once a 3D viewport exists, then stop the timer."""
    area = _find_view3d()
    if area is None:
        print("gui_paint M3: waiting for a 3D viewport...")
        return 1.0
    surface = Surface("SpaceView3D")
    surface.scene = build_scene()
    surface.enable(area)
    _state["surface"] = surface
    print("gui_paint M3: toolbar armed; call manual_m3.probe(x, y) to hit-test.")
    return None


def probe(x, y):
    """Print the widget under a region-local point, so hit-testing is checkable live."""
    surface = _state["surface"]
    if surface is None:
        print("gui_paint M3: not running; arm it first")
        return None
    node = surface.scene.hit_test(x, y)
    print(f"gui_paint M3: ({x}, {y}) -> {_describe(node)}")
    return node


def _describe(node):
    """Name a node by what it is and what it says, so a probe result is readable."""
    if node is None:
        return "nothing"
    text = getattr(node, "label", None) or getattr(node, "text", None)
    kind = type(node).__name__
    return f"{kind}({text!r})" if text else kind


def stop():
    """Disable the overlay and drop the timer."""
    if _state["surface"] is not None:
        _state["surface"].disable()
        _state["surface"] = None
    try:
        bpy.app.timers.unregister(_arm)
    except ValueError:
        pass
    print("gui_paint M3: stopped, nothing registered")


if __name__ == "__main__":
    bpy.app.timers.register(_arm, first_interval=1.0)
    print("gui_paint M3 manual check armed: watch the bottom-left of the 3D viewport.")
