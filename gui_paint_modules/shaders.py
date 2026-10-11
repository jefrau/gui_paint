"""Built-in shader handles, created once per process and reused.

Creating a shader inside a draw call is never allowed, so each handle is built on
first use and kept for the life of the process.
"""

import gpu

from . import compat

_handles = {}


def _cached(kind: str):
    """Return the process-wide handle for a built-in shader kind, building it once."""
    handle = _handles.get(kind)
    if handle is None:
        compat.ensure_gpu_ready()
        handle = gpu.shader.from_builtin(kind)
        _handles[kind] = handle
    return handle


def uniform_color():
    """Return the handle that fills flat-coloured shapes."""
    return _cached("UNIFORM_COLOR")
