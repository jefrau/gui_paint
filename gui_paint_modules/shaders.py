"""Built-in shader handles, created once per process and reused.

Creating a shader inside a draw call is never allowed, so the handle is built on
first use and kept for the life of the process.

Only one kind is needed so far, which is why the cache is a single slot rather than a
table keyed by kind; the second kind is what should turn it into a table.
"""

import gpu

from . import compat

_uniform_color = None


def uniform_color():
    """Return the handle that fills flat-coloured shapes."""
    global _uniform_color
    if _uniform_color is None:
        compat.ensure_gpu_ready()
        _uniform_color = gpu.shader.from_builtin("UNIFORM_COLOR")
    return _uniform_color
