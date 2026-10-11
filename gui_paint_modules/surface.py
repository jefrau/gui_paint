"""Surface — binds a Scene to an editor region and owns its registration.

Creating a surface does nothing. ``enable()`` registers one draw callback for the
chosen space type and region; ``disable()`` removes it and forgets the area, so
nothing stays registered or live.

The callback serves every area of that space type, so it draws only in the area the
surface was opened in. That keeps one registration cheap and scoped without per-area
bookkeeping, and it survives area splits, joins and fullscreen toggles.
"""

import bpy

from .canvas import Canvas


class Surface:
    """Binds a Scene to an editor region and manages its lifecycle."""

    def __init__(self, space_type, region_type="WINDOW", interactive=False):
        self.space_type = space_type
        self.region_type = region_type
        self.interactive = interactive
        self.canvas = None
        self.draw = None
        self._router = None
        self._handle = None
        self._area_ptr = None

    def enable(self, area):
        """Register drawing for this surface. Does nothing if already enabled."""
        if self._handle is not None:
            return
        self._area_ptr = area.as_pointer()
        space = getattr(bpy.types, self.space_type)
        self._handle = space.draw_handler_add(
            self._draw, (), self.region_type, "POST_PIXEL")

    def disable(self):
        """Remove drawing. The surface becomes invisible and inert."""
        if self._handle is None:
            return
        space = getattr(bpy.types, self.space_type)
        space.draw_handler_remove(self._handle, self.region_type)
        self._handle = None
        self._area_ptr = None

    def owns(self, area):
        """Whether this surface draws in the given area."""
        return area is not None and area.as_pointer() == self._area_ptr

    def _draw(self):
        """Draw callback registered with the space type."""
        if not self.owns(bpy.context.area):
            return
        if self.canvas is None:
            self.canvas = Canvas()
        if self.draw is not None:
            self.draw(self.canvas)
