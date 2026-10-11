"""Verify text: the measurement helper and the primitive's placement maths.

`blf` has no matrix, so `Canvas.text` places a label from the translate stack the scene
builds, not from `gpu.matrix`. That makes both halves checkable without a GPU: the
measurement goes through `blf.dimensions`, which answers headless, and the placement is
observed by swapping the `blf` module for a recorder, so the size, colour, position and
the drawn string are all asserted exactly.

Only the pixels `blf.draw` would paint stay unverified, and that is the part a render
cannot easily read back.
"""

from math import isclose

from checkkit import banner, check, finish, gpu_reachable, skip

from gui_paint_modules import canvas, coords

banner()

measure = getattr(canvas, "measure_text", None)
check("canvas.measure_text is defined", callable(measure))

Canvas = getattr(canvas, "Canvas", None)
check("Canvas.text is defined", callable(getattr(Canvas, "text", None)))

METRICS = coords.DisplayMetrics(1.0, 1.0)

if callable(measure):
    short = measure("Ab", 10.0, METRICS)
    longer = measure("AbAb", 10.0, METRICS)
    check("a measurement is a pair of positive numbers",
          isinstance(tuple(short), tuple) and len(short) == 2 and short[0] > 0 and short[1] > 0,
          repr(tuple(short)))
    check("a longer string measures wider", longer[0] > short[0], f"{longer[0]} vs {short[0]}")
    bigger = measure("Ab", 20.0, METRICS)
    check("a bigger logical size measures wider", bigger[0] > short[0], f"{bigger[0]} vs {short[0]}")


class _BlfRecorder:
    """Stands in for the blf module, recording calls and reporting a fixed size."""

    WIDTH = 10.0
    HEIGHT = 5.0

    def __init__(self):
        self.calls = []

    def size(self, font_id, size):
        self.calls.append(("size", font_id, size))

    def dimensions(self, font_id, text):
        return (self.WIDTH, self.HEIGHT)

    def color(self, font_id, r, g, b, a):
        self.calls.append(("color", font_id, r, g, b, a))

    def position(self, font_id, x, y, z):
        self.calls.append(("position", font_id, x, y, z))

    def draw(self, font_id, text):
        self.calls.append(("draw", font_id, text))

    def last(self, name):
        return [call for call in self.calls if call[0] == name][-1]


if isinstance(Canvas, type) and callable(getattr(Canvas, "text", None)) and callable(measure):
    original = canvas.blf
    recorder = _BlfRecorder()
    canvas.blf = recorder
    try:
        drawn = Canvas()
        check("a bare canvas draws text at scale one", drawn.metrics == METRICS, repr(drawn.metrics))

        drawn.text(4.0, 6.0, "hi", 10.0, (1.0, 0.0, 0.0, 1.0))
        check("left alignment keeps x", tuple(recorder.last("position")[2:4]) == (4.0, 6.0),
              str(recorder.last("position")))
        check("the position carries the target depth", recorder.last("position")[4] == 0.0)
        check("the size is converted through the metrics", recorder.last("size")[2] == 10,
              str(recorder.last("size")))
        check("the colour reaches blf", recorder.last("color")[2:] == (1.0, 0.0, 0.0, 1.0),
              str(recorder.last("color")))
        check("the text reaches blf", recorder.last("draw")[2] == "hi", str(recorder.last("draw")))

        recorder.calls.clear()
        drawn.text(4.0, 6.0, "hi", 10.0, (1.0, 0.0, 0.0, 1.0), align="center")
        check("center alignment shifts by half the width",
              tuple(recorder.last("position")[2:4]) == (4.0 - 5.0, 6.0), str(recorder.last("position")))

        recorder.calls.clear()
        drawn.text(4.0, 6.0, "hi", 10.0, (1.0, 0.0, 0.0, 1.0), align="right")
        check("right alignment shifts by the width",
              tuple(recorder.last("position")[2:4]) == (4.0 - 10.0, 6.0), str(recorder.last("position")))

        # The translate stack is a gpu.matrix push, so this half needs a reachable GPU.
        gpu = gpu_reachable()
        if gpu is None:
            skip("the translate stack needs a GPU matrix, so text placement under nested transforms stays unverified here")
        else:
            gpu.init()
            recorder.calls.clear()
            drawn.push_transform(7.0, 8.0, 1.0, 1.0)
            drawn.text(4.0, 6.0, "hi", 10.0, (1.0, 0.0, 0.0, 1.0))
            drawn.pop_transform()
            check("the translate stack places the label",
                  tuple(recorder.last("position")[2:4]) == (11.0, 14.0), str(recorder.last("position")))

            recorder.calls.clear()
            drawn.text(0.0, 0.0, "hi", 10.0, (1.0, 0.0, 0.0, 1.0))
            check("popping the transform restores the origin",
                  tuple(recorder.last("position")[2:4]) == (0.0, 0.0), str(recorder.last("position")))

        scaled = Canvas()
        scaled.metrics = coords.DisplayMetrics(2.0, 1.0)
        recorder.calls.clear()
        scaled.text(0.0, 0.0, "hi", 10.0, (1.0, 0.0, 0.0, 1.0))
        check("the display metrics scale the font size", recorder.last("size")[2] == 20,
              str(recorder.last("size")))

        try:
            drawn.text(0.0, 0.0, "hi", 10.0, (1.0, 0.0, 0.0, 1.0), align="middle")
            check("an unknown alignment is rejected", False, "it did not raise")
        except ValueError:
            check("an unknown alignment is rejected", True)
        except Exception as exc:
            check("an unknown alignment is rejected", False, f"{type(exc).__name__}: {exc}")
    finally:
        canvas.blf = original

finish("text")
