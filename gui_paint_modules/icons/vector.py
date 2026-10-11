"""Built-in vector icons: convex polygons in a unit box, tessellated once.

An icon is a tuple of polygons, each a tuple of (x, y) points inside the unit box and
each **convex**, so one fan tessellates it exactly. A concave glyph is expressed as
several convex parts — the ``move`` cross is two bars — which is the v1 limitation: a
general tessellator (ear clipping, holes) is only worth writing when a real icon needs
it.

The set is deliberately small and plain: the mechanism is what M3 delivers, and adding
an icon is adding a polygon list here.
"""

from ..canvas import fan_triangles

BUILTIN = {
    "select": (
        ((0.50, 0.95), (0.15, 0.10), (0.85, 0.10)),
    ),
    "grab": (
        ((0.20, 0.20), (0.80, 0.20), (0.80, 0.80), (0.20, 0.80)),
    ),
    "move": (
        ((0.40, 0.15), (0.60, 0.15), (0.60, 0.85), (0.40, 0.85)),
        ((0.15, 0.40), (0.85, 0.40), (0.85, 0.60), (0.15, 0.60)),
    ),
}


def triangles(name):
    """Return the named icon's polygons as one triangle list, inside the unit box."""
    return tuple(
        vertex
        for polygon in BUILTIN[name]
        for vertex in fan_triangles(polygon)
    )
