"""Verify the layout solve: the measure/place passes and the dirty tracking.

Every case uses scale 1 and base 1, so `logical_to_px` is `round` and the numbers in
the table are the logical ones. The dirty assertions use a sentinel rect written
straight into the node: a clean reflow must leave it alone, and a mutation, a metric
change or a new box must overwrite it.
"""

from checkkit import REPO, banner, check, finish

from gui_paint_modules.layout import Anchor, HBox, Size, VBox

banner()

try:
    from gui_paint_modules import coords
    from gui_paint_modules.nodes import Node
    from gui_paint_modules.scene import Scene
except Exception as exc:
    coords = Node = Scene = None
    check("scene imports", False, f"{type(exc).__name__}: {exc}")
else:
    check("scene imports", True)

BOX = (0.0, 0.0, 200.0, 200.0)
METRICS = coords.DisplayMetrics(1.0, 1.0) if coords is not None else None


def _solved(root, box=BOX, metrics=None):
    """Build a scene around the tree, solve it once and return it."""
    scene = Scene(root)
    scene.reflow(box, metrics or METRICS)
    return scene


if isinstance(Scene, type):
    # A — VBox with gap and padding: the first child sits at the content origin.
    root = Node(layout=VBox(gap=2, padding=3))
    a = Node(size=Size.fixed(10))
    b = Node(size=Size.fixed(20))
    root.add(a)
    root.add(b)
    _solved(root)
    check("the root takes the region box", root.rect == (0.0, 0.0, 200.0, 200.0), repr(root.rect))
    check("a VBox puts its first child at the content origin", a.rect == (0.0, 0.0, 10.0, 10.0), repr(a.rect))
    check("a VBox steps down by the gap", b.rect == (0.0, 12.0, 20.0, 20.0), repr(b.rect))

    # B — HBox with a fill child: the fill takes what is left between the fixed ones.
    root = Node(layout=HBox(gap=4))
    a = Node(size=Size.fixed(10))
    b = Node(size=Size.fill())
    c = Node(size=Size.fixed(10))
    root.add(a)
    root.add(b)
    root.add(c)
    _solved(root)
    check("an HBox places children left to right", a.rect == (0.0, 0.0, 10.0, 10.0), repr(a.rect))
    check("a fill child takes the remaining main space", b.rect == (14.0, 0.0, 172.0, 200.0), repr(b.rect))
    check("the child after the fill lands at the end", c.rect == (190.0, 0.0, 10.0, 10.0), repr(c.rect))

    # C — two fills split what is left, and the remainder goes to the last one.
    root = Node(layout=HBox())
    f1 = Node(size=Size.fill())
    f2 = Node(size=Size.fill())
    root.add(f1)
    root.add(f2)
    _solved(root, box=(0.0, 0.0, 101.0, 10.0))
    check("two fills split the space evenly", f1.rect[2] == 50.0, repr(f1.rect))
    check("the remainder goes to the last fill", f2.rect[2] == 51.0, repr(f2.rect))
    check("the second fill starts after the first", f2.rect[0] == 50.0, repr(f2.rect))

    # D — percent takes a fraction of the parent's content box on both axes.
    root = Node(layout=VBox())
    child = Node(size=Size.percent(0.5))
    root.add(child)
    _solved(root)
    check("percent takes a fraction on both axes", child.rect == (0.0, 0.0, 100.0, 100.0), repr(child.rect))

    # E — anchors leave the flow and pin to the content box corners and center.
    root = Node()
    top_right = Node(size=Size.fixed(10), anchor=Anchor.top_right(margin=5))
    middle = Node(size=Size.fixed(10), anchor=Anchor.center())
    bottom_left = Node(size=Size.fixed(10), anchor=Anchor.bottom_left(margin=8))
    root.add(top_right)
    root.add(middle)
    root.add(bottom_left)
    _solved(root)
    check("top_right pins to the far corner with its margin",
          top_right.rect == (185.0, 185.0, 10.0, 10.0), repr(top_right.rect))
    check("center pins to the middle", middle.rect == (95.0, 95.0, 10.0, 10.0), repr(middle.rect))
    check("bottom_left pins to the near corner with its margin",
          bottom_left.rect == (8.0, 8.0, 10.0, 10.0), repr(bottom_left.rect))

    # E2 — the remaining anchor branches, and an anchored child sized by percent.
    root = Node()
    placements = (
        ("top_left", Anchor.top_left(), (0.0, 190.0, 10.0, 10.0)),
        ("bottom_right", Anchor.bottom_right(), (190.0, 0.0, 10.0, 10.0)),
        ("top", Anchor.top(margin=3), (95.0, 187.0, 10.0, 10.0)),
        ("bottom", Anchor.bottom(margin=3), (95.0, 3.0, 10.0, 10.0)),
        ("left", Anchor.left(margin=3), (3.0, 95.0, 10.0, 10.0)),
        ("right", Anchor.right(margin=3), (187.0, 95.0, 10.0, 10.0)),
    )
    pinned = []
    for _, anchor, _ in placements:
        node = Node(size=Size.fixed(10), anchor=anchor)
        root.add(node)
        pinned.append(node)
    _solved(root)
    for (label, _, expected), node in zip(placements, pinned):
        check(f"anchor {label} places the node", node.rect == expected, repr(node.rect))

    root = Node()
    half = Node(size=Size.percent(0.5), anchor=Anchor.center())
    root.add(half)
    _solved(root)
    check("an anchored percent node takes half the content box on both axes",
          half.rect == (50.0, 50.0, 100.0, 100.0), repr(half.rect))

    # F — an auto container takes its intrinsic size and lays its own children out.
    box = Node(layout=VBox(gap=2, padding=3))
    box.add(Node(size=Size.fixed(10)))
    box.add(Node(size=Size.fixed(20)))
    root = Node(layout=VBox())
    root.add(box)
    _solved(root)
    check("an auto container takes its intrinsic size", box.rect == (0.0, 0.0, 26.0, 38.0), repr(box.rect))
    check("the auto container lays its own children out",
          box.children[1].rect == (0.0, 12.0, 20.0, 20.0), repr(box.children[1].rect))

    # G — margin insets a node inside the slot it was given.
    root = Node(layout=VBox())
    child = Node(size=Size.fixed(10), margin=5)
    root.add(child)
    _solved(root)
    check("margin insets the node in its slot", child.rect == (5.0, 5.0, 10.0, 10.0), repr(child.rect))

    # H — cross-axis alignment.
    root = Node(layout=VBox(align="center"))
    child = Node(size=Size.fixed(10))
    root.add(child)
    _solved(root)
    check("align center centers the cross axis", child.rect == (95.0, 0.0, 10.0, 10.0), repr(child.rect))

    # H2 — stretch and end, on both axes.
    root = Node(layout=VBox(align="stretch"))
    child = Node(size=Size.fixed(10))
    root.add(child)
    _solved(root)
    check("align stretch fills the VBox cross axis", child.rect == (0.0, 0.0, 200.0, 10.0), repr(child.rect))

    root = Node(layout=VBox(align="end"))
    child = Node(size=Size.fixed(10))
    root.add(child)
    _solved(root)
    check("align end pushes the VBox child to the far cross edge",
          child.rect == (190.0, 0.0, 10.0, 10.0), repr(child.rect))

    root = Node(layout=HBox(align="stretch"))
    child = Node(size=Size.fixed(10))
    root.add(child)
    _solved(root)
    check("align stretch fills the HBox cross axis", child.rect == (0.0, 0.0, 10.0, 200.0), repr(child.rect))

    root = Node(layout=HBox(align="end"))
    child = Node(size=Size.fixed(10))
    root.add(child)
    _solved(root)
    check("align end pushes the HBox child to the far cross edge",
          child.rect == (0.0, 190.0, 10.0, 10.0), repr(child.rect))

    # I — the root always takes the region box, whatever its own policy says.
    root = Node(size=Size.fixed(50), layout=VBox())
    _solved(root)
    check("the root always takes the region box", root.rect == (0.0, 0.0, 200.0, 200.0), repr(root.rect))

    # J — dirty tracking: clean reflow is a no-op, and every change re-solves.
    root = Node(layout=VBox())
    scene = _solved(root)
    root._rect = (99.0, 99.0, 99.0, 99.0)
    scene.reflow(BOX, METRICS)
    check("a clean reflow does not re-solve", root.rect == (99.0, 99.0, 99.0, 99.0), repr(root.rect))
    scene.mark_dirty()
    scene.reflow(BOX, METRICS)
    check("mark_dirty makes the next reflow re-solve", root.rect == (0.0, 0.0, 200.0, 200.0), repr(root.rect))
    added = Node(size=Size.fixed(10))
    root.add(added)
    scene.reflow(BOX, METRICS)
    check("adding a child marks the scene and re-solves", added.rect == (0.0, 0.0, 10.0, 10.0), repr(added.rect))
    root._rect = (7.0, 7.0, 7.0, 7.0)
    scene.reflow(BOX, coords.DisplayMetrics(2.0, 1.0))
    check("a metric change forces a re-solve", root.rect == (0.0, 0.0, 200.0, 200.0), repr(root.rect))
    root._rect = (8.0, 8.0, 8.0, 8.0)
    scene.reflow((0.0, 0.0, 300.0, 300.0), coords.DisplayMetrics(2.0, 1.0))
    check("a new box forces a re-solve", root.rect == (0.0, 0.0, 300.0, 300.0), repr(root.rect))

    # The display metrics value carries the two scales a solve needs.
    dm = getattr(coords, "DisplayMetrics", None)
    check("coords.DisplayMetrics is defined", isinstance(dm, type))
    if isinstance(dm, type):
        check("DisplayMetrics keeps scale and base", dm(1.5, 2.0).scale == 1.5 and dm(1.5, 2.0).base == 2.0)
        check("DisplayMetrics compares by value", dm(1.0, 1.0) == dm(1.0, 1.0))
        check("DisplayMetrics differs on scale", dm(1.0, 1.0) != dm(2.0, 1.0))
    check("coords.current_metrics is defined", callable(getattr(coords, "current_metrics", None)))

finish("reflow")
