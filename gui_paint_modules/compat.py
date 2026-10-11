"""Version- and capability-gated shims for the supported Blender versions.

Every reaction to the running Blender version in the package belongs in this module
and nowhere else, so the rest of the code reads as if there were only one version.

M1 needs one shim. Blender 5.2 requires the GPU module to be initialized before a
background process can build a shader or a batch; 4.2 exposes no ``gpu.init`` and is
already drawing by the time its draw callback runs. ``tests/check_gpu.py`` is what
established that difference.
"""

import gpu

_ready = False


def ensure_gpu_ready() -> None:
    """Initialize the GPU module when the running Blender requires it.

    Cheap and safe to call repeatedly: versions without ``gpu.init`` are left
    untouched, and the initialized state is remembered for the life of the process.
    """
    global _ready
    if _ready:
        return
    init = getattr(gpu, "init", None)
    if init is not None:
        init()
    _ready = True
