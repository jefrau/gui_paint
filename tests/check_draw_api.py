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
from mathutils import Matrix

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


def _glyph_span(module, translate=(0.0, 0.0), scale=(1.0, 1.0)):
    """Render one glyph into an offscreen under translate*scale; return its x-span.

    Returns None when nothing was painted. This is how the check measured that `blf`
    honours the GPU matrix: a label placed at a local point is moved by the transform,
    so a canvas must not also add the offset itself.
    """
    width = height = 96
    offscreen = module.types.GPUOffScreen(width, height)
    with offscreen.bind():
        module.state.viewport_set(0, 0, width, height)
        module.matrix.push_projection()
        module.matrix.load_projection_matrix(Matrix((
            (2.0 / width, 0.0, 0.0, -1.0),
            (0.0, 2.0 / height, 0.0, -1.0),
            (0.0, 0.0, 1.0, 0.0),
            (0.0, 0.0, 0.0, 1.0),
        )))
        offscreen.texture_color.clear(format="FLOAT", value=(0.0, 0.0, 0.0, 1.0))
        blf.size(0, 18)
        blf.color(0, 1.0, 1.0, 1.0, 1.0)
        module.matrix.load_identity()
        module.matrix.translate(translate)
        module.matrix.scale(scale)
        blf.position(0, 2.0, 10.0, 0.0)
        blf.draw(0, "H")
        module.matrix.pop_projection()
    rows = offscreen.texture_color.read().to_list()
    offscreen.free()
    lit = [x for x in range(width) for y in range(height) if sum(rows[y][x][:3]) > 30]
    return (min(lit), max(lit)) if lit else None


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

    # blf and the GPU matrix: the fact a text primitive's placement depends on.
    plain = _glyph_span(gpu)
    moved = _glyph_span(gpu, translate=(30.0, 0.0))
    scaled = _glyph_span(gpu, scale=(2.0, 2.0))
    check("blf paints into an offscreen, so its placement can be measured",
          plain is not None, "no ink found")
    if plain and moved:
        check("blf honours the matrix translation",
              abs((moved[0] - plain[0]) - 30) <= 1, f"{plain} moved to {moved}")
    if plain and scaled:
        check("blf honours the matrix scale",
              (scaled[1] - scaled[0]) >= 2 * (plain[1] - plain[0]) - 2,
              f"{plain} scaled to {scaled}")

finish("draw api")
