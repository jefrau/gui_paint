"""Verify the performance invariants: what a draw and an idle reflow must not do.

The contract's "Performance and redraw" rules are behavioural, not timing-based, so this
check asserts them deterministically and headless. The draw walk is a real solved `Scene`
observed through the recorder canvas: it must be deterministic, read the solved tree
without mutating it, not re-sort or re-measure, and an idle reflow must re-solve nothing.
No wall-clock timing is used anywhere, so the check is stable on both targets.
"""

from checkkit import RecorderCanvas, banner, check, finish

from gui_paint_modules.coords import DisplayMetrics
from gui_paint_modules.layout import Anchor, Size, VBox
from gui_paint_modules.nodes import Node
from gui_paint_modules.scene import Scene
from gui_paint_modules.widgets import Button, Label, Panel

BOX = (0.0, 0.0, 200.0, 200.0)
METRICS = DisplayMetrics(1.0, 1.0)


def _walk(node):
    """Every node in a subtree, root first, in declaration order."""
    yield node
    for child in node.children:
        yield from _walk(child)


def _tree():
    """A small mixed tree: a flow panel of widgets plus one anchored label."""
    panel = Panel(layout=VBox(gap=2, padding=3), anchor=Anchor.bottom_left(margin=4))
    panel.add(Button(label="Go"))
    panel.add(Label("Status", size=10.0))
    panel.add(Button(label="Stop"))
    root = Node()
    root.add(panel)
    root.add(Label("Corner", size=10.0, anchor=Anchor.top_right(margin=3)))
    scene = Scene(root)
    scene.reflow(BOX, METRICS)
    return scene, root


banner()

scene, root = _tree()
check("the tree mixes widgets and a bare container", len(list(_walk(root))) == 6)

# 1 -- the draw walk is deterministic.
first = RecorderCanvas()
scene.draw(first)
second = RecorderCanvas()
scene.draw(second)
check("two draws of the same solved tree emit the same primitives",
      first.calls == second.calls and len(first.calls) > 0,
      f"{len(first.calls)} vs {len(second.calls)}")

# 2 -- a draw is read-only over the solved tree.
rects_before = [node.rect for node in _walk(root)]
scene.draw(RecorderCanvas())
check("a draw leaves every solved rectangle unchanged",
      [node.rect for node in _walk(root)] == rects_before)

# 3 -- a draw neither dirties the scene nor rebuilds the per-frame structures.
z_before = [node._z_order for node in _walk(root)]
children_before = [node._children for node in _walk(root)]
scene.draw(RecorderCanvas())
check("a draw leaves the scene clean", scene._dirty is False)
check("a draw does not rebuild the child order or the child list",
      all(node._z_order is old for node, old in zip(_walk(root), z_before))
      and all(node._children is old for node, old in zip(_walk(root), children_before)))

# 4 -- an idle reflow re-solves nothing: a whole-tree sentinel survives it.
sentinel = (11.0, 12.0, 13.0, 14.0)
for node in _walk(root):
    node._rect = sentinel
scene.reflow(BOX, METRICS)
check("an idle reflow leaves every node untouched",
      all(node.rect == sentinel for node in _walk(root)))
check("an idle reflow keeps the scene clean", scene._dirty is False)

# 5 -- a draw calls no node's measure: the solve already produced every size.
counted = {"measure": 0}


def _counting(*_args, **_kwargs):
    counted["measure"] += 1
    return (0.0, 0.0)


for node in _walk(root):
    node.measure = _counting
try:
    scene.draw(RecorderCanvas())
finally:
    for node in _walk(root):
        del node.measure
check("a draw calls no node's measure", counted["measure"] == 0, str(counted["measure"]))

finish("performance")
