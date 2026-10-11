"""Verify the coordinate contract implemented in `gui_paint_modules/coords.py`.

Two things are checked:

- the single conversion point matches `px = round(units * ui_scale * base_factor)`,
  including the rounding edges and non-unit scales;
- the region rectangle is expressed in the canonical space (origin at the region's
  bottom-left corner).

The DPI reader needs a running UI, so it is only checked for existence here; the
draw path exercises it in task M1.4.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from gui_paint_modules import coords

failures = []


def check(label: str, condition: bool, detail: str = "") -> None:
    """Record one contract assertion and print its outcome."""
    if condition:
        print(f"  ok   {label}")
        return
    failures.append(label)
    print(f"  FAIL {label}{': ' + detail if detail else ''}")


convert = getattr(coords, "logical_to_px", None)
check("logical_to_px is defined", callable(convert))

if callable(convert):
    # (value, ui_scale, base_factor, expected). Python's round() is banker's
    # rounding, so the half-way cases are the interesting ones.
    cases = [
        (0.0, 1.0, 1.0, 0),
        (1.0, 1.0, 1.0, 1),
        (1.4, 1.0, 1.0, 1),
        (1.5, 1.0, 1.0, 2),
        (2.5, 1.0, 1.0, 2),
        (3.5, 1.0, 1.0, 4),
        (-1.5, 1.0, 1.0, -2),
        (10.0, 2.0, 1.0, 20),
        (10.0, 1.0, 2.0, 20),
        (7.0, 1.5, 2.0, 21),
        (0.4, 1.25, 1.0, 0),  # exactly 0.5 rounds to even, per round()
        (0.6, 1.25, 1.0, 1),  # 0.75 is not a tie
    ]
    for value, ui_scale, base_factor, expected in cases:
        got = convert(value, ui_scale, base_factor)
        check(
            f"logical_to_px({value}, {ui_scale}, {base_factor}) == {expected}",
            got == expected,
            f"got {got!r}",
        )

    check(
        "logical_to_px returns an int",
        isinstance(convert(1.0, 1.0, 1.0), int),
        f"got {type(convert(1.0, 1.0, 1.0)).__name__}",
    )


class _Region:
    """Minimal stand-in for a Blender region: only width and height are read."""

    def __init__(self, width, height):
        self.width = width
        self.height = height


region_rect = getattr(coords, "region_rect", None)
check("region_rect is defined", callable(region_rect))
if callable(region_rect):
    check(
        "region_rect starts at the region origin",
        region_rect(_Region(640, 480)) == (0.0, 0.0, 640.0, 480.0),
        f"got {region_rect(_Region(640, 480))!r}",
    )

check(
    "dpi_base_factor is defined",
    callable(getattr(coords, "dpi_base_factor", None)),
)

offenders = []
for path in sorted((REPO / "gui_paint_modules").glob("*.py")):
    if path.name == "coords.py":
        continue
    if "ui_scale" in path.read_text(encoding="utf-8"):
        offenders.append(path.name)
check("no other module scales by ui_scale", not offenders, str(offenders))

if failures:
    raise SystemExit(f"coords: {len(failures)} check(s) failed: {failures}")
print("coords: all checks passed")
