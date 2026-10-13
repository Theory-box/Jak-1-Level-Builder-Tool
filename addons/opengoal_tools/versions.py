# ---------------------------------------------------------------------------
# versions.py — OpenGOAL Level Tools
# Which Blender / OpenGOAL the user has, and which addon features it supports.
#
# OpenGOAL comes three ways:
#   release      a jak-project release (launcher / zip): version from gk --version
#   jak-project  a dev clone: git commit
#   mod-base     the modding fork (has engine/mods/mod-settings.gc): git commit
# FEATURES says per kind what a feature needs: a minimum release, a commit
# (the clone must contain it), False (never there) or True (always there).
# A "probe" (looks at the game source) wins over the version rules.
# ---------------------------------------------------------------------------
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import bpy

KINDS = {"release": "Release", "jak-project": "jak-project dev", "mod-base": "mod-base dev", "unknown": "Unknown"}

FEATURES = {
    "builtin_cameras": {
        "label": "Built-in cameras",
        "release": "0.3.4", "jak-project": True, "mod-base": True,
        "probe": "builtin_cameras",
    },
    "mod_base_spawn": {
        "label": "Boot straight into the spawn (mod-settings.gc)",
        "release": False, "jak-project": False, "mod-base": True,
        "probe": "mod_settings",
    },
    "time_of_day": {
        "label": "Time of day",
        "release": "0.3.8", "jak-project": "d04ac9d", "mod-base": "3a0aadf",
    },
}

_CACHE: dict = {}


def clear_cache():
    _CACHE.clear()


def _cached(key, fn):
    if key not in _CACHE:
        try:
            _CACHE[key] = fn()
        except Exception:
            _CACHE[key] = None
    return _CACHE[key]


def blender_version() -> tuple:
    return tuple(bpy.app.version)


def _vtuple(s) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", str(s))[:3])


def _git_root(start: Path):
    for d in [start, *start.parents]:
        if (d / ".git").exists():
            return d
    return None


def _git(root: Path, *args, timeout=5):
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=timeout,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return r


def mod_settings_path() -> Path:
    from .paths_core import data
    return data() / "goal_src" / "jak1" / "engine" / "mods" / "mod-settings.gc"


def game_info() -> dict:
    """{"kind", "version" (release, e.g. "0.3.8"), "commit" (dev), "root"}."""
    from .paths_core import data, exe_root, EXE
    d, gk = data(), exe_root() / f"gk{EXE}"
    key = ("game", str(d), str(gk))

    def _detect():
        info = {"kind": "unknown", "version": None, "commit": None, "root": None}
        mod_base = mod_settings_path().exists()
        root = _git_root(d) if d.exists() else None
        if root is not None:
            info["kind"] = "mod-base" if mod_base else "jak-project"
            info["root"] = str(root)
            r = _git(root, "rev-parse", "--short", "HEAD")
            info["commit"] = r.stdout.strip() or None
            return info
        if mod_base:
            info["kind"] = "mod-base"
            return info
        if gk.exists():
            r = subprocess.run([str(gk), "--version"], capture_output=True, text=True, timeout=10,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            m = re.search(r"v(\d+\.\d+\.\d+)", r.stdout + r.stderr)
            if m:
                info["kind"], info["version"] = "release", m.group(1)
        return info
    return _cached(key, _detect) or {"kind": "unknown", "version": None, "commit": None, "root": None}


def game_label() -> str:
    g = game_info()
    extra = f" v{g['version']}" if g["version"] else (f" @ {g['commit']}" if g["commit"] else "")
    return KINDS[g["kind"]] + extra


def _has_commit(root, commit):
    """True / False when the clone contains commit; None if git can't tell."""
    def _q():
        r = _git(root, "merge-base", "--is-ancestor", commit, "HEAD")
        return {0: True, 1: False}.get(r.returncode)
    return _cached(("commit", root, commit), _q)


def _probe(name):
    if name == "builtin_cameras":
        from .export.scene import builtin_cameras_supported
        return builtin_cameras_supported()
    if name == "mod_settings":
        return mod_settings_path().exists()
    return None


def feature_status(key) -> tuple:
    """(available, reason): available is True, False or None (can't tell)."""
    f = FEATURES[key]
    if f.get("blender") and blender_version() < tuple(f["blender"]):
        return False, f"needs Blender {'.'.join(map(str, f['blender']))}+"
    if f.get("probe"):
        ok = _probe(f["probe"])
        if ok is not None:
            return ok, ("found in this OpenGOAL's game code" if ok else _need_text(f))
    g = game_info()
    need = f.get(g["kind"])
    if g["kind"] == "unknown":
        return None, "OpenGOAL version not detected (set the paths in Developer Tools)"
    if need is True:
        return True, ""
    if need is False or need is None:
        return False, f"not available on {KINDS[g['kind']]}"
    if g["kind"] == "release":
        ok = _vtuple(g["version"]) >= _vtuple(need)
        return ok, ("" if ok else f"needs release v{need}+ (you have v{g['version']}): update OpenGOAL")
    if not g["root"]:
        return None, f"needs {KINDS[g['kind']]} from commit {need} or later; can't check without git: keep it up to date"
    ok = _has_commit(g["root"], need)
    if ok is None:
        return None, f"needs commit {need}; git couldn't check it: pull the latest {KINDS[g['kind']]}"
    return ok, ("" if ok else f"needs commit {need} or later: pull the latest {KINDS[g['kind']]}")


def _need_text(f):
    parts = []
    if isinstance(f.get("release"), str):
        parts.append(f"release v{f['release']}+")
    for k in ("jak-project", "mod-base"):
        if f.get(k) is True:
            parts.append(KINDS[k])
        elif isinstance(f.get(k), str):
            parts.append(f"{KINDS[k]} from {f[k]}")
    return "needs " + " or ".join(parts) if parts else "not available"


def feature_available(key) -> bool:
    """Treats "can't tell" as available (the user is expected to be up to date)."""
    return feature_status(key)[0] is not False


def draw_feature_note(layout, key):
    """A warning line under a feature's UI when this setup doesn't support it."""
    ok, why = feature_status(key)
    if ok is False:
        layout.label(text=f"{FEATURES[key]['label']}: {why}", icon="ERROR")
    elif ok is None:
        layout.label(text=why, icon="QUESTION")


def draw_versions(layout):
    box = layout.box()
    box.label(text=f"Blender {bpy.app.version_string}", icon="BLENDER")
    box.label(text=f"OpenGOAL: {game_label()}", icon="CONSOLE")
    col = box.column(align=True)
    for key, f in FEATURES.items():
        ok, why = feature_status(key)
        icon = "CHECKMARK" if ok else ("QUESTION" if ok is None else "X")
        col.label(text=f["label"], icon=icon)
        if why and ok is not True:
            sub = col.row(); sub.scale_y = 0.7
            sub.label(text="      " + why)
    box.operator("og.recheck_versions", icon="FILE_REFRESH")


class OG_OT_RecheckVersions(bpy.types.Operator):
    """Detect the OpenGOAL version again (after updating or changing paths)"""
    bl_idname = "og.recheck_versions"
    bl_label  = "Re-check Versions"

    def execute(self, ctx):
        clear_cache()
        self.report({"INFO"}, f"OpenGOAL: {game_label()}")
        return {"FINISHED"}


CLASSES = (OG_OT_RecheckVersions,)
