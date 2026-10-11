"""Verify the layout values: size policies, anchors and flow policies.

`layout.py` is a pure lower layer, so this check asserts two things: the factories
build the declared values and reject bad input, and the module imports nothing from
Blender or from the package. The second is a text heuristic, the same kind
`check_compat` uses for the version markers: it catches a module that starts reaching
upward, and a whitespace change would slip past it.
"""

from checkkit import REPO, banner, check, finish, raises_value_error

banner()

try:
    from gui_paint_modules import layout
except Exception as exc:
    layout = None
    check("layout imports", False, f"{type(exc).__name__}: {exc}")
else:
    check("layout imports", True)


if layout is not None:
    Size = getattr(layout, "Size", None)
    Anchor = getattr(layout, "Anchor", None)
    VBox = getattr(layout, "VBox", None)
    HBox = getattr(layout, "HBox", None)

    for name, value in (("Size", Size), ("Anchor", Anchor), ("VBox", VBox), ("HBox", HBox)):
        check(f"layout.{name} is defined", isinstance(value, type))

    if isinstance(Size, type):
        check("Size.auto takes no value", Size.auto().kind == "auto" and Size.auto().value is None)
        fixed = Size.fixed(4)
        check("Size.fixed keeps its units", fixed.kind == "fixed" and fixed.value == 4.0, repr(fixed.value))
        check("Size.fill takes no value", Size.fill().kind == "fill" and Size.fill().value is None)
        percent = Size.percent(0.5)
        check("Size.percent keeps its fraction", percent.kind == "percent" and percent.value == 0.5, repr(percent.value))
        check("Size.fixed rejects a negative size", raises_value_error(lambda: Size.fixed(-1)))
        check("Size.percent rejects zero", raises_value_error(lambda: Size.percent(0.0)))
        check("Size.percent rejects more than one", raises_value_error(lambda: Size.percent(1.5)))

    if isinstance(Anchor, type):
        corner = Anchor.top_left()
        check("Anchor.top_left names its corner", corner.corner == "top_left" and corner.margin == 0.0, repr(corner.corner))
        check("Anchor default margin is zero", Anchor.center().margin == 0.0)
        check("Anchor keeps its margin", Anchor.bottom_right(margin=8).margin == 8.0)
        check("Anchor rejects a negative margin", raises_value_error(lambda: Anchor.top_left(margin=-1)))
        corners = ("top_left", "top_right", "bottom_left", "bottom_right",
                   "top", "bottom", "left", "right", "center")
        built = [getattr(Anchor, name)().corner for name in corners]
        check("every anchor corner builds", built == list(corners), str(built))
        check("Anchor rejects an unknown corner", raises_value_error(lambda: Anchor("bottom_leftt")))

    for name, Flow, direction in (("VBox", VBox, "vertical"), ("HBox", HBox, "horizontal")):
        if not isinstance(Flow, type):
            continue
        flow = Flow()
        check(f"{name} defaults are zero and start", (flow.gap, flow.padding, flow.align) == (0.0, 0.0, "start"), repr((flow.gap, flow.padding, flow.align)))
        check(f"{name} stacks {direction}", flow.direction == direction, repr(flow.direction))
        kept = Flow(gap=2, padding=3, align="center")
        check(f"{name} keeps its values", (kept.gap, kept.padding, kept.align) == (2.0, 3.0, "center"), repr((kept.gap, kept.padding, kept.align)))
        check(f"{name} rejects a negative gap", raises_value_error(lambda: Flow(gap=-1)))
        check(f"{name} rejects a negative padding", raises_value_error(lambda: Flow(padding=-1)))
        check(f"{name} rejects an unknown alignment", raises_value_error(lambda: Flow(align="middle")))

    offenders = []
    for path in sorted((REPO / "gui_paint_modules").glob("*.py")):
        if path.name != "layout.py":
            continue
        text = path.read_text(encoding="utf-8")
        for marker in ("import bpy", "from .", "import gui_paint_modules"):
            if marker in text:
                offenders.append(marker)
    check("layout imports nothing from Blender or the package", not offenders, str(offenders))

finish("layout")
