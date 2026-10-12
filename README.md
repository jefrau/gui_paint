# gui_paint

A small, self-contained Python library for drawing and interacting with 2D UI inside any
Blender editor — viewport, timeline, graph, sequencer, node editor, and so on.

The library renders everything itself: it tessellates its own shapes, draws its own text
through `blf`, and owns its widgets. There is no dependency beyond Blender and the `numpy`
that ships with it, no manifest, and nothing registers at import time.

## Status

Milestones M1–M6 of the design contract are implemented and audited: surface, canvas and
coordinates; scene graph, layout and hit-testing; widgets and icons; the input router; menus;
and the compatibility/performance pass. The check suite is green on Blender 4.2 LTS and
5.2 LTS (23 checks per target). Blender 4.2 cannot reach the GPU from a background process,
so the GPU-dependent checks record a skip there instead of failing.

## Requirements

- Blender 4.2 LTS or 5.2 LTS (and newer).
- `numpy` — Blender ships it; there is no other dependency.

## Install

The delivery model is "copy the folder", not "install an extension":

1. Copy `gui_paint_modules/` into your addon package.
2. Import the public API from the copy's root, under whatever name the copy has:

   ```python
   from .gui_paint_modules import (
       Surface, Scene, Node, Panel, Label, Button, Menu, MenuItem, Icon,
       Size, Anchor, VBox, HBox,
   )
   ```

Nothing registers at import time; your addon decides when to enable and disable a surface.
Inside the package every import is relative, so the folder can be renamed or moved freely.

## Quick start

A clickable toolbar anchored to the bottom-left of the 3D viewport:

```python
import bpy
from .gui_paint_modules import Anchor, Button, Icon, Panel, Scene, Surface, VBox


def select_all():
    bpy.ops.object.select_all(action="SELECT")


scene = Scene(root=Panel(
    layout=VBox(gap=2, padding=3),
    anchor=Anchor.bottom_left(margin=8),
    children=[
        Button(label="Select", icon=Icon.named("select"), on_click=select_all),
        Button(label="Grab", icon=Icon.named("grab"), on_click=lambda: None),
    ],
))

toolbar = Surface(space_type="SpaceView3D", region_type="WINDOW", interactive=True)
toolbar.scene = scene
toolbar.enable(bpy.context.area)

# later, to take it down cleanly:
toolbar.disable()
```

`interactive=True` routes hover and clicks to the widgets: a click on a `Button` fires its
`on_click`. See `USAGE.md` for menus, custom nodes and everything else.

## Documentation

- **`ARCHITECTURE.md`** — the design contract. The single source of truth for how the
  library is meant to work; read it before changing behaviour.
- **`USAGE.md`** — a how-to: concepts, building a tree, layout, icons, input, menus, custom
  nodes, and the manual test scripts.

## Examples

`examples/toolbar_addon/` is a runnable addon that builds a config-driven toolbar with the
library: its tools live in a portable JSON a user can edit and move between machines. See its
[README](examples/toolbar_addon/README.md).

## Running the checks

```sh
tests/run.sh                       # every tests/check_*.py on both targets
tests/run.sh tests/check_menu.py   # only the given checks
```

- `BLENDER_42` / `BLENDER_52` override the Blender binaries.
- `CHECK_TIMEOUT` (default 300s) bounds each run.

## Repository layout

| Path | Role |
|---|---|
| `gui_paint_modules/` | The library. This is the copyable unit. |
| `examples/` | Runnable host examples; `toolbar_addon/` is the portable-toolbar one. |
| `ARCHITECTURE.md` | The design contract. |
| `USAGE.md` | How-to guide. |
| `AGENTS.md` | How to work in this repository. |
| `tests/` | The check suite and the manual scripts. |

## License

GPL-3.0 — see [`LICENSE`](LICENSE).
