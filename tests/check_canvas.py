"""Verify Canvas: the pure rect geometry, and the draw path where the host allows it.

The unit quad is pure data, so the geometry assertions run on both targets even
though 4.2 cannot reach the GPU from a background process. The draw-path smoke is
gated like `tests/check_compat.py`: it runs where `gpu.init` exists, and 4.2 records
a skip.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import bpy

from gui_paint_modules import canvas

failures = []
skips = []


def check(label: str, condition: bool, detail: str = "") -> None:
    """Record one contract assertion and print its outcome."""
    if condition:
        print(f"  ok   {label}")
        return
    failures.append(label)
    print(f"  FAIL {label}{': ' + detail if detail else ''}")


print(f"  -- {bpy.app.version_string}")

triangles = getattr(canvas, "quad_triangles", None)
check("canvas.quad_triangles is defined", callable(triangles))
if callable(triangles):
    expected = (
        (0.0, 0.0), (1.0, 0.0), (1.0, 1.0),
        (0.0, 0.0), (1.0, 1.0), (0.0, 1.0),
    )
    got = tuple(map(tuple, triangles()))
    check("the unit quad is six triangle vertices", got == expected, str(got))

key = getattr(canvas, "QUAD_BATCH_KEY", None)
check("QUAD_BATCH_KEY is a non-empty string", isinstance(key, str) and bool(key), repr(key))

Canvas = getattr(canvas, "Canvas", None)
check("canvas.Canvas is defined", isinstance(Canvas, type))
for method in ("rect", "push_transform", "pop_transform", "push_clip", "pop_clip"):
    check(f"Canvas.{method} is defined", callable(getattr(Canvas, method, None)))

if isinstance(Canvas, type) and callable(getattr(Canvas, "rect", None)):
    try:
        surface = Canvas()
        surface.rect(1.0, 2.0, 3.0, 4.0, (1.0, 0.0, 0.0, 1.0))
        surface.rect(5.0, 6.0, 7.0, 8.0, (0.0, 1.0, 0.0, 1.0))
    except Exception as exc:
        import gpu

        if hasattr(gpu, "init"):
            check("Canvas.rect runs the draw path", False, f"{type(exc).__name__}: {exc}")
        else:
            skips.append(f"draw path unreachable in this background build ({type(exc).__name__})")
    else:
        check("Canvas.rect runs the draw path", True)
        check(
            "two rects reuse one cached batch",
            len(surface._batches) == 1,
            f"{sorted(surface._batches)}",
        )

if skips:
    print("  skip " + "; ".join(skips))

if failures:
    raise SystemExit(f"canvas: {len(failures)} check(s) failed: {failures}")
print("canvas: all checks passed")
