"""The input layer: turning mouse events into node interactions.

This package holds the router that runs while an interactive surface is enabled, and the
normalizer that decides which raw Blender events it acts on. It imports no package code —
the router reaches a surface and its scene by the shape they expose — and ``surface`` is the
only module that imports it back.
"""
