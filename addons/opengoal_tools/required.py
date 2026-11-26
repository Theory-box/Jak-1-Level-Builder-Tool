"""Required fields of actors, in one place: the panels' warning counts, the
warning next to Export & Compile and the audit all use these.

Required today: schema task/object-reference fields and link slots marked
"required" in the database, required
paths (the Path panel's "required" option: path, pathb ...), and the sound
bank of a sound emitter's / particle spawner's sound (actors' own sounds:
see community-feedback/Actor Notes.md). Results for the
whole level are cached and only recomputed after an edit (depsgraph update).

Soft warnings (soft()): setups that don't break the game or the build but
make an actor do nothing useful (a nav-enemy with no nav-mesh, nav-mesh
parts / jump areas enemies can't use). Shown as a second, grey count.

Warning types (WARNING_TYPES) can be ignored per .blend in Developer Tools ›
Warning Settings: missing() / soft() leave them out, so counts and the audit
follow.
"""
from __future__ import annotations

import bpy

from . import db as _db
from .collections import actor_etype
from .data import _actor_link_slots, _actor_get_link, _actor_multi_links


# ── Warning types (Developer Tools › Warning Settings: ignore some, per .blend) ─
# (key, label, red). Every warning dict gets "type": one of these keys.
WARNING_TYPES = (
    ("req_link", "Required link missing", True),
    ("req_path", "Required path missing", True),
    ("req_field", "Required field or task not set", True),
    ("req_sound", "Sound emitter's sound bank not loaded", True),
    ("req_nav", "Linked nav-mesh problems", True),
    ("soft_trigger", "Nothing sends it 'trigger", False),
    ("soft_sound", "Actor's sound bank not loaded (silent sounds)", False),
    ("soft_link", "Optional link missing", False),
    ("soft_linked_by", "Not linked by the actor that should link it", False),
    ("soft_no_nav", "No nav-mesh (idles, can't chase)", False),
    ("soft_nav", "Nav-mesh soft issues", False),
    # Level > Settings > Visuals (moods, oceans)
    ("mood_clash", "Mood: slot used by time of day and an effect", False),
    ("mood_undriven", "Mood: Light switch / crystal slot won't light", False),
    ("ocean_map", "Ocean map not found / not exported", True),
    ("ocean_no_water", "Ocean: no water volume", False),
    ("ocean_past_grid", "Ocean: level past the ocean grid", False),
)


def ignored(scene, kind):
    """Is this warning type ignored (Warning Settings)?"""
    return kind in _ignored(scene)


def _warning_changed(self, ctx):
    mark_dirty()
    _redraw_sidebars()


OGWarningSettings = type("OGWarningSettings", (bpy.types.PropertyGroup,), {"__annotations__": {
    k: bpy.props.BoolProperty(name=label, default=False, update=_warning_changed,
                              description=("Required: the level may crash or not build. " if red else "")
                              + "On: these warnings don't show in the counts or the Level Audit")
    for k, label, red in WARNING_TYPES}})


def _ignored(scene):
    s = getattr(scene, "og_warnings", None)
    return {k for k, _l, _r in WARNING_TYPES if s is not None and getattr(s, k)}


def _keep(items, scene, kind):
    """Tag items without a type with `kind`, drop the ignored types."""
    ign = _ignored(scene)
    out = []
    for m in items:
        m.setdefault("type", kind)
        if m["type"] not in ign:
            out.append(m)
    return out


def draw_warning_settings(layout, scene):
    s = scene.og_warnings
    col = layout.column(align=True)
    col.label(text="Ignore warnings:")
    for k, label, red in WARNING_TYPES:
        r = col.row(align=True)
        r.alert = red
        r.prop(s, k, text=label + ("  (required)" if red else ""), icon="ERROR" if red else "INFO")
    h = layout.column(); h.enabled = False; h.scale_y = 0.7
    h.label(text="Red: the level may crash or not build", icon="INFO")
    h.label(text="Ignored: not counted, not in the Level Audit (this .blend)", icon="BLANK1")


def register_props():
    bpy.types.Scene.og_warnings = bpy.props.PointerProperty(type=OGWarningSettings)


def unregister_props():
    if hasattr(bpy.types.Scene, "og_warnings"):
        del bpy.types.Scene.og_warnings


def _has_path(o, name):
    if name == "path":
        return bool(len(getattr(o, "og_waypoint_sources", ())))
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
        return _keep([{"panel": "sound", "key": b, "sound": snd, "label": f"sound bank {b} (for {snd})"}],
                     scene, "req_sound")
    return []


def _pov_missing(o, et):
    """A camera choice that needs something: Camera animation with no animation picked,
    Camera animation actor with none linked."""
    from . import pov as _pov
    out = []
    get = lambda k, d=None: o.get(k, d)
    for f in _pov.fields_of(et):
        if _pov._active(o, f):
            g, a = _pov.picked(get, f["key"])
            if not (g and a):
                out.append({"panel": "custom-fields", "key": f["key"], "label": "camera animation not picked",
                            "type": "req_field"})
    if _pov._has_pov_choices(et):
        for f in _db.inherited_fields(et):
            ch = f.get("choices") if f.get("type") == "enum" else None
            if isinstance(ch, list) and any(c.get("pov") == 3 and c.get("value") == o.get(f["key"], f.get("default"))
                                            for c in ch):
                if not _actor_get_link(o, "pov-actor", 0):
                    out.append({"panel": "links", "key": "pov-actor", "slot": 0,
                                "label": "pov-actor (Camera animation actor to trigger)", "type": "req_link"})
    return out


def missing(o, scene=None, banks=None):
    """Missing required fields of an actor (and the sound bank a sound
    emitter / particle spawner needs): [{"panel": "links" | "path" | "sound",
    "key": lump / bank name, "label": text}] (empty when nothing is missing)."""
    scene = scene or bpy.context.scene
    et = actor_etype(o)
    if not et:
        return missing_bank(o, scene, banks)
    out = []
    # Required schema fields work for custom actors too; no per-etype rules.
    get = _db.prop_getter(o)
    for field in _db.inherited_fields(et):
        key = field.get("key")
        if not key or not field.get("required"):
            continue
        if field.get("type") == "object_ref":
            name = str(get(key, "") or "")
            target = scene.objects.get(name)
            kind = field.get("pick", "EMPTY")
            valid = target is not None and (target.name.startswith("CAMERA_") if kind == "CAMERA" else target.type == "EMPTY")
        elif field.get("type") == "task":
            valid = _db.task_expression(get, key) is not None
        else:
            continue
        if not valid:
            out.append({"panel": "game-task" if key == "og_game_task" else "custom-fields",
                        "key": key, "label": field.get("label", key), "type": "req_field"})
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
            out.append({"panel": "links", "key": lkey, "slot": sidx, "label": f"{lkey} ({label})" if label != lkey else lkey,
                        "type": "req_link"})
    out += _pov_missing(o, et)
    nm = scene.objects.get(o.get("og_navmesh_link", "") or "")
    if nm is not None:                                # the linked nav-mesh's problems
        from .export.navmesh import nav_issues
        for issue in nav_issues(nm):
            out.append({"panel": "nav", "key": nm.name, "label": f"nav-mesh: {issue}", "type": "req_nav"})
    if not _actor_get_link(o, "path-actor", 0):      # path-actor: every path read from that actor
        for name in _db._path_required(et):
            if not _has_path(o, name):
                help_text = _db.panel_option(et, "path", "path_help", {}).get(name, "")
                out.append({"panel": "path", "key": name, "label": f"{name}: {help_text}" if help_text else f"{name} (path)",
                            "type": "req_path"})
    return _keep(out, scene, "req_field") + missing_bank(o, scene, banks)


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


def trigger_senders(scene, objects=None):
    """{actor name: [sender names]}: actors an actor link sends 'trigger to
    (a link slot that accepts "event:trigger", e.g. a button's notify list)."""
    from .collections import _level_objects
    out = {}
    for s in (objects if objects is not None else _level_objects(scene)):
        et = actor_etype(s)
        if not et:
            continue
        slots = {(sl[0], sl[1]) for sl in _actor_link_slots(et) if any(str(a).startswith("event:trigger") for a in (sl[3] or []))}
        if not slots:
            continue
        for e in getattr(s, "og_actor_links", ()):
            if (e.lump_key, e.slot_index) in slots or (e.lump_key, 0) in slots:
                out.setdefault(e.target_name, []).append(s.name)
    return out


def _needs_trigger(o, et):
    """DB "needs_trigger": true, or {"unless_field": key} (that field set = it runs on its own)."""
    v = (_db.find_actor(et) or {}).get("needs_trigger")
    if isinstance(v, dict) and v.get("unless_field"):
        try:
            return not float(o.get(v["unless_field"], 0) or 0)
        except (TypeError, ValueError):
            return True
    return bool(v)


def linked_index(objects):
    """{(source etype, lump key): {target names}} of the given actors' links
    (built once per level check instead of scanning every object per actor)."""
    out = {}
    for x in objects:
        et = actor_etype(x)
        if et:
            for e in getattr(x, "og_actor_links", ()):
                if e.target_name:
                    out.setdefault((et, e.lump_key), set()).add(e.target_name)
    return out


def soft(o, scene=None, banks=None, senders=None, linked=None):
    """Soft warnings of an actor: [{"panel", "key", "label"}]."""
    scene = scene or bpy.context.scene
    et = actor_etype(o)
    if not et:
        return []
    out = []
    if _needs_trigger(o, et):
        snd = (senders if senders is not None else trigger_senders(scene)).get(o.name)
        if not snd:
            out.append({"panel": "links", "key": "trigger", "type": "soft_trigger",
                        "label": "nothing sends it 'trigger: it stays put (link it from a button's notify list)"})
    for choice, snds in actor_banks_missing(et, scene, banks):   # silent sounds
        b = " / ".join(choice)
        more = f" +{len(snds) - 3}" if len(snds) > 3 else ""
        out.append({"panel": "sound", "key": b, "sound": snds[0], "type": "soft_sound",
                    "label": f"sound bank {b} not loaded: no {', '.join(snds[:3])}{more}"})
    for sl in _db.link_slots(et):                          # links that only make it do less
        if sl.get("soft") and not _actor_get_link(o, sl["lump_key"], int(sl.get("slot", 0))):
            out.append({"panel": "links", "key": sl["lump_key"], "label": sl["soft"], "type": "soft_link"})
    lb = (_db.find_actor(et) or {}).get("soft_linked_by")   # an actor that should link this one
    if lb and not (lb.get("unless") and o.get(lb["unless"])):
        if linked is None:
            linked = linked_index(scene.objects)
        if o.name not in linked.get((lb["etype"], lb["lump_key"]), ()):
            out.append({"panel": "links", "key": lb["etype"], "label": lb["label"], "type": "soft_linked_by"})
    if _db.panel_exports(et, "nav-mesh") and _db.nav_unsafe(et):
        nm = scene.objects.get(o.get("og_navmesh_link", "") or "")
        if nm is None and not _actor_get_link(o, "nav-mesh-actor", 0):
            out.append({"panel": "nav", "key": "", "label": "no nav-mesh: it idles / notices Jak but can't pathfind",
                        "type": "soft_no_nav"})
        if nm is not None:
            from .export.navmesh import nav_soft_issues
            for issue in nav_soft_issues(nm):
                out.append({"panel": "nav", "key": nm.name, "label": f"nav-mesh: {issue}", "type": "soft_nav"})
    return _keep(out, scene, "soft_link")


def summary(items, header="Missing"):
    n = len(items)
    lines = [f"{header} {n} required field{'s' if n != 1 else ''}:"]
    lines += [f"- {m['label']}" for m in items]
    return "\n".join(lines)


def draw_header_count(layout, obj, panel=None):
    """Panel header: "N ⚠" when the actor misses required fields (panel =
    "links" / "path" / "nav" / None for all). Hover lists them, click opens a popup
    to fill them in."""
    items = [m for m in actor_missing(obj) if panel is None or m["panel"] == panel]
    if items:
        row = layout.row(align=True)
        row.alert = True
        row.ui_units_x = 1.2 + 0.4 * len(str(len(items)))     # as wide as "N⚠"
        op = row.operator("og.required_popup", text=f"{len(items)}⚠", emboss=False)
        op.actor_name = obj.name
        op.panel = panel or ""
    sitems = [m for m in actor_soft(obj) if panel is None or m["panel"] == panel]
    if sitems:                                           # soft: yellow triangle, no red
        row = layout.row(align=True)
        row.ui_units_x = 1.2 + 0.4 * len(str(len(sitems)))
        op = row.operator("og.required_popup", text=f"{len(sitems)}⚠", emboss=False)
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
                box.label(text=f"Missing {m['label']}", icon="ANIM")
                if m["key"] == "path":
                    _draw_path_add(box, ob, ctx.scene, ob.og_waypoint_sources)
                else:
                    box.label(text="Add it in the Path panel (Add Path)", icon="INFO")
            elif m["panel"] in ("game-task", "custom-fields"):
                from .panels.actor_fields import _draw_field
                field = next((f for f in _db.inherited_fields(et) if f.get("key") == m["key"]), None)
                if field:
                    _draw_field(box, ob, field)


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
    entries = ([(False, f"{n}⚠")] if n else []) + ([(True, f"{ns}⚠")] if ns else [])
    if not entries:
        return
    col = layout.column(align=True)
    col.ui_units_x = 1.6 + 0.4 * max(len(t) - 1 for _s, t in entries)
    for is_soft, text in entries:
        r = col.row(align=True)
        r.scale_y = 1.0 / len(entries)
        r.alert = not is_soft                                # required red, soft a yellow triangle
        op = r.operator("og.required_level_popup", text=text, emboss=False)
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


CLASSES = (OGWarningSettings, OG_OT_RequiredPopup, OG_OT_RequiredLevelPopup)


# ── level-wide, cached ──────────────────────────────────────────────────────
# Rebuilt after an edit: any depsgraph update that isn't only a move (see
# _on_depsgraph), any addon operator (track_operators: link / path list edits
# send no depsgraph update), undo / redo, file load.
_CACHE = {"dirty": True, "by_actor": {}, "soft": {}, "names": set()}


def mark_dirty(*_a):
    _CACHE["dirty"] = True


def level_missing(scene):
    """{actor name: missing list} for every actor of the active level with
    something missing. Cached until the next edit."""
    if _CACHE["dirty"]:
        from .export.navmesh import nav_pass
        nav_pass(True)
        try:
            _rebuild(scene)
        finally:
            nav_pass(False)
    return _CACHE["by_actor"]


def _rebuild(scene):
    """Recompute every level object's missing / soft lists."""
    from .collections import _level_objects
    res = {}
    objs = _level_objects(scene)
    banks = _sound_banks(scene)
    senders = trigger_senders(scene, objs)
    linked = linked_index(scene.objects)
    sres = {}
    for o in objs:
        m = missing(o, scene, banks=banks)
        if m:
            res[o.name] = m
        s = soft(o, scene, banks, senders, linked)
        if s:
            sres[o.name] = s
    _CACHE["by_actor"] = res
    _CACHE["soft"] = sres
    _CACHE["names"] = {o.name for o in objs}
    _CACHE["dirty"] = False


def actor_missing(o, scene=None):
    """missing(o) from the level cache (computed directly for an object
    outside the active level)."""
    scene = scene or bpy.context.scene
    level_missing(scene)
    if o is not None and o.name in _CACHE["names"]:
        return _CACHE["by_actor"].get(o.name, [])
    return missing(o, scene)


def actor_soft(o, scene=None):
    """soft(o) from the level cache (computed directly outside the level)."""
    scene = scene or bpy.context.scene
    level_missing(scene)
    if o is not None and o.name in _CACHE["names"]:
        return _CACHE["soft"].get(o.name, [])
    return soft(o, scene)


def track_operators(classes):
    """Every addon operator marks the level checks dirty when it finishes
    (call before the classes are registered)."""
    def wrap(f):
        def execute(self, ctx):
            try:
                return f(self, ctx)
            finally:
                _CACHE["dirty"] = True
                try:                      # race-ring circles inside this operator's undo step
                    from . import race_rings
                    race_rings.sync_now(ctx)
                except Exception:
                    pass
        execute._og_dirty = True
        execute.__doc__ = f.__doc__
        return execute
    for c in classes:
        if issubclass(c, bpy.types.Operator) and "execute" in c.__dict__ and not getattr(c.execute, "_og_dirty", False):
            c.execute = wrap(c.execute)


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


_HANDLERS = lambda: ((bpy.app.handlers.depsgraph_update_post, _on_depsgraph), (bpy.app.handlers.load_post, _on_load),
                     (bpy.app.handlers.undo_post, _on_load), (bpy.app.handlers.redo_post, _on_load))


def register_handlers():
    for hl, f in _HANDLERS():
        for old in [x for x in hl if getattr(x, "__name__", "") == f.__name__ and getattr(x, "__module__", "").endswith(".required")]:
            hl.remove(old)
        hl.append(f)


def unregister_handlers():
    for hl, f in _HANDLERS():
        if f in hl:
            hl.remove(f)
