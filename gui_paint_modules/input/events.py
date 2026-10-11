"""Normalized mouse events for the input router.

A Blender event carries many fields the router ignores. This module is the one place that
decides which raw events the router acts on and what their point is, so the rest of the
input layer reads a small, stable vocabulary instead of Blender's.

The point is **window** pixels, not region pixels. A window-level modal has no region, so
Blender reports ``mouse_region_x/y`` as (-1, -1); ``mouse_x/y`` is the coordinate that is
always valid. The router converts it to a surface's region itself. Both facts were measured
on a live 5.2, not assumed.
"""

MOVE = "move"
PRESS = "press"
RELEASE = "release"

_LEFT = "LEFTMOUSE"


def classify(event):
    """Return the router's event for a mouse move or a left-button press/release.

    ``kind`` is one of MOVE, PRESS or RELEASE and the point is in **window** pixels,
    bottom-left origin, the space ``event.mouse_x``/``mouse_y`` use.

    Returns None for everything else — a key, a wheel tick, another button, or a lone
    CLICK — so the caller passes those through to Blender untouched. The router tracks the
    press and the release itself, so a drag that leaves a node cancels instead of firing.
    """
    kind = event.type
    if kind == "MOUSEMOVE":
        return (MOVE, event.mouse_x, event.mouse_y)
    if kind != _LEFT:
        return None
    value = event.value
    if value == "PRESS":
        return (PRESS, event.mouse_x, event.mouse_y)
    if value == "RELEASE":
        return (RELEASE, event.mouse_x, event.mouse_y)
    return None
