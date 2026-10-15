"""Required fields of actors, in one place: the panels' warning counts, the
warning next to Export & Compile and the audit all use these.

Required today: link slots marked "required" in the database, and required
paths (the Path panel's "required" option: path, pathb ...). Results for the
whole level are cached and only recomputed after an edit (depsgraph update).
"""
from __future__ import annotations

import bpy

from . import db as _db
from .data import _actor_link_slots, _actor_get_link, _actor_multi_links


def actor_etype(o):
    """etype of an ACTOR_<etype>_... empty (not its waypoints), else None."""
    if o is None or o.type != "EMPTY" or not o.name.startswith("ACTOR_"):
        return None
    if "_wp_" in o.name or "_wpb_" in o.name:
        return None
    parts = o.name.split("_", 2)
    return parts[1] if len(parts) >= 3 else None


def _has_path(o, name, scene):
    if name == "path":
        if len(getattr(o, "og_waypoint_sources", ())):
            return True
        prefix = o.name + "_wp_"          # legacy waypoint empties
        return any(ob.name.startswith(prefix) and ob.name[len(prefix):].isdigit() for ob in scene.objects)
    return any(p.name.strip() == name and len(p.sources) for p in getattr(o, "og_extra_paths", ()))


def missing(o, scene=None):
    """Missing required fields of an actor: [{"panel": "links" | "path",
    "key": lump name, "label": text}] (empty when nothing is missing)."""
    et = actor_etype(o)
    if not et:
        return []
    scene = scene or bpy.context.scene
    out = []
    for slot in _actor_link_slots(et):
        lkey, sidx = slot[0], slot[1]
        label = slot[2] if len(slot) > 2 else lkey
        required = slot[4] if len(slot) > 4 else False
        if not required:
            continue
        if _db.link_slot(et, lkey, sidx).get("allow-multiple"):
            filled = bool(_actor_multi_links(o, lkey, sidx))
        else:
            e = _actor_get_link(o, lkey, sidx)
            filled = bool(e and e.target_name and scene.objects.get(e.target_name))
        if not filled:
            out.append({"panel": "links", "key": lkey, "slot": sidx, "label": f"{lkey} ({label})" if label != lkey else lkey})
    if not _actor_get_link(o, "path-actor", 0):      # path-actor: every path read from that actor
        for name in _db._path_required(et):
            if not _has_path(o, name, scene):
                out.append({"panel": "path", "key": name, "label": f"{name} (path)"})
    return out


def summary(items, header="Missing"):
    n = len(items)
    lines = [f"{header} {n} required field{'s' if n != 1 else ''}:"]
    lines += [f"- {m['label']}" for m in items]
    return "\n".join(lines)


def draw_header_count(layout, obj, panel=None):
    """Panel header: "N ⚠" when the actor misses required fields (panel =
    "links" / "path" / None for all). Hover lists them, click opens a popup
    to fill them in."""
    items = [m for m in missing(obj) if panel is None or m["panel"] == panel]
    if not items:
        return
    row = layout.row(align=True)
    row.alert = True
    op = row.operator("og.required_popup", text=f"{len(items)} ⚠", emboss=False)
    op.actor_name = obj.name
    op.panel = panel or ""


class OG_OT_RequiredPopup(bpy.types.Operator):
    bl_idname = "og.required_popup"
    bl_label = "Missing Required Fields"
    actor_name: bpy.props.StringProperty()
    panel: bpy.props.StringProperty()        # "" = every panel

    @classmethod
    def description(cls, ctx, props):
        ob = bpy.data.objects.get(props.actor_name)
        items = [m for m in missing(ob) if not props.panel or m["panel"] == props.panel] if ob else []
        return summary(items) + "\nClick to fill them in."

    def invoke(self, ctx, event):
        return ctx.window_manager.invoke_popup(self, width=380)

    def execute(self, ctx):
        return {"FINISHED"}

    def draw(self, ctx):
        layout = self.layout
        ob = bpy.data.objects.get(self.actor_name)
        if ob is None:
            layout.label(text="Actor not found", icon="ERROR")
            return
        items = [m for m in missing(ob, ctx.scene) if not self.panel or m["panel"] == self.panel]
        layout.label(text=f"{ob.name}: {len(items)} required field(s) missing", icon="ERROR")
        if not items:
            layout.label(text="Nothing missing", icon="CHECKMARK")
            return
        from .panels.selected import _draw_link_slot
        from .panels.actor import _draw_path_add
        et = actor_etype(ob)
        sel_actors = [o for o in ctx.selected_objects if o != ob and actor_etype(o)]
        for m in items:
            box = layout.box()
            if m["panel"] == "links":
                slot = next((s for s in _actor_link_slots(et) if s[0] == m["key"] and s[1] == m.get("slot", 0)), None)
                if slot:
                    box.label(text=m["key"], icon="LINKED")
                    _draw_link_slot(box, ob, ctx.scene, et, slot[0], slot[1], slot[2], slot[3], True, sel_actors)
            elif m["panel"] == "path":
                box.label(text=f"{m['key']}: no path", icon="ANIM")
                if m["key"] == "path":
                    _draw_path_add(box, ob, ctx.scene, ob.og_waypoint_sources)
                else:
                    box.label(text="Add it in the Path panel (Add Path)", icon="INFO")


CLASSES = (OG_OT_RequiredPopup,)


# ── level-wide, cached ──────────────────────────────────────────────────────
_CACHE = {"dirty": True, "by_actor": {}}


def mark_dirty(*_a):
    _CACHE["dirty"] = True


def level_missing(scene):
    """{actor name: missing list} for every actor of the active level with
    something missing. Cached until the next edit."""
    if _CACHE["dirty"]:
        from .collections import _level_objects
        res = {}
        for o in _level_objects(scene):
            m = missing(o, scene)
            if m:
                res[o.name] = m
        _CACHE["by_actor"] = res
        _CACHE["dirty"] = False
    return _CACHE["by_actor"]


@bpy.app.handlers.persistent
def _on_depsgraph(scene, depsgraph):
    _CACHE["dirty"] = True


@bpy.app.handlers.persistent
def _on_load(*_a):
    _CACHE["dirty"] = True


def register_handlers():
    for hl, f in ((bpy.app.handlers.depsgraph_update_post, _on_depsgraph), (bpy.app.handlers.load_post, _on_load)):
        for old in [x for x in hl if getattr(x, "__name__", "") == f.__name__ and getattr(x, "__module__", "").endswith(".required")]:
            hl.remove(old)
        hl.append(f)


def unregister_handlers():
    for hl, f in ((bpy.app.handlers.depsgraph_update_post, _on_depsgraph), (bpy.app.handlers.load_post, _on_load)):
        if f in hl:
            hl.remove(f)
