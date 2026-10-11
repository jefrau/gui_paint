"""Manual acceptance for M2: a laid-out tree inside the 3D viewport.

This step needs a Blender window, so it is deliberately not part of tests/run.sh.
Run it from an interactive session:

    /opt/blender/blender-4.2.23-linux-x64/blender --python tests/manual_m2.py
    /opt/blender/blender-5.2.2-linux-x64/blender --python tests/manual_m2.py

What to look for:

1. a blue panel in the bottom-left of the 3D viewport;
2. three coloured rectangles stacked inside it, top to bottom, with a gap, the
   bottom one taller because it fills the space left over;
3. a small yellow square pinned to the panel's top-right corner.

Hit-testing is interactive: from Blender's Python console, call
`manual_m2.probe(x, y)` with a region-local point (origin at the viewport's
bottom-left, y up) and it prints the node under that point, or `None`.

Run `import manual_m2; manual_m2.stop()` to end it and leave the viewport clean.
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))  # repo root, so gui_paint_modules imports
sys.path.insert(0, str(_HERE))  # tests/, so `import manual_m2` works from the console

# Blender runs this file as `__main__`, so a bare `import manual_m2` from the console
# would build a second, empty module whose _state knows nothing about the armed
# surface. Aliasing the running module under its own name makes the documented console
# commands (probe/stop) act on the one that is actually armed.
sys.modules.setdefault("manual_m2", sys.modules[__name__])

import bpy

from gui_paint_modules import Anchor, Node, Scene, Size, Surface, VBox

PANEL_COLOR = (0.10, 0.35, 0.65, 1.0)
STACK_COLORS = (
    (0.90, 0.30, 0.30, 1.0),
    (0.30, 0.80, 0.30, 1.0),
    (0.90, 0.60, 0.20, 1.0),
)
ANCHOR_COLOR = (0.95, 0.90, 0.25, 1.0)

_state = {"surface": None}


class DebugNode(Node):
    """A node that paints its own rectangle, so the layout is visible."""

    def __init__(self, name, color, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.color = color

    def draw(self, canvas):
        """Fill the node's box in its own pixel space."""
        canvas.rect(0.0, 0.0, float(self.rect[2]), float(self.rect[3]), self.color)


def build_scene():
    """Return the scene the manual step draws: a panel with stacked and pinned children."""
    panel = DebugNode(
        "panel",
        PANEL_COLOR,
        layout=VBox(gap=4, padding=6),
        size=Size.fixed(140),
        anchor=Anchor.bottom_left(margin=12),
    )
    panel.add(DebugNode("stack-0", STACK_COLORS[0], size=Size.fixed(36)))
    panel.add(DebugNode("stack-1", STACK_COLORS[1], size=Size.fixed(36)))
    panel.add(DebugNode("stack-2", STACK_COLORS[2], size=Size.fill()))
    panel.add(DebugNode("pinned", ANCHOR_COLOR, size=Size.fixed(20),
                        anchor=Anchor.top_right(margin=4)))

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
        print("gui_paint M2: waiting for a 3D viewport...")
        return 1.0
    surface = Surface("SpaceView3D")
    surface.scene = build_scene()
    surface.enable(area)
    _state["surface"] = surface
    print("gui_paint M2: panel armed; call manual_m2.probe(x, y) to hit-test.")
    return None


def probe(x, y):
    """Print the node under a region-local point, so hit-testing is checkable live."""
    surface = _state["surface"]
    if surface is None:
        print("gui_paint M2: not running; arm it first")
        return None
    node = surface.scene.hit_test(x, y)
    label = getattr(node, "name", None)
    if node is None:
        label = "nothing"
    elif label is None:
        label = "container"
    print(f"gui_paint M2: ({x}, {y}) -> {label}")
    return node


def stop():
    """Disable the overlay and drop the timer."""
    if _state["surface"] is not None:
        _state["surface"].disable()
        _state["surface"] = None
    try:
        bpy.app.timers.unregister(_arm)
    except ValueError:
        pass
    print("gui_paint M2: stopped, nothing registered")


if __name__ == "__main__":
    bpy.app.timers.register(_arm, first_interval=1.0)
    print("gui_paint M2 manual check armed: watch the bottom-left of the 3D viewport.")
