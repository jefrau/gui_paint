"""Manual acceptance for M5: a custom menu opened from a button.

This step needs a Blender window, so it is deliberately not part of tests/run.sh. Run it
from an interactive session:

    /opt/blender/blender-4.2.23-linux-x64/blender --python tests/manual_m5.py
    /opt/blender/blender-5.2.2-linux-x64/blender  --python tests/manual_m5.py

What to look for:

1. a dark panel in the bottom-left of the 3D viewport with a "Menu" button;
2. clicking the button opens a small popup with three rows above it;
3. moving the mouse over a row lightens it; leaving darkens it again;
4. clicking a row prints "clicked <label>" and closes the popup;
5. clicking anywhere outside the popup closes it and does nothing else;
6. after it closes, hovering the button lights it again, and moving or clicking outside
   the panel still orbits and zooms the viewport.

This run is also the live probe for the two facts the headless checks cannot pin: that
enabling a second surface from inside the running modal is safe (the menu opens, no second
modal), and that `bpy.context.window` inside a button's `on_click` is the modal's window,
so the menu lands in the right area.

Hit-testing stays interactive: from Blender's Python console, call `manual_m5.probe(x, y)`
with a region-local point and it prints the node under it (the menu first while one is
open), or `None`. Run `import manual_m5; manual_m5.stop()` to end it and leave the
viewport clean.
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))  # repo root, so gui_paint_modules imports
sys.path.insert(0, str(_HERE))  # tests/, so `import manual_m5` works from the console

# Blender runs this file as `__main__`, so a bare `import manual_m5` from the console
# would build a second, empty module. Aliasing the running module under its own name makes
# the documented console commands act on the one that is actually armed.
sys.modules.setdefault("manual_m5", sys.modules[__name__])

import bpy

from gui_paint_modules import (
    Anchor, Button, Icon, Menu, MenuItem, Node, Panel, Scene, Surface, VBox,
)

ITEMS = (
    ("Select All", "select"),
    ("Grab", "grab"),
    ("Move", "move"),
)

_state = {"surfaces": [], "menus": []}


def _clicked(label):
    """Return a handler that prints which row fired, so a live click is observable."""
    def handler():
        print(f"gui_paint M5: clicked {label}")
    return handler


def build_menu():
    """Return the menu layer: one row per item, anchored near the button."""
    items = [MenuItem(label=label, icon=Icon.named(icon), on_click=_clicked(label))
             for label, icon in ITEMS]
    return Menu(items=items, popup_anchor=Anchor.bottom_left(margin=16))


def build_scene(on_menu):
    """Return the toolbar scene: a panel with one button that opens the menu."""
    panel = Panel(layout=VBox(gap=2, padding=3), anchor=Anchor.bottom_left(margin=16))
    panel.add(Button(label="Menu", icon=Icon.named("select"), on_click=on_menu))
    root = Node()
    root.add(panel)
    return Scene(root)


def _view3d_areas():
    """Return every 3D viewport area in the current screen, in order."""
    screen = bpy.context.screen
    if screen is None:
        return []
    return [area for area in screen.areas if area.type == "VIEW_3D"]


def _open_menu(surface):
    """Open a menu over a surface's own area and remember it."""
    overlay = surface.open_menu(build_menu())
    _state["menus"].append(overlay)
    print("gui_paint M5: menu opened; click a row or outside it")


def _arm():
    """Enable one interactive surface per 3D viewport, then stop the timer."""
    areas = _view3d_areas()
    if not areas:
        print("gui_paint M5: waiting for a 3D viewport...")
        return 1.0
    for area in areas:
        surface = Surface("SpaceView3D", interactive=True)
        # The button's handler needs this surface; a default argument binds it per loop.
        surface.scene = build_scene(lambda s=surface: _open_menu(s))
        surface.enable(area)
        _state["surfaces"].append(surface)
    print(f"gui_paint M5: {len(areas)} toolbar(s) armed; click the Menu button.")
    return None


def _top_scene():
    """The scene the pointer should hit: the open menu first, then the toolbar."""
    for overlay in reversed(_state["menus"]):
        if overlay._handle is not None:
            return overlay.scene
    for surface in reversed(_state["surfaces"]):
        if surface._handle is not None:
            return surface.scene
    return None


def probe(x, y):
    """Print the widget under a region-local point, so hit-testing is checkable live."""
    scene = _top_scene()
    if scene is None:
        print("gui_paint M5: not running; arm it first")
        return None
    node = scene.hit_test(x, y)
    print(f"gui_paint M5: ({x}, {y}) -> {_describe(node)}")
    return node


def _describe(node):
    """Name a node by what it is and what it says, so a probe result is readable."""
    if node is None:
        return "nothing"
    text = getattr(node, "label", None) or getattr(node, "text", None)
    kind = type(node).__name__
    return f"{kind}({text!r})" if text else kind


def stop():
    """Disable every menu and overlay and drop the timer."""
    for overlay in _state["menus"]:
        overlay.disable()
    _state["menus"] = []
    for surface in _state["surfaces"]:
        surface.disable()
    _state["surfaces"] = []
    try:
        bpy.app.timers.unregister(_arm)
    except ValueError:
        pass
    print("gui_paint M5: stopped, nothing registered")


if __name__ == "__main__":
    bpy.app.timers.register(_arm, first_interval=1.0)
    print("gui_paint M5 manual check armed: watch the bottom-left of the 3D viewport.")
