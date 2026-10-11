"""InputRouter — dispatch mouse events to the interactive nodes of a window.

The router is the single entry point for the input loop: it normalizes a raw event, finds
the surface whose region holds the pointer, converts the point into that region's local
space, and drives the interactive node's hover, press and click hooks. An event that lands
on nothing interactive passes through to Blender untouched.

One router serves one window, and every interactive surface in the window shares it. The
dispatch reads no Blender state and is checkable headless: the surface supplies its region
rectangle, and a check substitutes one. The per-window registry and the modal operator live
at the end of this module.
"""

import bpy

from .events import MOVE, PRESS, RELEASE, classify

# One router and, at most, one modal per window. Both are keyed by the window pointer, so
# a closed window can never make a lookup raise.
_ROUTERS = {}
_MODALS = set()
_operator_registered = False


def is_interactive(node):
    """Whether a node takes input, i.e. it exposes a callable ``on_click``.

    A bare node is inert by design: only a widget that overrides ``on_click`` is routed
    to, so a plain container never swallows a click.
    """
    # Returns True for a node with a callable on_click, False otherwise.
    return node is not None and callable(getattr(node, "on_click", None))


def router_for(window):
    """Return the one router for a window, creating it on first request.

    One router per window: every interactive surface in the same window shares it, so a
    window never runs two modals pulling at the same events.

    Returns None when there is no window to key on, which is the case in a background
    process with no drawn interface.
    """
    if window is None:
        return None
    pointer = window.as_pointer()
    router = _ROUTERS.get(pointer)
    if router is None:
        router = InputRouter(window=window)
        _ROUTERS[pointer] = router
    return router


def _forget_pointer(pointer):
    """Drop a window's router and its modal marker, keyed by the window pointer.

    The modal uses this when it cancels. It takes a pointer and not a window because the
    window may already be gone by then, and a dead pointer left behind would suppress the
    next modal for a window that happens to reuse it.
    """
    if pointer is None:
        return
    _ROUTERS.pop(pointer, None)
    _MODALS.discard(pointer)


def _register_operator():
    """Register the modal operator class on first use, never at import time."""
    global _operator_registered
    if _operator_registered:
        return
    bpy.utils.register_class(_RouterModal)
    _operator_registered = True


def _launch_modal(router):
    """Ask Blender to run the modal that feeds this router's window.

    This is the input layer's one Blender-specific call, kept alone so a check can replace
    it and so the exact invocation has a single home. The modal's live event loop is what
    the M4 manual step observes, because a background process has no events to feed it.
    """
    _register_operator()
    bpy.ops.gui_paint.input_router("INVOKE_DEFAULT")


class InputRouter:
    """Routes mouse events to the interactive nodes of the registered surfaces.

    Consumes an event that lands on an interactive node and passes everything else
    through. The pressed gesture is tracked here, so a drag that leaves the node cancels
    instead of firing.
    """

    def __init__(self, window=None):
        """Store the window and start with no routing state.

        ``window`` is only used to stand the modal up and to key the per-window registry;
        the dispatch itself never reads it.
        """
        self._window = window
        self._running = False
        self._surfaces = []
        self._hot = None
        self._hot_surface = None
        self._pressed = None

    @property
    def surfaces(self):
        """The registered surfaces, oldest first."""
        return tuple(self._surfaces)

    @property
    def window(self):
        """The window this router serves, or None in a background process."""
        return self._window

    @property
    def running(self):
        """Whether a modal is standing up to feed this router."""
        return self._running

    def register(self, surface):
        """Add a surface to the routing list, oldest first, and start routing.

        A repeat is ignored. The first surface stands the window's modal up; a later
        surface in the same window shares it, so no second modal is launched.
        """
        if surface in self._surfaces:
            return
        self._surfaces.append(surface)
        self.start()

    def unregister(self, surface):
        """Remove a surface, drop any state that pointed at it, and stop when empty.

        A press belongs to one surface, so losing that surface cancels it; a hover is
        cleared through ``_set_hover``, so the node hears the pointer leave.
        """
        if surface not in self._surfaces:
            return
        self._surfaces.remove(surface)
        if self._pressed is not None and self._pressed[0] is surface:
            self._pressed = None
        if self._hot_surface is surface:
            self._set_hover(None, None)
        if not self._surfaces:
            self.stop()

    def start(self):
        """Stand the routing modal up for this window, once per window.

        A window that already has a modal is left alone: re-enabling a surface before the
        previous modal has seen an event must reuse it, not stack a second one that would
        handle every event twice.
        """
        if self._running:
            return
        self._running = True
        pointer = self._window.as_pointer() if self._window is not None else None
        if pointer is None:
            return
        if pointer in _MODALS:
            return
        _MODALS.add(pointer)
        _launch_modal(self)

    def stop(self):
        """Mark the router stopped; its modal cancels on the next event.

        Nothing is torn down here beyond the running flag: the modal sees no live router
        for its window and cancels itself, which is the "self-cancel on context change"
        rule doing the same work for disable.
        """
        self._running = False

    def handle(self, event):
        """Process one event and report whether the router consumed it.

        The point arrives in window pixels, because a window-level modal has no region.
        The router finds the surface whose region holds it and converts to that region's
        local space before hit-testing. Returns True when the event was consumed, False to
        pass it through: a key, a wheel tick, another button, or a lone CLICK never reaches
        a node.
        """
        classified = classify(event)
        if classified is None:
            return False
        kind, x, y = classified

        # A release finishes the gesture the router started, whatever the pointer is
        # now over, so it is handled before any surface lookup.
        if kind == RELEASE:
            return self._on_release(x, y)

        located = self._locate(x, y)
        if located is None:
            self._set_hover(None, None)
            return False
        surface, (local_x, local_y) = located
        if kind == MOVE:
            return self._on_move(surface, local_x, local_y)
        return self._on_press(surface, local_x, local_y)

    def _locate(self, x, y):
        """The newest surface whose region holds a window point, with local coordinates.

        Returns (surface, (local_x, local_y)) or None. A surface's region rectangle comes
        from its live area, so a moved or closed area simply stops matching and the event
        falls through to whichever surface still contains the pointer.
        """
        for surface in reversed(self._surfaces):
            rect = surface.window_rect()
            if rect is None:
                continue
            left, bottom, width, height = rect
            if left <= x < left + width and bottom <= y < bottom + height:
                return (surface, (x - left, y - bottom))
        return None

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

        The point is a window point; it is converted against the pressed surface's own
        region, so a release in another area simply misses. A press consumed the gesture,
        so its release is consumed too, even when it fires nothing.
        """
        # Returns True when a gesture was armed, False when there was nothing to finish.
        if self._pressed is None:
            return False
        surface, node = self._pressed
        self._pressed = None
        node.set_pressed(False)
        landed = None
        rect = surface.window_rect()
        if rect is not None:
            landed = self._interactive_at(surface, x - rect[0], y - rect[1])
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


class _RouterModal(bpy.types.Operator):
    """The modal that feeds a window's router while an interactive surface is enabled.

    It consumes an event the router handled and passes everything else through, so the
    rest of Blender keeps working. It cancels itself as soon as its window has no live
    router, which is how a stop and a closed window both take effect.
    """

    bl_idname = "gui_paint.input_router"
    bl_label = "gui_paint input router"
    bl_options = {"INTERNAL"}

    # The window captured at invoke, so a cancel can still clean up after the window is gone.
    _pointer = None

    def invoke(self, context, event):
        window = context.window
        self._pointer = window.as_pointer() if window is not None else None
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        window = context.window
        pointer = window.as_pointer() if window is not None else self._pointer
        router = _ROUTERS.get(pointer) if pointer is not None else None
        if router is None or not router.running:
            _forget_pointer(pointer)
            return {"CANCELLED"}
        if router.handle(event):
            return {"RUNNING_MODAL"}
        return {"PASS_THROUGH"}
