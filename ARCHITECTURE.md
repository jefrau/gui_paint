# gui_paint — Architecture

A small, self-contained library for drawing and interacting with 2D UI inside any
Blender editor (viewport, timeline, graph, sequencer, node editor, and so on).
Addons build a widget tree, attach it to an editor region, and get drawing, layout,
hit-testing, icons and mouse interaction. The library renders everything itself.

---

## Quick path

1. Read **Mental model** below to get the three core concepts.
2. Skim the **Decisions** table — it is the contract; everything else is detail.
3. Jump to the layer you need: Surface, Canvas, Scene/Layout, Widgets, Icons, Input.

---

## Mental model

Three concepts and two loops. If you remember only this section, you can navigate
the rest.

| Concept | What it is |
|---------|------------|
| **Surface** | *Where* the UI lives: a target editor region (space type + region type). Owns the draw registration and, if interactive, the input routing. |
| **Scene** | *What* is drawn: a tree of nodes with layout, transform, z-order and hit-testing. |
| **Node** | *One element* in the tree: a panel, button, label, icon, or a bare container. |

```
             enable()                       <- opt-in
                |
        +-------+-------------------------------+
        |             Surface                   |
        |                                       |
        |   draw loop  --->  Canvas  ---> GPU   |   paints every redraw
        |      ^                                |
        |      |                                |
        |   Scene (node tree)                   |   layout + z-order + hit-test
        |      ^                                |
        |      |                                |
        |   input loop <---  InputRouter        |   only while enabled
        |                   (modal)             |
        +---------------------------------------+
                |
             disable()                      <- gone: not drawn, not live
```

Both loops read the **same Scene**. Draw walks it back-to-front; input walks it
front-to-back. Layout is solved once, then reused by both until something changes.

---

## Decisions (the contract)

These are already settled. Treat them as constraints unless there is a strong reason
to revisit.

| # | Decision | Why |
|---|----------|-----|
| D1 | **Fully custom rendering.** Own widgets, own menus. No reliance on Blender's native widget drawing. | Full control over look and behavior; native menus cannot be laid out freely. |
| D2 | **Opt-in activation.** Nothing is registered until the user enables the UI; on disable it is removed. | Zero interference with Blender while off. No global hooks leaking into the session. |
| D3 | **Disabled = invisible and inert.** Not drawn, not interactive. | One state instead of many; no "half-alive" mode to reason about. |
| D4 | **Text is labels only.** No editable text fields. | Avoids keyboard focus and IME conflicts with Blender keymaps. |
| D5 | **Custom vector icons**, plus an optional external icon sheet loaded as a texture pack. | Icons must be drawable by us as GPU geometry or textures; no dependency on built-in icon APIs. |
| D6 | **Real layout engine**, not just manual offsets. | Declarative placement (stacks, anchors, padding, fill) instead of hand-computed coordinates per panel. |
| D7 | **Target: Blender 4.2 LTS and 5.2 LTS (and newer).** | A modern, narrow band keeps the compatibility layer small. |
| D8 | **One data model, two ways in**: the Node API in Python (primary) and an optional JSON loader that reads/writes the same model as a `Spec`. | Content is data; behavior is code. JSON is data-only, so behavior is referenced by name and resolved at runtime. See the authoring section. |
| D9 | **Local copy, not an extension.** The library ships by copying the `gui_paint_modules/` folder into a host addon, and stays relocatable under any parent package. | No manifest, no `bl_info`, no dependencies beyond Blender + numpy; the host drives registration. |

### Non-goals (out of scope, on purpose)

- Drawing in 3D space (world/screen positions of objects). This is UI-level only.
- Matching Blender's native widget appearance pixel for pixel.
- An embedded external GUI toolkit / separate OS window.
- Editable text input and rich text.

---

## Module layout

```
gui_paint_modules/
    __init__.py          public API re-exports
    surface.py           Surface: registration, enable/disable, area scoping
    canvas.py            Canvas: 2D primitives, shader reuse, clipping, batching
    shaders.py           built-in shader handles, created once per process
    coords.py            coordinate conversions and DPI scaling
    scene.py             Scene: node tree, reflow, z-order, hit-testing
    layout.py            Layout policies (VBox, HBox) and size/anchor values
    nodes.py             Node base class, Rect/Clip transforms
    widgets/
        __init__.py
        button.py        Button (label + icon + click)
        label.py         Label (static text)
        panel.py         Panel / container surface
        menu.py          Menu (transient, owns input while open)
        scroll.py        Scroll container (optional, uses clipping)
    icons/
        __init__.py      Icon registry and lookup
        vector.py        Path tessellation into cached GPU batches
        atlas.py         Texture atlas packing and lookup
    input/
        __init__.py
        router.py        InputRouter: modal lifecycle, dispatch, PASS_THROUGH rules
        events.py        Normalizes a raw event for the router
    spec.py              The serializable representation (Spec dataclasses)
    spec_json.py         Optional JSON loader/saver for the same representation
    compat.py            Version-gated shims (4.2 vs 4.5+ vs 5.x)
```

The `input/` package (router and events) exists as of M4; `widgets/menu.py`,
`widgets/scroll.py`, `icons/atlas.py`, `spec.py` and `spec_json.py` are still targets.

Design rule: lower layers (**canvas**, **coords**, **shaders**, **layout**, **nodes**,
**scene**) must not import higher layers. The dependency direction is always outward-in.

Relocatability (see D9): the folder is the copyable unit and must work under any
parent package. This splits into two import contexts:

- **Inside the package**: always relative (`from .canvas import ...`). Never
  `import gui_paint_modules` from within, so the folder can be renamed or moved.
- **Host code**: imports the public surface from the package root, under whatever
  name the copy was placed under (`from .gui_paint_modules import ...`). The root
  `__init__.py` re-exports the public API; hosts do not reach into submodules.

It registers nothing at import time and depends on nothing beyond Blender and numpy.

---

## Coordinate contract

Coordinate bugs are the most common failure in this kind of code. One contract, stated
once, enforced everywhere.

**Canonical space** = *region-local pixels, origin at the bottom-left of the region,
y pointing up.* This matches what Blender's draw callbacks, `blf` and `gpu` use.

Rules:

1. **Nodes store logical units**, never pixels. Conversion happens at draw/hit-test time.
2. **One scale function** converts logical units to pixels:
   `px = round(units * ui_scale * base_factor)`.
3. **Node rectangles are relative to their parent's content box**, not the region.
   Only the root is relative to the region.
4. **Only one conversion point** between this space and any other (window/screen/area).
   It lives in `coords.py` and nowhere else.
5. **Mouse events carry a window point, and the router converts it.** A window-level
   modal has no region, so Blender reports `mouse_region_x/y` as `(-1, -1)`; the coordinate
   that is always valid is `mouse_x`/`mouse_y`, in window pixels with a bottom-left origin.
   The router subtracts the surface's region origin (read from the live area) to reach the
   region-local point the scene was solved in. Both the `(-1, -1)` fact and the subtraction
   were measured on a live 5.2, not assumed.

```python
# coords.py (illustrative)

def logical_to_px(value, ui_scale, base_factor):
    """Convert a logical unit value to pixels for the current UI scale.
    Logical units keep layouts stable across DPI settings: base_factor carries
    the display's pixels per logical unit.
    """
    # Returns an int pixel value.
    return int(round(value * ui_scale * base_factor))


def region_rect(region):
    """Return the region rectangle in the canonical space.
    The origin is the region's bottom-left corner.
    """
    # Returns (x, y, width, height) in region-local pixels.
    return (0.0, 0.0, float(region.width), float(region.height))


def base_factor():
    """Return the display's extra pixels per logical unit (the HiDPI factor).

    One of the two readers of display scaling; everything else takes the factor
    as an argument and stays pure. The DPI ratio itself is `ui_scale`.
    """
    # pixel_size is already a ratio and defaults to 1.0.
    return float(bpy.context.preferences.system.pixel_size)
```

**Why not top-left / y-down?** Most UI toolkits use it, but it would force a flip on
every draw call and every event. Choosing the native space removes an entire class of
off-by-one and inverted-hitbox bugs.

---

## Surface layer

A `Surface` binds a Scene to an editor region and owns registration.

```python
class Surface:
    """Binds a Scene to an editor region and manages its lifecycle.

    Creating a Surface does nothing. Calling enable() registers drawing
    (and input, if interactive). Calling disable() removes everything.
    """

    def __init__(self, space_type, region_type="WINDOW", interactive=False):
        self.space_type = space_type
        self.region_type = region_type
        self.interactive = interactive
        self.scene = Scene()
        self._handle = None
        self._router = None
```

Registration model:

- Draw callbacks are registered **per space type**, at `POST_PIXEL`, in the chosen
  region type.
- A single callback serves every area of that type. It filters by **area identity**:
  it draws only in the area the Surface was opened in. This keeps the draw cheap and
  scoped without per-area bookkeeping.
- Interactive surfaces also start the input router (see below).
- `disable()` removes the draw callback and stops the router. Nothing remains.
- Both `enable()` and `disable()` ask the bound area to repaint with
  `area.tag_redraw()`. A draw handler only runs when Blender repaints the region, so
  without that request an enabled overlay can stay invisible until an unrelated redraw
  happens. Note that `Space` has no `tag_redraw`; `Area` and `Region` do.

```python
    def enable(self, area):
        """Register drawing (and input) for this surface. No-op if already on."""
        if self._handle is not None:
            return

        space = getattr(bpy.types, self.space_type)
        self._area = area
        self._area_ptr = area.as_pointer()
        self._handle = space.draw_handler_add(
            self._draw, (), self.region_type, "POST_PIXEL")
        area.tag_redraw()

        if self.interactive:
            self._router = router_for(bpy.context.window)
            if self._router is not None:
                self._router.register(self)

    def disable(self):
        """Remove drawing and input. The surface becomes invisible and inert."""
        if self._handle is not None:
            space = getattr(bpy.types, self.space_type)
            space.draw_handler_remove(self._handle, self.region_type)
            self._handle = None
        if self._router is not None:
            self._router.unregister(self)
            self._router = None

    def owns(self, area):
        """Whether this surface draws in the given area."""
        # Compare the pointer, so a closed area cannot make this raise.
        return area is not None and area.as_pointer() == self._area_ptr
```

**Why per space type and not per area?** Blender's draw handler API is keyed by space
type. Scoping by area pointer inside the callback is the cheapest correct approach and
survives area splits, joins and fullscreen toggles.

Parts of the sketch above are targets rather than state: `Scene` arrived with M2 and the
input router with M4, so the sketch now matches the code. An interactive surface registers
with the router of the window it was enabled in; that router arms the modal on the first
surface and takes it down on the last one.

---

## Canvas layer

`Canvas` is the drawing surface handed to nodes during a draw pass. It owns the shared
shaders, the batch cache and the transform/clip stacks.

Principles:

- **One shader per kind**, created once per process and reused. Never create a shader
  inside a draw call.
- **Batches are cached** by geometry signature. Static geometry (rounded rects, icon
  paths) is built once and replayed.
- **A solid rectangle reuses one cached unit quad** under a transform, so its geometry
  is built once per canvas instead of once per rectangle. The vertices come from
  `quad_triangles()` and the batch is cached under `QUAD_BATCH_KEY`.
- **Transform stack** wraps `gpu.matrix.push`/`pop` so nodes can draw in local space.
- **Clip stack** uses the scissor test so children can be clipped to a parent's box.

```python
class Canvas:
    """Immediate-mode 2D drawing surface for one region.

    Nodes call these primitives during draw. The canvas owns shader reuse,
    batching and the transform/clip stacks.
    """

    def rect(self, x, y, w, h, color):
        """Fill an axis-aligned rectangle with a solid color."""

    def rounded_rect(self, x, y, w, h, radius, color):
        """Fill a rectangle with rounded corners. Geometry is cached."""

    def circle(self, cx, cy, radius, color):
        """Fill a circle with a solid color."""

    def line(self, x1, y1, x2, y2, color, width=1.0):
        """Draw a straight line segment."""

    def dashed_line(self, x1, y1, x2, y2, color, dash=6.0, gap=4.0):
        """Draw a dashed line segment."""

    def text(self, x, y, text, size, color, align=None):
        """Draw a text label at a position. Text is never editable."""

    def image(self, texture, x, y, w, h, uv=None):
        """Draw a texture (used for atlas icons and user images)."""

    def push_transform(self, x, y, w, h):
        """Place and size subsequent drawing at (x, y) with (w, h)."""

    def pop_transform(self):
        """Undo the last push_transform()."""

    def push_clip(self, x, y, w, h):
        """Clip subsequent drawing to a rectangle."""

    def pop_clip(self):
        """Undo the last push_clip(), restoring the scissor that was in force."""
```

A note on text: `blf` draws in the same canonical space, so labels need no conversion.
The only care is sizing, which goes through the DPI helper (see Coordinate contract).

Parts of the sketch above are targets rather than state: `rect`, the transform stack, the
clip stack, `rounded_rect`, `circle` and `text` exist today, while `line`, `dashed_line`
and `image` are still to come. Note that a line has no shader to draw it —
`LINE_UNIFORM_COLOR` does not resolve on 5.2, which `tests/check_draw_api.py` pins — so it
will be tessellated into triangles when a caller needs it, not drawn by a line shader.

Text is the one primitive sized from logical units at draw time, so the canvas carries the
display metrics the scene solved under; the other primitives are placed or scaled by
solved geometry and take pixels. `blf` honours the GPU matrix — measured by
`tests/check_draw_api.py`, which renders a glyph under a translated and a scaled matrix
and reads the pixels back — so a label is placed by the same transform stack as everything
else and the canvas hands it a **local** point, never an accumulated one.

---

## Scene graph and layout

### Node model

Every element is a `Node`. Nodes form a tree; a node's rectangle is computed relative
to its parent's content box.

```python
class Node:
    """Base element in the scene tree.

    Nodes carry size policy, margin, anchor, optional layout and children,
    and are solved into absolute rectangles by Scene.reflow().
    """

    def __init__(self, size=None, margin=0, anchor=None, z=0,
                 layout=None, children=None):
        self.children = list(children or [])
        self.rect = (0.0, 0.0, 0.0, 0.0)   # computed: (x, y, w, h)
        self.size = size if size is not None else Size.auto()
        self.margin = margin
        self.anchor = anchor
        self.layout = layout
        self.z = z
        self.visible = True
        self.clip = False
```

### Layout

Layout is declarative and solved in one pass. The parent arranges its children through
its **layout policy**; each child may stretch or take its preferred size.

Layout policies and values are **plain data, not nodes**: they are assigned to node
properties (`layout=`, `anchor=`, `size=`) and carry no children of their own. This
keeps `layout.py` a pure lower layer (see the design rule above).

| Layout policy | Behavior |
|---------------|----------|
| `VBox(gap, padding, align)` | Stacks children top to bottom inside the content box. |
| `HBox(gap, padding, align)` | Stacks children left to right. |

| Placement value | Meaning |
|-----------------|---------|
| `Anchor.top_left()`, `Anchor.bottom_left(margin=8)`, `Anchor.center()`, … | Where a node sits inside its parent: a corner, an edge or the center, with an optional margin. A node with an `anchor` leaves the parent's flow. |

| Size policy | Meaning |
|-------------|---------|
| `Size.auto()` | Take the natural (content) size. |
| `Size.fixed(units)` | Exact logical size. |
| `Size.fill()` | Occupy the remaining space in the parent's flow. |
| `Size.percent(f)` | Fraction of the parent's content box. |

```python
def reflow(self):
    """Compute absolute rectangles for every node in the tree.

    Runs one top-down pass for sizing and one bottom-up pass for placement,
    then marks the scene clean until the next mutation.
    """
    # Root uses the region box; each child is placed in the parent's content box.
    self._size_pass(self.root)
    self._place_pass(self.root)
    self._dirty = False
```

**Anchors** are what make "a child pinned to a corner" expressible without arithmetic:
the parent's solved box is the reference, so moving or resizing the parent moves the
anchored child automatically. This is the hierarchy behavior the whole design is for.

### Hit-testing

Hit-testing walks the tree **front-to-back** (highest z first), respecting visibility
and clipping, and returns the deepest node under a point.

```python
def hit_test(self, x, y):
    """Return the topmost node containing the point, or None.

    Walks children in reverse z-order so the visually topmost node wins,
    and skips subtrees whose clip rectangle excludes the point.
    """
    # Returns the deepest matching Node, or None if the point hits nothing.
    return self._hit(self.root, x, y)
```

Hit-testing and drawing share the same rectangles, so they can never disagree — as long
as layout is solved before either runs.

---

## Widgets

Widgets are thin composites over Node. Each declares its own layout and look, and emits
events upward.

```python
class Button(Node):
    """A clickable element with a label and an optional icon.

    Renders a background, an icon, and a text label, and calls on_click
    when released inside its rectangle.
    """

    def __init__(self, label="", icon=None, on_click=None, size=Size.auto(), **kw):
        super().__init__(size=size, **kw)
        self.label = label
        self.icon = icon
        self.on_click = on_click
        self._hot = False
        self._pressed = False
```

A dock is just a scene: a panel with a stack of buttons and an anchor for the grip.

```python
# Host addon code. The folder is copied into the addon package, so the import path
# is whatever the copy is named under. Inside the package, imports are relative.
from .gui_paint_modules import Surface, Scene, Panel, Button, Icon, VBox, Anchor

scene = Scene(root=Panel(
    layout=VBox(gap=2, padding=3),
    anchor=Anchor.bottom_left(margin=8),
    children=[
        Button(label="Select", icon=Icon.named("select"), on_click=ops.select),
        Button(label="Grab",   icon=Icon.named("grab"),   on_click=ops.grab),
        Button(label="Move",   icon=Icon.named("move"),   on_click=ops.move),
    ],
))

dock = Surface(space_type="VIEW_3D", region_type="WINDOW", interactive=True)
dock.scene = scene
dock.enable(bpy.context.area)
```

---

## Icon system

Icons are first-class assets, resolved by name, and drawn by us.

Three sources, one interface:

| Source | Stored as | Drawn via |
|--------|-----------|-----------|
| Built-in vector icons | Path definitions in Python | Tessellated into cached triangle batches |
| Custom vector icons | Path definitions (own format or SVG-preprocessed) | Same as above |
| External icon sheet (optional) | A PNG atlas + a name→region map | `Canvas.image` with a UV sub-rect |

```python
class Icon:
    """Resolves an icon by name to drawable geometry or an atlas region.

    Vector icons are tessellated once and cached. Atlas icons store a
    texture reference and a UV rectangle.
    """

    @staticmethod
    def named(name):
        """Return the icon registered under this name.

        Raises a clear error at build time if the name is unknown, so
        broken icons are caught early instead of silently skipped.
        """
        # Returns an Icon instance bound to a vector path or atlas region.
        return _REGISTRY.resolve(name)
```

A built-in icon is a list of **convex** polygons in a unit box, so one fan tessellates it
exactly and a concave glyph is built from convex parts — the `move` cross is two bars.
A general tessellator (ear clipping, holes) is deliberately not written until a real icon
needs it.

**Preprocessing beats runtime parsing.** Convert SVG to a compact path list ahead of
time, or rasterize a sheet to an atlas. Doing this at load time (or as a build step)
keeps the draw path free of parsing and file I/O.

The optional external sheet is what allows using a third-party icon set — including a
Blender-derived one — without special-casing it in code.

---

## Input router

The router turns mouse events into node interactions. It runs **only while an interactive
surface is enabled**. A window-level modal reports each event in window pixels, so the
router finds the surface whose region holds the point and converts it to that region's
local space before hit-testing. Two decisions are settled here: the modal runs for the
whole time a surface is enabled, so hover is free, and one router per window is shared by
every interactive surface in it.

### Lifecycle

```
enable()  ->  router.register()  ->  first surface arms the window's modal
                                         |
                                     every event
                                         |
                           hit-test -> on a node?  -- yes --> dispatch, consume
                                         |
                                         no
                                         |
                                      PASS_THROUGH   -> Blender keeps working
disable() ->  router.unregister()  ->  last surface stops the router
                                        (its modal cancels on the next event)
```

### The key simplification from opt-in

Because the surface is enabled explicitly, the router can run as a modal operator for
the whole time the surface is live. A running modal receives mouse movement and clicks,
so the router gets hover and click **without any global keymap hook**. Opt-in removes
the need for a global mouse listener entirely. An idle modal receives no events while the
mouse is still, so its cost is bounded by the input itself.

### Discipline (non-negotiable)

These rules are what keep an interactive overlay from breaking the host application.

1. **Consume only what you use.** Return "consumed" for events that land on an
   interactive node; return "pass through" for everything else.
2. **Never block the keyboard.** No node takes focus in v1, so keyboard events always
   pass through.
3. **Self-cancel on context change.** If the area, window or mode the surface was bound
   to disappears, stop the router cleanly.
4. **One router per window.** Every interactive surface in a window shares one router and
   one modal: the first surface to enable arms it and the last to disable takes it down, so
   a window never runs two modals over the same events. An event goes to the newest surface
   whose region holds the pointer, converted to that region's local space. `input/events.py`
   normalizes a raw event to a move, a left press or a left release before the router sees
   it, so a key, a wheel tick or another button never reaches a node.

```python
class InputRouter:
    """Routes mouse events to the interactive nodes of one window's surfaces.

    Runs as a modal while any interactive surface in the window is enabled. Consumes an
    event that lands on an interactive node and passes everything else through.
    """

    def handle(self, event):
        """Process one event and report whether it was consumed."""
        # Returns True if the event was consumed, False to pass it through.
        ...
```

### Menus

A menu is a transient interactive scene. Opening it arms the router; while open it owns
input, including clicks outside its rectangle (which close it). Closing restores the
previous surface. Same router, different lifetime — no second mechanism.

---

## Data model and authoring

### The question: config files (JSON) or plain Python?

**Short answer: neither alone. One data model, two ways in.** Python authors the model
directly through the Node API (primary); a JSON loader reads the same model as a `Spec`
(optional). They are two forms of one thing: the runtime Node tree and its serializable
form.

Reasoning:

- A UI definition is **data** (structure, labels, sizes, colors) plus **behavior**
  (what a click does). Data maps naturally to JSON. Behavior does not — JSON has no
  functions, so a JSON-only design forces you to reference behavior by name and resolve
  it at runtime.
- **JSON-only costs are real and land on the developer, not the runtime:** no
  autocompletion, no type checking, errors at load instead of at import, a hand-written
  schema and validator to maintain, and a slow drift toward inventing a mini-language.
- This is a library **for addons**, whose authors already write Python. A declarative
  Python API costs nothing extra and gives you IDE support, early errors and direct
  callables. Done well, the Python *is* the config language.
- JSON earns its place for **user-editable** content: saved layouts, exported panel
  designs, hot-reloadable menus. That is a real feature — as an *optional loader*, not
  as the foundation.

So the shape is:

```
   Python (Node API) ───────────────────────────►  Scene  ─►  draw / input
                                                        ▲
   JSON loader ──►  Spec (plain data tree)  ──►  build ──┘
```

The `Spec` is a plain nested structure (dataclasses or dicts): the **serializable form**
of the widget tree, whose runtime form is the Node tree. Only the JSON loader produces a
`Spec`, and a builder turns it into nodes. Either way the engine consumes a Scene, so
adding an authoring path never touches it.

```python
class Spec:
    """Serializable description of a widget tree.

    Produced by the JSON loader (and by dumping a Node tree) and consumed by
    the builder. Behavior is referenced by name and resolved later.
    """

    def __init__(self, kind, props=None, children=None):
        self.kind = kind
        self.props = props or {}
        self.children = children or []
```

Python (primary): author Nodes directly. Behavior is a real callable, checked and
refactorable by the IDE.

```python
def toolbar():
    """Build a simple vertical toolbar."""
    return Panel(layout=VBox(gap=2), children=[
        Button(label="Select", icon=Icon.named("select"), on_click=select_all),
        Button(label="Grab",   icon=Icon.named("grab"),   on_click=grab),
    ])
```

JSON loader (optional, for user-editable content):

```json
{
  "kind": "Panel",
  "props": { "layout": "vbox", "gap": 2 },
  "children": [
    { "kind": "Button", "props": { "label": "Select", "icon": "select", "action": "select_all" } }
  ]
}
```

Note that the JSON form refers to `"select_all"` as a **name**, not code. The loader
resolves it against a registry of known actions. Never evaluate JSON as code.

```python
def resolve_action(name):
    """Resolve an action name from a spec to a callable.

    Names come from a registry populated by the addon. Unknown names raise,
    so a bad spec fails loudly instead of doing nothing.
    """
    # Returns the callable registered under this name.
    return _ACTIONS[name]
```

### Recommendation

Start with the Node API only. Add the JSON loader (and the `Spec` it needs) once there
is a concrete need to save or hand-edit layouts. Building both at once is premature; the
Node API will shape the model anyway.

---

## Performance and redraw

| Rule | Reason |
|------|--------|
| Mark the scene dirty on mutation; reflow once before drawing. | Avoids solving layout every frame. |
| Cache geometry (rounded rects, icon paths) by signature. | Rebuilding batches per frame is the main cost. |
| Draw with one shader per kind, bound once per batch group. | Minimizes state changes. |
| Tag redraw on state change, not on a fast timer. | Idle UI should cost nothing. |
| Use a slow timer only for content that genuinely animates. | Animations are the exception, not the baseline. |
| Cull nodes outside the region. | Large trees stay cheap. |

The draw callback runs on *every* redraw of the region, including redraws Blender
triggers for its own reasons. It must be fast and must never do file I/O, allocations
in the hot path, or shader creation.

---

## numpy usage

Blender ships numpy, so it is available without a new dependency. It is useful for
CPU-side work, not as a requirement:

- **Layout and geometry math** over many nodes at once.
- **Rounded-rect and circle tessellation** as vectorized array generation.
- **Atlas packing** for the icon system.
- **Color array generation** for batched fills.
- **Broad-phase hit-testing** when a scene has many nodes.

Two cautions:

1. Keep numpy **out of the per-frame path** for small scenes; the conversion overhead
   can exceed the gain. Use it where the element count is large.
2. Whether GPU buffers can be filled from numpy arrays directly should be verified
   early against the target versions before relying on it. The safe baseline is plain
   sequences; numpy is an optimization on top.

---

## Compatibility strategy

Target versions: **4.2 LTS and 5.2 LTS and newer.**

All version-dependent behavior lives in `compat.py`:

| Area | Note |
|------|------|
| GPU initialization | 5.2 needs `gpu.init()` before a background process can build a shader or a batch; 4.2 has no such function. `compat.ensure_gpu_ready()` covers both. |
| Line and point drawing | `LINE_UNIFORM_COLOR` does not resolve on 5.2 while `POINT_UNIFORM_COLOR` does (`tests/check_draw_api.py`); a line is tessellated into triangles, so no branch is needed. |
| Shader names | Already modern across the target range; keep a single lookup. |
| `blf` sizing | Measured stable across the range: `blf.size(fontid, size)` takes two arguments on both targets and `blf.dimensions` answers without a GPU. Keep the DPI helper centralized anyway. |
| Any 5.x removals | Absorb in `compat.py` so the rest of the code is version-agnostic. |

Rule: no version comparison outside `compat.py`, and prefer a capability check
(`hasattr`, a probe) over comparing numbers when the difference can be detected
directly. The rest of the codebase should read as if there were only one version.

---

## Risks

Ordered by impact.

1. **Modal coexistence.** An interactive surface runs a modal operator. Other modal
   tools (transform, sculpt, playback) may interact with it. Mitigation: consume
   minimally, self-cancel on context change, and test against common modal tools.
2. **Overlay ordering.** `POST_PIXEL` draws over the editor content but under native
   popups and menus. A custom panel cannot float above Blender's own popups.
3. **Region/area lifecycle.** Splits, joins, fullscreen, workspace switches and
   multi-window all invalidate assumptions. Mitigation: identity checks, self-cancel,
   re-arm logic.
4. **DPI and scaling.** Centralize in `coords.py`; never scale by hand in nodes.
5. **Version churn.** Contained by `compat.py`.
6. **Draw cost.** Enforced by the performance rules and a code review checklist.

---

## Suggested build order

Each milestone is independently useful and testable.

| Milestone | Deliverable | Proves |
|-----------|-------------|--------|
| M1 | Surface + Canvas + coords | Draw a rectangle in a chosen editor, toggle it on and off. |
| M2 | Scene + layout + hit-test | A parent panel with anchored and stacked children. |
| M3 | Widgets + icons | A clickable toolbar with labels and vector icons. |
| M4 | Input router | Hover and click reaching the right node; pass-through elsewhere. |
| M5 | Menus + Spec + JSON loader | A custom menu opened from a button, loadable from data. |
| M6 | Compat + performance pass | Works on 4.2 and 5.x; idle UI costs nothing. |

Build M1 first and resist adding widgets before the coordinate contract and the two
loops are solid. Everything else is easier once those are right.

---

## Open questions

- Is a stable node id needed for saved layouts and diffing, or are positional paths
  enough?
- Which external icon sheet format to support first (atlas + JSON index is the simplest).

---

## Glossary

| Term | Meaning |
|------|---------|
| **Region** | A sub-area of an editor that can host drawing (e.g. `WINDOW`). |
| **Space type** | The editor class drawing is registered against (e.g. `SpaceView3D`). |
| **Logical unit** | Resolution-independent size value; converted to pixels at draw time. |
| **Reflow** | The one-pass layout solve that assigns absolute rectangles to nodes. |
| **Spec** | Serializable widget description produced by the JSON loader (and by dumping a Node tree); the data form of the model. |
| **Passive surface** | Draw-only; never takes input. |
| **Interactive surface** | Draws and routes input while enabled. |
