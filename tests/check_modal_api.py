"""Record what the input layer can reach, per target, before M4 relies on it.

M4 routes mouse events, so this is the recorded answer to "what does a Blender event
expose, and can a modal operator be stood up, headless?" — the same question
`check_draw_api.py` answered for the draw layer, and the evidence the M4 plan is built on.

The facts it pins, all measured on both targets:

- `bpy.types.Event` carries the fields the router reads: `type`, `value`, the region-local
  and window-space mouse points, and the modifiers;
- `Event.value` includes `PRESS` and `RELEASE`, which the router tracks itself instead of
  trusting a lone `CLICK`, so a drag that leaves a button cancels rather than firing;
- `Event.type` includes the mouse-move and left-button ids the router consumes;
- an Operator with a `modal()` registers, is reached through `bpy.ops`, and unregisters.

What a background process cannot check is left to a live probe, recorded in the M4 plan
and settled by the manual step, not pretended here: how `mouse_region_x/y` relates to the
cursor's region, whether `PASS_THROUGH` keeps a modal alive *and* lets Blender act, and
the geometry of an area.
"""

import bpy

from checkkit import banner, check, finish

# The fields the router reads off a live event. A missing one would be a silent no-op.
FIELDS = (
    "type", "value",
    "mouse_x", "mouse_y", "mouse_region_x", "mouse_region_y",
    "mouse_prev_x", "mouse_prev_y",
    "shift", "ctrl", "alt",
)

# The values the router's decision depends on: it tracks PRESS and RELEASE itself.
REQUIRED_VALUES = ("PRESS", "RELEASE")

# The event ids the router consumes; everything else passes through untouched.
REQUIRED_TYPES = ("MOUSEMOVE", "LEFTMOUSE")

banner()

event_rna = bpy.types.Event.bl_rna.properties

missing_fields = [name for name in FIELDS if event_rna.get(name) is None]
check("Event exposes the fields the router reads", not missing_fields, f"missing {missing_fields}")

value_prop = event_rna.get("value")
values = [item.identifier for item in value_prop.enum_items] if value_prop is not None else []
check("Event.value is enumerable", bool(values), str(values))
missing_values = [name for name in REQUIRED_VALUES if name not in values]
check("Event.value carries PRESS and RELEASE", not missing_values,
      f"missing {missing_values} from {values}")

type_prop = event_rna.get("type")
types = [item.identifier for item in type_prop.enum_items] if type_prop is not None else []
check("Event.type is enumerable", bool(types), str(len(types)))
missing_types = [name for name in REQUIRED_TYPES if name not in types]
check("Event.type carries the mouse ids the router consumes", not missing_types,
      f"missing {missing_types} from {len(types)} ids")

# The modal shape: a class that can stand up, be reached through bpy.ops, and be removed.
# Registering a bpy class at import time is forbidden (D2/D9), so this happens here only.


class _ModalShapeProbe(bpy.types.Operator):
    bl_idname = "gui_paint_probe.modal_shape"
    bl_label = "gui_paint modal shape probe"
    bl_options = {"INTERNAL"}

    def invoke(self, context, event):
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        return {"PASS_THROUGH"}

    def execute(self, context):
        return {"FINISHED"}


registered = False
reachable = False
error = ""
try:
    bpy.utils.register_class(_ModalShapeProbe)
    registered = True
    namespace = getattr(bpy.ops, "gui_paint_probe", None)
    reachable = namespace is not None and hasattr(namespace, "modal_shape")
except Exception as exc:  # noqa: BLE001 - the check records the outcome, any error counts
    error = f"{type(exc).__name__}: {exc}"
finally:
    if registered:
        bpy.utils.unregister_class(_ModalShapeProbe)

check("a modal Operator registers, is reachable by bpy.ops and unregisters",
      registered and reachable and not hasattr(bpy.types, "_ModalShapeProbe"), error)

finish("modal api")
