"""Verify the Node base: the tree links and the dirty marking.

Nodes carry the layout-relevant properties, so every setter has to mark the attached
scene dirty — a mutation that is silently ignored would leave the layout stale. The
scene does not exist yet, so this check stands in a recorder for it and asserts the
property write reaches it through the parent chain.
"""

from checkkit import REPO, banner, check, finish, raises_value_error

from gui_paint_modules.layout import Anchor, Size, VBox

banner()


try:
    from gui_paint_modules import nodes
except Exception as exc:
    nodes = None
    check("nodes imports", False, f"{type(exc).__name__}: {exc}")
else:
    check("nodes imports", True)

Node = getattr(nodes, "Node", None) if nodes is not None else None


class _Scene:
    """Stand-in for the scene: records how often a mutation marks it dirty."""

    def __init__(self):
        self.dirty = 0

    def mark_dirty(self):
        self.dirty += 1


if isinstance(Node, type):
    fresh = Node()
    check("a fresh node has an empty rect", fresh.rect == (0.0, 0.0, 0.0, 0.0), repr(fresh.rect))
    check("a fresh node is visible and unclipped", fresh.visible is True and fresh.clip is False)
    check("a fresh node defaults to auto size", fresh.size.kind == "auto", repr(fresh.size.kind))
    check("a fresh node has no parent, anchor or layout",
          fresh.parent is None and fresh.anchor is None and fresh.layout is None)
    check("a fresh node has no children", fresh.children == ())

    parent = Node(layout=VBox(gap=2))
    first = Node(size=Size.fixed(10))
    second = Node(size=Size.fixed(20))
    parent.add(first)
    parent.add(second)
    check("add appends in order", parent.children == (first, second), repr(parent.children))
    check("add wires the parent link", first.parent is parent and second.parent is parent)
    check("the layout value is kept", parent.layout.gap == 2.0)

    other = Node()
    other.add(first)
    check("re-parenting moves the child", first.parent is other and parent.children == (second,), repr(parent.children))

    removed = parent.remove(second)
    check("remove returns the child", removed is second)
    check("remove detaches the child", second.parent is None and parent.children == ())
    check("a second remove is a no-op", parent.remove(second) is second and parent.children == ())

    built = Node(children=[Node(), Node()])
    check("the constructor wires its children",
          len(built.children) == 2 and all(child.parent is built for child in built.children))

    check("a node cannot be its own child", raises_value_error(lambda: parent.add(parent)))
    grand = Node()
    grand.add(parent)
    check("a node cannot be added under its own subtree",
          raises_value_error(lambda: parent.add(grand)))

    scene = _Scene()
    root = Node()
    root._scene = scene
    root.add(parent)
    before = scene.dirty
    root.size = Size.fixed(4)
    check("a property write on the root marks the scene", scene.dirty == before + 1, str(scene.dirty))
    started = scene.dirty
    parent.margin = 3
    check("a property write deep in the tree reaches the scene through the parent chain",
          scene.dirty == started + 1, str(scene.dirty))
    started = scene.dirty
    parent.visible = False
    check("visible marks the scene too", scene.dirty == started + 1, str(scene.dirty))
    started = scene.dirty
    parent.clip = True
    check("clip marks the scene too", scene.dirty == started + 1, str(scene.dirty))
    started = scene.dirty
    parent.add(Node())
    check("a structural change marks the scene too", scene.dirty == started + 1, str(scene.dirty))

    detached = Node()
    try:
        detached.size = Size.fixed(1)
        detached.margin = 1
    except Exception as exc:
        check("a mutation with no scene is safe", False, f"{type(exc).__name__}: {exc}")
    else:
        check("a mutation with no scene is safe", True)

    check("a negative node margin is rejected", raises_value_error(lambda: setattr(Node(), "margin", -1)))
    check("an anchor is kept on the node", Node(anchor=Anchor.center(margin=4)).anchor.margin == 4.0)

    text = (REPO / "gui_paint_modules" / "nodes.py").read_text(encoding="utf-8")
    check("nodes.py does not import Blender", "import bpy" not in text)

finish("nodes")
