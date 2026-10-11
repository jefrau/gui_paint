"""gui_paint — a self-contained library for drawing 2D UI inside any Blender editor.

The folder is the copyable unit: copy ``gui_paint_modules/`` into a host addon and
import the public surface from its root. Nothing here registers anything at import
time, and nothing here depends on anything beyond Blender and numpy.

The public surface grows per milestone; M1 exports ``Surface`` only.
"""

from .surface import Surface

__all__ = ["Surface"]
