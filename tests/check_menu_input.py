"""Verify the menu's input integration: opening from a button and the router.

`Surface.open_menu` is the host seam a button uses, and the router is the M4 one,
unchanged. The router half builds real Scenes and stand-in surfaces; the seam half uses
real Surfaces with the draw-handler API swapped, the way `check_surface_lifecycle.py`
does.
"""

import bpy

from checkkit import (
    StubArea, StubContext, StubEvent, StubSpace, StubSurface, StubWindow, banner, check,
    finish, node_center,
)

from gui_paint_modules.coords import DisplayMetrics
from gui_paint_modules.input.router import InputRouter
from gui_paint_modules.layout import Anchor
from gui_paint_modules.nodes import Node
from gui_paint_modules.scene import Scene
from gui_paint_modules.surface import Surface
from gui_paint_modules.widgets import Button, Menu, MenuItem

banner()

BOX = (0.0, 0.0, 200.0, 200.0)
METRICS = DisplayMetrics(1.0, 1.0)


def _solved(root):
    """Return a scene solved under the check's box."""
    scene = Scene(root)
    scene.reflow(BOX, METRICS)
    return scene


# -- the router half: an open menu owns the pointer --------------------------


def _stage():
    """A toolbar with one button, and a menu with one item, sharing a region."""
    clicks = []
    toolbar_root = Node()
    toolbar_button = Button(label="Open", on_click=lambda: clicks.append(True))
    toolbar_root.add(toolbar_button)

    dismissed = []
    actions = []
    item = MenuItem(label="Run", on_click=lambda: actions.append("run"))
    menu = Menu(items=[item], popup_anchor=Anchor.top_left(margin=6.0),
                on_dismiss=lambda: dismissed.append(True))

    router = InputRouter()
    toolbar = StubSurface(_solved(toolbar_root))
    overlay = StubSurface(_solved(menu))
    router.register(toolbar)
    router.register(overlay)
    return router, toolbar_button, clicks, menu, item, actions, dismissed, toolbar, overlay


(router, toolbar_button, clicks, menu, item, actions, dismissed,
 toolbar, overlay) = _stage()

consumed = router.handle(StubEvent("MOUSEMOVE", x=node_center(toolbar_button)[0],
                                   y=node_center(toolbar_button)[1]))
check("a move over the older surface is consumed by the menu layer", consumed is True, str(consumed))
check("the older button is not hovered while the menu is open", toolbar_button._hot is False,
      str(toolbar_button._hot))

consumed = router.handle(StubEvent("MOUSEMOVE", x=node_center(item)[0], y=node_center(item)[1]))
check("a move over an item is consumed", consumed is True, str(consumed))
check("the item is hovered", item._hot is True, str(item._hot))

router.handle(StubEvent("LEFTMOUSE", "PRESS", x=node_center(item)[0], y=node_center(item)[1]))
consumed = router.handle(StubEvent("LEFTMOUSE", "RELEASE", x=node_center(item)[0], y=node_center(item)[1]))
check("a click on an item is consumed", consumed is True, str(consumed))
check("selecting the item runs its action", actions == ["run"], str(actions))
check("selecting the item dismisses the menu", dismissed == [True], str(dismissed))
check("the older button never fired", clicks == [], str(clicks))

router, toolbar_button, clicks, menu, item, actions, dismissed, toolbar, overlay = _stage()
router.handle(StubEvent("LEFTMOUSE", "PRESS", x=2.0, y=2.0))
consumed = router.handle(StubEvent("LEFTMOUSE", "RELEASE", x=2.0, y=2.0))
check("a click outside the popup is consumed", consumed is True, str(consumed))
check("a click outside the popup dismisses the menu", dismissed == [True], str(dismissed))
check("a click outside the popup does not reach the button", clicks == [], str(clicks))

# -- closing restores the surface underneath ---------------------------------

router.unregister(overlay)
consumed = router.handle(StubEvent("MOUSEMOVE", x=node_center(toolbar_button)[0],
                                   y=node_center(toolbar_button)[1]))
check("after the menu closes the older surface gets the pointer", consumed is True, str(consumed))
check("the older button is hovered again", toolbar_button._hot is True, str(toolbar_button._hot))

# -- the seam: Surface.open_menu ---------------------------------------------

has_seam = callable(getattr(Surface, "open_menu", None))
check("Surface.open_menu is defined", has_seam)

if has_seam:
    import gui_paint_modules.input.router as router_module

    launches = []
    saved_launch = router_module._launch_modal
    router_module._ROUTERS.clear()
    router_module._MODALS.clear()
    router_module._launch_modal = lambda router: launches.append(router)

    original_space = getattr(bpy.types, "SpaceView3D", None)
    original_context = bpy.context
    context = StubContext(None)
    bpy.types.SpaceView3D = StubSpace()
    bpy.context = context
    try:
        area = StubArea(9001)
        window = StubWindow(9001)
        context.area = area
        context.window = window

        source = Surface("SpaceView3D", interactive=True)
        source.enable(area)
        check("the source surface starts one modal", len(launches) == 1, str(launches))

        first_menu = Menu(items=[MenuItem(label="A")])
        overlay = source.open_menu(first_menu)
        check("open_menu returns a live surface",
              isinstance(overlay, Surface) and overlay._handle is not None,
              str(overlay))
        check("the menu surface is interactive", overlay.interactive is True)
        check("the menu shares the source's space and region",
              (overlay.space_type, overlay.region_type) == (source.space_type, source.region_type),
              f"{overlay.space_type}/{overlay.region_type}")
        check("the menu shares the window router", overlay._router is source._router)
        check("the menu scene root is the menu", overlay.scene.root is first_menu)
        check("the menu is registered with the router", overlay in source._router.surfaces)
        check("opening a menu launches no extra modal", len(launches) == 1, str(launches))

        first_menu.on_click()
        check("dismissing the menu disables its surface", overlay._handle is None)

        first = source.open_menu(Menu(items=[]))
        second = source.open_menu(Menu(items=[]))
        check("a second open_menu closes the previous one",
              first._handle is None and second._handle is not None,
              f"{first._handle} {second._handle}")

        source.disable()
        check("disabling the source closes its menu", second._handle is None)
    finally:
        context.window = None
        router_module._launch_modal = saved_launch
        router_module._ROUTERS.clear()
        router_module._MODALS.clear()
        bpy.context = original_context
        if original_space is not None:
            bpy.types.SpaceView3D = original_space

    closed = Surface("SpaceView3D", interactive=True)
    raised = False
    try:
        closed.open_menu(Menu())
    except RuntimeError:
        raised = True
    except Exception:
        pass
    check("open_menu on a disabled surface raises", raised is True)

finish("menu input")
