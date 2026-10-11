"""Verify the widgets: the measure seam, Panel, Label and Button.

The whole check runs headless. A widget's shapes and text are observed through a recorder
canvas that stands in for `Canvas`, and a Label's intrinsic size goes through
`canvas.measure_text`, which reads `blf` and answers without a GPU on both targets. That
is why nothing here needs a GPU gate.
"""

from checkkit import banner, check, finish

from gui_paint_modules import canvas, coords
from gui_paint_modules.icons import Icon
from gui_paint_modules.layout import Size, VBox
from gui_paint_modules.nodes import Node
from gui_paint_modules.scene import Scene

banner()

BOX = (0.0, 0.0, 200.0, 200.0)
METRICS = coords.DisplayMetrics(1.0, 1.0)

measure_text = getattr(canvas, "measure_text", None)
check("canvas.measure_text is available", callable(measure_text))


class _RecorderCanvas:
    """Canvas stand-in: records the draw primitives a widget emits."""

    def __init__(self):
        self.calls = []
        self.metrics = coords.DisplayMetrics(1.0, 1.0)

    def rounded_rect(self, x, y, w, h, radius, color):
        self.calls.append(("rounded_rect", x, y, w, h, radius, color))

    def shape(self, key, triangles, x, y, w, h, color):
        self.calls.append(("shape", key, x, y, w, h, color))

    def text(self, x, y, text, size, color, align=None):
        self.calls.append(("text", x, y, text, size, color))

    def push_transform(self, x, y, w, h):
        pass

    def pop_transform(self):
        pass


def _names(recorder) -> list:
    """The draw primitives a recorder saw, in the order they arrived."""
    return [call[0] for call in recorder.calls]


# -- the measurement seam on Node -------------------------------------------

measure = getattr(Node, "measure", None)
check("Node.measure is defined", callable(measure))
if callable(measure):
    check("a bare node measures nothing", Node().measure(METRICS) == (0.0, 0.0),
          repr(Node().measure(METRICS)))


# -- the widgets package ----------------------------------------------------

try:
    from gui_paint_modules.widgets import Button, Label, Panel
except Exception as exc:
    Button = Label = Panel = None
    check("widgets imports", False, f"{type(exc).__name__}: {exc}")
else:
    check("widgets imports", True)

for _name, _widget in (("Panel", Panel), ("Label", Label), ("Button", Button)):
    check(f"widgets exports {_name}", isinstance(_widget, type))


# -- Label ------------------------------------------------------------------

if isinstance(Label, type) and callable(measure) and callable(measure_text):
    expected = tuple(measure_text("Ab", 10.0, METRICS))
    label = Label("Ab", size=10.0)
    check("a Label's intrinsic size follows measure_text",
          tuple(label.measure(METRICS)) == expected,
          f"{label.measure(METRICS)} vs {expected}")

    longer = Label("AbAb", size=10.0)
    check("a longer label measures wider",
          longer.measure(METRICS)[0] > label.measure(METRICS)[0],
          f"{longer.measure(METRICS)} vs {label.measure(METRICS)}")

    root = Node()
    auto = Label("Ab", size=10.0)
    root.add(auto)
    scene = Scene(root)
    scene.reflow(BOX, METRICS)
    check("a Label's auto slot comes from its measure",
          tuple(auto.rect[2:]) == expected, f"{auto.rect} vs {expected}")

    recorder = _RecorderCanvas()
    scene.draw(recorder)
    drawn = [call for call in recorder.calls if call[0] == "text"]
    check("a Label draws its text", len(drawn) == 1 and drawn[0][3] == "Ab", str(drawn))


# -- Button -----------------------------------------------------------------

if isinstance(Button, type) and callable(measure) and callable(measure_text):
    plain = Button(label="Go")
    with_icon = Button(label="Go", icon=Icon.named("select"))
    check("a Button sizes itself from its label", plain.measure(METRICS)[0] > 0.0)
    check("an icon widens the Button",
          with_icon.measure(METRICS)[0] > plain.measure(METRICS)[0],
          f"{with_icon.measure(METRICS)} vs {plain.measure(METRICS)}")

    root = Node()
    button = Button(label="Go", icon=Icon.named("select"))
    root.add(button)
    scene = Scene(root)
    scene.reflow(BOX, METRICS)
    check("a Button's auto slot comes from its measure",
          tuple(button.rect[2:]) == tuple(button.measure(METRICS)), str(button.rect))

    recorder = _RecorderCanvas()
    scene.draw(recorder)
    check("a Button draws background, then icon, then label",
          _names(recorder) == ["rounded_rect", "shape", "text"], str(_names(recorder)))
    shapes = [call for call in recorder.calls if call[0] == "shape"]
    check("the icon reaches the canvas under its own key",
          bool(shapes) and shapes[0][1] == ("icon", "select"), str(shapes))
    labels = [call for call in recorder.calls if call[0] == "text"]
    check("the label reaches the canvas", bool(labels) and labels[0][3] == "Go", str(labels))

    called = []
    interactive = Button(label="Go", on_click=lambda: called.append(True))
    scene = Scene(interactive)
    scene.reflow(BOX, METRICS)
    scene.draw(_RecorderCanvas())
    scene.hit_test(10.0, 10.0)
    check("a Button never invokes on_click", called == [], str(called))
    check("a Button starts cold and unpressed",
          interactive._hot is False and interactive._pressed is False,
          f"hot={interactive._hot} pressed={interactive._pressed}")


# -- Panel ------------------------------------------------------------------

if isinstance(Panel, type) and callable(measure):
    root = Node()
    panel = Panel(layout=VBox(gap=2.0, padding=3.0))
    first = Node(size=Size.fixed(10))
    second = Node(size=Size.fixed(10))
    panel.add(first)
    panel.add(second)
    root.add(panel)
    scene = Scene(root)
    scene.reflow(BOX, METRICS)
    check("a Panel takes its natural size from the flow",
          tuple(panel.rect[2:]) == (16.0, 28.0), str(panel.rect))
    check("a Panel stacks its children",
          second.rect[1] > first.rect[1] and tuple(first.rect[2:]) == (10.0, 10.0),
          f"{first.rect} {second.rect}")
    check("a Panel keeps its children inside its box",
          second.rect[1] + second.rect[3] <= panel.rect[3],
          f"{second.rect} in {panel.rect}")

    recorder = _RecorderCanvas()
    scene.draw(recorder)
    rounds = [call for call in recorder.calls if call[0] == "rounded_rect"]
    check("a Panel draws its rounded background",
          len(rounds) == 1 and tuple(rounds[0][3:5]) == (16.0, 28.0), str(rounds))


# -- widget content is layout-relevant, so it must invalidate the solve ------

if isinstance(Label, type) and isinstance(Button, type):
    root = Node()
    label = Label("Ab", size=10.0)
    root.add(label)
    scene = Scene(root)
    scene.reflow(BOX, METRICS)
    plain_width = label.rect[2]

    label.text = "AbAbAbAb"
    scene.reflow(BOX, METRICS)
    check("changing a Label's text re-solves the layout",
          label.rect[2] > plain_width, f"{plain_width} -> {label.rect[2]}")

    height_before = label.rect[3]
    label.font_size = 30.0
    scene.reflow(BOX, METRICS)
    check("changing a Label's font size re-solves the layout",
          label.rect[3] > height_before, f"{height_before} -> {label.rect[3]}")

    root = Node()
    button = Button(label="Go")
    root.add(button)
    scene = Scene(root)
    scene.reflow(BOX, METRICS)
    button_width = button.rect[2]
    button.label = "Go somewhere else"
    scene.reflow(BOX, METRICS)
    check("changing a Button's label re-solves the layout",
          button.rect[2] > button_width, f"{button_width} -> {button.rect[2]}")

    with_icon = button.rect[2]
    button.icon = Icon.named("select")
    scene.reflow(BOX, METRICS)
    check("changing a Button's icon re-solves the layout",
          button.rect[2] > with_icon, f"{with_icon} -> {button.rect[2]}")

    # A look-only change must NOT invalidate anything: the sentinel rect survives.
    root = Node()
    painted = Label("Ab", size=10.0)
    root.add(painted)
    scene = Scene(root)
    scene.reflow(BOX, METRICS)
    painted._rect = (7.0, 7.0, 7.0, 7.0)
    painted.color = (0.0, 0.0, 0.0, 1.0)
    scene.reflow(BOX, METRICS)
    check("changing a colour does not re-solve the layout",
          painted.rect == (7.0, 7.0, 7.0, 7.0), repr(painted.rect))


finish("widgets")
