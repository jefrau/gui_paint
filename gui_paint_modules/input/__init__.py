"""The input layer: turning mouse events into node interactions.

This package holds the router that runs while an interactive surface is enabled, and the
normalizer that decides which raw Blender events it acts on. It imports the scene tree and
the widgets, and is imported by ``surface``; nothing lower in the stack imports it back.
"""
