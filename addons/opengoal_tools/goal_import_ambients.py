"""Import > From GOAL files: ambients (sound emitters, music zones, hints).

Level .jsonc ambients are typed ("'sound", ["symbol", name], ["uint32", id]);
the game's entities .json ones raw ("sound", "effects": [{"name": ...}],
text-id ints, music-flava ints). Other ambient types (ocean-near-off ...)
have no object in the addon and are listed unpicked.
"""
from __future__ import annotations

import re

import bpy

SUPPORTED = ("sound", "music", "hint")


def ambient_type(e):
    lump = e.get("lump") if isinstance(e.get("lump"), dict) else {}
    t = lump.get("type", "")
    t = t[-1] if isinstance(t, list) else t
    return str(t).lstrip("'")


def _val(v):
    """First value of a typed / raw lump value."""
    if isinstance(v, list):
        if v and isinstance(v[0], str) and len(v) > 1:
            v = v[1]
        elif v:
            v = v[0]
        else:
            return None
    if isinstance(v, list):
        return v[0] if v else None
    return v


def _sym(v):
    v = _val(v)
    return str(v).lstrip("'") if v is not None else ""


_FLAVAS = {"key": None, "names": {}}


def music_flavas():
    """{music-flava number: name} from the game's gsound-h.gc."""
    import os
    from .export.paths import _goal_src
    p = _goal_src() / "engine" / "sound" / "gsound-h.gc"
    key = (str(p), os.path.getmtime(p) if p.exists() else 0)
    if key != _FLAVAS["key"]:
        names = {}
        if p.exists():
            txt = p.read_text(encoding="utf-8", errors="replace")
            i = txt.find("(defenum music-flava")
            j = txt.find("(def", i + 1) if i >= 0 else -1
            for n, v in re.findall(r"\(([\w-]+)\s+(\d+)\)", txt[i:j if j > 0 else None] if i >= 0 else ""):
                names[int(v)] = n
        _FLAVAS.update(key=key, names=names)
    return _FLAVAS["names"]


def _new_empty(ctx, name, loc, color, size, col_path):
    from .collections import _link_object_to_sub_collection, free_object_name
    if name in bpy.data.objects:
        name = free_object_name(name + "-", 1)
    o = bpy.data.objects.new(name, None)
    o.empty_display_type = "SPHERE"
    o.location = loc
    o.show_name = True
    o.empty_display_size = size
    o.color = color
    ctx.scene.collection.objects.link(o)
    _link_object_to_sub_collection(ctx.scene, o, *col_path)
    return o


def _obj_name(kind, name):
    """AMBIENT_<kind><name>; a name that already starts with the kind keeps it
    (the export writes the name after AMBIENT_)."""
    name = re.sub(r"[^\w-]", "_", name.lower()) or "ambient"
    return "AMBIENT_" + (name if name.startswith(kind) else kind + name)


def import_ambients(ctx, entries):
    from .collections import _COL_PATH_SOUND_EMITTERS, _COL_PATH_SPAWNS, _active_level_col
    from .goal_import_actors import game_to_blender
    from .operators.spawn import sound_radius_driver
    from .data import MUSIC_FLAVA_TABLE
    from . import hints
    made, skipped = [], []
    for e in entries:
        d = e["data"]
        lump = d.get("lump") or {}
        t = ambient_type(d)
        tr = d.get("trans") or [0, 0, 0, 10]
        loc = game_to_blender(tr)
        radius = float(tr[3]) if len(tr) > 3 else float((d.get("bsphere") or [0, 0, 0, 10])[3])
        name = e["name"]
        if t == "sound":
            effects = lump.get("effects")
            snd = effects[0].get("name", "") if isinstance(effects, list) and effects and isinstance(effects[0], dict) \
                else _sym(lump.get("effect-name"))
            if isinstance(snd, list):          # ["water-lap", "TIME_PE0IOD_LOOP"]: the sound + a flag
                snd = next((x for x in snd if isinstance(x, str)), "")
            if not snd:
                skipped.append(e["name"])
                continue
            o = _new_empty(ctx, _obj_name("snd", name), loc, (0.2, 0.8, 1.0, 1.0), 1.0, _COL_PATH_SOUND_EMITTERS)
            o["og_sound_name"] = snd.lower()
            o["og_sound_radius"] = radius
            cs = lump.get("cycle-speed")
            vals = [x for x in (cs[1:] if cs and isinstance(cs[0], str) else cs or []) if isinstance(x, (int, float))]
            if vals and vals[0] >= 0:
                o["og_sound_mode"] = "interval"
                o["og_cycle_min"] = float(vals[0])
                o["og_cycle_rnd"] = float(vals[1]) if len(vals) > 1 else 0.0
            else:
                o["og_sound_mode"] = "loop"
            sound_radius_driver(o)
        elif t == "music":
            fl = _val(lump.get("flava"))
            bank = _sym(lump.get("music"))
            flava = "default"
            if bank and bank in MUSIC_FLAVA_TABLE and isinstance(fl, (int, float)):
                lst = MUSIC_FLAVA_TABLE[bank]           # a level .jsonc: index in the bank's flavas
                flava = lst[int(fl)] if 0 <= int(fl) < len(lst) else "default"
            elif isinstance(fl, (int, float)):
                flava = music_flavas().get(int(fl), "default")   # the game: music-flava number
                col = _active_level_col(ctx.scene)
                lvl = str(col.get("og_music_bank", "")) if col is not None else ""
                banks = [lvl] + list(MUSIC_FLAVA_TABLE)
                bank = next((b for b in banks if flava in MUSIC_FLAVA_TABLE.get(b, ())), lvl or "village1")
            o = _new_empty(ctx, _obj_name("mus", name), loc, (1.0, 0.85, 0.1, 1.0), max(0.3, radius * 0.04),
                           _COL_PATH_SOUND_EMITTERS)
            o["og_music_bank"] = bank or "village1"
            o["og_music_flava"] = flava
            o["og_music_priority"] = float(_val(lump.get("priority")) or 10.0)
            o["og_music_radius"] = radius
        elif t == "hint":
            o = _new_empty(ctx, _obj_name("hint", name), loc, (1.0, 0.6, 0.1, 1.0), radius, _COL_PATH_SPAWNS)
            h = o.og_hint
            h.radius = radius
            o.empty_display_size = radius
            tid = _val(lump.get("text-id"))
            h.text = _hint_text(tid)
            snd = _sym(lump.get("sound-name"))
            if snd and _sym(lump.get("play-mode")) != "notice":
                h.voice = snd.lower()
            cm = lump.get("cmds")
            nums = [x for x in (cm[1:] if cm and isinstance(cm[0], str) else cm or []) if isinstance(x, int)]
            by_num = {c[3]: c[0] for c in hints.CMDS}
            for c, task in zip(nums[0::2], nums[1::2]):
                if c in by_num:
                    r = h.cmds.add()
                    r.cmd = by_num[c]
                    r.task = _task_id(task)
        else:
            skipped.append(e["name"])
            continue
        made.append(o)
    return made, skipped


def _task_id(n):
    from . import db
    for t in db.game_tasks():
        if t.get("value") == n:
            return t["id"]
    return str(n)


def _hint_text(tid):
    """A hint's text: a game text reference for the game's own ids, else a note
    (a custom level's text lives in its text file, not in the .jsonc)."""
    if not isinstance(tid, int):
        return ""
    from .game_text import vanilla_texts
    for n, (i, _en) in vanilla_texts().items():
        if i == tid:
            return f"[text:{n}]"
    return f"text #x{tid:x} (from the level's text file: retype it here)"
