"""Normalized mouse events for the input router.

A Blender event carries many fields the router ignores. This module is the one place that
decides which raw events the router acts on and what their region-local point is, so the
rest of the input layer reads a small, stable vocabulary instead of Blender's.

The raw facts it relies on — an event has ``type`` and ``value`` and a region-local point
— are recorded per target by ``tests/check_modal_api.py``, measured rather than assumed.
"""

MOVE = "move"
PRESS = "press"
RELEASE = "release"

_LEFT = "LEFTMOUSE"


def classify(event):
    """Return the router's event for a mouse move or a left-button press/release.

    ``kind`` is one of MOVE, PRESS or RELEASE and the point is region-local pixels.

    Returns None for everything else — a key, a wheel tick, another button, or a lone
    CLICK — so the caller passes those through to Blender untouched. The router tracks the
    press and the release itself, so a drag that leaves a node cancels instead of firing.
    """
    kind = event.type
    if kind == "MOUSEMOVE":
        return (MOVE, event.mouse_region_x, event.mouse_region_y)
    if kind != _LEFT:
        return None
    value = event.value
    if value == "PRESS":
        return (PRESS, event.mouse_region_x, event.mouse_region_y)
    if value == "RELEASE":
        return (RELEASE, event.mouse_region_x, event.mouse_region_y)
    return None
