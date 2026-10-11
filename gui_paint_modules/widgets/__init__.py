"""Widgets — thin Node composites with a look.

A widget declares its own appearance and intrinsic size and draws through the Canvas
primitives. Input stays out: a Button carries its handler and its hot/pressed flags for
M4's router to drive. Importing this package registers nothing and touches no Blender
state.
"""

from .button import Button
from .label import Label
from .panel import Panel

__all__ = ["Button", "Label", "Panel"]
