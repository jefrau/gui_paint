"""Surface — binds a Scene to an editor region and owns its registration.

Creating a surface does nothing. ``enable()`` registers one draw callback for the
chosen space type and region; ``disable()`` removes it and forgets the area, so
nothing stays registered or live.

Both ends ask the bound area to repaint. A draw handler only runs when Blender
repaints the region, so without that request an enabled overlay can stay invisible
until an unrelated redraw happens to occur.

The callback serves every area of that space type, so it draws only in the area the
surface was opened in. That keeps one registration cheap and scoped without per-area
bookkeeping, and it survives area splits, joins and fullscreen toggles.
"""

import bpy

from . import coords
from .canvas import Canvas
from .scene import Scene


class Surface:
    """Binds a Scene to an editor region and manages its lifecycle."""

    def __init__(self, space_type, region_type="WINDOW", interactive=False):
        self.space_type = space_type
        self.region_type = region_type
        self.interactive = interactive
        self.canvas = None
        self.draw = None
        self.scene = Scene()
        self._router = None
        self._handle = None
        self._area = None
        self._area_ptr = None

    def enable(self, area):
        """Register drawing for this surface. Does nothing if already enabled."""
        if self._handle is not None:
            return
        self._area = area
        self._area_ptr = area.as_pointer()
        space = getattr(bpy.types, self.space_type)
        self._handle = space.draw_handler_add(
            self._draw, (), self.region_type, "POST_PIXEL")
        if self.canvas is None:
            self.canvas = Canvas()
        self.canvas.prepare()
        self._tag_redraw()

    def disable(self):
        """Remove drawing. The surface becomes invisible and inert."""
        if self._handle is None:
            return
        space = getattr(bpy.types, self.space_type)
        space.draw_handler_remove(self._handle, self.region_type)
        self._handle = None
        self._area_ptr = None
        self._tag_redraw()
        self._area = None

    def owns(self, area):
        """Whether this surface draws in the given area."""
        return area is not None and area.as_pointer() == self._area_ptr

    def _tag_redraw(self):
        """Ask the bound area to repaint, so a state change becomes visible."""
        area = self._area
        if area is None:
            return
        try:
            area.tag_redraw()
        except ReferenceError:
            # The area was closed while the surface was enabled; nothing to repaint.
            self._area = None

    def _draw(self):
        """Draw callback registered with the space type."""
        if not self.owns(bpy.context.area):
            return
        if self.canvas is None:
            self.canvas = Canvas()
        self._draw_scene()
        if self.draw is not None:
            self.draw(self.canvas)

    def _draw_scene(self):
        """Solve and draw the scene into the bound region, when one is available.

        The region and the display metrics come from the live context; a draw callback
        that runs without a region (as some hosts do) simply skips the scene.
        """
        region = getattr(bpy.context, "region", None)
        if region is None:
            return
        self.scene.reflow(coords.region_rect(region), coords.current_metrics())
        self.scene.draw(self.canvas)
