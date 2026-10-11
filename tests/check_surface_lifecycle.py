"""Verify the Surface lifecycle: register once, disable cleanly, own one area.

Background mode has no real area, so the check injects a stub area and swaps
`bpy.types.SpaceView3D` for a recorder — the same technique
`tests/check_import_contract.py` uses to observe registration.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import bpy

from gui_paint_modules.surface import Surface

failures = []


def check(label: str, condition: bool, detail: str = "") -> None:
    """Record one contract assertion and print its outcome."""
    if condition:
        print(f"  ok   {label}")
        return
    failures.append(label)
    print(f"  FAIL {label}{': ' + detail if detail else ''}")


class _Area:
    """Stub area: the surface only ever reads as_pointer()."""

    def __init__(self, pointer):
        self._pointer = pointer

    def as_pointer(self):
        return self._pointer


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


check("Surface is defined", isinstance(Surface, type))
for method in ("enable", "disable", "owns"):
    check(f"Surface.{method} is defined", callable(getattr(Surface, method, None)))

recorder = _SpaceRecorder()
original = getattr(bpy.types, "SpaceView3D", None)
bpy.types.SpaceView3D = recorder
try:
    area = _Area(4242)
    other = _Area(777)

    surface = Surface("SpaceView3D")
    check("a fresh surface holds no handle", surface._handle is None)

    surface.enable(area)
    check("enable registers exactly one handler", len(recorder.added) == 1, str(len(recorder.added)))
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
    surface._draw()
    check("drawing without an area paints nothing", not painted, str(painted))

    surface.disable()
    check("disable removes the handler", len(recorder.removed) == 1, str(len(recorder.removed)))
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
    if original is not None:
        bpy.types.SpaceView3D = original

if failures:
    raise SystemExit(f"surface: {len(failures)} check(s) failed: {failures}")
print("surface: all checks passed")
