"""Menu — a transient popup layer that owns input while it is open.

A menu is a scene, not a second input mechanism. Its root spans the whole region, so
while it is the newest interactive surface in its window the router locates it first:
a click on an item reaches the item, a click on the popup's own background is consumed
and does nothing, and a click anywhere else reaches this layer and dismisses. The host
wires ``on_dismiss`` to close the menu's surface (see ``Surface.open_menu``).

Selecting an item runs the item's own action and then dismisses, which is what makes the
menu transient. There is no keyboard behaviour on purpose: D4 keeps the library to
labels, so a menu never takes focus and never blocks Blender's keymaps.
"""

from ..layout import Anchor, VBox
from ..nodes import Node
from .button import Button
from .panel import Panel

_IDLE_BACKGROUND = (0.0, 0.0, 0.0, 0.0)
_HOVER_BACKGROUND = (0.34, 0.34, 0.36, 1.0)
_PRESSED_BACKGROUND = (0.22, 0.22, 0.24, 1.0)


class MenuItem(Button):
    """A row in a menu: flat while idle, brighter under the pointer.

    It is still a ``Button`` — label, optional icon, measured size and ``on_click`` —
    with the menu's flat look instead of a boxed one.
    """

    def _background_color(self):
        """Return the row background for the current interaction state."""
        if self._pressed:
            return _PRESSED_BACKGROUND
        if self._hot:
            return _HOVER_BACKGROUND
        return _IDLE_BACKGROUND


class _MenuPopup(Panel):
    """The popup box: a click on its own background is consumed, not leaked.

    Without this a click between two rows would fall through to Blender and, for
    example, orbit the viewport, even though the menu is open.
    """

    def on_click(self):
        """Consume a click on the popup's background. It does not dismiss the menu."""


class Menu(Node):
    """The transient menu layer: a popup plus a click-anywhere dismiss.

    The layer spans the region it is solved in, so any click is caught. The popup is an
    anchored ``Panel`` holding the items; ``on_dismiss`` is called when the layer is
    clicked outside the popup and after an item is selected. Set ``on_dismiss`` to the
    surface's ``disable`` and the menu closes itself.
    """

    def __init__(self, items=(), popup_anchor=None, on_dismiss=None, layout=None, **kw):
        super().__init__(**kw)
        # The dismiss hook is a plain attribute: the host wires it after construction,
        # because the surface it closes does not exist yet while the menu is built.
        self.on_dismiss = on_dismiss
        self.popup = _MenuPopup(
            layout=VBox(gap=1.0, padding=4.0) if layout is None else layout,
            anchor=Anchor.top_left(margin=6.0) if popup_anchor is None else popup_anchor,
        )
        self.add(self.popup)
        for item in items:
            self.add_item(item)

    def add_item(self, item):
        """Add a row to the popup; selecting it runs its action and then dismisses."""
        action = item.on_click

        def select():
            if callable(action):
                action()
            self._dismiss()

        item.on_click = select
        self.popup.add(item)
        return item

    def on_click(self):
        """The layer was clicked outside the popup: dismiss the menu."""
        self._dismiss()

    def _dismiss(self):
        """Call the host's dismiss hook, if one is wired."""
        if callable(self.on_dismiss):
            self.on_dismiss()
