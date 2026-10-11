"""Verify the input event normalizer: which raw events the router acts on, and how.

`events.py` is the one place that decides what the router listens for. The check feeds it
small stand-ins that carry exactly the fields `check_modal_api` pinned on both targets, so
this tests our policy without a live event and without faking a Blender fact.
"""

from checkkit import StubEvent, banner, check, finish

from gui_paint_modules.input.events import MOVE, PRESS, RELEASE, classify


banner()

classified = (
    classify(StubEvent("MOUSEMOVE", x=5.0, y=5.0)),
    classify(StubEvent("LEFTMOUSE", "PRESS", x=5.0, y=5.0)),
    classify(StubEvent("LEFTMOUSE", "RELEASE", x=5.0, y=5.0)),
)
check("a move, a press and a release classify to three distinct kinds",
      len({item[0] for item in classified}) == 3, str(classified))

moved = classify(StubEvent("MOUSEMOVE", x=10.0, y=20.0))
check("a mouse move classifies as MOVE with its window point",
      moved == (MOVE, 10.0, 20.0), repr(moved))

pressed = classify(StubEvent("LEFTMOUSE", "PRESS", x=1.0, y=2.0))
check("a left press classifies as PRESS", pressed == (PRESS, 1.0, 2.0), repr(pressed))

released = classify(StubEvent("LEFTMOUSE", "RELEASE", x=3.0, y=4.0))
check("a left release classifies as RELEASE", released == (RELEASE, 3.0, 4.0), repr(released))

# The router tracks a press and a release itself, so a lone CLICK must not be trusted and
# must not carry action. Everything the router does not use passes through untouched.
for label, event in (
    ("a left CLICK alone", StubEvent("LEFTMOUSE", "CLICK")),
    ("a left double click", StubEvent("LEFTMOUSE", "DOUBLE_CLICK")),
    ("the right button", StubEvent("RIGHTMOUSE", "PRESS")),
    ("the middle button", StubEvent("MIDDLEMOUSE", "PRESS")),
    ("a wheel tick", StubEvent("WHEELUPMOUSE", "PRESS")),
    ("a key press", StubEvent("SPACE", "PRESS")),
    ("a key release", StubEvent("RET", "RELEASE")),
):
    check(f"{label} classifies as None", classify(event) is None)

finish("events")
