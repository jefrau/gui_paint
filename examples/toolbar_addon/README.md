# Portable toolbar — example addon

An example that shows how to use `gui_paint_modules` to build a **config-driven toolbar**
whose tools live in a portable JSON file. A user can edit the tools, export the file to
another machine and import it back, instead of keeping the setup trapped in a `.blend`.

It is an example host, not part of the library, and it lives outside `gui_paint_modules/`.

## What it shows

- Building a library `Scene` from data: a `Panel` in a `VBox` of `Button`s.
- An interactive `Surface` drawn over a 3D viewport, so a click runs a tool.
- A **portable config**: each button references a Blender operator by name
  (`bpy.ops.<category>.<operation>`) and its parameters — never a Python callable — so the
  same file works on any install.
- Export / import / reload / reset through a small sidebar panel.

## Run it

From the repository root, in an **interactive** Blender:

```sh
/opt/blender/blender-5.2.2-linux-x64/blender --python-expr \
  "import sys; sys.path.insert(0, '$PWD/examples'); import addon_utils; addon_utils.enable('toolbar_addon')"
```

Open a 3D viewport: the toolbar appears in the bottom-left after a moment, and the addon's
panel is in the N-sidebar, category **Toolbar**.

> A real addon **copies** `gui_paint_modules/` into its own package and imports it with a
> relative import (see the library's README). This example reaches into the repository
> instead — `examples/` is on `sys.path` and the addon finds the repository root for the
> library — so its copy can never drift. That is an example convenience, not the delivery
> model.

## The config file

The addon keeps the active tools in Blender's user config folder:

```
<blender config>/toolbar_addon/tools.json
```

It looks like this:

```json
{
  "format": 1,
  "name": "Default viewport tools",
  "buttons": [
    { "label": "Select All", "op": "object.select_all", "icon": "select",
      "params": { "action": "SELECT" } },
    { "label": "Edit Mode", "op": "object.mode_set", "icon": "grab",
      "params": { "mode": "EDIT" } }
  ]
}
```

- `format` — the file version; an unknown one is rejected, so the format can change safely.
- `op` — a `bpy.ops` idname; a name that is not a real operator is rejected on load.
- `icon` — one of the library's icons: `select`, `grab`, `move`. Blender's native icons are
  not available yet; an atlas / native icons are a deferred need.
- `params` — the keyword arguments for the operator, as JSON values.

Edit the file by hand and click **Reload toolbar**, or use **Import** / **Export** to move it
between machines.

### Choosing a tool's operator

A tool runs its operator the moment you click it, so the operator must **finish on its own**.
`object.select_all`, `object.mode_set` and `object.shade_smooth` do; an **interactive**
operator such as `transform.translate` (Grab), `transform.rotate` or `transform.scale` waits
for mouse input, so a toolbar button cannot complete it and the click looks like it did
nothing. Give a transform operator an explicit value only if you know it runs
non-interactively in your context; otherwise leave it out of a toolbar.

The shipped default tools are all immediate, and the config check asserts they resolve.

### Running the tool: the context override

The library calls a button's handler from inside its input router's **window-level modal**,
which has no area and no region. An operator that needs a 3D view — nearly every `object.*`
op — then fails its poll with *"context is incorrect"*. The example runs each tool inside a
`bpy.context.temp_override(window, area, region, space_data)` that points at the viewport the
toolbar is armed in, which is what makes the operator run. Any host that runs operators from a
library button needs this; a tool that only changes the config does not.

## A word on safety

A config file can name any operator, so **a config you did not write is code you chose to
run**. This example never evaluates anything (no `eval`), rejects malformed files and resolves
an operator by name only — but it does run whatever the file names. Treat a shared config as
you would a script.

## Files

| File | Role |
|---|---|
| `__init__.py` | The addon: `bl_info`, the operators, the sidebar panel, the surface lifecycle. |
| `config.py` | The portable config: the `ToolButton` record, load/save, validation, operator resolution. |
| `README.md` | This file. |

The config logic is covered headless by `tests/check_example_config.py`.
