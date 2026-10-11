"""Label — a line of text with an intrinsic size.

The label is the one widget whose natural size comes from the font: it measures through
``canvas.measure_text``, which reads ``blf`` and answers without a GPU, so a layout solve
can size it on either target. ``size`` is the logical font size, not the node's size
policy; that policy stays ``Size.auto()`` so the label always asks for its text size.
"""

from .. import canvas
from ..nodes import Node

_DEFAULT_FONT_SIZE = 12.0
_DEFAULT_COLOR = (1.0, 1.0, 1.0, 1.0)


class Label(Node):
    """A single line of text, sized from its own measurement."""

    def __init__(self, text="", size=_DEFAULT_FONT_SIZE, color=_DEFAULT_COLOR, **kw):
        super().__init__(**kw)
        self.text = text
        self.font_size = size
        # Look only: a colour is not part of the measurement, so it does not invalidate.
        self.color = tuple(color)

    @property
    def text(self):
        """The label's string. It is what gets measured, so changing it re-solves."""
        return self._text

    @text.setter
    def text(self, value):
        self._text = str(value)
        self.mark_dirty()

    @property
    def font_size(self):
        """The logical font size. It is part of the measurement, so it re-solves too."""
        return self._font_size

    @font_size.setter
    def font_size(self, value):
        self._font_size = float(value)
        self.mark_dirty()

    def measure(self, metrics):
        """Return the text's (width, height) in pixels at this label's font size."""
        return canvas.measure_text(self.text, self.font_size, metrics)

    def draw(self, canvas):
        canvas.text(0.0, 0.0, self.text, self.font_size, self.color)
