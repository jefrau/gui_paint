"""Coordinate conversions and DPI scaling.

Every conversion between logical units and pixels lives here and nowhere else, per
the coordinate contract in ARCHITECTURE.md:

    px = round(units * ui_scale * base_factor)

``ui_scale`` is the user's UI scale and ``base_factor`` the display's pixels per
logical unit. Only :func:`current_metrics` and the helper behind it read Blender state;
the conversions stay pure so they can be checked without a running UI.
"""

import bpy

# Blender's default DPI. A logical unit is one pixel at this density, so the factor is
# a ratio against it rather than a bare number.
_DEFAULT_DPI = 72.0


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


def dpi_base_factor() -> float:
    """Return the display's pixels per logical unit.

    One of the two readers of display state in the package; :func:`current_metrics`
    pairs it with the interface scale.
    """
    return float(bpy.context.preferences.system.pixel_size) / _DEFAULT_DPI


def ui_scale() -> float:
    """Return the user's interface scale, as a ratio against Blender's default."""
    return float(bpy.context.preferences.system.ui_scale)


def current_metrics() -> DisplayMetrics:
    """Return the display metrics for the running Blender.

    The single entry other layers use, so no module outside this one has to know how
    the two scales are read.
    """
    return DisplayMetrics(ui_scale(), dpi_base_factor())
