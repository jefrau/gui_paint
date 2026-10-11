"""Button — a rounded background, an optional icon and a label.

The router owns the interaction: it calls ``set_hover`` and ``set_pressed`` and fires
``on_click`` on release inside, so the button itself never reads an event. Drawing is
background, then icon, then label, all in this node's local box, so a widget never has
to know whether the icon is vector geometry or a later atlas region.
"""

from .. import coords
from ..canvas import measure_text
from ..layout import Size
from ..nodes import Node

_DEFAULT_RADIUS = 4.0
_DEFAULT_BACKGROUND = (0.22, 0.22, 0.22, 1.0)
_HOVER_BACKGROUND = (0.30, 0.30, 0.30, 1.0)
_PRESSED_BACKGROUND = (0.15, 0.15, 0.15, 1.0)
_DEFAULT_LABEL_COLOR = (1.0, 1.0, 1.0, 1.0)
_DEFAULT_ICON_COLOR = (1.0, 1.0, 1.0, 1.0)
_PADDING = 4.0
_GAP = 4.0
_ICON_SIZE = 12.0
_LABEL_SIZE = 12.0


class Button(Node):
    """A widget that draws a background, an icon and a label; the router drives it."""

    def __init__(self, label="", icon=None, on_click=None, size=Size.auto(), **kw):
        super().__init__(size=size, **kw)
        self.label = label
        self.icon = icon
        # Not layout-relevant: the handler and the interaction flags never change a size.
        self.on_click = on_click
        self._hot = False
        self._pressed = False
        # Solved-state cache: the size measure() read for the label, so a draw pass can
        # centre the text without reading a font metric of its own.
        self._label_size = (0.0, 0.0)

    def set_hover(self, hot):
        """The router calls this when the pointer enters or leaves the button.

        The flag is look-only: it changes no size, so it marks nothing dirty.
        """
        self._hot = bool(hot)

    def set_pressed(self, pressed):
        """The router calls this while the button is held down and again on release.

        The flag is look-only: it changes no size, so it marks nothing dirty.
        """
        self._pressed = bool(pressed)

    def _background_color(self):
        """The background for the current interaction state: pressed, hover, or idle."""
        if self._pressed:
            return _PRESSED_BACKGROUND
        if self._hot:
            return _HOVER_BACKGROUND
        return _DEFAULT_BACKGROUND

    @property
    def label(self):
        """The button's caption. It is measured, so changing it re-solves the layout."""
        return self._label

    @label.setter
    def label(self, value):
        self._label = str(value)
        self.mark_dirty()

    @property
    def icon(self):
        """The button's icon, or None. It adds to the measured width, so it re-solves."""
        return self._icon

    @icon.setter
    def icon(self, value):
        self._icon = value
        self.mark_dirty()

    def measure(self, metrics):
        """Return the label plus the icon, with padding, as (width, height) in pixels."""
        self._label_size = measure_text(self.label, _LABEL_SIZE, metrics)
        text_width, text_height = self._label_size
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
        canvas.rounded_rect(0.0, 0.0, width, height, radius, self._background_color())

        padding = coords.logical_to_px(_PADDING, metrics.scale, metrics.base)
        _, text_height = self._label_size
        x = padding
        if self.icon is not None:
            icon = coords.logical_to_px(_ICON_SIZE, metrics.scale, metrics.base)
            gap = coords.logical_to_px(_GAP, metrics.scale, metrics.base)
            self.icon.draw(canvas, x, (height - icon) / 2.0, icon, icon, _DEFAULT_ICON_COLOR)
            x += icon + gap
        canvas.text(x, (height - text_height) / 2.0, self.label, _LABEL_SIZE,
                    _DEFAULT_LABEL_COLOR)
