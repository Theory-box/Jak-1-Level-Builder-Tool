"""Level files clean up when a level's name changes.

Each export remembers the name a level was exported under
(collection["og_exported_name"]). When the name changed since, the next export
(Developer Tools > Build: "Clean renamed levels", on by default) first removes
the old name's files (.jsonc, .glb, .gd, -obs.gc; their folders when empty) and
its entries in game.gp / level-info.gc / load-boundary-data.gc, and points this
.blend's references to the old name (custom level fields, load commands,
continue names) at the new one. Only names this .blend exported are touched.

Developer Tools also lists "leftover levels": levels registered in game.gp
that no level of this .blend has (renamed before this existed, deleted, or
another .blend's), each with a remove button.
"""
from __future__ import annotations

import os
import re

import bpy
from bpy.props import StringProperty

KEY = "og_exported_name"


def _level_name(col):
    return str(col.get("og_level_name", col.name)).strip().lower().replace(" ", "-")


def pending_old_name(col):
    """The name this level was last exported under, when it isn't its name now."""
    old = str(col.get(KEY, "") or "")
    return old if old and old != _level_name(col) else ""


def _files(name):
    """The generated files of a level (that exist)."""
    from .export.paths import _goal_src, _levels_dir
    d = _levels_dir() / name
    out = [d / f"{name}.jsonc", d / f"{name}.glb"] + (sorted(d.glob("*.gd")) if d.exists() else [])
    out.append(_goal_src() / "levels" / name / f"{name}-obs.gc")
    return [p for p in out if p.exists()]


def level_files_exist(name):
    return bool(_files(name))


def remove_level_files(name):
    """Delete a level's generated files (folders only when left empty) and its
    build registrations. Returns log lines."""
    from .export.levels import _strip_level_registrations
    from .export.paths import _goal_src, _levels_dir, log
    msgs = []
    for p in _files(name):
        p.unlink()
        msgs.append(f"Deleted {p}")
    for d in (_levels_dir() / name, _goal_src() / "levels" / name):
        if d.exists() and not any(d.iterdir()):
            d.rmdir()
            msgs.append(f"Removed empty folder {d}")
    msgs += _strip_level_registrations(name)
    # a running GOALC still knows the removed files: the next build restarts it
    from .export import writers as _w
    _w.TYPES_CHANGED = True
    for m in msgs:
        log(f"[rename clean] {m}")
    return msgs


# ── references to the old name inside this .blend ────────────────────────────

def _sym_re(old):
    # the level symbol on its own ('old, (display old ...)) or a continue name ("old-start")
    return re.compile(rf"(?<![\w-]){re.escape(old)}(?![\w-])|(?<=\"){re.escape(old)}(?=-)")


def _fix_value(v, rx, new):
    if isinstance(v, str):
        n = rx.sub(new, v)
        return (n, n != v)
    return (v, False)


def _walk(group, rx, new):
    """Replace in the string values of an ID / property group (nested)."""
    changed = 0
    for k in list(group.keys()):
        v = group[k]
        if isinstance(v, str):
            n, c = _fix_value(v, rx, new)
            if c:
                group[k] = n
                changed += 1
        elif hasattr(v, "keys"):
            changed += _walk(v, rx, new)
        elif isinstance(v, list) or type(v).__name__ == "IDPropertyArray":
            for item in v:
                if hasattr(item, "keys"):
                    changed += _walk(item, rx, new)
    return changed


def repoint_references(old, new, scene):
    """This .blend's references to level `old` (custom level fields, load
    commands, continue names) now name `new`. Returns how many changed."""
    rx = _sym_re(old)
    from .collections import _all_level_collections
    n = 0
    for col in _all_level_collections(scene):
        n += _walk(col, rx, new)
    for o in bpy.data.objects:
        n += _walk(o, rx, new)
    return n


def other_references(old):
    """Shared game files that still name `old` after the clean (other .blends' levels)."""
    from .export.paths import _goal_src
    rx = _sym_re(old)
    hits = []
    for rel in (("engine", "level", "level-info.gc"), ("engine", "level", "load-boundary-data.gc")):
        p = _goal_src().joinpath(*rel)
        if p.exists() and rx.search(p.read_text(encoding="utf-8", errors="replace")):
            hits.append(p.name)
    return hits


def before_export(scene, col, name):
    """Called on the main thread before a level exports: clean the old name
    (when enabled) and remember this name."""
    if col is None:
        return
    from .export.paths import log
    from .collections import rename_sub_collections, retarget_tasks
    n = rename_sub_collections(col)          # sub-collections still named after an old name
    if n:
        log(f"[rename clean] {n} sub-collection(s) renamed to '{name}.…'")
    old = pending_old_name(col)
    if old and retarget_tasks(scene, old, col.name):   # tasks still set to the old name
        log(f"[rename clean] tasks of '{old}' now belong to '{col.name}'")
    if old and old != name:
        if getattr(scene.og_props, "og_clean_renamed", True):
            log(f"[rename clean] level renamed '{old}' -> '{name}': removing the old files")
            remove_level_files(old)
            n = repoint_references(old, name, scene)
            if n:
                log(f"[rename clean] {n} reference(s) to '{old}' in this .blend now name '{name}'")
            for f in other_references(old):
                log(f"[rename clean] WARNING: {f} still names '{old}' (another level's load commands / boundaries?)")
        else:
            log(f"[rename clean] off: the files of '{old}' stay (Developer Tools > Build)")
    col[KEY] = name


# ── leftover levels ──────────────────────────────────────────────────────────

_GP_CACHE = {"key": None, "names": []}


def registered_levels():
    """Custom levels registered in game.gp (cached until it changes)."""
    from .export.paths import _game_gp
    p = _game_gp()
    if not p.exists():
        return []
    key = (str(p), os.path.getmtime(p))
    if key != _GP_CACHE["key"]:
        txt = p.read_text(encoding="utf-8", errors="replace")
        names = []
        for m in re.finditer(r'\(build-custom-level "([^"]+)"\)', txt):
            if m.group(1) not in names:
                names.append(m.group(1))
        _GP_CACHE.update(key=key, names=names)
    return _GP_CACHE["names"]


def leftover_levels(scene):
    """Registered levels that no level of this .blend has (now or as its last export)."""
    from .collections import _all_level_collections
    mine = set()
    for col in _all_level_collections(scene):
        mine.add(_level_name(col))
        if col.get(KEY):
            mine.add(str(col[KEY]))
    return [n for n in registered_levels() if n not in mine]


class OG_OT_CleanOldLevelName(bpy.types.Operator):
    """Remove the files and build entries of this level's old name now (instead of at the next export)"""
    bl_idname = "og.clean_old_level_name"
    bl_label = "Clean Now"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        from .collections import _active_level_col
        col = _active_level_col(ctx.scene)
        old = pending_old_name(col) if col is not None else ""
        if not old:
            return {"CANCELLED"}
        remove_level_files(old)
        new = _level_name(col)
        n = repoint_references(old, new, ctx.scene)
        col[KEY] = new
        self.report({"INFO"}, f"Removed the files of '{old}'" + (f"; {n} reference(s) now name '{new}'" if n else ""))
        return {"FINISHED"}


class OG_OT_RemoveLeftoverLevel(bpy.types.Operator):
    """Remove this level's files and its game.gp / level-info / load boundary entries.
It isn't a level of this .blend: make sure no other .blend still uses it"""
    bl_idname = "og.remove_leftover_level"
    bl_label = "Remove Leftover Level"
    bl_options = {"REGISTER", "UNDO"}
    name: StringProperty()

    def invoke(self, ctx, event):
        return ctx.window_manager.invoke_confirm(self, event, title=f"Remove level '{self.name}'?",
                                                 message="Its files and build entries are deleted",
                                                 confirm_text="Remove", icon="WARNING")

    def execute(self, ctx):
        if not self.name:
            return {"CANCELLED"}
        remove_level_files(self.name)
        self.report({"INFO"}, f"Removed level '{self.name}'")
        return {"FINISHED"}


def draw_name_warning(layout, col):
    """Under the level name: the old name's files that will be cleaned / a clash."""
    old = pending_old_name(col)
    scene = bpy.context.scene
    if old:
        box = layout.box()
        auto = getattr(scene.og_props, "og_clean_renamed", True)
        r = box.row(); r.alert = not auto
        r.label(text=(f"Old files of '{old}' are removed on the next export" if auto
                      else f"Old files of '{old}' stay (auto clean is off)"), icon="INFO" if auto else "ERROR")
        box.operator("og.clean_old_level_name", icon="TRASH")
    name = _level_name(col)
    if str(col.get(KEY, "") or "") != name and level_files_exist(name):
        w = layout.row(); w.alert = True
        w.label(text=f"'{name}' already has level files (another .blend?): exporting overwrites them", icon="ERROR")


def draw_leftovers(layout, scene):
    left = leftover_levels(scene)
    head, body = layout.panel("og_leftover_levels", default_closed=True)
    head.label(text=f"Leftover levels ({len(left)})", icon="TRASH")
    if body is None:
        return
    if not left:
        body.label(text="None: every registered level is in this .blend", icon="CHECKMARK")
        return
    h = body.row(); h.enabled = False; h.scale_y = 0.7
    h.label(text="Registered in game.gp, not a level of this .blend (other .blends' levels show too)")
    for n in left:
        r = body.row(align=True)
        r.label(text=n, icon="FILE_FOLDER")
        r.operator("og.remove_leftover_level", text="", icon="X").name = n


CLASSES = (OG_OT_CleanOldLevelName, OG_OT_RemoveLeftoverLevel)
