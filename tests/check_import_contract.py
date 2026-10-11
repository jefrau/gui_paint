"""Verify the gui_paint package import contract.

Covers what the design contract requires (ARCHITECTURE.md, D9): relative imports only,
relocatability under a renamed parent package, and no registration at import time.

The public surface grows per milestone: M1 exported `Surface`, M2 the node tree with its
layout values and the scene, and M3 the widgets and the icon registry. M4 added the input
router, which stays internal, so the public surface is unchanged.
"""

import shutil
import sys
import tempfile
from pathlib import Path

import bpy

from checkkit import REPO, banner, check, finish

PACKAGE = REPO / "gui_paint_modules"
PUBLIC = ("Surface", "Scene", "Node", "Size", "Anchor", "VBox", "HBox",
          "Panel", "Label", "Button", "Icon")
MODULES = (
    "__init__.py",
    "canvas.py",
    "compat.py",
    "coords.py",
    "icons/__init__.py",
    "icons/vector.py",
    "input/__init__.py",
    "input/events.py",
    "input/router.py",
    "layout.py",
    "nodes.py",
    "scene.py",
    "shaders.py",
    "surface.py",
    "widgets/__init__.py",
    "widgets/button.py",
    "widgets/label.py",
    "widgets/panel.py",
)

banner()

check("package directory exists", PACKAGE.is_dir(), str(PACKAGE))

missing = [name for name in MODULES if not (PACKAGE / name).is_file()]
check("every expected module exists", not missing, f"missing {missing}")

offenders = []
for path in PACKAGE.rglob("*.py") if PACKAGE.is_dir() else []:
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip().startswith(("import gui_paint_modules", "from gui_paint_modules")):
            offenders.append(f"{path.name}:{line_number}")
check("no absolute self-import", not offenders, str(offenders))

# Import under a renamed parent package, with the draw handler API swapped for a
# recorder so any import-time registration becomes observable.
registered = []


class _DrawHandlerRecorder:
    @staticmethod
    def draw_handler_add(*args, **kwargs):
        registered.append(args)
        return object()

    @staticmethod
    def draw_handler_remove(*args, **kwargs):
        registered.append(args)


with tempfile.TemporaryDirectory() as tmp:
    host = Path(tmp) / "hostpkg"
    host.mkdir()
    (host / "__init__.py").write_text("", encoding="utf-8")
    if PACKAGE.is_dir():
        shutil.copytree(PACKAGE, host / "ui_kit")

    original = getattr(bpy.types, "SpaceView3D", None)
    bpy.types.SpaceView3D = _DrawHandlerRecorder
    sys.path.insert(0, tmp)
    try:
        import hostpkg.ui_kit as ui_kit

        imported, error = True, ""
    except Exception as exc:
        imported, error = False, f"{type(exc).__name__}: {exc}"
    finally:
        sys.path.remove(tmp)
        if original is not None:
            bpy.types.SpaceView3D = original

    check("imports under a renamed parent", imported, error)
    if imported:
        missing = [name for name in PUBLIC if not hasattr(ui_kit, name)]
        check("public surface re-exported", not missing, f"missing {missing}")
    check("nothing registered at import", not registered, str(registered))

finish("import contract")
