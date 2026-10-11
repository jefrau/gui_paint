"""Verify the input router: hover, press, release and pass-through.

The router turns a normalized mouse event into node hooks. This check builds a real
`Scene` and hit-tests it for real; only the event and the surface are stand-ins, so no
Blender fact is faked and no run loop is needed.
"""

from checkkit import banner, check, finish

from gui_paint_modules.coords import DisplayMetrics
from gui_paint_modules.input.router import InputRouter, is_interactive
from gui_paint_modules.layout import Size
from gui_paint_modules.nodes import Node
from gui_paint_modules.scene import Scene

BOX = (0.0, 0.0, 200.0, 200.0)
METRICS = DisplayMetrics(1.0, 1.0)


class _Probe(Node):
    """An interactive node that records every router hook it hears."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.clicks = 0
        self.hover_states = []
        self.press_states = []

    def on_click(self):
        """Record that the router fired a click."""
        self.clicks += 1

    def set_hover(self, hot):
        """Record the hover notification the router sends."""
        self.hover_states.append(hot)

    def set_pressed(self, pressed):
        """Record the press notification the router sends."""
        self.press_states.append(pressed)


class _Event:
    """Stand-in carrying the fields the normalizer reads, like check_events."""

    def __init__(self, type, value="NOTHING", x=0.0, y=0.0):
        self.type = type
        self.value = value
        self.mouse_region_x = x
        self.mouse_region_y = y


class _Surface:
    """Stand-in for a surface: a solved scene and a redraw counter."""

    def __init__(self, scene):
        self.scene = scene
        self.redraws = 0

    def _tag_redraw(self):
        """Count one repaint request from the router."""
        self.redraws += 1


def _stage():
    """Build a solved surface whose single probe sits at (0, 0, 20, 20)."""
    root = Node()
    probe = _Probe(size=Size.fixed(20))
    root.add(probe)
    scene = Scene(root)
    scene.reflow(BOX, METRICS)
    return _Surface(scene), probe


banner()

# -- is_interactive ---------------------------------------------------------

check("is_interactive is True for a callable on_click", is_interactive(_Probe()) is True)

check("is_interactive is False for a bare node", is_interactive(Node()) is False)

inert = _Probe()
inert.on_click = None
check("is_interactive is False when on_click is None", is_interactive(inert) is False)

# -- registration -----------------------------------------------------------

router = InputRouter()
check("a fresh router has no surfaces", router.surfaces == ())

surface_a, _ = _stage()
surface_b, _ = _stage()
router.register(surface_a)
router.register(surface_b)
check("register keeps the surfaces oldest first", router.surfaces == (surface_a, surface_b))

router.register(surface_a)
check("registering the same surface twice is ignored", router.surfaces == (surface_a, surface_b))

router.unregister(surface_a)
check("unregister removes the surface", router.surfaces == (surface_b,))

# -- pass-through: a key changes nothing ------------------------------------

surface, probe = _stage()
router = InputRouter()
router.register(surface)
consumed = router.handle(_Event("SPACE", "PRESS"))
check("a keyboard event is not consumed", consumed is False)
check("a keyboard event changes no state",
      probe.hover_states == [] and probe.press_states == [] and surface.redraws == 0,
      f"hover={probe.hover_states} press={probe.press_states} redraws={surface.redraws}")

# -- hover ------------------------------------------------------------------

consumed = router.handle(_Event("MOUSEMOVE", x=10.0, y=10.0))
check("a move over the probe is consumed", consumed is True)
check("a move sets hover once", probe.hover_states == [True], str(probe.hover_states))
check("a move tags one redraw", surface.redraws == 1, str(surface.redraws))

consumed = router.handle(_Event("MOUSEMOVE", x=10.0, y=10.0))
check("a repeated move is consumed again", consumed is True)
check("a repeated move does not re-notify hover", probe.hover_states == [True], str(probe.hover_states))
check("a repeated move does not tag another redraw", surface.redraws == 1, str(surface.redraws))

consumed = router.handle(_Event("MOUSEMOVE", x=150.0, y=150.0))
check("a move over empty space is not consumed", consumed is False)
check("a move over empty space clears hover", probe.hover_states == [True, False], str(probe.hover_states))
check("a move over empty space tags one redraw", surface.redraws == 2, str(surface.redraws))

# -- press and release ------------------------------------------------------

consumed = router.handle(_Event("LEFTMOUSE", "PRESS", x=10.0, y=10.0))
check("a press on the probe is consumed", consumed is True)
check("a press marks the node pressed", probe.press_states == [True], str(probe.press_states))

consumed = router.handle(_Event("LEFTMOUSE", "RELEASE", x=10.0, y=10.0))
check("a release is consumed", consumed is True)
check("a release fires on_click once", probe.clicks == 1, str(probe.clicks))
check("a release clears the pressed state", probe.press_states == [True, False], str(probe.press_states))

consumed = router.handle(_Event("LEFTMOUSE", "RELEASE", x=10.0, y=10.0))
check("a release with no press is not consumed", consumed is False)
check("a release with no press does not fire", probe.clicks == 1, str(probe.clicks))

# -- a drag that leaves the node cancels ------------------------------------

router.handle(_Event("LEFTMOUSE", "PRESS", x=10.0, y=10.0))
router.handle(_Event("MOUSEMOVE", x=150.0, y=150.0))
consumed = router.handle(_Event("LEFTMOUSE", "RELEASE", x=150.0, y=150.0))
check("a drag out and release is consumed", consumed is True)
check("a drag out and release does not fire", probe.clicks == 1, str(probe.clicks))
check("a drag out and release clears the pressed state",
      probe.press_states == [True, False, True, False], str(probe.press_states))

# -- a press on empty space arms nothing ------------------------------------

consumed = router.handle(_Event("LEFTMOUSE", "PRESS", x=150.0, y=150.0))
check("a press on empty space is not consumed", consumed is False)
consumed = router.handle(_Event("LEFTMOUSE", "RELEASE", x=150.0, y=150.0))
check("a press on empty space arms no gesture", consumed is False)

# -- no surface, and unregister while hot -----------------------------------

barren = InputRouter()
consumed = barren.handle(_Event("MOUSEMOVE", x=10.0, y=10.0))
check("a move with no surface registered is not consumed", consumed is False)

surface, probe = _stage()
router = InputRouter()
router.register(surface)
router.handle(_Event("MOUSEMOVE", x=10.0, y=10.0))
check("the probe is hot before unregister", probe.hover_states == [True], str(probe.hover_states))
router.unregister(surface)
check("unregistering the hot surface clears its hover",
      probe.hover_states == [True, False], str(probe.hover_states))

# -- the default target is the newest surface -------------------------------

older, older_probe = _stage()
newer, newer_probe = _stage()
router = InputRouter()
router.register(older)
router.register(newer)
consumed = router.handle(_Event("MOUSEMOVE", x=10.0, y=10.0))
check("the default target is the newest surface",
      consumed is True and newer_probe.hover_states == [True], str(newer_probe.hover_states))
check("the older surface is left untouched", older_probe.hover_states == [], str(older_probe.hover_states))

finish("router")
