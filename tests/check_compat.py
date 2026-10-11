"""Verify the version/capability shims and the shader handle cache.

Two invariants are checked:

- no package module outside `compat.py` reads the running Blender version;
- the shader cache hands back the same handle instead of building a second one.

The cache smoke test can only run where a background process reaches the GPU, so 4.2
records a skip there instead of a failure.
"""

from checkkit import REPO, banner, check, finish, skip

from gui_paint_modules import compat, shaders

VERSION_MARKERS = (
    "bpy.app.version",
    "bpy.app.version_string",
    "bpy.app.version_cycle",
    "bpy.app.version_file",
)

banner()

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
    text = path.read_text(encoding="utf-8")
    found = [marker for marker in VERSION_MARKERS if marker in text]
    if found:
        offenders.append(f"{path.name}:{found}")
check("no module outside compat.py reads the Blender version", not offenders, str(offenders))

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
            skip(f"shader cache unreachable in this background build ({type(exc).__name__})")
    else:
        check("shader cache returns one handle", first is second)
        check(
            "shader handle is a GPUShader",
            type(first).__name__ == "GPUShader",
            type(first).__name__,
        )

finish("compat")
