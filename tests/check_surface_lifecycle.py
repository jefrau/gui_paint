"""Verify the Surface lifecycle: register once, disable cleanly, own one area, draw.

Background mode has no real area, so the check injects a stub area, swaps
`bpy.types.SpaceView3D` for a recorder, and swaps `bpy.context` for a holder whose
`area` it controls. Both are module attributes, so both are restored before the check
finishes.
"""

import bpy

from checkkit import StubArea, StubSpace, banner, check, finish

from gui_paint_modules.canvas import Canvas
from gui_paint_modules.surface import Surface


class _Context:
    """Stands in for bpy.context, so the draw callback sees a chosen area and window."""

    def __init__(self, area, window=None):
        self.area = area
        self.window = window


class _Window:
    """Stands in for a Blender window: an identity for the per-window router registry."""

    def __init__(self, pointer):
        self._pointer = pointer

    def as_pointer(self):
        return self._pointer


banner()

check("Surface is defined", isinstance(Surface, type))
for method in ("enable", "disable", "owns"):
    check(f"Surface.{method} is defined", callable(getattr(Surface, method, None)))

recorder = StubSpace()
original_space = getattr(bpy.types, "SpaceView3D", None)
original_context = bpy.context
context = _Context(None)
bpy.types.SpaceView3D = recorder
bpy.context = context
try:
    area = StubArea(4242)
    other = StubArea(777)

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

    # -- input: an interactive surface joins the window's router -----------------

    import gui_paint_modules.input.router as router_module

    launches = []
    saved_launch = router_module._launch_modal
    router_module._ROUTERS.clear()
    router_module._MODALS.clear()
    router_module._launch_modal = lambda router: launches.append(router)

    window = _Window(7777)
    context.window = window
    try:
        interactive = Surface("SpaceView3D", interactive=True)
        interactive.enable(area)
        router = interactive._router
        check("an interactive surface registers with a router", router is not None)
        check("the first interactive surface starts the router", router.running is True)
        check("the first surface launches exactly one modal", launches == [router], str(launches))

        second = Surface("SpaceView3D", interactive=True)
        second.enable(area)
        check("a second interactive surface shares the router", second._router is router)
        check("a second interactive surface launches no modal", len(launches) == 1, str(launches))

        interactive.disable()
        check("disabling one of two leaves the router running", router.running is True)
        second.disable()
        check("disabling the last stops the router", router.running is False)
        check("a stopped router has no surfaces", router.surfaces == ())

        passive = Surface("SpaceView3D")
        passive.enable(area)
        check("a non-interactive surface starts no router", passive._router is None)
        check("a non-interactive surface launches no modal", len(launches) == 1, str(launches))
        passive.disable()
    finally:
        context.window = None
        router_module._launch_modal = saved_launch
        router_module._ROUTERS.clear()
        router_module._MODALS.clear()
finally:
    bpy.context = original_context
    if original_space is not None:
        bpy.types.SpaceView3D = original_space

finish("surface")
