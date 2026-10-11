"""Coordinate conversions and display scaling.

Every conversion between logical units and pixels lives here and nowhere else, per
the coordinate contract in ARCHITECTURE.md:

    px = round(units * ui_scale * base_factor)

``ui_scale`` is the user's resolution scale (the DPI ratio) and ``base_factor`` the
extra pixel factor for HiDPI displays, so the interface is drawn at their product.
Only :func:`current_metrics` and the two readers behind it touch Blender state; the
conversions stay pure so they can be checked without a running UI.
"""

import bpy


class DisplayMetrics:
    """The display scales one layout solve needs, as a single comparable value.

    The scene takes this, so a change to either number makes a solved tree stale and
    the next solve re-runs. Comparing by value is what lets the scene notice.
    """

    __slots__ = ("scale", "base")

    def __init__(self, scale, base):
        self.scale = float(scale)
        self.base = float(base)

    def __eq__(self, other):
        return (isinstance(other, DisplayMetrics)
                and (self.scale, self.base) == (other.scale, other.base))

    def __repr__(self):
        return f"DisplayMetrics(scale={self.scale!r}, base={self.base!r})"


def logical_to_px(value: float, ui_scale: float, base_factor: float) -> int:
    """Convert a logical unit value to pixels.

    Logical units keep layouts stable across DPI settings: ``ui_scale`` carries the
    user's UI scale and ``base_factor`` the display's pixels per logical unit.
    """
    return int(round(value * ui_scale * base_factor))


def region_rect(region) -> tuple:
    """Return the region rectangle as (x, y, width, height), in pixels.

    The canonical space puts the origin at the region's bottom-left corner, so the
    rectangle always starts at (0, 0).
    """
    return (0.0, 0.0, float(region.width), float(region.height))


def base_factor() -> float:
    """Return the display's extra pixels per logical unit, for HiDPI screens.

    Blender keeps two multipliers on the system preferences: ``ui_scale`` (the user's
    resolution scale, i.e. the DPI ratio) and ``pixel_size`` (the extra pixel factor
    for a HiDPI display). This is the second one.

    Dividing it by a nominal 72 was wrong: ``pixel_size`` is already a ratio and
    defaults to 1.0, so the division shrank every layout to a few pixels.
    """
    return float(bpy.context.preferences.system.pixel_size)


def ui_scale() -> float:
    """Return the user's resolution scale.

    A background process can leave this preference at 0.0 before the interface
    starts, and a zero scale would collapse every layout, so a non-positive value
    falls back to 1.0.
    """
    scale = float(bpy.context.preferences.system.ui_scale)
    return scale if scale > 0 else 1.0


def current_metrics() -> DisplayMetrics:
    """Return the display metrics for the running Blender.

    The single entry other layers use, so no module outside this one has to know how
    the two scales are read.
    """
    return DisplayMetrics(ui_scale(), base_factor())
