"""Verify the menu widget: the transient layer, its items and its hit-testing.

The menu is a real `Scene` solved under real metrics, and its look is observed through
the recorder canvas, so nothing here needs a GPU. The dismiss hook is a plain recorder,
so no surface or window is needed either; the router integration lives in
`check_menu_input.py`.
"""

from checkkit import RecorderCanvas, banner, check, finish, node_center, node_origin

from gui_paint_modules.coords import DisplayMetrics
from gui_paint_modules.input.router import is_interactive
from gui_paint_modules.layout import Anchor
from gui_paint_modules.scene import Scene

banner()

BOX = (0.0, 0.0, 240.0, 240.0)
METRICS = DisplayMetrics(1.0, 1.0)


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
    check("the popup sits inside the layer",
          menu.popup.rect[0] >= 0.0 and menu.popup.rect[1] >= 0.0, str(menu.popup.rect))
    check("both items sit inside the popup",
          first.rect[2] <= menu.popup.rect[2] and second.rect[2] <= menu.popup.rect[2],
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
    bare.on_click()
    check("a menu with no dismiss hook is tolerated", True)

    # -- look ----------------------------------------------------------------

    recorder = RecorderCanvas()
    scene.draw(recorder)
    rounds = [call for call in recorder.calls if call[0] == "rounded_rect"]
    labels = [call for call in recorder.calls if call[0] == "text"]
    check("the popup and its rows draw rounded backgrounds", len(rounds) >= 3, str(len(rounds)))
    check("both rows draw their labels",
          [call[3] for call in labels] == ["First", "Second"], str(labels))

finish("menu")
