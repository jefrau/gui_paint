"""Canvas — the immediate-mode 2D drawing surface for one region.

Owns the shared shader handles, the batch cache and the transform/clip stacks.
Nothing here may create a shader, do file I/O or allocate in a draw call.

A solid rectangle reuses one cached unit quad under a transform, so the geometry is
built once per canvas instead of once per rectangle. The unit quad carries its two
triangles as six vertices: task M1.4 probed Blender's indexed-batch constructor and
found it rejects the documented shape, while a plain triangle list is accepted.
"""

import gpu

from . import compat, shaders

QUAD_BATCH_KEY = "quad"


def quad_triangles() -> tuple:
    """Return the unit quad as six triangle vertices in the canonical space.

    Counter-clockwise from the origin: (0,0) (1,0) (1,1), then (0,0) (1,1) (0,1).
    """
    return (
        (0.0, 0.0), (1.0, 0.0), (1.0, 1.0),
        (0.0, 0.0), (1.0, 1.0), (0.0, 1.0),
    )


class Canvas:
    """Immediate-mode 2D drawing surface for one region."""

    def __init__(self):
        self._batches = {}
        self._clips = []

    def _quad_batch(self):
        """Return the cached unit-quad batch, building it on first use."""
        batch = self._batches.get(QUAD_BATCH_KEY)
        if batch is None:
            compat.ensure_gpu_ready()
            fmt = gpu.types.GPUVertFormat()
            fmt.attr_add(id="pos", comp_type="F32", len=2, fetch_mode="FLOAT")
            buf = gpu.types.GPUVertBuf(len=6, format=fmt)
            buf.attr_fill(id="pos", data=quad_triangles())
            batch = gpu.types.GPUBatch(type="TRIS", buf=buf)
            self._batches[QUAD_BATCH_KEY] = batch
        return batch

    def push_transform(self, x, y, w, h):
        """Place subsequent drawing at (x, y) and size it by (w, h).

        The unit quad is drawn under this transform, so a rectangle costs no new
        geometry. Always pair with pop_transform().
        """
        gpu.matrix.push()
        gpu.matrix.translate((x, y))
        gpu.matrix.scale((w, h))

    def pop_transform(self):
        """Undo the last push_transform()."""
        gpu.matrix.pop()

    def push_clip(self, x, y, w, h):
        """Clip subsequent drawing to a rectangle. Pair with pop_clip()."""
        self._clips.append(gpu.state.scissor_get())
        gpu.state.scissor_set(int(x), int(y), int(w), int(h))

    def pop_clip(self):
        """Undo the last push_clip(), restoring the scissor that was in force."""
        previous = self._clips.pop()
        if previous == (0, 0, 0, 0):
            gpu.state.scissor_test_set(False)
        else:
            gpu.state.scissor_set(*previous)

    def rect(self, x, y, w, h, color):
        """Fill an axis-aligned rectangle with a solid color."""
        batch = self._quad_batch()
        shader = shaders.uniform_color()
        self.push_transform(x, y, w, h)
        try:
            shader.bind()
            shader.uniform_float("color", color)
            batch.draw(shader)
        finally:
            self.pop_transform()
