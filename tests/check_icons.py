"""Verify the icon registry and the vector tessellation.

The geometry is pure data, so it is checked on both targets. Drawing is observed through
a recorder canvas that stands in for `Canvas.shape`, which keeps the whole check off the
GPU while still pinning the key, the box and the colour a draw passes down.
"""

from checkkit import banner, check, finish

banner()

try:
    from gui_paint_modules import icons
except Exception as exc:
    icons = None
    check("icons imports", False, f"{type(exc).__name__}: {exc}")
else:
    check("icons imports", True)

Icon = getattr(icons, "Icon", None) if icons is not None else None
check("Icon is defined", isinstance(Icon, type))

BUILTIN = ("select", "grab", "move")


class _RecorderCanvas:
    """Stands in for Canvas, recording the shape call an icon makes."""

    def __init__(self):
        self.calls = []

    def shape(self, key, triangles, x, y, w, h, color):
        self.calls.append((key, triangles, x, y, w, h, color))


def _raises_value_error(call) -> bool:
    try:
        call()
    except ValueError:
        return True
    except Exception:
        return False
    return False


if isinstance(Icon, type):
    for name in BUILTIN:
        icon = Icon.named(name)
        check(f"{name} resolves to an Icon", isinstance(icon, Icon))
        check(f"{name} keeps its name", icon.name == name, repr(icon.name))
        check(f"{name} returns the same icon each time", Icon.named(name) is icon)
        triangles = tuple(tuple(point) for point in icon.triangles)
        check(f"{name} tessellates into whole triangles",
              len(triangles) % 3 == 0 and len(triangles) > 0, str(len(triangles)))
        check(f"{name} stays inside the unit box",
              all(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 for x, y in triangles))

    check("grab is one polygon", len(Icon.named("grab").triangles) == 3 * 4,
          str(len(Icon.named("grab").triangles)))
    check("move is two convex bars", len(Icon.named("move").triangles) == 3 * 8,
          str(len(Icon.named("move").triangles)))

    check("an unknown name raises", _raises_value_error(lambda: Icon.named("nope")))

    icon = Icon.named("select")
    recorder = _RecorderCanvas()
    icon.draw(recorder, 3.0, 4.0, 12.0, 12.0, (1.0, 1.0, 1.0, 1.0))
    check("draw calls the canvas once", len(recorder.calls) == 1, str(len(recorder.calls)))
    if recorder.calls:
        key, triangles, x, y, w, h, color = recorder.calls[0]
        check("the shape is keyed by the icon name", key == ("icon", "select"), repr(key))
        check("the box is passed through", (x, y, w, h) == (3.0, 4.0, 12.0, 12.0),
              repr((x, y, w, h)))
        check("the colour is passed through", color == (1.0, 1.0, 1.0, 1.0), repr(color))
        check("the icon geometry reaches the canvas", triangles == icon.triangles)

finish("icons")
