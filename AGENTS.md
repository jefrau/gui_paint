# AGENTS.md

gui_paint is a self-contained Python library for drawing and interacting with 2D UI in
any Blender editor. The design lives in ARCHITECTURE.md — read it before changing behavior.

## Repository layout

| Path | Role |
|---|---|
| gui_paint_modules/ | The library code. This is the copyable unit. |
| ARCHITECTURE.md | Design contract. Single source of truth. |
| AGENTS.md | This file. How to work here. |

## Read before you touch

| Before editing | Read in ARCHITECTURE.md |
|---|---|
| Imports, folder structure, dependencies | Module layout · D9 |
| Coordinates, sizes, DPI | Coordinate contract |
| Anything under the draw callback | Canvas layer · Performance and redraw |
| Version-dependent code | Compatibility strategy |
| Input, modals, menus | Input router |

## Skills

| Task | Skill |
|---|---|
| Write/extract/refactor functions, move or delete files | programming-practices |
| Add comments or docstrings | python-comment-conventions |
| Write a commit message | commit-message |
| Refactor existing code | refactoring |

## Commits

- Git repo at the project root.
- Use git-native operations for tracked-file moves and deletes.
- Messages follow the commit-message skill.
- Never add co-author or AI-attribution trailers.
