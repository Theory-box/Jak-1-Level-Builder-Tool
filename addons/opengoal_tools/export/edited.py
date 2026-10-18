# ───────────────────────────────────────────────────────────────────────
# export/edited.py — OpenGOAL Level Tools
#
# Edited actors: GOAL files that change a vanilla actor for custom levels
# (a child type, or a patch). Two places hold them:
#   addon   the addon's subtypes/ folder; an actor's DB record names its
#           default one ("edited": "<file stem>")
#   custom  the Custom code folder (Preferences / this .blend's folders):
#           a file's ";; edits: <etype> ..." header line says which actors
#           it's for (no header: offered for every actor)
# A file with "(deftype __TYPE__" is a child type (the actor exports as it),
# without it a patch (the actor keeps its etype).
#
# Each actor picks in GOAL Code: the DB default, Vanilla (none), or any
# file for its etype (og_edited_code = "", "vanilla" or "<source>:<stem>").
# Each file is placed (this .blend's setting, default from a ";; place:
# shared" header, else obs):
#   obs     in the level's -obs.gc, type <level>-<stem>
#   shared  its own file goal_src/levels/level-tools/edited/lt-<stem>.gc,
#           type lt-<stem>, compiled once (game.gp) and listed in the .gd of
#           every level that uses it, so levels reuse it
# ───────────────────────────────────────────────────────────────────────
from __future__ import annotations

import os
import re
from pathlib import Path

ADDON_DIR = Path(__file__).resolve().parent.parent / "subtypes"
SHARED_DIR = "levels/level-tools/edited"
_TAG = "; og-level-tools"

_CACHE = {"key": None, "files": {}}


def custom_dir():
    """The Custom code folder (this .blend's folders first, then Preferences), or None."""
    try:
        import bpy
        props = bpy.context.scene.og_props
        if getattr(props, "og_blend_paths_enabled", False) and props.og_blend_code_path.strip():
            p = bpy.path.abspath(props.og_blend_code_path.strip())
        else:
            a = bpy.context.preferences.addons.get(__package__.split(".")[0])
            p = bpy.path.abspath(getattr(a.preferences, "custom_code_path", "") or "") if a else ""
    except Exception:
        return None
    return Path(p) if p and os.path.isdir(p) else None


def _read(source, path):
    text = path.read_text(encoding="utf-8", errors="replace")
    head = text[:4000]
    edits = []
    for m in re.finditer(r"^;;\s*edits:\s*(.+)$", head, re.M):
        edits += m.group(1).split()
    place = re.search(r"^;;\s*place:\s*(obs|shared)\b", head, re.M)
    return {"id": f"{source}:{path.stem}", "source": source, "stem": path.stem, "path": path,
            "child": "(deftype __TYPE__" in text, "edits": edits,
            "place": place.group(1) if place else "obs"}


def files():
    """{id: file record} of the addon's and the Custom code folder's .gc files
    (cached until a file / the folder changes)."""
    dirs = [("addon", ADDON_DIR)] + ([("custom", custom_dir())] if custom_dir() else [])
    paths = [(s, p) for s, d in dirs for p in sorted(d.glob("*.gc"))]
    key = tuple((s, str(p), p.stat().st_mtime) for s, p in paths)
    if key != _CACHE["key"]:
        out = {}
        for s, p in paths:
            r = _read(s, p)
            out[r["id"]] = r
        _CACHE.update(key=key, files=out)
    return _CACHE["files"]


def default_id(etype):
    """The DB's edited file of an etype ("edited": "<stem>"), as an id, or None."""
    from .. import db
    rec = db.find_actor(etype) or {}
    stem = rec.get("edited")
    return f"addon:{stem}" if stem else None


def choices(etype):
    """[(id, label, description)] for an actor's Code picker."""
    d = default_id(etype)
    out = [("", "Default" + (f" ({d.split(':', 1)[1]}.gc)" if d else " (vanilla)"),
            "The database's choice for this actor")]
    out.append(("vanilla", "Vanilla", "No edited code: the game's own type"))
    for fid, r in files().items():
        if fid == d:
            continue
        if r["source"] == "addon":
            continue                      # addon files are the DB defaults of their actors
        if r["edits"] and etype not in r["edits"]:
            continue
        out.append((fid, f"{r['stem']}.gc", f"Custom code folder: {r['path']}"))
    return out


def resolve(o, etype):
    """The file record an actor uses, or None (vanilla)."""
    sel = str(getattr(o, "og_edited_code", "") or "")
    if sel == "vanilla":
        return None
    fid = sel or default_id(etype)
    return files().get(fid) if fid else None


def place(scene, rec):
    """obs / shared for a file (this .blend's setting, else the file's header)."""
    if scene is None:
        return rec["place"]
    return str(scene.get("og_edited_place", {}).get(rec["id"], rec["place"]))


def type_name(scene, rec, level_prefix):
    if not rec["child"]:
        return None
    return f"lt-{rec['stem']}" if place(scene, rec) == "shared" else f"{level_prefix}-{rec['stem']}"


def used(scene, objects):
    """{id: record} of the files the level's actors use."""
    out = {}
    for o in objects:
        if o.type == "EMPTY" and o.name.startswith("ACTOR_") and o.name.count("_") >= 2:
            r = resolve(o, o.name.split("_", 2)[1])
            if r is not None:
                out[r["id"]] = r
    return out


def gc_lines(scene, pfx, objects):
    """GOAL of the level's obs-placed edited files (__TYPE__ = <level>-<stem>)."""
    lines = []
    for r in used(scene, objects).values():
        if place(scene, r) != "obs":
            continue
        text = r["path"].read_text(encoding="utf-8")
        lines += [""] + text.replace("__TYPE__", f"{pfx}-{r['stem']}").rstrip("\n").split("\n")
    return lines


def shared_objects(scene, objects):
    """[.o] of the level's shared edited files (its .gd lists them after the actor code)."""
    return [f"lt-{r['stem']}.o" for r in used(scene, objects).values() if place(scene, r) == "shared"]


def ensure_shared(scene, objects):
    """Write the level's shared edited files (only when changed) and register
    them once in game.gp (goal-src after their actor's code)."""
    from .paths import _goal_src, _game_gp
    from .level_tools import _write_if_changed, _patch
    from ..data import ETYPE_CODE
    lines = []
    for r in used(scene, objects).values():
        if place(scene, r) != "shared":
            continue
        text = r["path"].read_text(encoding="utf-8").replace("__TYPE__", f"lt-{r['stem']}")
        _write_if_changed(_goal_src() / SHARED_DIR / f"lt-{r['stem']}.gc", text)
        etypes = r["edits"] or [r["stem"]]
        deps = ["process-drawable"] + [Path(o).stem for e in etypes for o in ETYPE_CODE.get(e, [])]
        deps = list(dict.fromkeys(deps))
        lines.append(f'(goal-src "{SHARED_DIR}/lt-{r["stem"]}.gc" {" ".join(chr(34) + d + chr(34) for d in deps)}) {_TAG}')
    gp = _game_gp()
    if lines and gp.exists():
        _patch(gp, lines, '(group-list "all-code"', "shared edited actors")
