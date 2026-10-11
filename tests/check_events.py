"""Verify the input event normalizer: which raw events the router acts on, and how.

`events.py` is the one place that decides what the router listens for. The check feeds it
small stand-ins that carry exactly the fields `check_modal_api` pinned on both targets, so
this tests our policy without a live event and without faking a Blender fact.
"""

from checkkit import banner, check, finish

from gui_paint_modules.input.events import MOVE, PRESS, RELEASE, classify


class _Event:
    """Stand-in carrying exactly the fields the normalizer reads.

    ``mouse_region_x/y`` is (-1, -1) to mirror a window-level modal, which has no region;
    the normalizer must use the window point instead.
    """

    def __init__(self, type, value="NOTHING", x=0.0, y=0.0):
        self.type = type
        self.value = value
        self.mouse_x = x
        self.mouse_y = y
        self.mouse_region_x = -1
        self.mouse_region_y = -1


banner()

check("the three kinds are distinct", len({MOVE, PRESS, RELEASE}) == 3)

moved = classify(_Event("MOUSEMOVE", x=10.0, y=20.0))
check("a mouse move classifies as MOVE with its window point",
      moved == (MOVE, 10.0, 20.0), repr(moved))

pressed = classify(_Event("LEFTMOUSE", "PRESS", x=1.0, y=2.0))
check("a left press classifies as PRESS", pressed == (PRESS, 1.0, 2.0), repr(pressed))

released = classify(_Event("LEFTMOUSE", "RELEASE", x=3.0, y=4.0))
check("a left release classifies as RELEASE", released == (RELEASE, 3.0, 4.0), repr(released))

# The router tracks a press and a release itself, so a lone CLICK must not be trusted and
# must not carry action. Everything the router does not use passes through untouched.
for label, event in (
    ("a left CLICK alone", _Event("LEFTMOUSE", "CLICK")),
    ("a left double click", _Event("LEFTMOUSE", "DOUBLE_CLICK")),
    ("the right button", _Event("RIGHTMOUSE", "PRESS")),
    ("the middle button", _Event("MIDDLEMOUSE", "PRESS")),
    ("a wheel tick", _Event("WHEELUPMOUSE", "PRESS")),
    ("a key press", _Event("SPACE", "PRESS")),
    ("a key release", _Event("RET", "RELEASE")),
):
    check(f"{label} classifies as None", classify(event) is None)

finish("events")
