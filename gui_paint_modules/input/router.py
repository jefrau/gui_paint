"""InputRouter — dispatch region-local mouse events to scene nodes.

The router is the single entry point for the input loop: it normalizes a raw event,
finds the interactive node under the pointer, and drives its hover, press and click
hooks. An event that lands on nothing interactive passes through to Blender untouched.

One router serves one window, and every interactive surface in the window shares it. The
dispatch reads no Blender state and is checkable headless; the modal that feeds it and the
"which surface is under the pointer" resolver are injected, and the per-window registry
and the modal operator live at the end of this module.
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
        router = InputRouter(window=window, resolve=_area_resolver)
        _ROUTERS[pointer] = router
    return router


def _active_router(window):
    """The router registered for a window, or None. A lookup, never a creation."""
    if window is None:
        return None
    return _ROUTERS.get(window.as_pointer())


def _area_resolver(router, event):
    """Pick the surface whose bound area holds the pointer, for a multi-surface window.

    ``bpy.context.area`` is the area under the pointer while a modal runs, and a surface
    owns exactly one area pointer, so the newest surface owning that area is the target.
    The whole mapping hinges on that one live fact, which is what the M4 manual step
    observes with two surfaces in one window.
    """
    surface = router.surface_for_area(getattr(bpy.context, "area", None))
    return surface if surface is not None else router.default_surface


def _forget_window(window):
    """Drop a window's router and its modal marker once the modal has stopped."""
    if window is None:
        return
    pointer = window.as_pointer()
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

    def __init__(self, resolve=None, window=None):
        """Store the optional resolver and window, and start with no routing state.

        ``resolve(router, event)`` maps an event to the surface under the pointer; when it
        is None the newest registered surface is used, which covers the single-surface
        case. ``window`` is only used to stand the modal up and to key the per-window
        registry.
        """
        self._resolve = resolve
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

    def surface_for_area(self, area):
        """The newest registered surface that owns an area, or None.

        This is what maps a live event to a surface when a window holds more than one:
        a surface owns one area pointer, so the pointer's area names the surface.
        """
        if area is None:
            return None
        for surface in reversed(self._surfaces):
            if surface.owns(area):
                return surface
        return None

    @property
    def default_surface(self):
        """The newest registered surface, the fallback when the pointer names none."""
        return self._surfaces[-1] if self._surfaces else None

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
            return self._resolve(self, event)
        return self.default_surface

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


class _RouterModal(bpy.types.Operator):
    """The modal that feeds a window's router while an interactive surface is enabled.

    It consumes an event the router handled and passes everything else through, so the
    rest of Blender keeps working. It cancels itself as soon as its window has no live
    router, which is how a stop and a closed window both take effect.
    """

    bl_idname = "gui_paint.input_router"
    bl_label = "gui_paint input router"
    bl_options = {"INTERNAL"}

    def invoke(self, context, event):
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        router = _active_router(context.window)
        if router is None or not router.running:
            _forget_window(context.window)
            return {"CANCELLED"}
        if router.handle(event):
            return {"RUNNING_MODAL"}
        return {"PASS_THROUGH"}
