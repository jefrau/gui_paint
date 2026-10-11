"""Canvas — the immediate-mode 2D drawing surface for one region.

Owns the shared shader handles, the batch cache and the transform/clip stacks.
Nothing here may create a shader, do file I/O or allocate in a draw call.

The primitives land in task M1.4; the shader handles are created once per process
and cached in task M1.3.
"""
