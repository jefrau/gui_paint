"""Canvas — the immediate-mode 2D drawing surface for one region.

Owns the shared shader handles, the batch cache and the transform/clip stacks.
Nothing here may create a shader, do file I/O or allocate in a draw call.

A solid rectangle reuses one cached unit quad under a transform, so the geometry is
built once per canvas instead of once per rectangle. The unit quad carries its two
triangles as six vertices: task M1.4 probed Blender's indexed-batch constructor and
found it rejects the documented shape, while a plain triangle list is accepted.

A rounded rectangle and a circle do **not** reuse a unit shape: scaling a unit box would
stretch a round corner into an ellipse, so their geometry is built at its real pixel size
and cached under that shape, then drawn under a translate-only transform.
"""

import math

import blf
import gpu

from . import compat, coords, shaders

QUAD_BATCH_KEY = "quad"

# A plain triangle list is what the GPU batch constructor accepts (M1.4), so every shape
# here is expressed as vertices, never as an index buffer.
_CIRCLE_SEGMENTS = 32
_CORNER_SEGMENTS = 6

# Text uses Blender's own font; there is no font loading in M3, and `blf.size` takes the
# same two arguments on both supported versions (see `check_draw_api`).
_FONT_ID = 0


def quad_triangles() -> tuple:
    """Return the unit quad as six triangle vertices in the canonical space.

    Counter-clockwise from the origin: (0,0) (1,0) (1,1), then (0,0) (1,1) (0,1).
    """
    return (
        (0.0, 0.0), (1.0, 0.0), (1.0, 1.0),
        (0.0, 0.0), (1.0, 1.0), (0.0, 1.0),
    )


def circle_outline(radius: float, segments: int = _CIRCLE_SEGMENTS) -> tuple:
    """Return a circle centred on the origin as a closed outline, counter-clockwise."""
    return tuple(
        (radius * math.cos(2.0 * math.pi * step / segments),
         radius * math.sin(2.0 * math.pi * step / segments))
        for step in range(segments)
    )


def rounded_rect_outline(w: float, h: float, radius: float,
                         segments: int = _CORNER_SEGMENTS) -> tuple:
    """Return the (0, 0) to (w, h) rounded rectangle as a closed outline.

    The radius is clamped to half the short side, and a zero radius returns the four
    corners, so a plain rectangle is the degenerate case rather than a special shape.
    """
    radius = max(0.0, min(float(radius), min(w, h) / 2.0))
    if radius == 0.0:
        return ((0.0, 0.0), (w, 0.0), (w, h), (0.0, h))
    corners = (
        ((w - radius, radius), -math.pi / 2.0, 0.0),
        ((w - radius, h - radius), 0.0, math.pi / 2.0),
        ((radius, h - radius), math.pi / 2.0, math.pi),
        ((radius, radius), math.pi, 3.0 * math.pi / 2.0),
    )
    points = []
    for (cx, cy), start, end in corners:
        for step in range(segments + 1):
            angle = start + (end - start) * step / segments
            points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return tuple(points)


def fan_triangles(outline) -> tuple:
    """Return a convex outline as a triangle list, fanned from its centroid.

    A rounded rectangle and a circle are both convex, so the fan is exact. A concave
    outline would need a real tessellator, and nothing asks for one yet.
    """
    count = len(outline)
    cx = sum(point[0] for point in outline) / count
    cy = sum(point[1] for point in outline) / count
    triangles = []
    for index, point in enumerate(outline):
        triangles.extend(((cx, cy), point, outline[(index + 1) % count]))
    return tuple(triangles)


def rounded_rect_triangles(w: float, h: float, radius: float,
                           segments: int = _CORNER_SEGMENTS) -> tuple:
    """Return the rounded rectangle as a triangle list, in local pixel space."""
    return fan_triangles(rounded_rect_outline(w, h, radius, segments))


def circle_triangles(radius: float, segments: int = _CIRCLE_SEGMENTS) -> tuple:
    """Return a circle centred on the origin as a triangle list."""
    return fan_triangles(circle_outline(radius, segments))


def measure_text(text: str, size: float, metrics) -> tuple:
    """Return the size of ``text`` at a logical ``size``, as (width, height) in pixels.

    ``blf.dimensions`` answers without a GPU (see ``check_draw_api``), so a widget can
    ask for its intrinsic text size during a layout solve and this stays checkable on
    both targets.
    """
    blf.size(_FONT_ID, coords.logical_to_px(size, metrics.scale, metrics.base))
    return tuple(blf.dimensions(_FONT_ID, text))


class Canvas:
    """Immediate-mode 2D drawing surface for one region."""

    def __init__(self):
        self._batches = {}
        self._clips = []
        # The display metrics the draw pass runs under. A bare canvas is at scale one;
        # the scene overwrites this before it walks a solved tree.
        self.metrics = coords.DisplayMetrics(1.0, 1.0)
        # blf has no matrix, so text placement is tracked here as the translate stack.
        self._translations = [(0.0, 0.0)]

    def _batch(self, key, triangles):
        """Return the cached batch for a triangle list, building it on first use.

        The key is the geometry signature: everything that changes the vertices has to
        be part of it, or two shapes would share one batch.
        """
        batch = self._batches.get(key)
        if batch is None:
            compat.ensure_gpu_ready()
            fmt = gpu.types.GPUVertFormat()
            fmt.attr_add(id="pos", comp_type="F32", len=2, fetch_mode="FLOAT")
            buf = gpu.types.GPUVertBuf(len=len(triangles), format=fmt)
            buf.attr_fill(id="pos", data=triangles)
            batch = gpu.types.GPUBatch(type="TRIS", buf=buf)
            self._batches[key] = batch
        return batch

    def prepare(self) -> None:
        """Build the cached GPU resources now, so the first draw does not have to.

        Best effort: a surface can be enabled before a GPU context exists, in which
        case the first draw builds them instead. Only the unit quad is warmed, because
        the other shapes depend on sizes that are not known here.
        """
        try:
            self._batch(QUAD_BATCH_KEY, quad_triangles())
            shaders.uniform_color()
        except (RuntimeError, SystemError):
            return

    def push_transform(self, x, y, w, h):
        """Place subsequent drawing at (x, y) and size it by (w, h).

        The unit quad is drawn under this transform, so a rectangle costs no new
        geometry. Always pair with pop_transform().
        """
        gpu.matrix.push()
        gpu.matrix.translate((x, y))
        gpu.matrix.scale((w, h))
        previous = self._translations[-1]
        self._translations.append((previous[0] + x, previous[1] + y))

    def pop_transform(self):
        """Undo the last push_transform()."""
        gpu.matrix.pop()
        self._translations.pop()

    @property
    def translation(self):
        """The accumulated translate offset, which is what text placement uses."""
        return self._translations[-1]

    def push_clip(self, x, y, w, h):
        """Clip subsequent drawing to a rectangle. Pair with pop_clip().

        `gpu.state.scissor_set` only records the rectangle; the test itself has to be
        switched on separately, or nothing is clipped.
        """
        self._clips.append(gpu.state.scissor_get())
        gpu.state.scissor_set(int(x), int(y), int(w), int(h))
        gpu.state.scissor_test_set(True)

    def pop_clip(self):
        """Undo the last push_clip(), restoring the scissor that was in force."""
        previous = self._clips.pop()
        if self._clips:
            gpu.state.scissor_set(*previous)
        else:
            gpu.state.scissor_test_set(False)

    def shape(self, key, triangles, x, y, w, h, color):
        """Fill a triangle list defined in a unit box, scaled into (x, y, w, h).

        The key is the geometry signature: whatever changes the vertices has to be part
        of it, or two shapes would share one batch. Pass ``w = h = 1`` to draw geometry
        that is already in pixels.
        """
        batch = self._batch(key, triangles)
        shader = shaders.uniform_color()
        self.push_transform(x, y, w, h)
        try:
            shader.bind()
            shader.uniform_float("color", color)
            batch.draw(shader)
        finally:
            self.pop_transform()

    def rect(self, x, y, w, h, color):
        """Fill an axis-aligned rectangle with a solid color."""
        self.shape(QUAD_BATCH_KEY, quad_triangles(), x, y, w, h, color)

    def rounded_rect(self, x, y, w, h, radius, color):
        """Fill a rectangle with rounded corners. Geometry is cached by shape.

        The geometry is built at its real size and drawn unscaled, because scaling one
        unit shape would stretch a round corner into an ellipse.
        """
        self.shape(("round", w, h, radius), rounded_rect_triangles(w, h, radius),
                   x, y, 1.0, 1.0, color)

    def circle(self, cx, cy, radius, color):
        """Fill a circle with a solid color. Geometry is cached by radius."""
        self.shape(("circle", radius), circle_triangles(radius), cx, cy, 1.0, 1.0, color)

    def text(self, x, y, text, size, color, align=None):
        """Draw a text label, sized from a logical ``size`` and optionally aligned.

        ``blf`` has no matrix, so the label is placed from the translate stack and sized
        through the display metrics; it does not scale with a transform that scales.
        ``align`` is ``None``/``"left"``, ``"center"`` or ``"right"``.
        """
        if align not in (None, "left", "center", "right"):
            raise ValueError(f"align must be None, 'left', 'center' or 'right', got {align!r}")
        width, _ = measure_text(text, size, self.metrics)
        if align == "center":
            x -= width / 2.0
        elif align == "right":
            x -= width
        origin_x, origin_y = self.translation
        blf.size(_FONT_ID, coords.logical_to_px(size, self.metrics.scale, self.metrics.base))
        blf.color(_FONT_ID, color[0], color[1], color[2], color[3])
        blf.position(_FONT_ID, origin_x + x, origin_y + y, 0.0)
        blf.draw(_FONT_ID, text)


