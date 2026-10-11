"""Button — a rounded background, an optional icon and a label.

The button is inert until M4's router drives it: it stores its handler and the
``_hot``/``_pressed`` flags, but never calls the handler itself. Drawing is background,
then icon, then label, all in this node's local box, so a widget never has to know
whether the icon is vector geometry or a later atlas region.
"""

from .. import coords
from ..canvas import measure_text
from ..layout import Size
from ..nodes import Node

_DEFAULT_RADIUS = 4.0
_DEFAULT_BACKGROUND = (0.22, 0.22, 0.22, 1.0)
_DEFAULT_LABEL_COLOR = (1.0, 1.0, 1.0, 1.0)
_DEFAULT_ICON_COLOR = (1.0, 1.0, 1.0, 1.0)
_PADDING = 4.0
_GAP = 4.0
_ICON_SIZE = 12.0
_LABEL_SIZE = 12.0


class Button(Node):
    """A widget that draws a background, an icon and a label; it never handles input."""

    def __init__(self, label="", icon=None, on_click=None, size=Size.auto(), **kw):
        super().__init__(size=size, **kw)
        self.label = label
        self.icon = icon
        self.on_click = on_click
        self._hot = False
        self._pressed = False

    def measure(self, metrics):
        """Return the label plus the icon, with padding, as (width, height) in pixels."""
        text_width, text_height = measure_text(self.label, _LABEL_SIZE, metrics)
        padding = coords.logical_to_px(_PADDING, metrics.scale, metrics.base)
        width = text_width
        height = text_height
        if self.icon is not None:
            icon = coords.logical_to_px(_ICON_SIZE, metrics.scale, metrics.base)
            gap = coords.logical_to_px(_GAP, metrics.scale, metrics.base)
            width += icon + gap
            height = max(height, icon)
        return (width + 2.0 * padding, height + 2.0 * padding)

    def draw(self, canvas):
        metrics = canvas.metrics
        width, height = self.rect[2], self.rect[3]
        radius = coords.logical_to_px(_DEFAULT_RADIUS, metrics.scale, metrics.base)
        canvas.rounded_rect(0.0, 0.0, width, height, radius, _DEFAULT_BACKGROUND)

        padding = coords.logical_to_px(_PADDING, metrics.scale, metrics.base)
        _, text_height = measure_text(self.label, _LABEL_SIZE, metrics)
        x = padding
        if self.icon is not None:
            icon = coords.logical_to_px(_ICON_SIZE, metrics.scale, metrics.base)
            gap = coords.logical_to_px(_GAP, metrics.scale, metrics.base)
            self.icon.draw(canvas, x, (height - icon) / 2.0, icon, icon, _DEFAULT_ICON_COLOR)
            x += icon + gap
        canvas.text(x, (height - text_height) / 2.0, self.label, _LABEL_SIZE,
                    _DEFAULT_LABEL_COLOR)
