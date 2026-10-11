"""Layout values: size policies, anchors and flow policies.

These are plain data, not nodes. A node carries them as properties, and the layout
solve reads them; none of them has children of its own. That keeps this a pure lower
layer: the module imports nothing from Blender and nothing from the package, so the
dependency direction the architecture fixes stays intact.

Everything here is expressed in logical units. The conversion to pixels happens once,
in the reflow solve, through `coords.logical_to_px`.
"""

_ALIGNMENTS = ("start", "center", "end", "stretch")

_CORNERS = (
    "top_left", "top_right", "bottom_left", "bottom_right",
    "top", "bottom", "left", "right", "center",
)


class Size:
    """How a node asks to be sized inside its parent.

    The four policies are the ones the architecture lists: take the natural size,
    take an exact size, take a share of what the flow has left, or take a fraction of
    the parent's content box.
    """

    def __init__(self, kind, value=None):
        self.kind = kind
        self.value = value

    @classmethod
    def auto(cls):
        """Take the natural (content) size: zero for a leaf, intrinsic for a container."""
        return cls("auto")

    @classmethod
    def fixed(cls, units):
        """Ask for an exact size, in logical units."""
        if units < 0:
            raise ValueError(f"fixed size must not be negative, got {units!r}")
        return cls("fixed", float(units))

    @classmethod
    def fill(cls):
        """Take a share of the space the parent's flow has left."""
        return cls("fill")

    @classmethod
    def percent(cls, fraction):
        """Take a fraction of the parent's content box, in the range (0, 1]."""
        if not 0.0 < fraction <= 1.0:
            raise ValueError(f"percent must be in (0, 1], got {fraction!r}")
        return cls("percent", float(fraction))


class Anchor:
    """Where a node sits inside its parent, outside the parent's flow.

    A node with an anchor leaves the flow: it is placed against a corner, an edge or
    the center of the parent's content box, inset by ``margin`` logical units. Making
    the parent's solved box the reference is what moves an anchored child for free
    when the parent moves or resizes.
    """

    def __init__(self, corner, margin=0.0):
        if margin < 0:
            raise ValueError(f"anchor margin must not be negative, got {margin!r}")
        self.corner = corner
        self.margin = float(margin)

    @classmethod
    def top_left(cls, margin=0.0):
        return cls("top_left", margin)

    @classmethod
    def top_right(cls, margin=0.0):
        return cls("top_right", margin)

    @classmethod
    def bottom_left(cls, margin=0.0):
        return cls("bottom_left", margin)

    @classmethod
    def bottom_right(cls, margin=0.0):
        return cls("bottom_right", margin)

    @classmethod
    def top(cls, margin=0.0):
        return cls("top", margin)

    @classmethod
    def bottom(cls, margin=0.0):
        return cls("bottom", margin)

    @classmethod
    def left(cls, margin=0.0):
        return cls("left", margin)

    @classmethod
    def right(cls, margin=0.0):
        return cls("right", margin)

    @classmethod
    def center(cls, margin=0.0):
        return cls("center", margin)


class _Flow:
    """Shared behavior of the stacking policies; subclasses fix the direction.

    ``gap`` separates neighbours, ``padding`` insets the container's content box for
    every child, and ``align`` places a child on the cross axis.
    """

    direction = None

    def __init__(self, gap=0.0, padding=0.0, align="start"):
        if gap < 0:
            raise ValueError(f"gap must not be negative, got {gap!r}")
        if padding < 0:
            raise ValueError(f"padding must not be negative, got {padding!r}")
        if align not in _ALIGNMENTS:
            raise ValueError(f"align must be one of {_ALIGNMENTS}, got {align!r}")
        self.gap = float(gap)
        self.padding = float(padding)
        self.align = align


class VBox(_Flow):
    """Stacks children bottom-to-top, in declaration order."""

    direction = "vertical"


class HBox(_Flow):
    """Stacks children left-to-right, in declaration order."""

    direction = "horizontal"
