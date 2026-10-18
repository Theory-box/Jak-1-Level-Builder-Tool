"""Required fields of actors, in one place: the panels' warning counts, the
warning next to Export & Compile and the audit all use these.

Required today: link slots marked "required" in the database, required
paths (the Path panel's "required" option: path, pathb ...), and the sound
bank of a sound emitter's / particle spawner's sound (actors' own sounds:
see community-feedback/Actor Notes.md). Results for the
whole level are cached and only recomputed after an edit (depsgraph update).

Soft warnings (soft()): setups that don't break the game or the build but
make an actor do nothing useful (a nav-enemy with no nav-mesh, nav-mesh
parts / jump areas enemies can't use). Shown as a second, yellow count.
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


def _has_path(o, name, scene, names=None):
    if name == "path":
        if len(getattr(o, "og_waypoint_sources", ())):
            return True
        prefix = o.name + "_wp_"          # legacy waypoint empties
        return any(n.startswith(prefix) and n[len(prefix):].isdigit()
                   for n in (names if names is not None else (ob.name for ob in scene.objects)))
    return any(p.name.strip() == name and len(p.sources) for p in getattr(o, "og_extra_paths", ()))


def _sound_banks(scene):
    """(banks the level loads, {sound: banks it's in})."""
    from .collections import _get_level_prop
    loaded = {"common"} | {str(_get_level_prop(scene, k, "none") or "none").lower()
                           for k in ("og_sound_bank_1", "og_sound_bank_2")}
    where = {}
    for bank, sounds in _db.bank_sfx().items():
        for s in sounds:
            where.setdefault(s, set()).add(bank)
    return loaded, where


def object_sound(o):
    """The sound a sound emitter / particle spawner plays, else None."""
    if o.name.startswith("AMBIENT_") and o.get("og_sound_name"):
        return str(o["og_sound_name"]).split("__")[0]
    if actor_etype(o) == "part-spawner" and str(o.get("og_part_sound", "none")) not in ("", "none"):
        return str(o["og_part_sound"]).split("__")[0]
    return None


def missing_bank(o, scene, banks=None):
    """[{"panel": "sound", ...}] when the object's sound is in a bank the level
    doesn't load (common or one of its two sound banks)."""
    snd = object_sound(o)
    if not snd:
        return []
    loaded, where = banks or _sound_banks(scene)
    found = where.get(snd)
    if found and not (found & loaded):
        b = " / ".join(sorted(found))
        return [{"panel": "sound", "key": b, "sound": snd, "label": f"sound bank {b} (for {snd})"}]
    return []


def missing(o, scene=None, names=None, banks=None):
    """Missing required fields of an actor (and the sound bank a sound
    emitter / particle spawner needs): [{"panel": "links" | "path" | "sound",
    "key": lump / bank name, "label": text}] (empty when nothing is missing)."""
    scene = scene or bpy.context.scene
    et = actor_etype(o)
    if not et:
        return missing_bank(o, scene, banks)
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
    nm = scene.objects.get(o.get("og_navmesh_link", "") or "")
    if nm is not None:                                # the linked nav-mesh's problems
        from .export.navmesh import nav_issues
        for issue in nav_issues(nm):
            out.append({"panel": "nav", "key": nm.name, "label": f"nav-mesh: {issue}"})
    if not _actor_get_link(o, "path-actor", 0):      # path-actor: every path read from that actor
        for name in _db._path_required(et):
            if not _has_path(o, name, scene, names):
                out.append({"panel": "path", "key": name, "label": f"{name} (path)"})
    return out + missing_bank(o, scene, banks)


def actor_banks_missing(et, scene, banks=None):
    """[(bank choices, [sounds])] for the actor's sounds (DB "sounds": the ones
    its code and art play that aren't in common) whose bank the level doesn't
    load. A sound in several banks needs any one of them."""
    snds = (_db.find_actor(et) or {}).get("sounds") or []
    if not snds:
        return []
    loaded, where = banks or _sound_banks(scene)
    groups = {}
    for x in snds:
        b = where.get(x)
        if b and not (b & loaded):
            groups.setdefault(tuple(sorted(b)), []).append(x)
    return sorted(groups.items())


def soft(o, scene=None, banks=None):
    """Soft warnings of an actor: [{"panel", "key", "label"}]."""
    scene = scene or bpy.context.scene
    et = actor_etype(o)
    if not et:
        return []
    out = []
    for choice, snds in actor_banks_missing(et, scene, banks):   # silent sounds
        b = " / ".join(choice)
        more = f" +{len(snds) - 3}" if len(snds) > 3 else ""
        out.append({"panel": "sound", "key": b, "sound": snds[0],
                    "label": f"sound bank {b} not loaded: no {', '.join(snds[:3])}{more}"})
    if _db.panel_exports(et, "nav-mesh") and _db.nav_unsafe(et):
        nm = scene.objects.get(o.get("og_navmesh_link", "") or "")
        if nm is None and not _actor_get_link(o, "nav-mesh-actor", 0):
            out.append({"panel": "nav", "key": "", "label": "no nav-mesh: it idles / notices Jak but can't pathfind"})
        if nm is not None:
            from .export.navmesh import nav_soft_issues
            for issue in nav_soft_issues(nm):
                out.append({"panel": "nav", "key": nm.name, "label": f"nav-mesh: {issue}"})
    return out


def summary(items, header="Missing"):
    n = len(items)
    lines = [f"{header} {n} required field{'s' if n != 1 else ''}:"]
    lines += [f"- {m['label']}" for m in items]
    return "\n".join(lines)


def draw_header_count(layout, obj, panel=None):
    """Panel header: "N ⚠" when the actor misses required fields (panel =
    "links" / "path" / "nav" / None for all). Hover lists them, click opens a popup
    to fill them in."""
    items = [m for m in missing(obj) if panel is None or m["panel"] == panel]
    if items:
        row = layout.row(align=True)
        row.alert = True
        row.ui_units_x = 1.2 + 0.4 * len(str(len(items)))     # as wide as "N⚠"
        op = row.operator("og.required_popup", text=f"{len(items)}⚠", emboss=False)
        op.actor_name = obj.name
        op.panel = panel or ""
    sitems = [m for m in soft(obj) if panel is None or m["panel"] == panel]
    if sitems:                                           # soft: yellow triangle, no red
        row = layout.row(align=True)
        row.ui_units_x = 1.6 + 0.4 * len(str(len(sitems)))
        op = row.operator("og.required_popup", text=str(len(sitems)), icon="ERROR", emboss=False)
        op.actor_name = obj.name
        op.panel = panel or ""
        op.soft = True


class OG_OT_RequiredPopup(bpy.types.Operator):
    bl_idname = "og.required_popup"
    bl_label = "Missing Required Fields"
    actor_name: bpy.props.StringProperty()
    panel: bpy.props.StringProperty()        # "" = every panel
    soft: bpy.props.BoolProperty()           # the soft warnings instead

    @classmethod
    def description(cls, ctx, props):
        ob = bpy.data.objects.get(props.actor_name)
        if props.soft:
            items = [m for m in soft(ob) if not props.panel or m["panel"] == props.panel] if ob else []
            return soft_summary(items)
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
        if self.soft:
            items = [m for m in soft(ob, ctx.scene) if not self.panel or m["panel"] == self.panel]
            layout.label(text=f"{ob.name}: {len(items)} soft warning(s)", icon="ERROR")
            layout.label(text="It works, but this setup makes it do less than it could:", icon="INFO")
            for m in items:
                layout.box().label(text=m["label"], icon="DOT")
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
            elif m["panel"] == "sound":
                box.label(text=f"'{m['sound']}' is in the {m['key']} sound bank", icon="SPEAKER")
                box.label(text="Load it: Level > Settings > Sound & Music", icon="INFO")
            elif m["panel"] == "nav":
                box.label(text=f"{m['key']}: {m['label'][len('nav-mesh: '):]}", icon="MOD_MESHDEFORM")
            elif m["panel"] == "path":
                box.label(text=f"{m['key']}: no path", icon="ANIM")
                if m["key"] == "path":
                    _draw_path_add(box, ob, ctx.scene, ob.og_waypoint_sources)
                else:
                    box.label(text="Add it in the Path panel (Add Path)", icon="INFO")


def soft_summary(items):
    n = len(items)
    return "\n".join([f"{n} soft warning{'s' if n != 1 else ''} (works, but does less):"] + [f"- {m['label']}" for m in items])


def level_summary(by_actor):
    n = sum(len(v) for v in by_actor.values())
    lines = [f"{n} required field{'s' if n != 1 else ''} missing:"]
    for name, items in by_actor.items():
        lines.append(f"{name} is missing {len(items)}:")
        lines += [f"  - {m['label']}" for m in items]
    return "\n".join(lines)


def draw_level_count(layout, scene, row_scale=1.0):
    """Next to Export & Compile: the level's warnings ("N⚠", cached) in one
    column as wide as the text. One kind of warning takes the row's full
    height; more kinds later split it (row_scale: unused, kept for callers)."""
    by_actor = level_missing(scene)
    n = sum(len(v) for v in by_actor.values())
    ns = sum(len(v) for v in level_soft(scene).values())
    entries = ([(False, f"{n}⚠")] if n else []) + ([(True, str(ns))] if ns else [])
    if not entries:
        return
    col = layout.column(align=True)
    col.ui_units_x = 1.6 + 0.4 * max(len(t) - 1 for _s, t in entries)
    for is_soft, text in entries:
        r = col.row(align=True)
        r.scale_y = 1.0 / len(entries)
        r.alert = not is_soft                                # required red, soft a yellow triangle
        op = r.operator("og.required_level_popup", text=text, icon="ERROR" if is_soft else "NONE", emboss=False)
        op.soft = is_soft


class OG_OT_RequiredLevelPopup(bpy.types.Operator):
    bl_idname = "og.required_level_popup"
    bl_label = "Missing Required Fields (Level)"
    soft: bpy.props.BoolProperty()

    @classmethod
    def description(cls, ctx, props):
        if props.soft:
            by = level_soft(ctx.scene)
            n = sum(len(v) for v in by.values())
            return "\n".join([f"{n} soft warning{'s' if n != 1 else ''} (works, but does less):"]
                             + [f"{a}: {m['label']}" for a, v in by.items() for m in v]) + "\nClick to see them."
        return level_summary(level_missing(ctx.scene)) + "\nClick to see them."

    def invoke(self, ctx, event):
        return ctx.window_manager.invoke_popup(self, width=420)

    def execute(self, ctx):
        return {"FINISHED"}

    def draw(self, ctx):
        layout = self.layout
        by_actor = level_soft(ctx.scene) if self.soft else level_missing(ctx.scene)
        if not by_actor:
            layout.label(text="Nothing missing", icon="CHECKMARK")
            return
        if self.soft:
            layout.label(text="Soft warnings: these work, but do less than they could", icon="ERROR")
            for name, items in by_actor.items():
                box = layout.box()
                op = box.row().operator("og.select_and_frame", text=name, icon="RESTRICT_SELECT_OFF")
                op.obj_name = name
                col = box.column(align=True); col.scale_y = 0.8
                for m in items:
                    col.label(text=m["label"], icon="DOT")
            return
        layout.label(text="Click an actor to select it; its header warning fills the fields in", icon="INFO")
        for name, items in by_actor.items():
            box = layout.box()
            row = box.row(align=True)
            op = row.operator("og.select_and_frame", text=name, icon="RESTRICT_SELECT_OFF")
            op.obj_name = name
            op = row.operator("og.required_popup", text=f"{len(items)} ⚠")
            op.actor_name = name; op.panel = ""
            col = box.column(align=True); col.scale_y = 0.8
            for m in items:
                col.label(text=m["label"], icon="DOT")


CLASSES = (OG_OT_RequiredPopup, OG_OT_RequiredLevelPopup)


# ── level-wide, cached ──────────────────────────────────────────────────────
_CACHE = {"dirty": True, "by_actor": {}, "soft": {}, "t": 0.0}
_MAX_AGE = 1.0      # s: some edits (link / path collections) send no depsgraph update


def mark_dirty(*_a):
    _CACHE["dirty"] = True


def level_missing(scene):
    """{actor name: missing list} for every actor of the active level with
    something missing. Cached until the next edit (or for at most _MAX_AGE:
    link / path list edits don't always send a depsgraph update)."""
    import time
    now = time.monotonic()
    if _CACHE["dirty"] or now - _CACHE["t"] > _MAX_AGE:
        from .collections import _level_objects
        res = {}
        objs = _level_objects(scene)
        wp = {ob.name for ob in objs if "_wp_" in ob.name}     # legacy waypoints, looked up once
        banks = _sound_banks(scene)
        sres = {}
        for o in objs:
            m = missing(o, scene, wp, banks)
            if m:
                res[o.name] = m
            s = soft(o, scene, banks)
            if s:
                sres[o.name] = s
        _CACHE["by_actor"] = res
        _CACHE["soft"] = sres
        _CACHE["dirty"] = False
        _CACHE["t"] = now
    return _CACHE["by_actor"]


def level_soft(scene):
    """{actor name: soft warnings} of the active level (same cache as level_missing)."""
    level_missing(scene)
    return _CACHE["soft"]


@bpy.app.handlers.persistent
def _on_depsgraph(scene, depsgraph):
    """Any edit except moving things (transform-only updates, every frame
    while dragging) may change what's missing."""
    if _CACHE["dirty"]:
        return
    for u in depsgraph.updates:
        if not (u.is_updated_transform and not u.is_updated_geometry and not u.is_updated_shading):
            _CACHE["dirty"] = True
            _redraw_sidebars()          # the Export & Compile count shows the new list
            return


def _redraw_sidebars():
    try:
        for w in bpy.context.window_manager.windows:
            for a in w.screen.areas:
                if a.type == "VIEW_3D":
                    for r in a.regions:
                        if r.type == "UI":
                            r.tag_redraw()
    except Exception:
        pass


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
