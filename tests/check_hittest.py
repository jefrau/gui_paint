"""Verify hit-testing: front-to-back, visibility, clipping and depth.

Layout is solved first, then a region-local point is walked down the tree. The point
and the rectangles are both in pixels, so no conversion happens here: this is the
payoff of the coordinate contract.
"""

from checkkit import banner, check, finish

from gui_paint_modules.layout import Size, VBox

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


def _solved(root, box=BOX):
    scene = Scene(root)
    scene.reflow(box, METRICS)
    return scene


if isinstance(Scene, type):
    check("Scene.hit_test is defined", callable(getattr(Scene, "hit_test", None)))

if isinstance(Scene, type) and callable(getattr(Scene, "hit_test", None)):
    empty = Scene()
    check("an empty scene hits nothing", empty.hit_test(5.0, 5.0) is None)

    # A VBox of fixed children: each child is under its own rect and the gap is root.
    root = Node(layout=VBox(gap=2))
    a = Node(size=Size.fixed(10))
    b = Node(size=Size.fixed(20))
    root.add(a)
    root.add(b)
    scene = _solved(root)
    check("a point inside the first child returns it", scene.hit_test(5.0, 5.0) is a)
    check("a point inside the second child returns it", scene.hit_test(5.0, 15.0) is b)
    check("a point in the gap returns the container", scene.hit_test(5.0, 11.0) is root)
    check("a point outside the region hits nothing", scene.hit_test(250.0, 250.0) is None)
    check("the right edge is exclusive", scene.hit_test(10.0, 5.0) is root, "expected the half-open edge")

    # Visibility: an invisible node is skipped, and the container shows through.
    a.visible = False
    scene.reflow(BOX, METRICS)
    check("an invisible child is skipped", scene.hit_test(5.0, 5.0) is root)
    a.visible = True

    # Stacking: higher z wins, and equal z keeps the later sibling on top.
    root = Node()
    low = Node(size=Size.fixed(10), z=1)
    high = Node(size=Size.fixed(10), z=5)
    root.add(low)
    root.add(high)
    scene = _solved(root)
    check("the higher z wins", scene.hit_test(5.0, 5.0) is high)
    high.z = 0
    low.z = 0
    scene.reflow(BOX, METRICS)
    check("equal z keeps the later sibling on top", scene.hit_test(5.0, 5.0) is high, "later-declared must win")

    # Depth: the deepest node under the point wins over its container.
    root = Node(layout=VBox())
    panel = Node(size=Size.fixed(40), layout=VBox())
    child = Node(size=Size.fixed(10))
    root.add(panel)
    panel.add(child)
    scene = _solved(root)
    check("the deepest node under the point wins", scene.hit_test(5.0, 5.0) is child)
    check("the container is hit where no child is", scene.hit_test(15.0, 15.0) is panel)
    check("the root is hit outside the child container", scene.hit_test(60.0, 60.0) is root)

    # Clipping: a clipped container hides an overflowing child; unclipped it is live.
    site = Node(size=Size.fixed(100))
    over = Node(size=Size.fixed(50))
    clipper = Node(size=Size.fixed(10))
    clipper.clip = True
    clipper.add(over)
    site.add(clipper)
    root = Node()
    root.add(site)
    scene = _solved(root)
    check("the overflowing child is the deepest hit inside the clip", scene.hit_test(5.0, 5.0) is over)
    check("a clipped container hides its overflowing child", scene.hit_test(30.0, 30.0) is site, "the child must be hidden")
    clipper.clip = False
    scene.reflow(BOX, METRICS)
    check("without the clip the overflowing child is live", scene.hit_test(30.0, 30.0) is over)

finish("hittest")
