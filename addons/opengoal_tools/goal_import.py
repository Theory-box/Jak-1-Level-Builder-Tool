"""Import > From GOAL files: read level definitions (a custom level .jsonc,
the game's decompiler_out/jak1/entities actor / ambient .json files, an
entity.gc or <level>-nav.gc, a level-info.gc) from a file or the clipboard,
list what they define by category, and import the picked ones.

The parsed entries stay in this module (not saved in the .blend); the window
manager keeps the list rows (name, category, picked).
"""
from __future__ import annotations

import json
import os
import re

import bpy
from bpy.props import BoolProperty, CollectionProperty, IntProperty, PointerProperty, StringProperty

# category id, label, icon (list order)
CATEGORIES = (
    ("ACTORS", "Actors", "OUTLINER_OB_EMPTY"),
    ("AMBIENTS", "Ambients", "OUTLINER_OB_SPEAKER"),
    ("CAMERAS", "Cameras", "OUTLINER_OB_CAMERA"),
    ("NAVMESHES", "Nav-meshes", "MOD_TRIANGULATE"),
    ("CHECKPOINTS", "Checkpoints", "EMPTY_SINGLE_ARROW"),
    ("BOUNDARIES", "Load boundaries", "MOD_EDGESPLIT"),
)
_CAT_LABEL = {c: l for c, l, _i in CATEGORIES}

_ENTRIES = []          # parsed entries: {"cat", "name", "info", "data", "source"} (index = row.index)


# ── GOAL reader ──────────────────────────────────────────────────────────────

_TOKEN = re.compile(r"""\s+|;[^\n]*|\#\|.*?\|\#|"(?:\\.|[^"\\])*"|[()]|'|[^\s()";']+""", re.S)


def read_sexprs(text):
    """The top-level forms of GOAL text as nested lists. Atoms stay strings
    (a string literal keeps its quotes); 'x reads as ["quote", x]."""
    out, stack = [], [[]]
    qs = [0]                                    # per depth: pending quote count
    for m in _TOKEN.finditer(text):
        t = m.group(0)
        if t[0].isspace() or t[0] == ";" or t.startswith("#|"):
            continue
        if t == "'":
            qs[-1] += 1
            continue
        if t == "(":
            stack.append([])
            qs.append(0)
            continue
        if t == ")":
            if len(stack) == 1:
                continue                        # stray paren
            form = stack.pop()
            qs.pop()
            item = form
        else:
            item = t
        while qs[-1]:
            item = ["quote", item]
            qs[-1] -= 1
        stack[-1].append(item)
    return stack[0]


def _walk(form):
    yield form
    if isinstance(form, list):
        for f in form:
            yield from _walk(f)


def is_new_static(form, typ):
    """(new 'static 'typ ...)"""
    return (isinstance(form, list) and len(form) >= 3 and form[0] == "new"
            and form[1] == ["quote", "static"] and form[2] == ["quote", typ])


def static_fields(form):
    """{":key": value} of a (new 'static 'type :key value ...) form."""
    out, i = {}, 3
    while i + 1 < len(form):
        k = form[i]
        if isinstance(k, str) and k.startswith(":"):
            out[k[1:]] = form[i + 1]
            i += 2
        else:
            i += 1
    return out


def _unstring(s):
    return s[1:-1] if isinstance(s, str) and len(s) >= 2 and s[0] == '"' else s


# ── Finding the entries ──────────────────────────────────────────────────────

def _actor_name(a, i):
    lump = a.get("lump") or {}
    n = lump.get("name") if isinstance(lump, dict) else None
    return str(n) if n else f"{a.get('etype', 'actor')}-{i}"


def _json_entries(data, source):
    """Entries of a custom level .jsonc (dict) or a game entities .json (list)."""
    out = []
    if isinstance(data, dict) and "trans" in data:
        data = [data]                           # one copied entry
    if isinstance(data, dict):
        groups = (("ACTORS", data.get("actors")), ("AMBIENTS", data.get("ambients")), ("CAMERAS", data.get("cameras")))
    elif isinstance(data, list):
        # loose entries: actors have an etype, ambients a lump "type", cameras neither
        ents = [e for e in data if isinstance(e, dict) and "trans" in e]
        lt = lambda e: isinstance(e.get("lump"), dict) and "type" in e["lump"]
        groups = (("ACTORS", [e for e in ents if "etype" in e]),
                  ("AMBIENTS", [e for e in ents if "etype" not in e and lt(e)]),
                  ("CAMERAS", [e for e in ents if "etype" not in e and not lt(e)]))
    else:
        groups = ()
    for cat, items in groups:
        for i, e in enumerate(items or ()):
            if not isinstance(e, dict):
                continue
            if cat == "ACTORS" and e.get("etype") == "lt-checkpoint":
                # a checkpoint's trigger (the export's lt-checkpoint actor): joins its checkpoint
                lump = e.get("lump") if isinstance(e.get("lump"), dict) else {}
                cn = lump.get("continue-name")
                cn = cn[-1] if isinstance(cn, list) else cn
                out.append({"cat": "CHECKPOINTS", "name": f"{cn} trigger", "info": "trigger", "data": e,
                            "trigger_of": str(cn or ""), "source": source})
                continue
            if cat == "ACTORS":
                from . import db
                from .goal_import_actors import resolve_etype
                et = resolve_etype(e)
                name, info = _actor_name(e, i), et
                if not db.find_actor(et):
                    info = f"{et} (custom actor)"
            else:
                lump = e.get("lump") if isinstance(e.get("lump"), dict) else {}
                name = str(lump.get("name") or f"{cat.lower()[:-1]}-{i}")
                t = lump.get("type", "")
                info = str(t[-1] if isinstance(t, list) else t).lstrip("'")
                if cat == "AMBIENTS":
                    from .goal_import_ambients import SUPPORTED
                    if info not in SUPPORTED:
                        out.append({"cat": cat, "name": name, "info": f"{info} (no addon object for it)", "data": e,
                                    "source": source, "pick": False})
                        continue
            ent = {"cat": cat, "name": name, "info": info, "data": e, "source": source}
            if cat == "ACTORS" and isinstance(data, dict) and "aid" not in e:
                ent["aid"] = int(data.get("base_id", 10000)) + i + 1   # a level .jsonc: base id + its place
            out.append(ent)
    return out


_LB_BLOCK = re.compile(r";; ===== OG CUSTOM BOUNDARIES: (\S+) =====(.*?);; ===== END OG CUSTOM BOUNDARIES: \1 =====", re.S)


def _goal_entries(text, source):
    """Nav-meshes (entity.gc case entries, custom-nav defines), continue-points
    (level-info.gc) and load boundaries (load-boundary-data.gc: a custom
    level's block says which level it is) of GOAL text."""
    out = []
    if "static-load-boundary" in text:
        blocks = [(m.group(1), m.group(2)) for m in _LB_BLOCK.finditer(text)]
        rest = _LB_BLOCK.sub("", text)
        for level, body in blocks + [(None, rest)]:
            n = 0
            for top in read_sexprs(body):
                for f in _walk(top):
                    if isinstance(f, list) and f and f[0] == "static-load-boundary":
                        n += 1
                        out.append({"cat": "BOUNDARIES", "name": f"{level or 'boundary'}-{n}",
                                    "info": level or "", "data": f, "level": level, "source": source})
        text = rest
    forms = read_sexprs(text)
    for top in forms:
        # custom-nav: (define *nav-sym* (new 'static 'nav-mesh ...))
        if isinstance(top, list) and len(top) >= 3 and top[0] == "define" and is_new_static(top[2], "nav-mesh"):
            sym = top[1].strip("*")
            sym = sym[4:] if sym.startswith("nav-") else sym
            out.append({"cat": "NAVMESHES", "name": sym, "info": "custom-nav", "data": top[2], "source": source})
            continue
        for f in _walk(top):
            # current system: ((aid) (set! (-> this nav-mesh) (new 'static 'nav-mesh ...)))
            if (isinstance(f, list) and len(f) >= 2 and isinstance(f[0], list) and len(f[0]) == 1
                    and isinstance(f[1], list) and len(f[1]) == 3 and f[1][0] == "set!"
                    and f[1][1] == ["->", "this", "nav-mesh"] and is_new_static(f[1][2], "nav-mesh")):
                aid = f[0][0]
                out.append({"cat": "NAVMESHES", "name": f"aid {aid}", "info": "entity.gc", "data": f[1][2],
                            "aid": aid, "source": source})
            elif is_new_static(f, "continue-point"):
                sf = static_fields(f)
                name = _unstring(sf.get("name", "")) or "continue-point"
                lev = sf.get("level")
                lev = lev[1] if isinstance(lev, list) and lev[0] == "quote" else lev
                out.append({"cat": "CHECKPOINTS", "name": name, "info": str(lev or ""), "data": f, "source": source})
    return out


def _json_values(js):
    """The JSON values of (comment-stripped) text: the whole text, a copied
    part of a list / object (entries with commas between them, an
    "actors": [...] key), or JSON blocks between other text (the Export
    Selected Definitions file)."""
    t = js.strip().rstrip(",")
    for cand in (t, "[" + t + "]", "{" + t + "}"):
        try:
            return [json.loads(cand)]
        except ValueError:
            pass
    out, dec, i = [], json.JSONDecoder(), 0
    for m in re.finditer(r"^[ \t]*[\[{]", js, re.M):
        if m.start() < i:
            continue
        j = m.end() - 1
        try:
            v, end = dec.raw_decode(js, j)
        except ValueError:
            continue
        out.append(v)
        i = end
    return out


def parse_text(text, source):
    """Entries found in a file's / the clipboard's text: JSON (whole or in
    parts) and GOAL forms."""
    from .export.includes import strip_jsonc
    s = text.lstrip("\ufeff")
    out = []
    if "{" in s or "[" in s:
        for v in _json_values(strip_jsonc(s)):
            out += _json_entries(v, source)
    if "(new 'static" in s or "static-load-boundary" in s:
        out += _goal_entries(s, source)
    return out


# ── List state ───────────────────────────────────────────────────────────────

class OGImportRow(bpy.types.PropertyGroup):
    cat: StringProperty()
    info: StringProperty()
    source: StringProperty()
    index: IntProperty()
    pick: BoolProperty(name="Import", default=True, description="Import this one")


class OGGoalImport(bpy.types.PropertyGroup):
    filepath: StringProperty(name="File", subtype="FILE_PATH",
                             description="A level .jsonc, a game entities .json (decompiler_out/jak1/entities), "
                                         "an entity.gc / <level>-nav.gc, a level-info.gc or a load-boundary-data.gc")
    rows: CollectionProperty(type=OGImportRow)
    active: IntProperty()


def _state(ctx=None):
    return (ctx or bpy.context).window_manager.og_goal_import


def _add_entries(ctx, entries, source):
    """Replace the rows from this source with its new entries."""
    global _ENTRIES
    st = _state(ctx)
    keep = [(r.cat, r.name, r.info, r.source, r.pick, _ENTRIES[r.index]) for r in st.rows
            if r.source != source and r.index < len(_ENTRIES)]
    _ENTRIES = [k[5] for k in keep] + list(entries)
    st.rows.clear()
    for i, (cat, name, info, src, pick, _e) in enumerate(keep):
        r = st.rows.add()
        r.cat, r.name, r.info, r.source, r.pick, r.index = cat, name, info, src, pick, i
    for j, e in enumerate(entries):
        r = st.rows.add()
        r.cat, r.name, r.info, r.source, r.index = e["cat"], e["name"], e["info"], source, len(keep) + j
        r.pick = e.get("pick", True)


def entry(row):
    return _ENTRIES[row.index] if row.index < len(_ENTRIES) else None


def all_entries():
    """Every loaded entry (actor links look up their targets in all of them)."""
    return list(_ENTRIES)


# ── Operators ────────────────────────────────────────────────────────────────

class OG_OT_GoalImportLoad(bpy.types.Operator):
    """Read the file and list what it defines (adds to the list: load the actor and ambient files,
an entity.gc and a level-info.gc one after the other)"""
    bl_idname = "og.goal_import_load"
    bl_label = "Load"

    def execute(self, ctx):
        path = bpy.path.abspath(_state(ctx).filepath)
        if not os.path.isfile(path):
            self.report({"ERROR"}, f"No file at {path}")
            return {"CANCELLED"}
        with open(path, encoding="utf-8", errors="replace") as f:
            entries = parse_text(f.read(), os.path.basename(path))
        if not entries:
            self.report({"WARNING"}, f"Nothing to import found in {os.path.basename(path)}")
            return {"CANCELLED"}
        _add_entries(ctx, entries, os.path.basename(path))
        self.report({"INFO"}, f"{len(entries)} definition(s) in {os.path.basename(path)}")
        return {"FINISHED"}


class OG_OT_GoalImportPaste(bpy.types.Operator):
    """List the definitions in the copied text (the clipboard)"""
    bl_idname = "og.goal_import_paste"
    bl_label = "Paste from Clipboard"

    def execute(self, ctx):
        entries = parse_text(ctx.window_manager.clipboard or "", "clipboard")
        if not entries:
            self.report({"WARNING"}, "Nothing to import found in the clipboard")
            return {"CANCELLED"}
        _add_entries(ctx, entries, "clipboard")
        self.report({"INFO"}, f"{len(entries)} definition(s) from the clipboard")
        return {"FINISHED"}


class OG_OT_GoalImportClear(bpy.types.Operator):
    """Empty the list"""
    bl_idname = "og.goal_import_clear"
    bl_label = "Clear"

    def execute(self, ctx):
        global _ENTRIES
        _ENTRIES = []
        _state(ctx).rows.clear()
        return {"FINISHED"}


class OG_OT_GoalImportPick(bpy.types.Operator):
    """Pick or unpick every definition (of this category)"""
    bl_idname = "og.goal_import_pick"
    bl_label = "Select All"

    cat: StringProperty(default="")
    pick: BoolProperty(default=True)

    @classmethod
    def description(cls, ctx, props):
        what = f"every {_CAT_LABEL.get(props.cat, '').lower()} entry" if props.cat else "everything in the list"
        return ("Pick " if props.pick else "Unpick ") + what

    def execute(self, ctx):
        for r in _state(ctx).rows:
            if not self.cat or r.cat == self.cat:
                r.pick = self.pick
        return {"FINISHED"}


class OG_OT_GoalImportRun(bpy.types.Operator):
    """Import the picked definitions into the active level (they end up selected)"""
    bl_idname = "og.goal_import_run"
    bl_label = "Import"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, ctx):
        from .collections import _active_level_col
        if _active_level_col(ctx.scene) is None:
            cls.poll_message_set("Create or pick a level first: the objects go into the active level")
            return False
        return any(r.pick for r in _state(ctx).rows)

    def execute(self, ctx):
        picked = [entry(r) for r in _state(ctx).rows if r.pick]
        picked = [e for e in picked if e is not None]
        by_cat = {}
        for e in picked:
            by_cat.setdefault(e["cat"], []).append(e)
        made, later, skipped = [], [], []
        for cat, label, _i in CATEGORIES:
            items = by_cat.get(cat)
            if not items:
                continue
            fn = IMPORTERS.get(cat)
            if fn is None:
                later.append(f"{len(items)} {label.lower()}")
                continue
            got = fn(ctx, items)
            if isinstance(got, tuple):
                got, sk = got
                skipped += sk
            made += got
        if made:
            for o in ctx.selected_objects:
                o.select_set(False)
            for o in made:
                o.select_set(True)
            ctx.view_layer.objects.active = made[0]
        msg = f"{len(made)} object(s) imported"
        if skipped:
            msg += f"; skipped {len(skipped)} (nothing to make them from): {', '.join(skipped[:5])}"
        if later:
            msg += f"; not importable yet: {', '.join(later)}"
        self.report({"WARNING"} if later or skipped else {"INFO"}, msg)
        return {"FINISHED"}


def _import_actors(ctx, entries):
    from .goal_import_actors import import_actors
    return import_actors(ctx, entries)


def _import_ambients(ctx, entries):
    from .goal_import_ambients import import_ambients
    return import_ambients(ctx, entries)


def _import_cameras(ctx, entries):
    from .goal_import_cameras import import_cameras
    return import_cameras(ctx, entries)


def _import_gc(fn):
    def run(ctx, entries):
        from . import goal_import_gc
        return getattr(goal_import_gc, fn)(ctx, entries)
    return run


# category -> fn(ctx, entries) -> [objects made] or ([objects made], [skipped names])
IMPORTERS = {"ACTORS": _import_actors, "AMBIENTS": _import_ambients, "CAMERAS": _import_cameras,
             "NAVMESHES": _import_gc("import_navmeshes"), "CHECKPOINTS": _import_gc("import_checkpoints"),
             "BOUNDARIES": _import_gc("import_boundaries")}


# ── UI ───────────────────────────────────────────────────────────────────────

class OG_UL_GoalImport(bpy.types.UIList):
    """One category's rows (list_id = the category)."""

    def draw_item(self, ctx, layout, data, item, icon, active_data, active_prop, index):
        row = layout.row(align=True)
        row.prop(item, "pick", text="")
        row.label(text=item.name)
        if item.info:
            sub = row.row()
            sub.enabled = False
            sub.label(text=item.info)

    def filter_items(self, ctx, data, prop):
        rows = getattr(data, prop)
        flt = [self.bitflag_filter_item if r.cat == self.list_id else 0 for r in rows]
        if self.filter_name:
            f = self.filter_name.lower()
            flt = [b if b and (f in r.name.lower() or f in r.info.lower()) else 0 for b, r in zip(flt, rows)]
        return flt, []


def draw_goal_import(layout, ctx):
    st = _state(ctx)
    row = layout.row(align=True)
    row.prop(st, "filepath", text="")
    row.operator("og.goal_import_load", text="Load", icon="IMPORT")
    layout.operator("og.goal_import_paste", icon="PASTEDOWN")
    if not st.rows:
        layout.label(text="Load a file or paste copied text", icon="INFO")
        return
    counts = {}
    for r in st.rows:
        n, p = counts.get(r.cat, (0, 0))
        counts[r.cat] = (n + 1, p + int(r.pick))
    row = layout.row(align=True)
    row.operator("og.goal_import_pick", text="Select All", icon="CHECKBOX_HLT").pick = True
    row.operator("og.goal_import_pick", text="Deselect All", icon="CHECKBOX_DEHLT").pick = False
    row.operator("og.goal_import_clear", text="", icon="TRASH")
    for cat, label, icon in CATEGORIES:
        if cat not in counts:
            continue
        n, p = counts[cat]
        head, body = layout.panel(f"og_goal_import_{cat}", default_closed=True)
        hr = head.row(align=True)
        hr.label(text=f"{label}  ({p} / {n})", icon=icon)
        op = hr.operator("og.goal_import_pick", text="", icon="CHECKBOX_HLT", emboss=False)
        op.cat, op.pick = cat, True
        op = hr.operator("og.goal_import_pick", text="", icon="CHECKBOX_DEHLT", emboss=False)
        op.cat, op.pick = cat, False
        if body:
            body.template_list("OG_UL_GoalImport", cat, st, "rows", st, "active", rows=6)
    total = sum(p for _n, p in counts.values())
    r = layout.row()
    r.scale_y = 1.3
    r.operator("og.goal_import_run", text=f"Import {total} picked", icon="IMPORT")


CLASSES = (
    OGImportRow, OGGoalImport,
    OG_OT_GoalImportLoad, OG_OT_GoalImportPaste, OG_OT_GoalImportClear, OG_OT_GoalImportPick, OG_OT_GoalImportRun,
    OG_UL_GoalImport,
)


def register_props():
    bpy.types.WindowManager.og_goal_import = PointerProperty(type=OGGoalImport)


def unregister_props():
    if hasattr(bpy.types.WindowManager, "og_goal_import"):
        del bpy.types.WindowManager.og_goal_import
