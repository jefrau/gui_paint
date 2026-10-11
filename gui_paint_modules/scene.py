"""Scene — the node tree, its layout solve and its hit-testing.

One Scene owns one root Node and solves the tree into pixel rectangles. The solve is
the single conversion point between the logical sizes the nodes carry and the pixels
everything downstream uses: it calls ``coords.logical_to_px`` once per authored value
and keeps the remaining arithmetic in integers. Drawing and hit-testing then read the
same rectangles, so the two loops can never disagree.

The solve runs only when something changed. A node mutation marks the scene dirty (see
``Node.mark_dirty``), and passing different metrics or a different box re-solves too,
so a DPI change or a region resize is picked up without a separate signal.

A child's rectangle is relative to its parent's content box, which is the parent's
rectangle inset by the layout's padding. Only the root is relative to the region.
"""

from . import coords


def _px(value, metrics):
    """Convert a logical value to pixels through the single conversion point."""
    return coords.logical_to_px(value, metrics.scale, metrics.base)


class Scene:
    """Owns a node tree, solves its layout and hit-tests it."""

    def __init__(self, root=None):
        self._root = None
        self._dirty = True
        self._box = None
        self._metrics = None
        self.root = root

    @property
    def root(self):
        """The root node, or None while the scene is empty."""
        return self._root

    @root.setter
    def root(self, node):
        if self._root is not None:
            self._root._scene = None
        self._root = node
        if node is not None:
            node._scene = self
        self.mark_dirty()

    def mark_dirty(self):
        """Flag the solved layout as stale. A node mutation calls this for you."""
        self._dirty = True

    def reflow(self, box, metrics):
        """Solve the tree into pixel rectangles under ``box`` and ``metrics``.

        ``box`` is the region rectangle in pixels and ``metrics`` carries the display
        scales. The call is a no-op while the tree is clean and both inputs are
        unchanged.
        """
        if not self._dirty and self._box == tuple(box) and self._metrics == metrics:
            return
        self._box = tuple(box)
        self._metrics = metrics
        root = self._root
        if root is not None:
            root._rect = tuple(box)
            self._measure(root, metrics)
            self._place_children(root, metrics)
        self._dirty = False

    # -- draw: back-to-front -------------------------------------------------

    def draw(self, canvas):
        """Draw the tree back-to-front: ascending ``z``, then declaration order.

        Each node is placed by a translate-only transform, in pixels, and its children
        are entered through the content box. A clipped node pushes its absolute
        rectangle, so the Canvas scissor holds its whole subtree in.
        """
        if self._root is not None:
            self._draw_node(self._root, canvas, 0.0, 0.0)

    def _draw_node(self, node, canvas, origin_x, origin_y):
        """Recursive back-to-front descent. ``origin_*`` is the parent content origin."""
        if not node.visible:
            return
        left = origin_x + node.rect[0]
        bottom = origin_y + node.rect[1]
        if node.clip:
            canvas.push_clip(left, bottom, node.rect[2], node.rect[3])
        canvas.push_transform(node.rect[0], node.rect[1], 1.0, 1.0)
        node.draw(canvas)
        padding = node._padding
        canvas.push_transform(padding, padding, 1.0, 1.0)
        for child in node._z_order:
            self._draw_node(child, canvas, left + padding, bottom + padding)
        canvas.pop_transform()
        canvas.pop_transform()
        if node.clip:
            canvas.pop_clip()

    # -- measure: natural sizes, children first -----------------------------

    def _measure(self, node, metrics):
        """Give every node its natural size, bottom-up, so a parent can size itself."""
        for child in node.children:
            self._measure(child, metrics)
        node._natural = self._intrinsic(node, metrics)

    def _intrinsic(self, node, metrics):
        """The natural size, in pixels, of a node with no slot yet."""
        policy = node.size
        if policy.kind == "fixed":
            side = _px(policy.value, metrics)
            return (side, side)
        if policy.kind in ("fill", "percent"):
            # Resolved against the parent's content box during placement instead.
            return (0, 0)
        layout = node.layout
        if layout is None:
            return (0, 0)
        flow = [child for child in node.children if child.anchor is None]
        padding = _px(layout.padding, metrics)
        if not flow:
            return (2 * padding, 2 * padding)
        gap = _px(layout.gap, metrics)
        outer = [self._outer(child, metrics) for child in flow]
        if layout.direction == "vertical":
            width = max(width for width, _ in outer) + 2 * padding
            height = sum(height for _, height in outer) + gap * (len(flow) - 1) + 2 * padding
        else:
            width = sum(width for width, _ in outer) + gap * (len(flow) - 1) + 2 * padding
            height = max(height for _, height in outer) + 2 * padding
        return (width, height)

    def _outer(self, node, metrics):
        """A node's natural size plus its margin, in pixels."""
        margin = _px(node.margin, metrics)
        natural = node._natural
        return (natural[0] + 2 * margin, natural[1] + 2 * margin)

    # -- place: resolve slots, top-down -------------------------------------

    def _place_children(self, node, metrics):
        """Place a node's children inside its content box, then recurse into them.

        Also writes the node's child-order solved state: the `(z, declaration)` rule
        lives here and nowhere else, and the draw and hit walks only iterate the result,
        so neither of them sorts or copies anything per frame.
        """
        layout = node.layout
        padding = _px(layout.padding, metrics) if layout is not None else 0
        node._padding = padding
        content_w = max(0, node.rect[2] - 2 * padding)
        content_h = max(0, node.rect[3] - 2 * padding)
        children = node.children
        node._z_order = tuple(
            child for _, child in sorted(enumerate(children), key=lambda item: (item[1].z, item[0])))
        flow = [child for child in children if child.anchor is None]
        anchored = [child for child in children if child.anchor is not None]
        if layout is None:
            self._place_overlay(flow, content_w, content_h, metrics)
        else:
            self._place_flow(flow, content_w, content_h, layout, metrics)
        for child in anchored:
            child._rect = self._anchor_rect(child, content_w, content_h, metrics)
        for child in children:
            self._place_children(child, metrics)

    def _place_flow(self, flow, content_w, content_h, layout, metrics):
        """Stack the flow children along the layout's main axis."""
        vertical = layout.direction == "vertical"
        main_extent = content_h if vertical else content_w
        cross_extent = content_w if vertical else content_h
        gap = _px(layout.gap, metrics)
        slots = [self._main_slot(child, main_extent, vertical, metrics) for child in flow]
        used = sum(outer for _, _, outer in slots)
        gaps = gap * (len(flow) - 1) if flow else 0
        remaining = max(0, main_extent - used - gaps)
        fills = [index for index, child in enumerate(flow) if child.size.kind == "fill"]
        if fills:
            share = remaining // len(fills)
            extra = remaining - share * len(fills)
            for order, index in enumerate(fills):
                main, margin, _ = slots[index]
                main = share + (extra if order == len(fills) - 1 else 0)
                slots[index] = (main, margin, main + 2 * margin)
        cursor = 0
        for index, child in enumerate(flow):
            main, margin, outer = slots[index]
            cross, cross_offset = self._cross_slot(
                child, cross_extent, layout.align, margin, vertical, metrics)
            if vertical:
                child._rect = (cross_offset, cursor + margin, cross, main)
            else:
                child._rect = (cursor + margin, cross_offset, main, cross)
            cursor += outer + gap

    def _main_slot(self, node, main_extent, vertical, metrics):
        """The (main size, margin, outer size) a node asks for along the flow axis."""
        margin = _px(node.margin, metrics)
        policy = node.size
        if policy.kind == "fixed":
            main = _px(policy.value, metrics)
        elif policy.kind == "percent":
            main = int(round(policy.value * main_extent))
        elif policy.kind == "fill":
            main = 0  # the flow decides the final size; this pass only reserves margins
        else:
            main = node._natural[1] if vertical else node._natural[0]
        return (main, margin, main + 2 * margin)

    def _cross_slot(self, node, cross_extent, align, margin, vertical, metrics):
        """The (size, offset) a node gets on the cross axis of a flow."""
        policy = node.size
        if align == "stretch":
            size = max(0, cross_extent - 2 * margin)
        elif policy.kind == "fixed":
            size = _px(policy.value, metrics)
        elif policy.kind == "percent":
            size = int(round(policy.value * cross_extent))
        elif policy.kind == "fill":
            size = max(0, cross_extent - 2 * margin)
        else:
            size = node._natural[0] if vertical else node._natural[1]
        if align == "center":
            offset = (cross_extent - size) // 2
        elif align == "end":
            offset = cross_extent - size - margin
        else:
            offset = margin
        return (size, offset)

    def _place_overlay(self, flow, content_w, content_h, metrics):
        """Place flow children at the content origin when the parent has no flow."""
        for child in flow:
            margin = _px(child.margin, metrics)
            width, height = self._boxed_size(child, content_w, content_h, metrics)
            child._rect = (margin, margin, width, height)

    def _boxed_size(self, node, content_w, content_h, metrics):
        """The size a node takes when it may use the whole content box."""
        policy = node.size
        if policy.kind == "fixed":
            side = _px(policy.value, metrics)
            return (side, side)
        if policy.kind == "percent":
            return (int(round(policy.value * content_w)), int(round(policy.value * content_h)))
        if policy.kind == "fill":
            return (content_w, content_h)
        return node._natural

    def _anchor_rect(self, node, content_w, content_h, metrics):
        """The rectangle an anchored node takes inside its parent's content box."""
        margin = _px(node.anchor.margin, metrics)
        width, height = self._boxed_size(node, content_w, content_h, metrics)
        corner = node.anchor.corner
        if corner == "top_left":
            x, y = margin, content_h - height - margin
        elif corner == "top_right":
            x, y = content_w - width - margin, content_h - height - margin
        elif corner == "bottom_left":
            x, y = margin, margin
        elif corner == "bottom_right":
            x, y = content_w - width - margin, margin
        elif corner == "top":
            x, y = (content_w - width) // 2, content_h - height - margin
        elif corner == "bottom":
            x, y = (content_w - width) // 2, margin
        elif corner == "left":
            x, y = margin, (content_h - height) // 2
        elif corner == "right":
            x, y = content_w - width - margin, (content_h - height) // 2
        else:
            x, y = (content_w - width) // 2, (content_h - height) // 2
        return (x, y, width, height)

    # -- hit-test: front-to-back --------------------------------------------

    def hit_test(self, x, y):
        """Return the deepest visible node containing the region-local point.

        The walk is front-to-back: higher ``z`` first, and a later-declared sibling on
        top of an earlier one. A subtree result always beats its container, which is
        what makes the returned node the deepest one. Call ``reflow`` first; an
        unsolved scene has empty rects and hits nothing.
        """
        root = self._root
        if root is None:
            return None
        return self._hit(root, float(x), float(y), 0.0, 0.0)

    def _hit(self, node, x, y, origin_x, origin_y):
        """Recursive front-to-back descent. ``origin_*`` is the parent content origin."""
        if not node.visible:
            return None
        left = origin_x + node.rect[0]
        bottom = origin_y + node.rect[1]
        right = left + node.rect[2]
        top = bottom + node.rect[3]
        inside = left <= x < right and bottom <= y < top
        if node.clip and not inside:
            # A clipped node hides everything outside its box, subtree included.
            return None
        padding = node._padding
        content_x = left + padding
        content_y = bottom + padding
        for child in reversed(node._z_order):
            found = self._hit(child, x, y, content_x, content_y)
            if found is not None:
                return found
        return node if inside else None
