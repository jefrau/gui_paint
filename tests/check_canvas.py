"""Verify Canvas: the pure rect geometry, and the drawing path where the host allows it.

The unit quad is pure data, so the geometry assertions run on both targets even though
4.2 cannot reach the GPU from a background process. Everything GPU-bound — the rect
draw, the transform stack and the clip stack — is gated by `checkkit.gpu_reachable()`
and records a skip on 4.2.

`gpu.state` exposes no getter for whether the scissor *test* is on, only for its
rectangle, so the base pop is asserted not to collapse the rectangle rather than to
disable the test. The manual step covers the rest.
"""

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

    base = gpu.state.scissor_get()
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
    check("the base pop left the scissor where it was", gpu.state.scissor_get() == base or base == (0, 0, 0, 0))

finish("canvas")
