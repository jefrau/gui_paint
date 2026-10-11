"""Coordinate conversions and DPI scaling.

Every conversion between logical units and pixels lives here and nowhere else, per
the coordinate contract in ARCHITECTURE.md:

    px = round(units * ui_scale * base_factor)

``ui_scale`` is the user's UI scale and ``base_factor`` the display's pixels per
logical unit. Only :func:`dpi_base_factor` reads Blender state; the conversions stay
pure so they can be checked without a running UI.
"""

import bpy

# Blender's default DPI. A logical unit is one pixel at this density, so the factor is
# a ratio against it rather than a bare number.
_DEFAULT_DPI = 72.0


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

    This is the only place in the package that reads display scaling out of Blender.
    """
    return float(bpy.context.preferences.system.pixel_size) / _DEFAULT_DPI
