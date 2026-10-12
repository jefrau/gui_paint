"""Verify the version/capability shims and the shader handle cache.

Three invariants are checked:

- no package module outside `compat.py` reads the running Blender version or build;
- no package module outside `compat.py` reaches the 5.2-only `gpu.init` capability, and
  `compat.py` is where that shim lives;
- the shader cache hands back the same handle instead of building a second one.

The cache smoke test can only run where a background process reaches the GPU, so 4.2
records a skip there instead of a failure.
"""

from checkkit import REPO, banner, check, finish, gpu_reachable, skip

from gui_paint_modules import compat, shaders

VERSION_MARKERS = (
    "bpy.app.version",
    "bpy.app.version_string",
    "bpy.app.version_cycle",
    "bpy.app.version_file",
    "bpy.app.build_",
)

# The 5.2-only capability the shim detects, in both spellings it can take: a direct call
# and the capability probe `compat.py` uses so it never compares version numbers.
CAPABILITY_MARKERS = ('gpu.init', 'getattr(gpu, "init"')

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
check("no module outside compat.py reads the Blender version or build", not offenders, str(offenders))

capability_offenders = []
for path in sorted((REPO / "gui_paint_modules").rglob("*.py")):
    if path.name == "compat.py":
        continue
    text = path.read_text(encoding="utf-8")
    found = [marker for marker in CAPABILITY_MARKERS if marker in text]
    if found:
        capability_offenders.append(f"{path.name}:{found}")
check("no module outside compat.py touches gpu.init", not capability_offenders, str(capability_offenders))

compat_source = (REPO / "gui_paint_modules" / "compat.py").read_text(encoding="utf-8")
check("compat.py owns the gpu.init capability shim",
      any(marker in compat_source for marker in CAPABILITY_MARKERS))

uniform_color = getattr(shaders, "uniform_color", None)
check("shaders.uniform_color is defined", callable(uniform_color))
if callable(uniform_color):
    if gpu_reachable() is None:
        skip("this background build cannot reach the GPU, so the shader cache stays unverified here")
    else:
        first = uniform_color()
        second = uniform_color()
        check("shader cache returns one handle", first is second)
        check(
            "shader handle is a GPUShader",
            type(first).__name__ == "GPUShader",
            type(first).__name__,
        )

finish("compat")
