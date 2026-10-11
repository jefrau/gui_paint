"""Verify the rounded rect and the circle: their outlines, and the fill path.

The outlines are pure data, so the geometry runs on both targets. The fill path is
GPU-bound, so it is gated by `checkkit.gpu_reachable()` and records a skip on 4.2. The
corner test renders through Canvas and reads a pixel back: with a radius of half the box,
the sharp corner must keep the background, which only holds if the corner is really cut
and not merely drawn over.
"""

import math

from mathutils import Matrix

from checkkit import banner, check, finish, gpu_reachable, skip

from gui_paint_modules import canvas

banner()

for name in ("rounded_rect_outline", "circle_outline", "rounded_rect_triangles", "circle_triangles"):
    check(f"canvas.{name} is defined", callable(getattr(canvas, name, None)))

Canvas = getattr(canvas, "Canvas", None)
for name in ("rounded_rect", "circle"):
    check(f"Canvas.{name} is defined", callable(getattr(Canvas, name, None)))

rounded_outline = getattr(canvas, "rounded_rect_outline", None)
if callable(rounded_outline):
    sharp = rounded_outline(10.0, 6.0, 0.0)
    check("a zero radius is the four corners",
          tuple(map(tuple, sharp)) == ((0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)),
          str(tuple(map(tuple, sharp))))

    segments = 4
    outline = tuple(map(tuple, rounded_outline(10.0, 6.0, 2.0, segments)))
    check("a rounded outline has one arc per corner",
          len(outline) == 4 * (segments + 1), str(len(outline)))
    check("the outline stays inside the box",
          all(0.0 <= x <= 10.0 and 0.0 <= y <= 6.0 for x, y in outline))
    check("the sharp corner is gone", (0.0, 0.0) not in outline)
    bottom_left = outline[3 * (segments + 1):]
    check("the bottom-left arc keeps the radius",
          all(abs(math.hypot(x - 2.0, y - 2.0) - 2.0) < 1e-9 for x, y in bottom_left),
          str(bottom_left))
    check("a radius larger than the short side is clamped",
          len(tuple(rounded_outline(10.0, 6.0, 99.0, segments))) == 4 * (segments + 1))

triangle_fn = getattr(canvas, "rounded_rect_triangles", None)
if callable(triangle_fn) and callable(rounded_outline):
    triangles = tuple(triangle_fn(10.0, 6.0, 2.0, segments))
    check("the rounded triangle list fans the outline",
          len(triangles) == 3 * len(tuple(rounded_outline(10.0, 6.0, 2.0, segments))),
          str(len(triangles)))

circle_outline = getattr(canvas, "circle_outline", None)
if callable(circle_outline):
    points = tuple(map(tuple, circle_outline(5.0, 32)))
    check("a circle has the requested segments", len(points) == 32, str(len(points)))
    check("every circle point sits on the radius",
          all(abs(math.hypot(x, y) - 5.0) < 1e-9 for x, y in points),
          str(points[:2]))

circle_triangles = getattr(canvas, "circle_triangles", None)
if callable(circle_triangles):
    check("the circle triangle list fans its outline",
          len(tuple(circle_triangles(5.0, 32))) == 3 * 32,
          str(len(tuple(circle_triangles(5.0, 32)))))

gpu = gpu_reachable()
if gpu is None:
    skip("this background build cannot reach the GPU, so the fill path stays unverified here")
elif isinstance(Canvas, type) and callable(getattr(Canvas, "rounded_rect", None)):
    gpu.init()
    drawn = Canvas()
    drawn.rounded_rect(0.0, 0.0, 20.0, 10.0, 3.0, (1.0, 0.0, 0.0, 1.0))
    drawn.rounded_rect(5.0, 5.0, 20.0, 10.0, 3.0, (0.0, 1.0, 0.0, 1.0))
    check("two draws of one shape reuse one batch", len(drawn._batches) == 1, f"{sorted(map(str, drawn._batches))}")
    drawn.rounded_rect(0.0, 0.0, 10.0, 10.0, 2.0, (0.0, 0.0, 1.0, 1.0))
    check("a different shape adds a second batch", len(drawn._batches) == 2, str(len(drawn._batches)))
    drawn.circle(0.0, 0.0, 4.0, (1.0, 1.0, 1.0, 1.0))
    check("a circle caches its own batch", len(drawn._batches) == 3, str(len(drawn._batches)))

    # A shape is cached and built at whole pixels, so a fractional size and its rounded
    # twin must share both the key and the geometry they were built from.
    twisted = Canvas()
    twisted.rounded_rect(0.0, 0.0, 20.4, 10.4, 3.2, (1.0, 0.0, 0.0, 1.0))
    twisted.rounded_rect(9.0, 9.0, 20.0, 10.0, 3.0, (0.0, 1.0, 0.0, 1.0))
    check("a fractional size and its rounded twin share one batch",
          len(twisted._batches) == 1, f"{sorted(map(str, twisted._batches))}")
    twisted.circle(0.0, 0.0, 4.4, (1.0, 1.0, 1.0, 1.0))
    twisted.circle(0.0, 0.0, 4.0, (1.0, 1.0, 1.0, 1.0))
    check("a fractional radius and its rounded twin share one batch",
          len(twisted._batches) == 2, f"{sorted(map(str, twisted._batches))}")

    width = height = 16
    background = (1.0, 0.0, 0.0, 1.0)
    filled = (0.0, 1.0, 0.0, 1.0)
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
        shaped = Canvas()
        shaped.rounded_rect(0.0, 0.0, float(width), float(height), width / 2.0, filled)
        gpu.matrix.pop_projection()
    rows = offscreen.texture_color.read().to_list()
    offscreen.free()

    def sampled(x, y):
        """Return the readback pixel at (x, y) as an rgb triple rounded to 0..1."""
        return tuple(round(channel / 255.0, 3) for channel in rows[y][x][:3])

    corner = sampled(0, 0)
    middle = sampled(width // 2, height // 2)
    check("the corner is really cut, not drawn over",
          corner == background[:3] and middle == filled[:3],
          f"corner={corner} middle={middle}")

finish("shapes")
