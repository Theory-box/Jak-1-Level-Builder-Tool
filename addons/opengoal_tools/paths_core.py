# ---------------------------------------------------------------------------
# paths_core.py — OpenGOAL Level Tools
# Single source for where the OpenGOAL install lives (exe / data / decompiler
# folders). build.py and export/paths.py both resolve through here.
#
# Priority, highest first:
#   1. This .blend's Project Folders (Developer Tools), when enabled
#   2. Addon preferences manual overrides (exe_path / data_path / decompiler_path)
#   3. Addon preferences auto-detect (og_root_path + og_active_version / _data)
#
# Also owns the install scanner and its cache — the preferences panel draws
# from the cache so it never walks the filesystem on redraw.
# ---------------------------------------------------------------------------
from __future__ import annotations

import sys
from pathlib import Path

import bpy

EXE = ".exe" if sys.platform == "win32" else ""

# Build configs a dev (jak-project) clone may have compiled, in preference order.
DEV_BUILD_CONFIGS = ("Release", "RelWithDebInfo", "Debug")


def strip(p) -> str:
    return (p or "").strip().rstrip("\\").rstrip("/")


def prefs():
    a = bpy.context.preferences.addons.get("opengoal_tools")
    return a.preferences if a else None


def _blend_override(attr: str) -> str:
    """This .blend's Project Folders value for attr, or "" when unset/disabled.
    Safe to call from worker threads (no scene -> no override)."""
    try:
        props = bpy.context.scene.og_props
    except Exception:
        return ""
    if not getattr(props, "og_blend_paths_enabled", False):
        return ""
    return strip(getattr(props, attr, ""))


def _active(field: str) -> Path | None:
    p = prefs()
    if not p:
        return None
    root = strip(getattr(p, "og_root_path", ""))
    sub = strip(getattr(p, field, ""))
    if root and sub:
        return Path(root) / sub
    return None


def exe_root() -> Path:
    v = _blend_override("og_blend_exe_path")
    if v:
        return Path(v)
    p = prefs()
    if p and strip(p.exe_path):
        return Path(strip(p.exe_path))
    return _active("og_active_version") or Path(".")


def data_root() -> Path:
    v = _blend_override("og_blend_data_path")
    if v:
        return Path(v)
    p = prefs()
    if p and strip(p.data_path):
        return Path(strip(p.data_path))
    # Separate data folder if picked, else the exe folder (release installs
    # keep data/ next to gk).
    return _active("og_active_data") or _active("og_active_version") or Path(".")


def data() -> Path:
    """Dev layout (repo root holds goal_src/jak1) -> root; release -> root/data."""
    root = data_root()
    if (root / "goal_src" / "jak1").exists():
        return root
    return root / "data"


def decompiler_path() -> Path:
    v = _blend_override("og_blend_decompiler_path")
    if v:
        return Path(v)
    p = prefs()
    if p and strip(p.decompiler_path):
        return Path(strip(p.decompiler_path))
    return data() / "decompiler_out" / "jak1"


# ── Install scanner ────────────────────────────────────────────────────────

def _is_exe_dir(d: Path) -> bool:
    return (d / f"gk{EXE}").exists() and (d / f"goalc{EXE}").exists()


def _is_data_dir(d: Path) -> bool:
    return (d / "goal_src" / "jak1").exists() or (d / "data" / "goal_src" / "jak1").exists()


def dev_exe_dirs(d: Path) -> list[Path]:
    """gk/goalc folders a dev clone builds into: <clone>/out/build/<config>/bin."""
    out = []
    for cfg in DEV_BUILD_CONFIGS:
        b = d / "out" / "build" / cfg / "bin"
        if _is_exe_dir(b):
            out.append(b)
    return out


def scan_for_installs(root: Path, max_depth: int = 4):
    """Find exe folders and data folders at or under root.

    Returns (exe_folders, data_folders). The root itself counts (a dev clone
    picked as the root is its own data folder), and a dev clone's
    out/build/<config>/bin is checked even though out/ is otherwise skipped.
    """
    skip_dirs = {
        "data", "out", "decompiler_out", "goal_src", "custom_assets",
        "iso_data", "third_party", "node_modules", ".git",
    }
    exe_folders: list[Path] = []
    data_folders: list[Path] = []

    def _claim(d: Path) -> bool:
        claimed = False
        if _is_exe_dir(d):
            exe_folders.append(d)
            claimed = True
        if _is_data_dir(d):
            data_folders.append(d)
            exe_folders.extend(x for x in dev_exe_dirs(d) if x not in exe_folders)
            claimed = True
        return claimed

    def _walk(path: Path, depth: int):
        if depth > max_depth:
            return
        try:
            for d in sorted(path.iterdir()):
                if not d.is_dir() or d.name.startswith(".") or d.name.lower() in skip_dirs:
                    continue
                if _claim(d):
                    continue   # don't recurse into an install
                _walk(d, depth + 1)
        except (PermissionError, OSError):
            pass

    if not _claim(root):
        _walk(root, 0)
    return exe_folders, data_folders


# Cache: root string -> (exe_folders, data_folders). Filled by Find Files and
# by changing the root; the preferences panel only ever reads it.
_SCAN_CACHE: dict[str, tuple[list[Path], list[Path]]] = {}


def cached_scan(root: Path, refresh: bool = False):
    key = str(root)
    if refresh or key not in _SCAN_CACHE:
        _SCAN_CACHE[key] = scan_for_installs(root) if root.exists() else ([], [])
    return _SCAN_CACHE[key]


def rel_to(root: Path, d: Path) -> str:
    try:
        r = str(d.relative_to(root)).replace("\\", "/")
        return r if r != "" else "."
    except ValueError:
        return str(d)


def auto_select(p, root: Path, exe_folders, data_folders, only_if_empty: bool = False):
    """Pick the best exe + data folder into the preferences. With only_if_empty,
    keeps a selection the user already made (as long as it still exists)."""
    import re

    def _ver_key(d: Path):
        m = re.search(r"(\d+)[._-](\d+)[._-](\d+)", str(d))
        return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)

    if exe_folders and not (only_if_empty and p.og_active_version
                            and (root / p.og_active_version).exists()):
        # A dev clone picked as the root -> its own build wins; otherwise
        # highest version number.
        own = [d for d in exe_folders if d in dev_exe_dirs(root)]
        best = own[0] if own else sorted(exe_folders, key=_ver_key, reverse=True)[0]
        p.og_active_version = rel_to(root, best)
    if data_folders and not (only_if_empty and p.og_active_data
                             and (root / p.og_active_data).exists()):
        # Root itself (dev clone) > the picked exe's own install (release
        # installs keep data/ next to gk) > a folder named "active" > first.
        exe_dir = root / p.og_active_version if p.og_active_version else None
        if root in data_folders:
            best = root
        elif exe_dir is not None and exe_dir in data_folders:
            best = exe_dir
        else:
            best = next((d for d in data_folders if "active" in str(d).lower()), data_folders[0])
        p.og_active_data = rel_to(root, best)
