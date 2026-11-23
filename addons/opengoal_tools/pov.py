"""Camera animations (pov-camera): the game's list (DB "PovCameras"), the
picker for an actor's camera animation, and what a level needs to play one.

A field of type "pov_camera" (DB) stores on the object:
    <key>_cam         camera art group id (a PovCameras key) or "custom"
    <key>_cam_custom  typed art group name (without -ag.go)
    <key>_anim        animation name or "custom"
    <key>_anim_custom typed animation name
and exports the lumps
    pov-sg    ["symbol", "*og-pov-<group id>-sg*"]   the skeleton group to play
    pov-anim  ["string", "<animation>"]
The level's -obs.gc defines those skeleton groups (skel_lines) and the level
loads the camera art group (art_groups). Actors read the symbol's value at run
time, so the shared edited-actor files need nothing level specific.
"""
from __future__ import annotations

import bpy

from . import db as _db


def catalogue() -> dict:
    """{group id: {group, file, jg, mg, default, label, anims {name: description}}}."""
    return _db.DB.get("PovCameras", {}) or {}


def anims(group_id: str) -> dict:
    return dict((catalogue().get(group_id) or {}).get("anims") or {})


def entry(group_id: str) -> dict:
    """The catalogue entry, or one built from the usual naming for a typed group."""
    e = catalogue().get(group_id)
    if e:
        return e
    g = group_id[:-len("-ag.go")] if group_id.endswith("-ag.go") else group_id
    return {"group": g, "file": f"{g}-ag.go", "jg": f"{g}-lod0-jg", "mg": f"{g}-lod0-mg", "default": None}


def picked(get, key: str) -> tuple[str, str]:
    """(group id, animation) picked in the field `key` ("" when unset)."""
    g = str(get(f"{key}_cam", "") or "")
    if g == "custom":
        g = str(get(f"{key}_cam_custom", "") or "").strip()
    if g.endswith("-ag.go"):
        g = g[:-len("-ag.go")]
    a = str(get(f"{key}_anim", "") or "")
    if a == "custom":
        a = str(get(f"{key}_anim_custom", "") or "").strip()
    return g, a


def skel_name(group_id: str) -> str:
    return f"*og-pov-{group_id}-sg*"


def lumps(group_id: str, anim: str) -> dict:
    if not (group_id and anim):
        return {}
    return {"pov-sg": ["symbol", skel_name(group_id)], "pov-anim": ["string", anim]}


def skel_lines(group_ids) -> list[str]:
    """defskelgroup for each camera art group used in the level."""
    out = []
    for gid in sorted(set(g for g in group_ids if g)):
        e = entry(gid)
        g = e["group"]
        default = e.get("default") or f"{g}-{next(iter(anims(gid)), 'anim')}-ja"
        out += ["", f"(defskelgroup {skel_name(gid)}", f"  {g}", f"  {e['jg']}", f"  {default}",
                f"  (({e['mg']} (meters 999999)))", "  :bounds (static-spherem 0 0 0 20))"]
    return out


def art_file(group_id: str) -> str:
    return entry(group_id)["file"] if group_id else ""


# ── which objects use which camera ─────────────────────────────────────────

def fields_of(etype: str) -> list:
    return [f for f in _db.inherited_fields(etype) if f.get("type") == "pov_camera"]


def _active(o, f) -> bool:
    """A pov_camera field only counts while its visible_if holds (e.g. the actor's
    shot set to "Camera animation")."""
    vi = f.get("visible_if") or {}
    for k, v in vi.items():
        cur = o.get(k, None)
        if cur is None:
            fd = next((x for x in _db.inherited_fields(_etype(o)) if x.get("key") == k), {})
            cur = fd.get("default")
        if (cur not in v) if isinstance(v, list) else (cur != v):
            return False
    return True


def _etype(o):
    from .collections import actor_etype
    return actor_etype(o) or ""


def used(o) -> list[tuple[str, str]]:
    """[(group id, animation)] the object plays."""
    et = _etype(o)
    if not et:
        return []
    get = lambda k, d=None: o.get(k, d)
    out = []
    for f in fields_of(et):
        if _active(o, f):
            g, a = picked(get, f["key"])
            if g and a:
                out.append((g, a))
    return out


def library_needed(objects) -> bool:
    """An actor with camera choices (an enum with a choice marked "pov" in the DB: 1 normal
    camera, 2 camera animation, 3 Camera animation actor) calls the lt-pov-play library
    whatever is picked, so the level must load it."""
    return any(_has_pov_choices(_etype(o)) for o in objects)


_POV_ETYPES: dict = {}


def _has_pov_choices(et) -> bool:
    if not et:
        return False
    if _POV_ETYPES.get("__db") is not _db.DB:      # the database was reloaded
        _POV_ETYPES.clear()
        _POV_ETYPES["__db"] = _db.DB
    v = _POV_ETYPES.get(et)
    if v is None:
        v = _POV_ETYPES[et] = any(
            f.get("type") == "enum" and isinstance(f.get("choices"), list) and any(c.get("pov") for c in f["choices"])
            for f in _db.inherited_fields(et))
    return v


def level_groups(objects) -> list[str]:
    return sorted({g for o in objects for g, _a in used(o)})


# ── picker UI ──────────────────────────────────────────────────────────────

def draw(layout, o, field):
    """Art group + animation pickers (search popups), Custom… for typed names."""
    key = field["key"]
    label = field.get("label", "Camera animation")
    box = layout.box()
    box.label(text=label, icon="CAMERA_DATA")
    g = str(o.get(f"{key}_cam", "") or "")
    a = str(o.get(f"{key}_anim", "") or "")
    cat = catalogue()
    row = box.row(align=True)
    row.label(text="Camera:")
    gl = "Custom…" if g == "custom" else (cat.get(g, {}).get("label", g) if g else "Pick…")
    op = row.operator("og.pov_pick", text=gl, icon="VIEWZOOM"); op.key, op.what = key, "cam"
    if g == "custom":
        _custom_row(box, o, f"{key}_cam_custom", "Art group", "Type an art group")
    row = box.row(align=True)
    row.enabled = bool(g)
    row.label(text="Animation:")
    al = "Custom…" if a == "custom" else (a or "Pick…")
    op = row.operator("og.pov_pick", text=al, icon="VIEWZOOM"); op.key, op.what = key, "anim"
    if a == "custom":
        _custom_row(box, o, f"{key}_anim_custom", "Animation", "Type an animation")
    elif g in cat and a in anims(g):
        r = box.row(); r.enabled = False; r.scale_y = 0.8
        r.label(text=anims(g)[a], icon="INFO")
    if g and g in cat:
        r = box.row(); r.enabled = False; r.scale_y = 0.8
        r.label(text=f"Loads {cat[g]['file']}", icon="FILE")


def _custom_row(box, o, prop, label, add_text):
    if prop in o:
        box.prop(o, f'["{prop}"]', text=label)
    else:
        box.operator("og.pov_init_custom", text=add_text, icon="GREASEPENCIL").prop = prop


_ITEMS: list = []


def _items(self, ctx):
    o = ctx.active_object if ctx else None
    cat = catalogue()
    if self.what == "cam":
        items = [("custom", "Custom…", "Type a camera art group name")]
        items += [(gid, f"{e.get('label', gid)}  ({gid}, {len(e.get('anims', {}))})", e.get("file", ""))
                  for gid, e in sorted(cat.items(), key=lambda kv: kv[1].get("label", kv[0]))]
    else:
        g = str(o.get(f"{self.key}_cam", "") or "") if o else ""
        items = [("custom", "Custom…", "Type an animation name")]
        items += [(a, f"{a}  —  {d}", d) for a, d in anims(g).items()]
    _ITEMS[:] = [(a, b, c, i) for i, (a, b, c) in enumerate(items)]
    return _ITEMS


class OG_OT_PovPick(bpy.types.Operator):
    """Pick the camera animation's art group or animation (search), or Custom… to type one"""
    bl_idname = "og.pov_pick"
    bl_label = "Pick Camera Animation"
    bl_options = {"REGISTER", "UNDO"}
    bl_property = "pick"
    key: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    what: bpy.props.StringProperty(default="cam", options={"HIDDEN", "SKIP_SAVE"})
    pick: bpy.props.EnumProperty(name="Camera", items=_items)

    def invoke(self, ctx, event):
        ctx.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, ctx):
        o = ctx.active_object
        if o is None or not self.key:
            return {"CANCELLED"}
        if self.what == "cam":
            o[f"{self.key}_cam"] = self.pick
            names = list(anims(self.pick))
            if str(o.get(f"{self.key}_anim", "")) not in names + ["custom"]:
                o[f"{self.key}_anim"] = names[0] if names else "custom"
        else:
            o[f"{self.key}_anim"] = self.pick
        return {"FINISHED"}


class OG_OT_PovInitCustom(bpy.types.Operator):
    """Add the text field to type the name in"""
    bl_idname = "og.pov_init_custom"
    bl_label = "Type a Name"
    bl_options = {"REGISTER", "UNDO"}
    prop: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    def execute(self, ctx):
        o = ctx.active_object
        if o is None or not self.prop:
            return {"CANCELLED"}
        o[self.prop] = ""
        return {"FINISHED"}


CLASSES = (OG_OT_PovPick, OG_OT_PovInitCustom)
