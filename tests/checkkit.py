"""Shared plumbing for the gui_paint check scripts.

`tests/run.sh` puts this directory and the repo root on the import path before it
hands a script to Blender, so a check imports only what it needs from here.

Three decisions live in this module because more than one check repeats them: the
ok/FAIL report format, the failure and skip bookkeeping that sets the process exit
status, and the rule that bad input raises `ValueError` rather than another exception.
"""

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

failures = []
skips = []


def banner() -> None:
    """Print which Blender is running, so one log tells the targets apart."""
    import bpy

    print(f"  -- {bpy.app.version_string}")


def check(label: str, condition: bool, detail: str = "") -> None:
    """Record one contract assertion and print its outcome."""
    if condition:
        print(f"  ok   {label}")
        return
    failures.append(label)
    print(f"  FAIL {label}{': ' + detail if detail else ''}")


def skip(reason: str) -> None:
    """Record an environment limitation that is not a failure."""
    skips.append(reason)


class RecorderCanvas:
    """Canvas stand-in that records the draw primitives it is handed.

    A check that watches a widget or a scene draw uses this instead of a real Canvas, so
    the check needs no GPU and runs on both targets. It carries a default metrics object
    with the two numbers a draw reads; a solved scene replaces it with the real one. The
    library is deliberately not imported here, so this module stays pure plumbing.
    """

    class _DefaultMetrics:
        scale = 1.0
        base = 1.0

    def __init__(self):
        self.calls = []
        self.metrics = self._DefaultMetrics()

    def prepare(self):
        """No-op: Surface.enable warms a real canvas, and there is nothing to warm here."""

    def __getattr__(self, name):
        """Record any other primitive as (name, *args) instead of drawing it."""
        def record(*args, **kwargs):
            self.calls.append((name,) + args)
            return None
        return record


class StubArea:
    """Stand-in for a Blender area: identity and repaint requests, nothing else."""

    def __init__(self, pointer):
        self._pointer = pointer
        self.redraws = 0

    def as_pointer(self):
        return self._pointer

    def tag_redraw(self):
        self.redraws += 1


class StubSpace:
    """Stand-in for a Blender space type, recording handler add and remove calls."""

    def __init__(self):
        self.added = []
        self.removed = []

    def draw_handler_add(self, callback, args, region_type, draw_type):
        self.added.append((callback, args, region_type, draw_type))
        return ("handle", len(self.added))

    def draw_handler_remove(self, handle, region_type):
        self.removed.append((handle, region_type))


class StubEvent:
    """Stand-in for a Blender event carrying the fields the normalizer reads.

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


class StubSurface:
    """Stand-in for a surface: a solved scene, a region rect and a redraw counter.

    ``window_rect`` returns the region in window pixels with the origin at (0, 0), so a
    window point equals the region-local point; assign an instance attribute to move it.
    """

    def __init__(self, scene):
        self.scene = scene
        self.redraws = 0

    def window_rect(self):
        """The surface's region in window pixels, spanning (0, 0) to (200, 200)."""
        return (0.0, 0.0, 200.0, 200.0)

    def _tag_redraw(self):
        """Count one repaint request from the router."""
        self.redraws += 1


class StubWindow:
    """Stand-in for a Blender window: an identity for the router registry."""

    def __init__(self, pointer):
        self._pointer = pointer

    def as_pointer(self):
        return self._pointer


def raises_value_error(call) -> bool:
    """Whether a zero-argument call raises ValueError, and nothing else.

    Shared by the checks that pin input validation, so the decision "a bad argument
    raises ValueError, not TypeError or SystemExit" lives in one place.
    """
    try:
        call()
    except ValueError:
        return True
    except Exception:
        return False
    return False


def gpu_reachable():
    """Return the `gpu` module where a background process can use it, else None.

    Blender 4.2 exposes no ``gpu.init`` and refuses every GPU call from a background
    process, so this is the gate the GPU-dependent checks share.
    """
    try:
        import gpu
    except Exception:
        return None
    return gpu if hasattr(gpu, "init") else None


def finish(kind: str) -> None:
    """Print the skips, then exit non-zero if anything failed."""
    if skips:
        print("  skip " + "; ".join(skips))
    if failures:
        raise SystemExit(f"{kind}: {len(failures)} check(s) failed: {failures}")
    print(f"{kind}: all checks passed")
