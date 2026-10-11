"""Record what the draw layer can reach, per target, before M3 relies on it.

M3 needs shapes, text and (later) textures, so this is the recorded answer to "what
exists on each target, headless?" — the same question `check_gpu.py` answered for M1,
and the evidence the M3 plan is built on.

Two findings it pins:

- `blf` measurement is **not** GPU-bound: `blf.size` and `blf.dimensions` answer on both
  targets in background, so text metrics are checkable everywhere and text needs no
  version branch. Only `blf.draw` needs the GPU.
- `LINE_UNIFORM_COLOR` and `2D_IMAGE` **do not resolve** on a GPU-reachable 5.2, so a line
  is tessellated into triangles rather than drawn by a line shader. The check makes that
  an observed fact: if a later Blender brings the shader back, this fails on purpose so
  the design is revisited instead of quietly switched.

Everything GPU-bound is gated by `checkkit.gpu_reachable()` and records a skip on 4.2.
"""

import blf

from checkkit import banner, check, finish, gpu_reachable, skip

banner()

# -- text: measurement answers without a GPU, drawing does not ---------------

check("blf.size is defined", callable(getattr(blf, "size", None)))
check("blf.dimensions is defined", callable(getattr(blf, "dimensions", None)))
check("blf.draw is defined", callable(getattr(blf, "draw", None)))

try:
    blf.size(0, 12)
    short = blf.dimensions(0, "Ab")
    longer = blf.dimensions(0, "AbAb")
    ok = (isinstance(short, tuple) and len(short) == 2 and short[0] > 0 and short[1] > 0
          and longer[0] > short[0])
    check("blf measures text without a GPU", ok, f"short={short!r} longer={longer!r}")
except Exception as exc:
    check("blf measures text without a GPU", False, f"{type(exc).__name__}: {exc}")


def resolves(module, name):
    """Whether a builtin shader name resolves, without raising."""
    try:
        return type(module.shader.from_builtin(name)).__name__
    except Exception:
        return None


gpu = gpu_reachable()
if gpu is None:
    skip("this background build cannot reach the GPU, so the shader, buffer and texture probes stay unverified here")
else:
    gpu.init()

    for name in ("UNIFORM_COLOR", "IMAGE_COLOR", "POINT_UNIFORM_COLOR"):
        kind = resolves(gpu, name)
        check(f"builtin shader {name} resolves", kind == "GPUShader", repr(kind))

    absent = {
        "LINE_UNIFORM_COLOR": "a line is tessellated into triangles",
        "2D_IMAGE": "a texture is drawn through IMAGE_COLOR",
    }
    for name, note in absent.items():
        kind = resolves(gpu, name)
        check(
            f"builtin shader {name} stays unavailable ({note})",
            kind is None,
            f"it resolves again as {kind!r}; revisit the M3 design before using it",
        )

    import numpy

    fmt = gpu.types.GPUVertFormat()
    fmt.attr_add(id="pos", comp_type="F32", len=2, fetch_mode="FLOAT")
    try:
        buf = gpu.types.GPUVertBuf(len=6, format=fmt)
        buf.attr_fill(id="pos", data=numpy.zeros((6, 2), dtype="f"))
        check("a numpy array fills a vertex buffer", True)
    except Exception as exc:
        check("a numpy array fills a vertex buffer", False, f"{type(exc).__name__}: {exc}")

    try:
        texture = gpu.types.GPUTexture((4, 4))
        check("a GPUTexture builds", type(texture).__name__ == "GPUTexture", type(texture).__name__)
    except Exception as exc:
        check("a GPUTexture builds", False, f"{type(exc).__name__}: {exc}")

finish("draw api")
