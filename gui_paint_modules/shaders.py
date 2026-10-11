"""Built-in shader handles, created once per process and reused.

Creating a shader inside a draw call is never allowed. The handle cache lands in
task M1.3.
"""
