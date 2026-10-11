"""Verify the Surface lifecycle: register once, disable cleanly, own one area, draw.

Background mode has no real area, so the check injects a stub area, swaps
`bpy.types.SpaceView3D` for a recorder, and swaps `bpy.context` for a holder whose
`area` it controls. Both are module attributes, so both are restored before the check
finishes.
"""

import bpy

from checkkit import banner, check, finish

from gui_paint_modules.canvas import Canvas
from gui_paint_modules.surface import Surface


class _Area:
    """Stub area: the surface only reads as_pointer() and asks for redraws."""

    def __init__(self, pointer):
        self._pointer = pointer
        self.redraws = 0

    def as_pointer(self):
        return self._pointer

    def tag_redraw(self):
        self.redraws += 1


class _Context:
    """Stands in for bpy.context, so the draw callback sees a chosen area."""

    def __init__(self, area):
        self.area = area


class _SpaceRecorder:
    """Stand-in for a Blender space type, recording handler add/remove calls."""

    def __init__(self):
        self.added = []
        self.removed = []

    def draw_handler_add(self, callback, args, region_type, draw_type):
        self.added.append((callback, args, region_type, draw_type))
        return ("handle", len(self.added))

    def draw_handler_remove(self, handle, region_type):
        self.removed.append((handle, region_type))


banner()

check("Surface is defined", isinstance(Surface, type))
for method in ("enable", "disable", "owns"):
    check(f"Surface.{method} is defined", callable(getattr(Surface, method, None)))

recorder = _SpaceRecorder()
original_space = getattr(bpy.types, "SpaceView3D", None)
original_context = bpy.context
context = _Context(None)
bpy.types.SpaceView3D = recorder
bpy.context = context
try:
    area = _Area(4242)
    other = _Area(777)

    surface = Surface("SpaceView3D")
    check("a fresh surface holds no handle", surface._handle is None)

    surface.enable(area)
    check("enable registers exactly one handler", len(recorder.added) == 1, str(len(recorder.added)))
    check("enable asks the bound area to redraw", area.redraws == 1, str(area.redraws))
    if recorder.added:
        _, args, region_type, draw_type = recorder.added[0]
        check("handler runs at POST_PIXEL in the chosen region",
              (draw_type, region_type) == ("POST_PIXEL", "WINDOW"), f"{draw_type}/{region_type}")
        check("handler is registered without extra arguments", args == (), str(args))

    surface.enable(area)
    check("a second enable adds nothing", len(recorder.added) == 1, str(len(recorder.added)))

    check("owns the bound area", surface.owns(area))
    check("does not own a different area", not surface.owns(other))
    check("does not own a missing area", not surface.owns(None))

    painted = []
    surface.draw = painted.append

    context.area = None
    surface._draw()
    check("drawing with no area present paints nothing", not painted, str(len(painted)))

    context.area = other
    surface._draw()
    check("drawing in another area paints nothing", not painted, str(len(painted)))

    context.area = area
    surface._draw()
    check("drawing in the bound area paints once", len(painted) == 1, str(len(painted)))
    check("the callback receives a Canvas", bool(painted) and isinstance(painted[0], Canvas))

    surface._draw()
    check("the canvas is reused between draws", len(painted) == 2 and painted[0] is painted[1])

    surface.disable()
    check("disable removes the handler", len(recorder.removed) == 1, str(len(recorder.removed)))
    check("disable asks the area to redraw too", area.redraws == 2, str(area.redraws))
    check("disable leaves no handle", surface._handle is None)
    check("disable forgets the area", not surface.owns(area))

    surface.disable()
    check("a second disable removes nothing", len(recorder.removed) == 1, str(len(recorder.removed)))

    surface.enable(other)
    check("enable works again after disable", len(recorder.added) == 2 and surface.owns(other))
    surface.disable()

    interactive = Surface("SpaceView3D", interactive=True)
    interactive.enable(area)
    check("an interactive surface starts no router in M1", interactive._router is None)
    interactive.disable()
finally:
    bpy.context = original_context
    if original_space is not None:
        bpy.types.SpaceView3D = original_space

finish("surface")
