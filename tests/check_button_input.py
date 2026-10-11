"""Verify a Button reacts to the router: hover, press, click, and a look-only shade.

The button is built into a real solved scene and driven by a real router through
synthetic events, so the interaction is checked end to end without a live modal.
"""

from checkkit import RecorderCanvas, StubEvent, StubSurface, banner, check, finish

from gui_paint_modules.coords import DisplayMetrics
from gui_paint_modules.input.router import InputRouter
from gui_paint_modules.layout import Size
from gui_paint_modules.nodes import Node
from gui_paint_modules.scene import Scene
from gui_paint_modules.widgets import Button

BOX = (0.0, 0.0, 200.0, 200.0)
METRICS = DisplayMetrics(1.0, 1.0)


def _stage():
    """Build a solved scene with one fixed-size Button at (0, 0, 40, 40)."""
    clicks = []
    button = Button(label="Go", size=Size.fixed(40), on_click=lambda: clicks.append(1))
    root = Node()
    root.add(button)
    scene = Scene(root)
    scene.reflow(BOX, METRICS)
    return StubSurface(scene), button, clicks


def _background(button):
    """Draw the button into a recorder canvas and return the background colour."""
    canvas = RecorderCanvas()
    button.draw(canvas)
    colours = [call[6] for call in canvas.calls if call[0] == "rounded_rect"]
    return colours[0] if colours else None


banner()

import gui_paint_modules.input.router as router_module

router_module._ROUTERS.clear()
router_module._MODALS.clear()
router_module._launch_modal = lambda router: None

surface, button, clicks = _stage()
router = InputRouter()
router.register(surface)

check("the fixed button solves to its box", button.rect == (0.0, 0.0, 40.0, 40.0), str(button.rect))

idle_shade = _background(button)
check("an idle button draws a background", idle_shade is not None, str(idle_shade))

router.handle(StubEvent("MOUSEMOVE", x=10.0, y=10.0))
check("a move over the button sets it hot", button._hot is True)
hover_shade = _background(button)
check("hover changes the shade", hover_shade != idle_shade, f"{hover_shade} vs {idle_shade}")

router.handle(StubEvent("MOUSEMOVE", x=150.0, y=150.0))
check("a move off the button clears hot", button._hot is False)
check("leaving restores the idle shade", _background(button) == idle_shade)

router.handle(StubEvent("LEFTMOUSE", "PRESS", x=10.0, y=10.0))
check("a press sets the button pressed", button._pressed is True)
check("a press keeps it hot", button._hot is True)
pressed_shade = _background(button)
check("press changes the shade again", pressed_shade not in (idle_shade, hover_shade), str(pressed_shade))

router.handle(StubEvent("LEFTMOUSE", "RELEASE", x=10.0, y=10.0))
check("a release inside fires on_click once", clicks == [1], str(clicks))
check("a release clears pressed", button._pressed is False)

router.handle(StubEvent("LEFTMOUSE", "PRESS", x=10.0, y=10.0))
router.handle(StubEvent("LEFTMOUSE", "RELEASE", x=150.0, y=150.0))
check("a release outside fires nothing", clicks == [1], str(clicks))

# The flags are look-only: flipping them must not mark the solved layout dirty.
scene = surface.scene
scene.reflow(BOX, METRICS)
check("the scene is clean after a solve", scene._dirty is False)
button.set_hover(True)
button.set_pressed(True)
check("flipping the flags does not dirty the layout", scene._dirty is False)

finish("button input")
