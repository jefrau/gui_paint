"""Coordinate conversions and DPI scaling.

Every conversion between logical units and pixels lives here and nowhere else, per
the coordinate contract in ARCHITECTURE.md:

    px = round(units * ui_scale * base_factor)

The conversions themselves land in task M1.2.
"""
