"""InputRouter — dispatch region-local mouse events to scene nodes.

The router is the single entry point for the input loop: it normalizes a raw event,
finds the interactive node under the pointer, and drives its hover, press and click
hooks. An event that lands on nothing interactive passes through to Blender untouched.

It reads no Blender state of its own, so it can be checked headless. The surface it
dispatches to and the "which surface is under the pointer" resolver are both seams the
caller injects; the real window resolver is wired later.
"""

from .events import MOVE, PRESS, RELEASE, classify


def is_interactive(node):
    """Whether a node takes input, i.e. it exposes a callable ``on_click``.

    A bare node is inert by design: only a widget that overrides ``on_click`` is routed
    to, so a plain container never swallows a click.
    """
    # Returns True for a node with a callable on_click, False otherwise.
    return node is not None and callable(getattr(node, "on_click", None))


class InputRouter:
    """Routes mouse events to the interactive nodes of the registered surfaces.

    Consumes an event that lands on an interactive node and passes everything else
    through. The pressed gesture is tracked here, so a drag that leaves the node cancels
    instead of firing.
    """

    def __init__(self, resolve=None):
        """Store the optional surface resolver and start with no routing state.

        ``resolve`` maps an event to the surface under the pointer; when it is None the
        newest registered surface is used, which covers the single-surface case.
        """
        self._resolve = resolve
        self._surfaces = []
        self._hot = None
        self._hot_surface = None
        self._pressed = None

    @property
    def surfaces(self):
        """The registered surfaces, oldest first."""
        return tuple(self._surfaces)

    def register(self, surface):
        """Add a surface to the routing list, oldest first. A repeat is ignored."""
        if surface not in self._surfaces:
            self._surfaces.append(surface)

    def unregister(self, surface):
        """Remove a surface and drop any state that pointed at it.

        A press belongs to one surface, so losing that surface cancels it; a hover is
        cleared through ``_set_hover``, so the node hears the pointer leave.
        """
        if surface in self._surfaces:
            self._surfaces.remove(surface)
        if self._pressed is not None and self._pressed[0] is surface:
            self._pressed = None
        if self._hot_surface is surface:
            self._set_hover(None, None)

    def handle(self, event):
        """Process one event and report whether the router consumed it.

        Returns True when the event was consumed, False to pass it through to Blender:
        a key, a wheel tick, another button, or a lone CLICK never reaches a node.
        """
        classified = classify(event)
        if classified is None:
            return False
        kind, x, y = classified

        # A release finishes the gesture the router started, whatever the pointer is
        # now over, so it is handled before any surface lookup.
        if kind == RELEASE:
            return self._on_release(x, y)

        surface = self._target(event)
        if surface is None:
            self._set_hover(None, None)
            return False
        if kind == MOVE:
            return self._on_move(surface, x, y)
        return self._on_press(surface, x, y)

    def _target(self, event):
        """The surface an event belongs to, or None when there is none.

        Uses the injected resolver when present; otherwise the newest registered
        surface, which is the whole answer for a single-surface scene.
        """
        # Returns the resolved Surface, or None.
        if self._resolve is not None:
            return self._resolve(event)
        return self._surfaces[-1] if self._surfaces else None

    def _interactive_at(self, surface, x, y):
        """The interactive node of a surface under the point, or None.

        Hit-tests the surface's solved scene once and keeps the node only when it takes
        input; a plain container under the pointer is treated as empty space.
        """
        # Returns the hit Node when it is interactive, else None.
        node = surface.scene.hit_test(x, y)
        return node if is_interactive(node) else None

    def _on_move(self, surface, x, y):
        """Update the hover for a move and report whether the event is consumed.

        Only a move that ends on an interactive node is consumed; a move over empty
        space passes through, but still clears a stale hover.
        """
        # Returns True when the pointer is over an interactive node.
        node = self._interactive_at(surface, x, y)
        if self._set_hover(surface, node):
            surface._tag_redraw()
        return node is not None

    def _on_press(self, surface, x, y):
        """Arm a pressed gesture on the node under the pointer, if there is one.

        A press on empty space is not consumed and arms nothing. A press on a node
        stores it as the gesture owner and marks it pressed.
        """
        # Returns True when a node was armed, False for empty space.
        node = self._interactive_at(surface, x, y)
        self._set_hover(surface, node)
        if node is None:
            return False
        self._pressed = (surface, node)
        node.set_pressed(True)
        surface._tag_redraw()
        return True

    def _on_release(self, x, y):
        """Finish the armed gesture, firing the click when it ends on the same node.

        A press consumed the gesture, so its release is consumed too, even when it
        lands outside and fires nothing.
        """
        # Returns True when a gesture was armed, False when there was nothing to finish.
        if self._pressed is None:
            return False
        surface, node = self._pressed
        self._pressed = None
        node.set_pressed(False)
        landed = self._interactive_at(surface, x, y)
        self._set_hover(surface, landed)
        if landed is node:
            node.on_click()
        surface._tag_redraw()
        return True

    def _set_hover(self, surface, node):
        """Point the hover at a node and notify the nodes that entered or left.

        Returns True when the hover changed, so the caller knows whether to repaint; a
        repeat of the same node on the same surface is a no-op.
        """
        # Returns True when the hover changed, False when it did not.
        if self._hot is node and self._hot_surface is surface:
            return False
        if self._hot is not None:
            self._hot.set_hover(False)
        self._hot = node
        self._hot_surface = surface
        if node is not None:
            node.set_hover(True)
        return True
