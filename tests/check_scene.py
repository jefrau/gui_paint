"""Verify the scene draw walk, the Surface wiring and the public surface.

The draw walk is checked with a recorder canvas, so nothing here touches the GPU and
the whole check runs on both targets. The Surface part swaps `bpy.context` and
`bpy.types.SpaceView3D` for stubs, the same technique the lifecycle check uses, and
hands the surface a recorder canvas so its draw path stays headless too.
"""

import bpy

from checkkit import banner, check, finish

from gui_paint_modules import coords
from gui_paint_modules.layout import Size
from gui_paint_modules.nodes import Node
from gui_paint_modules.scene import Scene

banner()

BOX = (0.0, 0.0, 200.0, 200.0)
METRICS = coords.DisplayMetrics(1.0, 1.0)

try:
    import gui_paint_modules as pkg
except Exception as exc:
    pkg = None
    check("package imports", False, f"{type(exc).__name__}: {exc}")
else:
    check("package imports", True)

PUBLIC = ("Surface", "Scene", "Node", "Size", "Anchor", "VBox", "HBox")
if pkg is not None:
    missing = [name for name in PUBLIC if not hasattr(pkg, name)]
    check("the public surface is re-exported", not missing, f"missing {missing}")


class _RecorderCanvas:
    """Canvas stand-in: records the transform and clip calls, draws nothing."""

    def __init__(self):
        self.calls = []

    def prepare(self):
        """No-op: Surface.enable warms the canvas, and there is nothing to warm here."""

    def push_transform(self, x, y, w, h):
        self.calls.append(("push_transform", x, y, w, h))

    def pop_transform(self):
        self.calls.append(("pop_transform",))

    def push_clip(self, x, y, w, h):
        self.calls.append(("push_clip", x, y, w, h))

    def pop_clip(self):
        self.calls.append(("pop_clip",))


def _painter(name, sink, **kw):
    """A node whose draw records its name into `sink`, so the walk order shows."""
    node = Node(**kw)
    node.draw = lambda canvas: sink.append(name)
    return node


check("Scene.draw is defined", callable(getattr(Scene, "draw", None)))
check("Node.draw is defined", callable(getattr(Node, "draw", None)))

if callable(getattr(Scene, "draw", None)) and callable(getattr(Node, "draw", None)):
    sink = []
    holder = _painter("holder", sink)
    a = _painter("a", sink, size=Size.fixed(10), z=1)
    b = _painter("b", sink, size=Size.fixed(10), z=5)
    holder.add(a)
    holder.add(b)
    scene = Scene(holder)
    scene.reflow(BOX, METRICS)
    scene.draw(_RecorderCanvas())
    check("the walk draws the container first, then back-to-front by z",
          sink == ["holder", "a", "b"], str(sink))

    sink.clear()
    a.z = 0
    b.z = 0
    scene.reflow(BOX, METRICS)
    scene.draw(_RecorderCanvas())
    check("equal z keeps the later sibling on top", sink == ["holder", "a", "b"], str(sink))

    sink.clear()
    b.visible = False
    scene.reflow(BOX, METRICS)
    scene.draw(_RecorderCanvas())
    check("an invisible node is not drawn", sink == ["holder", "a"], str(sink))
    b.visible = True

    # A clipped node pushes its absolute rectangle and pops it again.
    sink = []
    root = _painter("root", sink)
    site = _painter("site", sink, size=Size.fixed(50), margin=5)
    site.clip = True
    root.add(site)
    scene = Scene(root)
    scene.reflow(BOX, METRICS)
    canvas = _RecorderCanvas()
    scene.draw(canvas)
    pushed = [call for call in canvas.calls if call[0] == "push_clip"]
    popped = [call for call in canvas.calls if call[0] == "pop_clip"]
    check("a clipped node pushes its absolute rectangle",
          pushed == [("push_clip", 5.0, 5.0, 50, 50)], str(pushed))
    check("the clip is popped again", len(popped) == 1, str(canvas.calls))
    check("the node enters its own box before drawing",
          ("push_transform", 5, 5, 1.0, 1.0) in canvas.calls, str(canvas.calls))


# -- Surface wiring ---------------------------------------------------------


class _Area:
    def __init__(self, pointer):
        self._pointer = pointer
        self.redraws = 0

    def as_pointer(self):
        return self._pointer

    def tag_redraw(self):
        self.redraws += 1


class _Region:
    width = 200
    height = 200


class _System:
    pixel_size = 72
    ui_scale = 1.0


class _Preferences:
    system = _System()


class _Context:
    def __init__(self, area, region):
        self.area = area
        self.region = region
        self.preferences = _Preferences()


class _SpaceRecorder:
    def __init__(self):
        self.added = []
        self.removed = []

    def draw_handler_add(self, callback, args, region_type, draw_type):
        self.added.append((callback, args, region_type, draw_type))
        return ("handle", len(self.added))

    def draw_handler_remove(self, handle, region_type):
        self.removed.append((handle, region_type))


if pkg is not None and callable(getattr(Scene, "draw", None)):
    original_space = getattr(bpy.types, "SpaceView3D", None)
    original_context = bpy.context
    area = _Area(4242)
    bpy.types.SpaceView3D = _SpaceRecorder()
    bpy.context = _Context(area, _Region())
    try:
        surface = pkg.Surface("SpaceView3D")
        check("a surface owns a scene", isinstance(surface.scene, Scene))
        drawn = []
        surface.scene = Scene(Node(size=Size.fixed(10)))
        surface.scene.root.draw = lambda canvas: drawn.append("node")
        surface.canvas = _RecorderCanvas()  # keep the draw path off the GPU
        surface.draw = lambda canvas: drawn.append("callback")
        surface.enable(area)
        surface._draw()
        check("the surface draws its scene then its callback", drawn == ["node", "callback"], str(drawn))
        surface._draw()
        check("a later draw draws both again", len(drawn) == 4, str(len(drawn)))
        surface.disable()
    finally:
        bpy.context = original_context
        if original_space is not None:
            bpy.types.SpaceView3D = original_space

finish("scene")
