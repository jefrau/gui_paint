"""Node — the base element in the scene tree.

A node carries a size policy, a margin, an anchor, a z-order, an optional layout and
its children. It holds no look: the scene calls a draw hook, and the widgets that give
a node its appearance arrive with M3.

Every layout-relevant property is a setter that marks the attached scene dirty, so a
mutation cannot be silently ignored and leave the layout stale. ``mark_dirty`` walks
the parent chain to the root, which is where the scene is attached, so a shared
subtree needs no per-node scene bookkeeping and re-parenting just works.

All sizes and margins here are logical units; the reflow solve converts them once,
through ``coords.logical_to_px``.
"""

from .layout import Size


class Node:
    """Base element in the scene tree, solved into a rect by the scene's reflow."""

    def __init__(self, size=None, margin=0, anchor=None, z=0, layout=None, children=None):
        self._parent = None
        self._scene = None
        self._children = []
        # Solved state. The scene's reflow is the only writer: `_rect` in pixels,
        # `_natural` the measured preferred size, `_padding` the solved content inset,
        # `_z_order` the children in draw order. They exist from construction so the
        # draw and hit walks never guess at them, and an unsolved tree is simply inert.
        self._rect = (0.0, 0.0, 0.0, 0.0)
        self._natural = (0.0, 0.0)
        self._padding = 0
        self._z_order = ()
        self._size = Size.auto()
        self._margin = 0.0
        self._anchor = None
        self._z = 0
        self._layout = None
        self._visible = True
        self._clip = False
        # Route the arguments through the setters, so defaults and validation live in
        # one place and a fresh tree is already marked dirty through its attachments.
        self.size = size
        self.margin = margin
        self.anchor = anchor
        self.z = z
        self.layout = layout
        for child in children or ():
            self.add(child)

    # -- tree ---------------------------------------------------------------

    @property
    def parent(self):
        """The node this one is a child of, or None while detached."""
        return self._parent

    @property
    def children(self):
        """The children as a read-only tuple; mutate the tree with add()/remove()."""
        return tuple(self._children)

    def add(self, child):
        """Append a child, re-parenting it if it already had a parent.

        Rejects a node that would create a cycle, so reflow and hit-testing can walk
        the tree without a guard of their own.
        """
        if child is self:
            raise ValueError("a node cannot be its own child")
        node = self
        while node is not None:
            if node is child:
                raise ValueError("a node cannot be added inside its own subtree")
            node = node._parent
        if child._parent is self:
            return child
        if child._parent is not None:
            child._parent.remove(child)
        child._parent = self
        self._children.append(child)
        self.mark_dirty()
        return child

    def remove(self, child):
        """Detach a child. A node that is not a child here is returned unchanged."""
        if child._parent is not self:
            return child
        self._children.remove(child)
        child._parent = None
        self.mark_dirty()
        return child

    # -- solved geometry ----------------------------------------------------

    @property
    def rect(self):
        """The solved rectangle, in pixels, relative to the parent's content box.

        The scene's reflow is the only writer; it is (0, 0, 0, 0) until the tree is
        solved.
        """
        return self._rect

    # -- drawing ------------------------------------------------------------

    def draw(self, canvas):
        """Draw this node's own look. A bare node draws nothing; M3 overrides this."""

    # -- dirty tracking -----------------------------------------------------

    def mark_dirty(self):
        """Flag the scene this node belongs to, if it is attached to one.

        Walks to the root first: the scene is attached there, so any depth of
        mutation reaches it. A detached tree has nothing to flag and is a no-op.
        """
        node = self
        while node._parent is not None:
            node = node._parent
        if node._scene is not None:
            node._scene.mark_dirty()

    # -- layout-relevant properties ----------------------------------------

    @property
    def size(self):
        """The size policy; a missing value means Size.auto()."""
        return self._size

    @size.setter
    def size(self, value):
        self._size = value if value is not None else Size.auto()
        self.mark_dirty()

    @property
    def margin(self):
        """The inset, in logical units, between this node and the slot it got."""
        return self._margin

    @margin.setter
    def margin(self, value):
        if value < 0:
            raise ValueError(f"margin must not be negative, got {value!r}")
        self._margin = float(value)
        self.mark_dirty()

    @property
    def anchor(self):
        """The placement inside the parent, or None to take part in the flow."""
        return self._anchor

    @anchor.setter
    def anchor(self, value):
        self._anchor = value
        self.mark_dirty()

    @property
    def z(self):
        """The stacking order among siblings; higher is nearer the viewer."""
        return self._z

    @z.setter
    def z(self, value):
        self._z = value
        self.mark_dirty()

    @property
    def layout(self):
        """The flow policy this node arranges its children with, or None."""
        return self._layout

    @layout.setter
    def layout(self, value):
        self._layout = value
        self.mark_dirty()

    @property
    def visible(self):
        """Whether the node is drawn and hit-tested at all."""
        return self._visible

    @visible.setter
    def visible(self, value):
        self._visible = bool(value)
        self.mark_dirty()

    @property
    def clip(self):
        """Whether children are clipped to this node's box."""
        return self._clip

    @clip.setter
    def clip(self, value):
        self._clip = bool(value)
        self.mark_dirty()
