"""Manual acceptance for M4: an interactive toolbar in the 3D viewport.

This step needs a Blender window, so it is deliberately not part of tests/run.sh. Run it
from an interactive session:

    /opt/blender/blender-4.2.23-linux-x64/blender --python tests/manual_m4.py
    /opt/blender/blender-5.2.2-linux-x64/blender  --python tests/manual_m4.py

What to look for:

1. a dark rounded panel in the bottom-left of the 3D viewport with three icon buttons;
2. moving the mouse over a button lightens it; leaving it darkens it again;
3. pressing a button darkens it further, and releasing inside prints "clicked <name>";
4. dragging off a button before releasing prints nothing;
5. moving the mouse or clicking outside the panel still orbits and zooms the viewport.

Hit-testing stays interactive: from Blender's Python console, call `manual_m4.probe(x, y)`
with a region-local point and it prints the widget under it, or `None`. Run
`import manual_m4; manual_m4.stop()` to end it and leave the viewport clean.

Split the 3D viewport into two before running to also exercise two interactive surfaces in
one window: each half then draws its own toolbar and answers its own buttons, which is the
multi-surface resolver observed live.
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))  # repo root, so gui_paint_modules imports
sys.path.insert(0, str(_HERE))  # tests/, so `import manual_m4` works from the console

# Blender runs this file as `__main__`, so a bare `import manual_m4` from the console
# would build a second, empty module whose _state knows nothing about the armed
# surfaces. Aliasing the running module under its own name makes the documented console
# commands (probe/stop) act on the one that is actually armed.
sys.modules.setdefault("manual_m4", sys.modules[__name__])

import bpy

from gui_paint_modules import Anchor, Button, Icon, Node, Panel, Scene, Surface, VBox

BUTTONS = (
    ("Select", "select"),
    ("Grab", "grab"),
    ("Move", "move"),
)

_state = {"surfaces": []}


def _clicked(label):
    """Return a handler that prints which button fired, so a live click is observable."""
    def handler():
        print(f"gui_paint M4: clicked {label}")
    return handler


def build_scene():
    """Return the toolbar: a panel anchored bottom-left with interactive buttons."""
    panel = Panel(layout=VBox(gap=2, padding=3), anchor=Anchor.bottom_left(margin=12))
    for label, icon_name in BUTTONS:
        panel.add(Button(label=label, icon=Icon.named(icon_name), on_click=_clicked(label)))
    root = Node()
    root.add(panel)
    return Scene(root)


def _view3d_areas():
    """Return every 3D viewport area in the current screen, in order."""
    screen = bpy.context.screen
    if screen is None:
        return []
    return [area for area in screen.areas if area.type == "VIEW_3D"]


def _arm():
    """Enable one interactive surface per 3D viewport, then stop the timer."""
    areas = _view3d_areas()
    if not areas:
        print("gui_paint M4: waiting for a 3D viewport...")
        return 1.0
    for area in areas:
        surface = Surface("SpaceView3D", interactive=True)
        surface.scene = build_scene()
        surface.enable(area)
        _state["surfaces"].append(surface)
    print(f"gui_paint M4: {len(areas)} toolbar(s) armed; hover and click a button.")
    return None


def probe(x, y):
    """Print the widget under a region-local point, so hit-testing is checkable live."""
    surfaces = _state["surfaces"]
    if not surfaces:
        print("gui_paint M4: not running; arm it first")
        return None
    node = surfaces[0].scene.hit_test(x, y)
    print(f"gui_paint M4: ({x}, {y}) -> {_describe(node)}")
    return node


def _describe(node):
    """Name a node by what it is and what it says, so a probe result is readable."""
    if node is None:
        return "nothing"
    text = getattr(node, "label", None) or getattr(node, "text", None)
    kind = type(node).__name__
    return f"{kind}({text!r})" if text else kind


def stop():
    """Disable every overlay and drop the timer."""
    for surface in _state["surfaces"]:
        surface.disable()
    _state["surfaces"] = []
    try:
        bpy.app.timers.unregister(_arm)
    except ValueError:
        pass
    print("gui_paint M4: stopped, nothing registered")


if __name__ == "__main__":
    bpy.app.timers.register(_arm, first_interval=1.0)
    print("gui_paint M4 manual check armed: watch the bottom-left of the 3D viewport.")
