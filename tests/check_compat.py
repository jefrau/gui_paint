"""Verify the version/capability shims and the per-process shader handle cache.

Two invariants are checked:

- `compat` is the only package module that reacts to the running Blender version;
- the shader cache hands back one handle per kind, and never builds a second one.

The cache smoke test can only run where a background process reaches the GPU. The
probe in `check_gpu.py` shows 4.2 refuses every GPU call headless while 5.2 works
after `gpu.init()`, so 4.2 records a skip here instead of a failure.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import bpy

from gui_paint_modules import compat, shaders

failures = []
skips = []


def check(label: str, condition: bool, detail: str = "") -> None:
    """Record one contract assertion and print its outcome."""
    if condition:
        print(f"  ok   {label}")
        return
    failures.append(label)
    print(f"  FAIL {label}{': ' + detail if detail else ''}")


print(f"  -- {bpy.app.version_string}")

ensure_ready = getattr(compat, "ensure_gpu_ready", None)
check("compat.ensure_gpu_ready is defined", callable(ensure_ready))

if callable(ensure_ready):
    try:
        ensure_ready()
        ensure_ready()
        check("ensure_gpu_ready is safe to call twice", True)
    except Exception as exc:
        check("ensure_gpu_ready is safe to call twice", False, f"{type(exc).__name__}: {exc}")

offenders = []
for path in sorted((REPO / "gui_paint_modules").rglob("*.py")):
    if path.name == "compat.py":
        continue
    if "bpy.app.version" in path.read_text(encoding="utf-8"):
        offenders.append(path.name)
check("version branching stays in compat.py", not offenders, str(offenders))

uniform_color = getattr(shaders, "uniform_color", None)
check("shaders.uniform_color is defined", callable(uniform_color))
if callable(uniform_color):
    try:
        first = uniform_color()
        second = uniform_color()
    except Exception as exc:
        import gpu

        if hasattr(gpu, "init"):
            check("shader cache builds a handle", False, f"{type(exc).__name__}: {exc}")
        else:
            skips.append(f"shader cache unreachable in this background build ({type(exc).__name__})")
    else:
        check("shader cache returns one handle", first is second)
        check(
            "shader handle is a GPUShader",
            type(first).__name__ == "GPUShader",
            type(first).__name__,
        )

if skips:
    print("  skip " + "; ".join(skips))

if failures:
    raise SystemExit(f"compat: {len(failures)} check(s) failed: {failures}")
print("compat: all checks passed")
