# gui_paint — usage

A practical guide to building UI with `gui_paint_modules`. It assumes the three concepts
below and defers the design rationale to `ARCHITECTURE.md`, which is the contract.

## The three concepts

| Concept | What it is |
|---------|------------|
| **Surface** | *Where* the UI lives: a Blender editor region. Owns the draw registration and, if interactive, the input routing. |
| **Scene** | *What* is drawn: a tree of nodes, with layout, transforms, z-order and hit-testing. |
| **Node** | *One element* in the tree: a panel, button, label, or a bare container. |

You build a `Scene` out of `Node`s, hand it to a `Surface`, and call `enable(area)`. Both
loops — draw and input — read the same solved scene.

```python
import bpy

from .gui_paint_modules import Anchor, Panel, Scene, Surface, VBox

scene = Scene(root=Panel(layout=VBox(gap=2), anchor=Anchor.bottom_left(margin=8)))
surface = Surface(space_type="SpaceView3D", interactive=True)
surface.scene = scene
surface.enable(bpy.context.area)
```

## Building a tree

### Containers and children

Any `Node` can hold children. `Panel` is a `Node` with a rounded background; a bare `Node`
draws nothing and is useful as a root or a group.

```python
from .gui_paint_modules import Node, Panel

panel = Panel()
panel.add(Node())               # add() re-parents and returns the child
panel.remove(panel.children[0])
root = Node(children=[panel])   # or pass children to the constructor
```

### Layout

A parent arranges its children through its **layout policy**, which is plain data, not a
node. Children with an `anchor` leave the flow.

```python
from .gui_paint_modules import HBox, VBox

VBox(gap=2, padding=3, align="start")  # stacks children along the vertical axis
HBox(gap=2, padding=3, align="center") # stacks them left to right
```

`align` places a child on the cross axis: `"start"`, `"center"`, `"end"` or `"stretch"`.

### Size policies

A child asks for a size with `Size`:

```python
from .gui_paint_modules import Size

Size.auto()          # the natural (content) size — the default
Size.fixed(20)       # an exact size, in logical units
Size.fill()          # whatever the parent's flow has left
Size.percent(0.5)    # half of the parent's content box
```

All sizes and margins are in **logical units**, converted to pixels once during the solve
(see *Coordinates and DPI*).

### Anchors

A node with an `anchor` is placed inside its parent's content box, outside the parent's flow.

```python
from .gui_paint_modules import Anchor

Anchor.bottom_left(margin=8)
Anchor.top_right(margin=4)
Anchor.center()
# also: top_left, top, bottom, left, right, bottom_right
```

### Widgets

| Widget | What it is |
|--------|------------|
| `Label(text="", size=12, color=(1,1,1,1))` | A line of text, sized from its own measurement. |
| `Button(label="", icon=None, on_click=None, size=Size.auto())` | A rounded background, an icon and a label; fires `on_click` on release inside. |
| `Panel(color=(0.16,0.16,0.16,0.9), radius=4)` | A rounded background that also arranges its children. |
| `Menu(...)` / `MenuItem(...)` | A transient popup, see *Menus*. |

```python
from .gui_paint_modules import Button, Icon, Label

Label("Ready", size=10)
Button(label="Grab", icon=Icon.named("grab"), on_click=grab)
```

### Icons

Icons resolve by name and draw through the canvas. Built-ins: `select`, `grab`, `move`. An
unknown name raises `ValueError` at build time, so a typo is caught early.

```python
from .gui_paint_modules import Icon
Button(label="Select", icon=Icon.named("select"))
```

## Showing it: the Surface

```python
surface = Surface(space_type="SpaceView3D", region_type="WINDOW", interactive=False)
```

- `space_type` is a Blender space **class name** (`"SpaceView3D"`, `"SpaceTimeline"`,
  `"SpaceGraphEditor"`, …). With `region_type="WINDOW"` the UI draws over the editor.
- `enable(area)` registers one draw callback for that space type and draws only in the area
  the surface was opened in; `disable()` removes everything — not drawn, not live.
- `surface.draw` is an optional extra callback; it runs after the scene, with the `Canvas`.

```python
surface.draw = lambda canvas: canvas.text(8, 8, "hello", 12, (1, 1, 1, 1))
```

Both `enable()` and `disable()` ask the area to repaint, so an overlay never stays invisible
waiting for an unrelated redraw.

## Input

Set `interactive=True` and the surface routes hover and clicks to its widgets. A `Button`
handles hover and press feedback, and fires `on_click` when the pointer is released **inside**
its rectangle; a drag that leaves it cancels.

```python
Button(label="Select", on_click=select_all)
```

One **router per window** serves every interactive surface in it, and one modal operator owns
the events. An event goes to the newest surface whose region holds the pointer. Anything that
is not a left-button press/release or a mouse move — the keyboard included — passes straight
through, so Blender keeps working. You never import the input layer; it is wired by `Surface`.

A button's handler runs inside the router's modal, which has **no area and no region**, so a
bare `bpy.ops` call that needs a 3D view fails its poll (*"context is incorrect"*). To run an
operator from a button, wrap it in a context override that points at the surface's area — the
toolbar example in `examples/toolbar_addon/` shows the shape.

## Menus

A menu is a transient popup a surface opens over its own area. While it is open it owns the
pointer: a click on a row runs the row's action and closes it, a click outside closes it, and
both are consumed.

```python
from .gui_paint_modules import Anchor, Menu, MenuItem

def on_choose(label):
    print("chose", label)

menu = Menu(
    items=[MenuItem(label="Select All", on_click=lambda: on_choose("Select All")),
           MenuItem(label="Grab", on_click=lambda: on_choose("Grab"))],
    popup_anchor=Anchor.bottom_left(margin=12),
)

toolbar.open_menu(menu)          # returns the menu's surface; closes any previous one
```

`Surface.open_menu(menu)` enables a new interactive surface for the menu and wires
`menu.on_dismiss` to close it. Selecting a row dismisses automatically. There is no keyboard
or ESC handling: the library never takes focus (see the contract's D4).

## Coordinates and DPI

- Nodes store **logical units**; the solve converts them once. The one conversion point is
  `coords.logical_to_px(value, ui_scale, base_factor)`.
- A solved `node.rect` is in **pixels**, relative to the parent's content box; the root's is
  relative to the region (origin at its bottom-left, y up).
- `Scene.hit_test(x, y)` takes a **region-local** point and returns the deepest node under it.

```python
from .gui_paint_modules import coords

coords.logical_to_px(20, 1.0, 1.0)   # 20 logical units at scale 1
coords.current_metrics()             # the DisplayMetrics of the running Blender
```

## Custom nodes

Subclass `Node` and override the seams you need:

```python
from .gui_paint_modules import coords, Node

class Dot(Node):
    def measure(self, metrics):
        # intrinsic size in pixels, so Size.auto() works
        size = coords.logical_to_px(8, metrics.scale, metrics.base)
        return (size, size)

    def draw(self, canvas):
        canvas.circle(self.rect[2] / 2, self.rect[3] / 2, self.rect[2] / 2,
                      (1.0, 0.5, 0.0, 1.0))
```

`measure(metrics)` is called during the solve; `draw(canvas)` during the draw pass and must
not read font metrics or create GPU resources. `set_hover(hot)` and `set_pressed(pressed)`
are the interaction hooks the router drives.

## Dynamic updates

Mutating the tree marks the scene dirty automatically, so the next draw re-solves it — no
manual invalidation.

```python
label.text = "Working…"     # re-solves the layout: text is measured
button.label = "Done"       # re-solves too
label.color = (1, 0, 0, 1)  # look-only, does NOT re-solve
```

Widget content that changes the measured size (`Label.text`, `Label.font_size`, `Button.label`,
`Button.icon`) invalidates the layout; look-only changes (colors, hover/press flags) do not.

## Manual test scripts

The interactive scripts under `tests/` are the live acceptance steps. Run one from the repo
root on either LTS, e.g.:

```sh
/opt/blender/blender-5.2.2-linux-x64/blender --python tests/manual_m4.py
```

- `manual_m1.py` toggles a rectangle.
- `manual_m2.py` draws the scene/layout tree; `probe(x, y)` hit-tests a region-local point.
- `manual_m3.py` draws the widget toolbar.
- `manual_m4.py` draws an interactive toolbar (hover and click).
- `manual_m5.py` opens a menu from a button.

From Blender's Python console, `import manual_m4; manual_m4.stop()` tears it down.

## Current limitations

Not in the library yet, and deliberately deferred until a consumer needs them:

- Editable text and keyboard input (D4 keeps text to labels).
- A scroll container, an external icon sheet / atlas.
- `Canvas.line`, `dashed_line` and `image`; region culling in the draw walk.
- A JSON authoring loader (`Spec` + `spec_json`); the Node API is the primary authoring path.

See `ARCHITECTURE.md`'s "Open questions" and "Performance and redraw" for the recorded
reasons.
