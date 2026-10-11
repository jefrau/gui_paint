"""The icon registry: resolve an icon by name to something the canvas can draw.

An icon owns its geometry and how to draw it, so a widget never has to know whether an
icon came from a vector definition or (later) a texture atlas. `named` caches by name, so
the same icon object comes back and the canvas caches its batch under one key.
"""

from . import vector


class Icon:
    """A named icon with cached triangle geometry in a unit box."""

    def __init__(self, name, triangles):
        self.name = name
        self.triangles = triangles

    @classmethod
    def named(cls, name):
        """Return the icon registered under ``name``.

        Raises a clear error for an unknown name, so a broken icon is caught at build
        time instead of being skipped in silence.
        """
        if name not in vector.BUILTIN:
            raise ValueError(f"unknown icon {name!r}; known: {sorted(vector.BUILTIN)}")
        icon = _CACHE.get(name)
        if icon is None:
            icon = cls(name, vector.triangles(name))
            _CACHE[name] = icon
        return icon

    def draw(self, canvas, x, y, w, h, color):
        """Draw the icon into the (x, y, w, h) box, which scales its unit geometry."""
        canvas.shape(("icon", self.name), self.triangles, x, y, w, h, color)


_CACHE = {}
