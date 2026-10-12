"""A portable, config-driven toolbar built with gui_paint_modules.

This is an example host, not part of the library. It shows the whole shape of a real addon:
the library draws an interactive toolbar over a 3D viewport, and every button comes from a
JSON config a user can edit by hand, export to another machine and import back. A button runs
a Blender operator **by name**, so the config travels where a Python callable would not.

A real addon copies `gui_paint_modules/` into its own package (see the library's README); this
example reaches into the repository instead, so its copy of the library can never drift.
"""

import os
import sys

import bpy
from bpy_extras.io_utils import ExportHelper, ImportHelper

# Reach the library, which lives at the repository root (a real addon would copy the folder).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from gui_paint_modules import Anchor, Button, Icon, Node, Panel, Scene, Surface, VBox

from . import config as toolconfig

bl_info = {
    "name": "gui_paint toolbar example",
    "author": "gui_paint",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "3D Viewport > Sidebar (N) > Toolbar, and a toolbar panel bottom-left",
    "description": "A portable, config-driven toolbar built with gui_paint_modules",
    "category": "Interface",
}

# The example's live state: the active config and the surface drawing it.
_STATE = {"config": None, "surface": None, "area": None}


# -- config storage ---------------------------------------------------------


def config_path():
    """The user config file: a portable JSON in Blender's user config folder."""
    folder = bpy.utils.user_resource("CONFIG", path="toolbar_addon", create=True)
    return os.path.join(folder, "tools.json")


def load_config():
    """The active config: the user's file when it exists, else the shipped default.

    A file that does not parse is reported and ignored, so a broken edit never stops the
    addon from coming up; the user can fix it and reload.
    """
    path = config_path()
    if os.path.exists(path):
        try:
            return toolconfig.ToolbarConfig.load(path)
        except (toolconfig.ConfigError, OSError) as exc:
            print(f"toolbar example: ignoring {path}: {exc}")
    return toolconfig.default_config()


# -- the library scene ------------------------------------------------------


def _icon(tool):
    """The tool's icon object, or None when it has none."""
    return Icon.named(tool.icon) if tool.icon else None


def _overrides():
    """A 3D-viewport context, so an operator runs there instead of in the router's modal.

    A library button calls back from inside the input router's window-level modal, which has
    no area and no region, so an operator such as ``object.select_all`` fails its poll with
    "context is incorrect". Overriding the context with the viewport the toolbar is armed in
    is what lets the operator run. Measured: ``bpy.context.temp_override`` accepts
    ``window``/``area``/``region``/``space_data`` on both 4.2 and 5.2.
    """
    overrides = {}
    window = bpy.context.window
    if window is not None:
        overrides["window"] = window
    area = _STATE.get("area")
    if area is not None:
        try:
            region = next((item for item in area.regions if item.type == "WINDOW"), None)
            overrides["area"] = area
            overrides["space_data"] = area.spaces.active
            if region is not None:
                overrides["region"] = region
        except ReferenceError:
            pass  # the area was closed; run with whatever context is left
    return overrides


def _runner(tool):
    """A click handler that runs the tool's operator in the viewport context.

    A failure is reported, not raised: an operator whose poll still refuses (no active
    object, wrong mode) must not take the UI down.
    """
    def run():
        try:
            with bpy.context.temp_override(**_overrides()):
                tool.invoke()
        except Exception as exc:
            print(f"toolbar example: {tool.label!r}: {type(exc).__name__}: {exc}")
    return run


def build_scene(cfg):
    """The library Scene for a config: a bottom-left panel with one button per tool."""
    panel = Panel(layout=VBox(gap=2, padding=3), anchor=Anchor.bottom_left(margin=12))
    for tool in cfg.buttons:
        panel.add(Button(label=tool.label, icon=_icon(tool), on_click=_runner(tool)))
    root = Node()
    root.add(panel)
    return Scene(root)


# -- the surface lifecycle --------------------------------------------------


def _view3d_area():
    """The first 3D viewport area in the current screen, or None."""
    screen = bpy.context.screen
    if screen is None:
        return None
    return next((area for area in screen.areas if area.type == "VIEW_3D"), None)


def _shutdown_surface():
    """Take the toolbar down, if it is up."""
    surface = _STATE["surface"]
    if surface is not None:
        surface.disable()
        _STATE["surface"] = None


def _arm():
    """Enable the toolbar over the first 3D viewport, retrying until one exists."""
    area = _view3d_area()
    if area is None:
        return 1.0
    _shutdown_surface()
    surface = Surface("SpaceView3D", interactive=True)
    surface.scene = build_scene(_STATE["config"])
    surface.enable(area)
    _STATE["surface"] = surface
    _STATE["area"] = area
    print("toolbar example: toolbar armed in the 3D viewport")
    return None


def refresh():
    """Rebuild the toolbar from the active config, after an import or a reload."""
    area = _STATE["area"]
    if _STATE["surface"] is None or area is None:
        return
    _shutdown_surface()
    surface = Surface("SpaceView3D", interactive=True)
    surface.scene = build_scene(_STATE["config"])
    surface.enable(area)
    _STATE["surface"] = surface


# -- Blender operators ------------------------------------------------------


class TOOLBAR_OT_export(bpy.types.Operator, ExportHelper):
    """Write the current toolbar to a portable JSON file."""

    bl_idname = "toolbar.export_config"
    bl_label = "Export toolbar"
    bl_description = "Save the current tools to a JSON file you can copy to another machine"
    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        _STATE["config"].save(self.filepath)
        self.report({"INFO"}, f"exported {len(_STATE['config'].buttons)} tools")
        return {"FINISHED"}


class TOOLBAR_OT_import(bpy.types.Operator, ImportHelper):
    """Load a toolbar from a JSON file, replacing the current one."""

    bl_idname = "toolbar.import_config"
    bl_label = "Import toolbar"
    bl_description = "Replace the current tools with the ones in a JSON file"
    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        try:
            loaded = toolconfig.ToolbarConfig.load(self.filepath)
        except (toolconfig.ConfigError, OSError) as exc:
            self.report({"ERROR"}, f"could not import: {exc}")
            return {"CANCELLED"}
        _STATE["config"] = loaded
        refresh()
        self.report({"INFO"}, f"imported {len(loaded.buttons)} tools")
        return {"FINISHED"}


class TOOLBAR_OT_reload(bpy.types.Operator):
    """Reload the toolbar from the user config file."""

    bl_idname = "toolbar.reload_config"
    bl_label = "Reload toolbar"
    bl_description = "Re-read the config file after editing it by hand"

    def execute(self, context):
        _STATE["config"] = load_config()
        refresh()
        self.report({"INFO"}, f"loaded {len(_STATE['config'].buttons)} tools")
        return {"FINISHED"}


class TOOLBAR_OT_reset(bpy.types.Operator):
    """Reset the toolbar to the tools that ship with the example."""

    bl_idname = "toolbar.reset_config"
    bl_label = "Reset to default tools"
    bl_description = "Replace the current tools with the ones that ship with the example"

    def execute(self, context):
        _STATE["config"] = toolconfig.default_config()
        refresh()
        self.report({"INFO"}, "reset to the default tools")
        return {"FINISHED"}


class TOOLBAR_PT_panel(bpy.types.Panel):
    """A sidebar panel that exports, imports, reloads and resets the toolbar config."""

    bl_idname = "TOOLBAR_PT_panel"
    bl_label = "gui_paint toolbar"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Toolbar"

    def draw(self, context):
        cfg = _STATE["config"]
        layout = self.layout
        layout.label(text=cfg.name if cfg is not None else "Toolbar")
        layout.label(text=f"{len(cfg.buttons) if cfg is not None else 0} tools")
        layout.operator(TOOLBAR_OT_export.bl_idname)
        layout.operator(TOOLBAR_OT_import.bl_idname)
        layout.separator()
        layout.operator(TOOLBAR_OT_reload.bl_idname)
        layout.operator(TOOLBAR_OT_reset.bl_idname)


_CLASSES = (
    TOOLBAR_OT_export, TOOLBAR_OT_import, TOOLBAR_OT_reload, TOOLBAR_OT_reset, TOOLBAR_PT_panel,
)


def register():
    """Register the operators and the panel, then arm the toolbar over a viewport."""
    _STATE["config"] = load_config()
    path = config_path()
    if not os.path.exists(path):
        # Leave an editable file on disk from the first run.
        _STATE["config"].save(path)
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    if not bpy.app.timers.is_registered(_arm):
        bpy.app.timers.register(_arm, first_interval=1.0)


def unregister():
    """Take the toolbar down and unregister everything."""
    if bpy.app.timers.is_registered(_arm):
        bpy.app.timers.unregister(_arm)
    _shutdown_surface()
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
    _STATE["config"] = None
