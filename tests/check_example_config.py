"""Verify the example's portable tool config: round-trip, validation and resolution.

The config is pure data plus a Blender operator name, so this check runs headless on both
targets and needs no window. Resolving an operator reads `bpy.ops`, which exists in a
background process, so it is checked here rather than left to the live run.
"""

import tempfile
from pathlib import Path

import bpy

from checkkit import banner, check, finish, raises_value_error

banner()

try:
    from examples.toolbar_addon import config
except Exception as exc:
    config = None
    check("the example config imports", False, f"{type(exc).__name__}: {exc}")
else:
    check("the example config imports", True)

if config is not None:
    ToolButton = config.ToolButton
    ToolbarConfig = config.ToolbarConfig

    # -- one button's validation --------------------------------------------

    check("a button takes a label and an operator",
          ToolButton("Select All", "object.select_all").label == "Select All")

    check("a button needs a non-empty label",
          raises_value_error(lambda: ToolButton("", "object.select_all")))
    check("a button needs an operator idname",
          raises_value_error(lambda: ToolButton("X", "no_dot")))
    check("a button rejects an unknown icon",
          raises_value_error(lambda: ToolButton("X", "object.select_all", icon="nope")))
    check("a button rejects non-object params",
          raises_value_error(lambda: ToolButton("X", "object.select_all", params=[1, 2])))

    # -- round-trip ----------------------------------------------------------

    record = ToolButton("Mute", "sequencer.mute", icon="select", params={"unselected": False})
    check("a button round-trips through a dict",
          ToolButton.from_dict(record.to_dict()).to_dict() == record.to_dict(),
          str(record.to_dict()))

    default = config.default_config()
    check("the default config is valid and non-empty",
          isinstance(default, ToolbarConfig) and len(default.buttons) > 0)

    unresolved = []
    for tool in default.buttons:
        try:
            tool.resolve()
        except Exception as exc:
            unresolved.append(f"{tool.label}: {exc}")
    check("every default tool names a real operator", not unresolved, str(unresolved))

    reloaded = ToolbarConfig.from_json(default.to_json())
    check("a config round-trips through JSON unchanged",
          reloaded.to_dict() == default.to_dict(), reloaded.to_json())

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "tools.json"
        default.save(path)
        from_file = ToolbarConfig.load(path)
        check("a config round-trips through a file",
              from_file.to_dict() == default.to_dict(), str(path))
        check("the file is human-readable JSON",
              '"format"' in path.read_text(encoding="utf-8"))

    # -- validation failures fail loudly ------------------------------------

    check("an unknown format version is rejected",
          raises_value_error(lambda: ToolbarConfig.from_dict({"format": 99, "buttons": []})))
    check("a missing buttons list is rejected",
          raises_value_error(lambda: ToolbarConfig.from_dict({"format": config.FORMAT})))
    check("a button without an operator is rejected",
          raises_value_error(lambda: ToolbarConfig.from_dict(
              {"format": config.FORMAT, "buttons": [{"label": "X"}]})))
    check("malformed JSON is rejected",
          raises_value_error(lambda: ToolbarConfig.from_json("{ not json")))

    # -- operator resolution -------------------------------------------------

    op = ToolButton("Select All", "object.select_all").resolve()
    check("a real operator idname resolves to a bpy.ops entry", callable(op))
    check("an unknown operator is rejected",
          raises_value_error(lambda: ToolButton("X", "nope.nothing").resolve()))

    # -- the addon module: import-safe, and its shape ------------------------

    try:
        from examples.toolbar_addon import bl_info, build_scene, register, unregister
    except Exception as exc:
        check("the addon module imports", False, f"{type(exc).__name__}: {exc}")
    else:
        check("the addon module imports", True)
        check("the addon declares bl_info", isinstance(bl_info, dict) and bool(bl_info.get("name")))
        check("register and unregister are callable",
              callable(register) and callable(unregister))
        check("importing the addon registers nothing", "toolbar" not in dir(bpy.ops))

        scene = build_scene(default)
        panel = scene.root.children[0] if scene.root is not None and scene.root.children else None
        check("the addon builds a scene from a config", panel is not None)
        check("the scene has one button per tool",
              panel is not None and len(panel.children) == len(default.buttons),
              f"{None if panel is None else len(panel.children)} vs {len(default.buttons)}")

finish("example config")
