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
