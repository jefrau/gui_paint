"""Verify the menu widget: the transient layer, its items and its hit-testing.

The menu is a real `Scene` solved under real metrics, and its look is observed through
the recorder canvas, so nothing here needs a GPU. The dismiss hook is a plain recorder,
so no surface or window is needed either; the router integration lives in
`check_menu_input.py`.
"""

from checkkit import RecorderCanvas, banner, check, finish, node_center, node_origin

from gui_paint_modules.coords import DisplayMetrics
from gui_paint_modules.input.router import is_interactive
from gui_paint_modules.layout import Anchor, HBox, VBox
from gui_paint_modules.scene import Scene

banner()

BOX = (0.0, 0.0, 240.0, 240.0)
METRICS = DisplayMetrics(1.0, 1.0)


def _absolute_rect(node):
    """A solved node's rectangle in absolute scene pixels."""
    x, y = node_origin(node)
    return (x, y, x + node.rect[2], y + node.rect[3])


def _within(inner, outer):
    """Whether a node's absolute rectangle lies inside another's."""
    ix0, iy0, ix1, iy1 = _absolute_rect(inner)
    ox0, oy0, ox1, oy1 = _absolute_rect(outer)
    return ox0 <= ix0 and oy0 <= iy0 and ix1 <= ox1 and iy1 <= oy1


def _shade(item):
    """Draw a row into a recorder canvas and return its background colour.

    The recorded call is unpacked by name, so a change to ``rounded_rect``'s arity
    raises here instead of silently reading the wrong argument.
    """
    canvas = RecorderCanvas()
    item.draw(canvas)
    for name, *args in canvas.calls:
        if name == "rounded_rect":
            _x, _y, _width, _height, _radius, colour = args
            return colour
    return None


try:
    from gui_paint_modules.widgets import Menu, MenuItem
except Exception as exc:
    Menu = MenuItem = None
    check("menu imports", False, f"{type(exc).__name__}: {exc}")
else:
    check("menu imports", True)

for _name, _widget in (("Menu", Menu), ("MenuItem", MenuItem)):
    check(f"widgets exports {_name}", isinstance(_widget, type))

if isinstance(Menu, type) and isinstance(MenuItem, type):
    dismissed = []
    actions = []
    first = MenuItem(label="First")
    second = MenuItem(label="Second", on_click=lambda: actions.append("second"))
    menu = Menu(items=[first, second], popup_anchor=Anchor.top_left(margin=6.0),
                on_dismiss=lambda: dismissed.append(True))

    scene = Scene(menu)
    scene.reflow(BOX, METRICS)

    check("the menu layer spans the region", menu.rect == BOX, str(menu.rect))
    check("the popup sits inside the layer", _within(menu.popup, menu), str(menu.popup.rect))
    check("both items sit inside the popup",
          _within(first, menu.popup) and _within(second, menu.popup),
          f"{first.rect} {second.rect} in {menu.popup.rect}")

    # -- hit-testing: item, popup background, layer --------------------------

    hit = scene.hit_test(*node_center(first))
    check("an item centre hit-tests to that item", hit is first, str(hit))

    popup_x, popup_y = node_origin(menu.popup)
    hit = scene.hit_test(popup_x + 1.0, popup_y + 1.0)
    check("the popup background hit-tests to the popup", hit is menu.popup, str(hit))

    hit = scene.hit_test(2.0, 2.0)
    check("a point outside the popup hit-tests to the layer", hit is menu, str(hit))

    check("the layer is interactive", is_interactive(menu) is True)
    check("the popup is interactive", is_interactive(menu.popup) is True)
    check("an item is interactive", is_interactive(first) is True)

    # -- dismissal -----------------------------------------------------------

    menu.on_click()
    check("clicking the layer dismisses once", dismissed == [True], str(dismissed))

    second.on_click()
    check("selecting an item runs its action first", actions == ["second"], str(actions))
    check("selecting an item also dismisses", len(dismissed) == 2, str(dismissed))

    first.on_click()
    check("selecting an action-less item still dismisses", len(dismissed) == 3, str(dismissed))

    bare = Menu()
    try:
        bare.on_click()
        tolerated = True
    except Exception:
        tolerated = False
    check("a menu with no dismiss hook is tolerated", tolerated is True)

    # -- layout: the layer's own and the popup's are separate parameters -----

    layer_layout = VBox(gap=3.0)
    layered = Menu(items=[], layout=layer_layout)
    check("Menu keeps Node.layout for the layer itself",
          layered.layout is layer_layout, str(layered.layout))

    popup_layout = HBox(gap=5.0)
    try:
        nested = Menu(items=[], popup_layout=popup_layout)
        reached = nested.popup.layout is popup_layout
    except Exception:
        reached = False
    check("popup_layout sets the popup's layout", reached is True)

    # -- look ----------------------------------------------------------------

    idle = _shade(first)
    check("a row draws a background", idle is not None, str(idle))
    first.set_hover(True)
    hover = _shade(first)
    check("hover changes the row's shade", hover != idle, f"{hover} vs {idle}")
    first.set_pressed(True)
    pressed = _shade(first)
    check("pressing the row changes the shade again",
          pressed not in (idle, hover), str(pressed))
    first.set_hover(False)
    first.set_pressed(False)
    check("releasing restores the row's idle shade", _shade(first) == idle)

    recorder = RecorderCanvas()
    scene.draw(recorder)
    rounds = [call for call in recorder.calls if call[0] == "rounded_rect"]
    labels = [call for call in recorder.calls if call[0] == "text"]
    check("the popup and its two rows draw exactly one background each",
          len(rounds) == 3, str(len(rounds)))
    check("both rows draw their labels",
          [call[3] for call in labels] == ["First", "Second"], str(labels))

finish("menu")
