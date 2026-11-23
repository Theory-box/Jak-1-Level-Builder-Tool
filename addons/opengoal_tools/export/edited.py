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

from ..collections import actor_etype

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
            from ..paths_core import pref
            p = bpy.path.abspath(pref("custom_code_path", "") or "")
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
    (cached until a file / the folder changes; files are looked at again at
    most every 2 s while the folders stay the same: panels ask every redraw)."""
    import time
    cd = custom_dir()
    dirs = [("addon", ADDON_DIR)] + ([("custom", cd)] if cd else [])
    try:
        dkey = tuple((s, str(d), d.stat().st_mtime_ns) for s, d in dirs)
    except OSError:
        dkey = None
    now = time.monotonic()
    if dkey is not None and dkey == _CACHE.get("dkey") and now - _CACHE.get("t", 0.0) < 2.0:
        return _CACHE["files"]
    _CACHE.update(dkey=dkey, t=now)
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


def custom_actor(etype) -> bool:
    """An addon-made actor ("custom_actor": true, e.g. Actor Light): no vanilla type,
    its file is always shared (lt-<stem>)."""
    from .. import db
    return bool((db.find_actor(etype) or {}).get("custom_actor"))


def choices(etype):
    """[(id, label, description)] for an actor's Code picker."""
    d = default_id(etype)
    out = [("", "Default" + (f" ({d.split(':', 1)[1]}.gc)" if d else " (vanilla)"),
            "The database's choice for this actor")]
    if not custom_actor(etype):
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
    if sel == "vanilla" and not custom_actor(etype):
        return None
    if sel == "vanilla":
        sel = ""
    fid = sel or _variant_id(o, etype) or default_id(etype)
    return files().get(fid) if fid else None


def _variant_id(o, etype):
    """A variant's own edited file ("edited" on the chosen choice, e.g. the red / blue /
    yellow caged sages), as an id, or None."""
    from .. import db
    stem = db.actor_variant(etype, lambda k, d=None: o.get(k, d)).get("edited")
    return f"addon:{stem}" if stem else None


def place(scene, rec):
    """obs / shared for a file (this .blend's setting, else the file's header)."""
    if scene is None or any(custom_actor(e) for e in rec["edits"]):
        return rec["place"]
    return str(scene.get("og_edited_place", {}).get(rec["id"], rec["place"]))


def type_name(scene, rec, level_prefix):
    if not rec["child"]:
        return None
    return f"lt-{rec['stem']}" if place(scene, rec) == "shared" else f"{level_prefix}-{rec['stem']}"


def used(scene, objects):
    """{id: record} of the files the level's actors use (and the camera shot
    library lt-pov-play when an actor's camera choice needs it)."""
    out = {}
    for o in objects:
        et = actor_etype(o)
        if et:
            r = resolve(o, et)
            if r is not None:
                out[r["id"]] = r
    from .. import pov as _pov
    if out and _pov.library_needed(objects):
        lib = files().get("addon:pov-play")
        if lib is not None:
            out[lib["id"]] = lib
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
    from .fileio import write_if_changed, patch
    from ..data import ETYPE_CODE
    lines = []
    for r in used(scene, objects).values():
        if place(scene, r) != "shared":
            continue
        text = r["path"].read_text(encoding="utf-8").replace("__TYPE__", f"lt-{r['stem']}")
        write_if_changed(_goal_src() / SHARED_DIR / f"lt-{r['stem']}.gc", text)
        etypes = r["edits"] or [r["stem"]]
        deps = ["process-drawable"] + [Path(o).stem for e in etypes for o in ETYPE_CODE.get(e, [])]
        deps = list(dict.fromkeys(deps))
        lines.append(f'(goal-src "{SHARED_DIR}/lt-{r["stem"]}.gc" {" ".join(chr(34) + d + chr(34) for d in deps)}) {_TAG}')
    gp = _game_gp()
    if lines and gp.exists():
        # Dependencies can change when the database or custom header changes.
        # Replace our previous registration by source path, not by whole line:
        # appending a second goal-src for one output makes GOALC reject game.gp.
        text = gp.read_text(encoding="utf-8")
        for line in lines:
            source = line.split('"', 2)[1]
            pattern = re.compile(r'^[ \t]*\(goal-src "' + re.escape(source)
                                 + r'"[^\n]*\) ' + re.escape(_TAG) + r'[^\n]*$', re.M)
            matches = list(pattern.finditer(text))
            if matches:
                first = matches[0].start()
                text = pattern.sub(lambda m: line if m.start() == first else "", text)
        write_if_changed(gp, text)
        patch(gp, lines, '(group-list "all-code"', "shared edited actors")
