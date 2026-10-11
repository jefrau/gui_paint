"""Version-gated shims for the supported Blender versions (4.2 LTS and 5.2 LTS).

Every ``bpy.app.version`` branch in the package belongs in this module and nowhere
else, so the rest of the code reads as if there were only one version. The M1 shims
land in task M1.3.
"""
