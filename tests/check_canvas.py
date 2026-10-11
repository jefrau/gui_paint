"""Verify Canvas: the pure rect geometry, and the drawing path where the host allows it.

The unit quad is pure data, so the geometry assertions run on both targets even though
4.2 cannot reach the GPU from a background process. Everything GPU-bound — the rect
draw, the transform stack and the clip stack — is gated by `checkkit.gpu_reachable()`
and records a skip on 4.2.

`gpu.state` exposes no getter for whether the scissor *test* is on, only for its
rectangle, so the clip stack is verified by rendering through Canvas and reading a
pixel back: the pixel outside the clip keeps the cleared background, the pixel inside
shows the clipped colour. Dropping `gpu.state.scissor_test_set(True)` from
`Canvas.push_clip` leaves both pixels the clipped colour and fails the check.
"""

from mathutils import Matrix

from checkkit import banner, check, finish, gpu_reachable, skip

from gui_paint_modules import canvas

banner()

triangles = getattr(canvas, "quad_triangles", None)
check("canvas.quad_triangles is defined", callable(triangles))
if callable(triangles):
    expected = (
        (0.0, 0.0), (1.0, 0.0), (1.0, 1.0),
        (0.0, 0.0), (1.0, 1.0), (0.0, 1.0),
    )
    got = tuple(map(tuple, triangles()))
    check("the unit quad is six triangle vertices", got == expected, str(got))

key = getattr(canvas, "QUAD_BATCH_KEY", None)
check("QUAD_BATCH_KEY is a non-empty string", isinstance(key, str) and bool(key), repr(key))

Canvas = getattr(canvas, "Canvas", None)
check("canvas.Canvas is defined", isinstance(Canvas, type))
for method in ("rect", "push_transform", "pop_transform", "push_clip", "pop_clip"):
    check(f"Canvas.{method} is defined", callable(getattr(Canvas, method, None)))

gpu = gpu_reachable()
if gpu is None:
    skip("this background build cannot reach the GPU, so the draw path and both stacks stay unverified here")
elif isinstance(Canvas, type) and callable(getattr(Canvas, "rect", None)):
    gpu.init()
    drawn = Canvas()

    drawn.rect(1.0, 2.0, 3.0, 4.0, (1.0, 0.0, 0.0, 1.0))
    drawn.rect(5.0, 6.0, 7.0, 8.0, (0.0, 1.0, 0.0, 1.0))
    check("two rects reuse one cached batch", len(drawn._batches) == 1, f"{sorted(drawn._batches)}")

    before = gpu.matrix.get_model_view_matrix()
    drawn.push_transform(10.0, 20.0, 2.0, 3.0)
    moved = gpu.matrix.get_model_view_matrix()
    drawn.pop_transform()
    restored = gpu.matrix.get_model_view_matrix()
    check("push_transform moves the matrix", moved != before)
    check(
        "push_transform translates by (x, y)",
        tuple(round(value, 3) for value in moved.translation)[:2] == (10.0, 20.0),
        str(tuple(round(value, 3) for value in moved.translation)),
    )
    check(
        "push_transform scales by (w, h)",
        tuple(round(value, 3) for value in moved.to_scale())[:2] == (2.0, 3.0),
        str(tuple(round(value, 3) for value in moved.to_scale())),
    )
    check("pop_transform restores the matrix", restored == before)

    drawn.push_clip(1, 2, 30, 40)
    check("push_clip sets the scissor", gpu.state.scissor_get() == (1, 2, 30, 40), str(gpu.state.scissor_get()))
    drawn.push_clip(5, 6, 7, 8)
    check("a nested push_clip narrows the scissor", gpu.state.scissor_get() == (5, 6, 7, 8), str(gpu.state.scissor_get()))
    drawn.pop_clip()
    check("pop_clip restores the outer scissor", gpu.state.scissor_get() == (1, 2, 30, 40), str(gpu.state.scissor_get()))
    drawn.pop_clip()
    check(
        "popping the base clip does not collapse the scissor",
        gpu.state.scissor_get() != (0, 0, 0, 0),
        str(gpu.state.scissor_get()),
    )

    # scissor_get only reports the rectangle scissor_set recorded, so it cannot see a
    # dead clip stack. Render through Canvas and read the pixels back instead.
    width, height = 16, 16
    background = (1.0, 0.0, 0.0, 1.0)
    clipped = (0.0, 1.0, 0.0, 1.0)
    offscreen = gpu.types.GPUOffScreen(width, height)
    with offscreen.bind():
        gpu.state.viewport_set(0, 0, width, height)
        gpu.matrix.push_projection()
        gpu.matrix.load_projection_matrix(Matrix((
            (2.0 / width, 0.0, 0.0, -1.0),
            (0.0, 2.0 / height, 0.0, -1.0),
            (0.0, 0.0, 1.0, 0.0),
            (0.0, 0.0, 0.0, 1.0),
        )))
        gpu.matrix.load_identity()
        gpu.state.scissor_test_set(False)
        offscreen.texture_color.clear(format="FLOAT", value=background)
        clipped_canvas = Canvas()
        clipped_canvas.push_clip(0, 0, width // 2, height)
        clipped_canvas.rect(0.0, 0.0, float(width), float(height), clipped)
        clipped_canvas.pop_clip()
        gpu.matrix.pop_projection()
    rows = offscreen.texture_color.read().to_list()
    offscreen.free()

    def sampled(x, y):
        """Return the readback pixel at (x, y) as an rgba triple rounded to 0..1."""
        return tuple(round(channel / 255.0, 3) for channel in rows[y][x][:3])

    inside = sampled(2, height // 2)
    outside = sampled(width - 2, height // 2)
    check(
        "push_clip clips the render: outside is background, inside is the clipped colour",
        inside == clipped[:3] and outside == background[:3],
        f"inside={inside} outside={outside}",
    )

finish("canvas")
