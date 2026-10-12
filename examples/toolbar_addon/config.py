"""The portable tool config: a toolbar's buttons as plain data.

A tool references a Blender operator **by name** (`bpy.ops.<category>.<operation>`), never a
Python callable, so a config written on one machine loads on another: every Blender install
has the same operators. The file is small JSON, readable and editable by hand, and can be
copied to another PC or pasted into a forum.

This module is the data layer only. It registers no `bpy` class and imports the library
nowhere, so the addon can build its Scene from a config without this layer knowing about it.

A tool must name an operator that **runs to completion on its own**. Interactive operators
(``transform.translate``, ``rotate``, ``scale``) need mouse input, so a toolbar button cannot
finish them; a config that names one loads fine but the button will appear to do nothing.
"""

import json

FORMAT = 1
# The icons this example can draw come from the library's vector registry; an atlas or
# Blender's own icons are not available yet, so an unknown name is rejected here.
KNOWN_ICONS = ("", "select", "grab", "move")


class ConfigError(ValueError):
    """A config that cannot be loaded safely or does not make sense."""


class ToolButton:
    """One toolbar button: a label, an optional icon, and an operator to run.

    ``op`` is a Blender operator idname such as ``"object.select_all"``; ``params`` is the
    keyword arguments to pass it, as JSON-compatible values.
    """

    __slots__ = ("label", "icon", "op", "params")

    def __init__(self, label, op, icon="", params=None):
        if not isinstance(label, str) or not label:
            raise ConfigError(f"a button needs a non-empty label, got {label!r}")
        if not isinstance(op, str) or "." not in op:
            raise ConfigError(f"a button needs an operator idname like 'object.select_all', got {op!r}")
        if icon not in KNOWN_ICONS:
            raise ConfigError(f"unknown icon {icon!r}; known: {KNOWN_ICONS}")
        if params is not None and not isinstance(params, dict):
            raise ConfigError(f"params must be an object or absent, got {type(params).__name__}")
        self.label = label
        self.icon = icon
        self.op = op
        self.params = dict(params) if params else {}

    def to_dict(self):
        """The button as plain JSON data; empty fields are left out to keep it tidy."""
        record = {"label": self.label, "op": self.op}
        if self.icon:
            record["icon"] = self.icon
        if self.params:
            record["params"] = dict(self.params)
        return record

    @classmethod
    def from_dict(cls, record):
        """Build a button from loaded data, raising ``ConfigError`` on anything wrong."""
        if not isinstance(record, dict):
            raise ConfigError(f"a button must be an object, got {type(record).__name__}")
        for field in ("label", "op"):
            if field not in record:
                raise ConfigError(f"a button is missing {field!r}")
        return cls(label=record["label"], op=record["op"],
                   icon=record.get("icon", ""), params=record.get("params"))

    def resolve(self):
        """Return the `bpy.ops` entry this button references, or raise ``ConfigError``.

        Blender's ``bpy.ops`` hands back a proxy for *any* name, real or not, and only raises
        when that proxy is called (measured: ``getattr(bpy.ops, "nope")`` returns a module).
        Existence is therefore checked against ``dir()``, which lists the real categories and
        operators, instead of trusting ``getattr``.
        """
        # Imported here so the data layer stays importable without Blender.
        import bpy

        category, _, operation = self.op.partition(".")
        module = getattr(bpy.ops, category) if category in dir(bpy.ops) else None
        if module is None or operation not in dir(module):
            raise ConfigError(f"no such operator: {self.op!r}")
        return getattr(module, operation)

    def invoke(self):
        """Run the referenced operator with this button's parameters."""
        return self.resolve()(**self.params)


class ToolbarConfig:
    """A named list of tool buttons, saved as JSON and portable across machines."""

    def __init__(self, name="", buttons=()):
        self.name = str(name)
        self.buttons = list(buttons)

    def to_dict(self):
        """The whole config as plain JSON data, with a format version for the future."""
        return {"format": FORMAT, "name": self.name,
                "buttons": [button.to_dict() for button in self.buttons]}

    def to_json(self):
        """The config as indented JSON text."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data):
        """Build a config from loaded data, raising ``ConfigError`` on anything wrong."""
        if not isinstance(data, dict):
            raise ConfigError(f"the config must be an object, got {type(data).__name__}")
        version = data.get("format")
        if version != FORMAT:
            raise ConfigError(f"unsupported config format {version!r}; expected {FORMAT}")
        records = data.get("buttons")
        if not isinstance(records, list):
            raise ConfigError("the config needs a 'buttons' list")
        return cls(name=data.get("name", ""),
                   buttons=[ToolButton.from_dict(record) for record in records])

    @classmethod
    def from_json(cls, text):
        """Build a config from JSON text, raising ``ConfigError`` on anything wrong."""
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"not valid JSON: {exc}") from None
        return cls.from_dict(data)

    def save(self, path):
        """Write the config to ``path`` as JSON."""
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(self.to_json() + "\n")

    @classmethod
    def load(cls, path):
        """Read a config from ``path``."""
        with open(path, encoding="utf-8") as handle:
            return cls.from_json(handle.read())


def default_config():
    """The toolbar that ships with the example: immediate, object-mode viewport tools.

    Every tool names a Blender operator that finishes on its own and applies in **object
    mode**. Interactive operators (``transform.translate`` and friends) are deliberately
    absent — they need mouse input, so a button cannot complete them — and so is anything
    that changes the mode, because then the other tools would stop applying mid-session.
    """
    return ToolbarConfig("Default viewport tools", [
        ToolButton("Select All", "object.select_all", icon="select", params={"action": "SELECT"}),
        ToolButton("Deselect All", "object.select_all", icon="select", params={"action": "DESELECT"}),
        ToolButton("Invert Selection", "object.select_all", icon="grab", params={"action": "INVERT"}),
        ToolButton("Shade Smooth", "object.shade_smooth", icon="move"),
    ])
