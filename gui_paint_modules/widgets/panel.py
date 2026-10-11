"""Panel — a rounded background that also arranges its children.

A panel is a container: its only look is its rounded background, and its children are
placed by the layout it carries. Its natural size therefore comes from the layout solve,
which measures the children, so the panel itself needs no measure of its own.
"""

from .. import coords
from ..nodes import Node

_DEFAULT_COLOR = (0.16, 0.16, 0.16, 0.90)
_DEFAULT_RADIUS = 4.0


class Panel(Node):
    """A rounded container background with room for children."""

    def __init__(self, color=_DEFAULT_COLOR, radius=_DEFAULT_RADIUS, **kw):
        super().__init__(**kw)
        self.color = tuple(color)
        self.radius = float(radius)

    def draw(self, canvas):
        metrics = canvas.metrics
        radius = coords.logical_to_px(self.radius, metrics.scale, metrics.base)
        canvas.rounded_rect(0.0, 0.0, self.rect[2], self.rect[3], radius, self.color)
