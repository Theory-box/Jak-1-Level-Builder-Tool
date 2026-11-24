"""Moods tab: custom moods (fog / lights / sun tables, time of day) and mood functions.

A mood (the game's mood-context) holds, for 8 slots, a fog, a lights and a sun entry, and
three hour tables saying which two slots are mixed at each hour (fog, lights + vertex
palettes, sky + sun). Slot N is also the geometry's bake layer N (_SUNRISE .. _GREENSUN).
A mood function (update-mood-<name>) runs every frame: it mixes the tables by the hour and
adds its effects. Both are exported into GAME.CGO (export/moods_export.py): the game looks
them up when a level starts loading, before its own code is there.
"""
from __future__ import annotations

import re

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty,
                       FloatVectorProperty, IntProperty, PointerProperty, StringProperty)

from . import db as _db

SLOT_NAMES = ("Sunrise", "Morning", "Noon", "Afternoon", "Sunset", "Twilight", "Evening", "Green Sun")
DEFAULT_HOURS = (7, 9, 12, 15, 18, 19, 23, 4)          # the game's default hour table peaks

# timeline presets: slot -> hour (missing = off); "fixed" uses one slot all day
PRESETS = {
    "all": dict(enumerate(DEFAULT_HOURS)),
    "village1": {0: 7, 1: 9, 2: 12, 3: 15, 4: 18, 6: 23, 7: 4},
    "two": {0: 12, 1: 0},
    "three": {1: 12, 2: 19, 3: 0},
    "four": {0: 7, 1: 12, 2: 18, 3: 0},
}
PRESET_ITEMS = [("all", "All 8 (default)", "Every slot is a time of day, like most levels"),
                ("village1", "7 (Twilight free)", "Like Sandover: slot 5 is free for an effect (lamps)"),
                ("two", "2 (day / night)", "Slots 0 (day) and 1 (night) only, like Misty / Rock Village: 2-7 free"),
                ("three", "3 (day / evening / night)", "Slots 1-3, like Fire Canyon / Snowy: the others free"),
                ("four", "4", "Slots 0-3, like Precursor Basin: 4-7 free"),
                ("fixed", "Fixed slot (no time of day)", "One slot all day, like the caves: the others free")]


def clean(s):
    return re.sub(r"[^a-z0-9-]+", "-", s.strip().lower()).strip("-")


def group_name(scene=None):
    """Name of this .blend's mood files (lt-moods-<group>.gc)."""
    g = clean(bpy.path.display_name_from_filepath(bpy.data.filepath)) if bpy.data.filepath else ""
    return g or "moods"


# ── per-slot settings ───────────────────────────────────────────────────────

class OGMoodTimeSlot(bpy.types.PropertyGroup):
    enabled: BoolProperty(name="On", default=True)
    hour: IntProperty(name="Hour", default=12, min=0, max=23, description="Hour this slot is at full strength")


class OGMoodFogSlot(bpy.types.PropertyGroup):
    enabled: BoolProperty(name="On", default=True, description="Off: an empty entry (like the vanilla caves' unused slots)")
    color: FloatVectorProperty(name="Fog colour", subtype="COLOR", size=3, min=0.0, max=1.0, default=(0.63, 0.59, 0.78))
    start: FloatProperty(name="Start (m)", default=64.0, min=0.0, unit="LENGTH")
    end: FloatProperty(name="End (m)", default=1640.0, min=0.0, unit="LENGTH")
    clear_start: FloatProperty(name="Clear at start", default=255.0, min=0.0, max=255.0,
                               description="How clear the view is at Start (255 = no fog)")
    clear_end: FloatProperty(name="Clear at end", default=25.5, min=0.0, max=255.0,
                             description="How clear the view is at End (lower = thicker fog)")
    erase: FloatVectorProperty(name="Erase colour", subtype="COLOR", size=3, min=0.0, max=1.0, default=(0.0, 0.0, 0.0),
                               description="The colour behind everything (where no sky is drawn)")


class OGMoodLightSlot(bpy.types.PropertyGroup):
    enabled: BoolProperty(name="On", default=True)
    direction: FloatVectorProperty(name="Direction", subtype="DIRECTION", size=3, default=(0.0, -0.26, 0.97),
                                   description="Toward the light (Blender axes: Z up)")
    color: FloatVectorProperty(name="Light colour", subtype="COLOR", size=3, min=0.0, soft_max=2.0, default=(1.6, 1.6, 1.44),
                               description="The sun light on actors (1.0 = normal, up to about 2)")
    ambient: FloatVectorProperty(name="Ambient", subtype="COLOR", size=3, min=0.0, soft_max=2.0, default=(0.36, 0.36, 0.43))
    prt_auto: BoolProperty(name="Particles: auto", default=True, description="Particle colour from the lights (as most levels)")
    prt_color: FloatVectorProperty(name="Particle colour", subtype="COLOR", size=3, min=0.0, soft_max=2.0, default=(1.0, 1.0, 1.0))


class OGMoodSunSlot(bpy.types.PropertyGroup):
    enabled: BoolProperty(name="On", default=True)
    sun: FloatVectorProperty(name="Sun colour", subtype="COLOR", size=3, min=0.0, max=1.0, default=(1.0, 0.5, 0.0),
                             description="The sun sprite and its halo")
    env: FloatVectorProperty(name="Env colour", subtype="COLOR", size=3, min=0.0, max=1.0, default=(1.0, 0.88, 0.38),
                             description="Tint of shiny surfaces and water reflections")


def _table_items(kind):
    def items(self, ctx):
        v = _db.vanilla_moods().get(kind, {})
        out = [("custom", "Custom", "Set every slot here")]
        out += [(f"vanilla:{k}", f"{k} (game)", f"The game's *{k}-mood-{kind}-table*") for k in sorted(v)]
        sc = ctx.scene if ctx else None
        for m in (getattr(sc, "og_moods", None) or []):
            if m is not self and m.name:
                out.append((f"mood:{m.name}", f"{m.name} (this file)", "That mood's table"))
        _ITEMS[kind][:] = [(a, b, c, i) for i, (a, b, c) in enumerate(out)]
        return _ITEMS[kind]
    return items


_ITEMS = {"fog": [], "lights": [], "sun": [], "interp": []}


def _interp_items(self, ctx):
    out = [("timeline", "Timeline", "Built from the timeline above")]
    out += [(f"vanilla:{k}", k, "The game's hour table") for k in sorted(_db.vanilla_moods().get("interp", {}))]
    _ITEMS["interp"][:] = [(a, b, c, i) for i, (a, b, c) in enumerate(out)]
    return _ITEMS["interp"]


class OGMood(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="", description="The mood is *<name>* in the game")
    export: BoolProperty(name="Export", default=True)
    expanded: BoolProperty(default=True)
    show_time: BoolProperty(default=False)
    show_fog: BoolProperty(default=False)
    show_lights: BoolProperty(default=False)
    show_sun: BoolProperty(default=False)
    time_preset: EnumProperty(name="Preset", items=PRESET_ITEMS, default="all")
    fixed_slot: IntProperty(name="Slot", default=0, min=0, max=7, description="The slot used all day")
    times: CollectionProperty(type=OGMoodTimeSlot)
    fog_interp: EnumProperty(name="Fog hours", items=_interp_items)
    palette_interp: EnumProperty(name="Lights hours", items=_interp_items)
    sky_interp: EnumProperty(name="Sky hours", items=_interp_items)
    fog_from: EnumProperty(name="Fog", items=_table_items("fog"))
    lights_from: EnumProperty(name="Lights", items=_table_items("lights"))
    sun_from: EnumProperty(name="Sun", items=_table_items("sun"))
    fog: CollectionProperty(type=OGMoodFogSlot)
    lights: CollectionProperty(type=OGMoodLightSlot)
    sun: CollectionProperty(type=OGMoodSunSlot)
    num_stars: FloatProperty(name="Stars", default=85.0, min=0.0, max=255.0,
                             description="Stars at night (0 = none; they need more than 45 and a sky)")
    match_level: BoolProperty(name="Match level lighting", default=False,
                              description="Build the lights and sun tables from a level's Light Baking > Time of day "
                                          "suns and worlds at every export, so actors are lit like the baked level")
    match_col: PointerProperty(type=bpy.types.Collection, name="Level", poll=lambda self, c: bool(c.get("og_is_level")),
                               description="The level whose Time of day suns / worlds are used (empty: the active level)")
    match_strength: FloatProperty(name="Strength", default=1.0, min=0.0, soft_max=4.0,
                                  description="Multiplies the light and ambient colours taken from the suns / worlds")
    match_fog: BoolProperty(name="Fog colour from the world", default=False,
                            description="Each slot's fog colour is its world's colour too")


class OGMoodFunc(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="", description="The function is update-mood-<name> in the game")
    export: BoolProperty(name="Export", default=True)
    expanded: BoolProperty(default=True)


def _fill(m):
    """8 entries in each per-slot list (new moods), the timeline at the game's default hours."""
    while len(m.times) < 8:
        t = m.times.add()
        t.hour = DEFAULT_HOURS[len(m.times) - 1]
    for coll in (m.fog, m.lights, m.sun):
        while len(coll) < 8:
            coll.add()


def apply_preset(m, preset):
    _fill(m)
    m.time_preset = preset
    if preset == "fixed":
        for i, t in enumerate(m.times):
            t.enabled = i == m.fixed_slot
        return
    hours = PRESETS[preset]
    for i, t in enumerate(m.times):
        t.enabled = i in hours
        if i in hours:
            t.hour = hours[i]


# ── unit conversions (game <-> panel) ──────────────────────────────────────

def blender_to_game_dir(v):
    return (v[0], v[2], -v[1])


def game_to_blender_dir(v):
    return (v[0], -v[2], v[1])


def load_vanilla(m, level):
    """Copy a vanilla mood's tables into the custom slots (a template)."""
    _fill(m)
    v = _db.vanilla_moods()
    info = v.get("moods", {}).get(level, {})
    for kind, coll in (("fog", m.fog), ("lights", m.lights), ("sun", m.sun)):
        src = info.get(f"mood-{kind}-table", level)
        rows = v.get(kind, {}).get(src) or [None] * 8
        for e, row in zip(coll, rows):
            e.enabled = row is not None
            if row is None:
                continue
            if kind == "fog":
                e.color = [c / 255.0 for c in row["fog_color"][:3]]
                e.start, e.end = row["fog_dists"][0] / 4096.0, row["fog_dists"][1] / 4096.0
                e.clear_start, e.clear_end = row["fog_dists"][2], row["fog_dists"][3]
                e.erase = [c / 255.0 for c in row["erase_color"][:3]]
            elif kind == "lights":
                d = row["direction"][:3]
                e.direction = game_to_blender_dir(d) if any(d) else (0.0, 0.0, 1.0)
                e.color = row["lgt_color"][:3]
                e.ambient = row["amb_color"][:3]
                e.prt_auto = not any(row["prt_color"][:3])
                if not e.prt_auto:
                    e.prt_color = row["prt_color"][:3]
            else:
                e.sun = [c / 255.0 for c in row["sun_color"][:3]]
                e.env = [c / 255.0 for c in row["env_color"][:3]]
    m.fog_from = m.lights_from = m.sun_from = "custom"
    for key, prop in (("fog-interp", "fog_interp"), ("palette-interp", "palette_interp"), ("sky-texture-interp", "sky_interp")):
        it = info.get(key)
        if it:
            setattr(m, prop, f"vanilla:{it}")
    m.num_stars = float(info.get("num-stars", 85.0))


# ── match level lighting ───────────────────────────────────────────────────

def _sun_of(coll):
    if coll is None:
        return None
    suns = [o for o in coll.all_objects if o.type == "LIGHT" and o.data.type == "SUN"]
    return min(suns, key=lambda o: o.name) if suns else None


def _world_colour(w):
    """(colour, strength) of a world's Background node (or its viewport colour)."""
    if w.use_nodes and w.node_tree:
        bg = next((n for n in w.node_tree.nodes if n.type == "BACKGROUND"), None)
        if bg is not None:
            return tuple(bg.inputs["Color"].default_value[:3]), float(bg.inputs["Strength"].default_value)
    return tuple(w.color), 1.0


def match_col(m, scene):
    from .collections import _active_level_col
    return m.match_col or _active_level_col(scene)


def level_lighting(m, scene):
    """Per slot (8): what the level's Time of day gives it, or None: {dir, color, sun} from
    the time's first sun (by name) in its light collection, {ambient, fog} from its world."""
    out = [None] * 8
    col = match_col(m, scene) if m.match_level else None
    if col is None:
        return out
    from .bake import tod_times
    s = m.match_strength
    for k, (_key, _attr, _label, t) in enumerate(tod_times(col.og_bake)):
        d = {}
        sun = _sun_of(t.lights)
        if sun is not None:
            z = sun.matrix_world.to_3x3() @ __import__("mathutils").Vector((0.0, 0.0, 1.0))
            z.normalize()                                  # a sun shines along its -Z: +Z points at it
            c, e = tuple(sun.data.color), sun.data.energy * s
            d.update(dir=tuple(z), color=tuple(x * e for x in c), sun=tuple(min(1.0, x) for x in c))
        if t.world is not None:
            c, e = _world_colour(t.world)
            d.update(ambient=tuple(x * e * s for x in c), fog=tuple(min(1.0, x) for x in c))
        out[k] = d or None
    return out


def table_source(m, kind):
    """Where a table comes from at export: matching makes lights / sun (and fog) custom."""
    if m.match_level and (kind in ("lights", "sun") or kind == "fog" and m.match_fog):
        return "custom"
    return getattr(m, f"{kind}_from")


# ── problems ───────────────────────────────────────────────────────────────

def problems(scene):
    """[(kind, index, text)] that stop the export."""
    out = []
    vanilla = set(_db.vanilla_moods().get("moods", {}))
    seen = set()
    for i, m in enumerate(scene.og_moods):
        if not m.export:
            continue
        n = clean(m.name)
        if not n:
            out.append(("mood", i, "needs a name"))
        elif n in vanilla or n in seen:
            out.append(("mood", i, f"name '{n}' is already used (the game's or this file's)"))
        seen.add(n)
        if not any(t.enabled for t in m.times) and "timeline" in (m.fog_interp, m.palette_interp, m.sky_interp):
            out.append(("mood", i, "the timeline has no slot on"))
    seen = set()
    vfuncs = {f"{k}" for k in vanilla} | {"default", "quick", "interior", "exterior"}
    for i, f in enumerate(scene.og_mood_funcs):
        if not f.export:
            continue
        n = clean(f.name)
        if not n:
            out.append(("func", i, "needs a name"))
        elif n in vfuncs or n in seen:
            out.append(("func", i, f"name '{n}' is already used (the game's or this file's)"))
        seen.add(n)
    return out


# ── operators ───────────────────────────────────────────────────────────────

def _level_name(ctx):
    from .collections import _active_level_col, level_name
    col = _active_level_col(ctx.scene)
    return clean(level_name(col)) if col is not None else "my-level"


class OG_OT_MoodAdd(bpy.types.Operator):
    """Add a custom mood (a copy of Sandover's to start from)"""
    bl_idname = "og.mood_add"
    bl_label = "Add Mood"
    bl_options = {"REGISTER", "UNDO"}
    kind: StringProperty(default="mood", options={"HIDDEN"})

    def execute(self, ctx):
        base = _level_name(ctx)
        if self.kind == "func":
            names = {f.name for f in ctx.scene.og_mood_funcs}
            f = ctx.scene.og_mood_funcs.add()
            f.name = base if base not in names else next(f"{base}-{k}" for k in range(2, 99) if f"{base}-{k}" not in names)
            return {"FINISHED"}
        names = {m.name for m in ctx.scene.og_moods}
        m = ctx.scene.og_moods.add()
        m.name = (f"{base}-mood" if f"{base}-mood" not in names
                  else next(f"{base}-mood-{k}" for k in range(2, 99) if f"{base}-mood-{k}" not in names))
        apply_preset(m, "all")
        load_vanilla(m, "village1")
        m.fog_interp = m.palette_interp = m.sky_interp = "timeline"
        return {"FINISHED"}


class OG_OT_MoodRemove(bpy.types.Operator):
    """Delete it"""
    bl_idname = "og.mood_remove"
    bl_label = "Delete"
    bl_options = {"REGISTER", "UNDO"}
    kind: StringProperty(default="mood", options={"HIDDEN"})
    index: IntProperty(options={"HIDDEN"})

    def execute(self, ctx):
        coll = ctx.scene.og_mood_funcs if self.kind == "func" else ctx.scene.og_moods
        if 0 <= self.index < len(coll):
            coll.remove(self.index)
        return {"FINISHED"}


class OG_OT_MoodDuplicate(bpy.types.Operator):
    """Make a copy of it"""
    bl_idname = "og.mood_duplicate"
    bl_label = "Duplicate"
    bl_options = {"REGISTER", "UNDO"}
    kind: StringProperty(default="mood", options={"HIDDEN"})
    index: IntProperty(options={"HIDDEN"})

    def execute(self, ctx):
        coll = ctx.scene.og_mood_funcs if self.kind == "func" else ctx.scene.og_moods
        if not (0 <= self.index < len(coll)):
            return {"CANCELLED"}
        src = coll[self.index]
        dst = coll.add()
        _copy(src, dst)
        names = {x.name for x in coll}
        dst.name = next(f"{src.name}-copy{'' if k == 1 else k}" for k in range(1, 99)
                        if f"{src.name}-copy{'' if k == 1 else k}" not in names)
        coll.move(len(coll) - 1, self.index + 1)
        return {"FINISHED"}


def _copy(src, dst):
    for p in src.bl_rna.properties:
        k = p.identifier
        if k in ("rna_type",) or p.is_readonly and p.type != "COLLECTION":
            continue
        if p.type == "COLLECTION":
            d = getattr(dst, k)
            d.clear()
            for e in getattr(src, k):
                _copy(e, d.add())
        elif p.type == "POINTER":
            if issubclass(getattr(bpy.types, p.fixed_type.identifier, type(None)), bpy.types.ID):
                setattr(dst, k, getattr(src, k))
        else:
            try:
                setattr(dst, k, getattr(src, k))
            except (TypeError, AttributeError):
                pass


def _template_items(self, ctx):
    out = [(k, f"{k} (game)", "") for k in sorted(_db.vanilla_moods().get("moods", {}))]
    _ITEMS.setdefault("tpl", [])[:] = [(a, b, c, i) for i, (a, b, c) in enumerate(out)]
    return _ITEMS["tpl"]


class OG_OT_MoodTemplate(bpy.types.Operator):
    """Fill this mood from one of the game's moods (its tables, hour tables and stars)"""
    bl_idname = "og.mood_template"
    bl_label = "Template"
    bl_options = {"REGISTER", "UNDO"}
    bl_property = "pick"
    index: IntProperty(options={"HIDDEN"})
    pick: EnumProperty(name="Mood", items=_template_items)

    def invoke(self, ctx, event):
        ctx.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, ctx):
        m = ctx.scene.og_moods[self.index]
        load_vanilla(m, self.pick)
        self.report({"INFO"}, f"{m.name}: tables of {self.pick}")
        return {"FINISHED"}


class OG_OT_MoodPreset(bpy.types.Operator):
    """Set the timeline from a preset"""
    bl_idname = "og.mood_preset"
    bl_label = "Timeline Preset"
    bl_options = {"REGISTER", "UNDO"}
    index: IntProperty(options={"HIDDEN"})
    preset: EnumProperty(items=PRESET_ITEMS)

    def execute(self, ctx):
        m = ctx.scene.og_moods[self.index]
        apply_preset(m, self.preset)
        m.fog_interp = m.palette_interp = m.sky_interp = "timeline"
        return {"FINISHED"}


def _file_items(kind):
    def items(self, ctx):
        coll = ctx.scene.og_mood_funcs if kind == "func" else ctx.scene.og_moods
        out = [(clean(x.name), x.name, "") for x in coll if x.name]
        _ITEMS.setdefault("file" + kind, [])[:] = [(a, b, c, i) for i, (a, b, c) in enumerate(out or [("", "(none in this file)", "")])]
        return _ITEMS["file" + kind]
    return items


class OG_OT_LevelUseMood(bpy.types.Operator):
    """Use one of this file's moods for the active level"""
    bl_idname = "og.level_use_mood"
    bl_label = "This File's Mood"
    bl_options = {"REGISTER", "UNDO"}
    bl_property = "pick"
    pick: EnumProperty(name="Mood", items=_file_items("mood"))

    def invoke(self, ctx, event):
        ctx.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, ctx):
        if not self.pick:
            return {"CANCELLED"}
        from .collections import _active_level_col
        col = _active_level_col(ctx.scene)
        if col is None:
            return {"CANCELLED"}
        ctx.scene.og_props.mood = "custom"
        col.og_level.mood_custom = f"*{self.pick}*"
        return {"FINISHED"}


class OG_OT_LevelUseMoodFunc(bpy.types.Operator):
    """Use one of this file's mood functions for the active level"""
    bl_idname = "og.level_use_mood_func"
    bl_label = "This File's Mood Function"
    bl_options = {"REGISTER", "UNDO"}
    bl_property = "pick"
    pick: EnumProperty(name="Mood function", items=_file_items("func"))

    def invoke(self, ctx, event):
        ctx.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, ctx):
        if not self.pick:
            return {"CANCELLED"}
        from .collections import _active_level_col
        col = _active_level_col(ctx.scene)
        if col is None:
            return {"CANCELLED"}
        col.og_level.mood_func = "CUSTOM"
        col.og_level.mood_func_custom = f"update-mood-{self.pick}"
        return {"FINISHED"}


# ── drawing ────────────────────────────────────────────────────────────────

def _head(box, item, kind, i, label, issues):
    row = box.row(align=True)
    row.prop(item, "expanded", text="", emboss=False, icon="TRIA_DOWN" if item.expanded else "TRIA_RIGHT")
    row.prop(item, "export", text="")
    row.label(text=label)
    mine = [t for k, j, t in issues if k == kind and j == i]
    if mine:
        w = row.row(); w.alert = True
        w.label(text=f"{len(mine)}⚠")
    op = row.operator("og.mood_duplicate", text="", icon="DUPLICATE", emboss=False); op.kind, op.index = kind, i
    op = row.operator("og.mood_remove", text="", icon="X", emboss=False); op.kind, op.index = kind, i
    for t in mine if item.expanded else ():
        w = box.row(); w.alert = True
        w.label(text=t, icon="ERROR")
    return item.expanded


def _fold(box, item, prop, text):
    r = box.row()
    r.prop(item, prop, text=text, emboss=False, icon="TRIA_DOWN" if getattr(item, prop) else "TRIA_RIGHT")
    return getattr(item, prop)


def _draw_mood(layout, m, i, issues):
    box = layout.box()
    if not _head(box, m, "mood", i, f"*{clean(m.name) or '?'}*", issues):
        return
    box.prop(m, "name")
    box.operator("og.mood_template", text="Template from a game mood…", icon="PRESET").index = i
    ov = [None] * 8
    mb = box.box()
    mb.prop(m, "match_level")
    if m.match_level:
        col = match_col(m, bpy.context.scene)
        mb.prop(m, "match_col", text="Level")
        if m.match_col is None and col is not None:
            h = mb.row(); h.enabled = False; h.scale_y = 0.7
            h.label(text=f"Empty: the active level ({col.name})")
        r = mb.row(align=True); r.prop(m, "match_strength"); r.prop(m, "match_fog", text="Fog colour")
        ov = level_lighting(m, bpy.context.scene)
        if col is None:
            w = mb.row(); w.alert = True
            w.label(text="No level to match", icon="ERROR")
        else:
            for what, key in (("sun", "dir"), ("world", "ambient")):
                miss = [SLOT_NAMES[k] for k in range(8) if m.lights[k].enabled and not (ov[k] or {}).get(key)]
                h = mb.row(); h.enabled = False; h.scale_y = 0.7
                if miss:
                    h.label(text=f"No {what}: {', '.join(miss)} (kept as set below)", icon="INFO")
                else:
                    h.label(text=f"Every slot has a {what}", icon="CHECKMARK")
    # time of day
    if _fold(box, m, "show_time", "Time of day"):
        tb = box.box()
        r = tb.row(align=True)
        r.label(text="Preset:")
        for key, label, _d in PRESET_ITEMS:
            op = r.operator("og.mood_preset", text=label.split(" ")[0], depress=m.time_preset == key)
            op.index, op.preset = i, key
        if m.time_preset == "fixed":
            tb.prop(m, "fixed_slot")
        col = tb.column(align=True)
        for k, t in enumerate(m.times):
            r = col.row(align=True)
            r.prop(t, "enabled", text=f"{k} {SLOT_NAMES[k]}")
            sub = r.row(align=True); sub.enabled = t.enabled
            sub.prop(t, "hour", text="Hour")
        h = tb.row(); h.enabled = False; h.scale_y = 0.7
        h.label(text="Off slots are free for the mood function's effects", icon="INFO")
        c = tb.column(align=True)
        c.prop(m, "fog_interp")
        c.prop(m, "palette_interp")
        c.prop(m, "sky_interp")
    # tables
    for kind, prop, show in (("fog", "fog_from", "show_fog"), ("lights", "lights_from", "show_lights"), ("sun", "sun_from", "show_sun")):
        r = box.row(align=True)
        r.prop(m, show, text="", emboss=False, icon="TRIA_DOWN" if getattr(m, show) else "TRIA_RIGHT")
        driven = table_source(m, kind) != getattr(m, prop)
        if driven:
            r.label(text=f"{prop[:-5].capitalize()}: driven by level lights")
        else:
            r.prop(m, prop)
        if not getattr(m, show) or table_source(m, kind) != "custom":
            continue
        tb = box.box()
        for k, e in enumerate(getattr(m, kind)):
            sb = tb.column(align=True)
            sb.prop(e, "enabled", text=f"{k} {SLOT_NAMES[k]}")
            if not e.enabled:
                continue
            got = ov[k] or {}

            def field(name, key, s=sb):
                f = s.row(); f.enabled = key not in got
                f.prop(e, name)
            if kind == "fog":
                field("color", "fog" if m.match_fog else "-")
                rr = sb.row(align=True); rr.prop(e, "start"); rr.prop(e, "end")
                rr = sb.row(align=True); rr.prop(e, "clear_start"); rr.prop(e, "clear_end")
                sb.prop(e, "erase")
            elif kind == "lights":
                field("direction", "dir")
                field("color", "color")
                field("ambient", "ambient")
                rr = sb.row(align=True); rr.prop(e, "prt_auto")
                if not e.prt_auto:
                    rr.prop(e, "prt_color", text="")
            else:
                field("sun", "sun")
                sb.prop(e, "env")
    box.prop(m, "num_stars")


def _draw_func(layout, f, i, issues):
    box = layout.box()
    if not _head(box, f, "func", i, f"update-mood-{clean(f.name) or '?'}", issues):
        return
    box.prop(f, "name")
    h = box.row(); h.enabled = False; h.scale_y = 0.7
    h.label(text="Mixes the mood's tables by the hour (effects: coming next)", icon="INFO")


def draw(layout, ctx):
    sc = ctx.scene
    issues = problems(sc)
    for line in ("A mood is a level's light: fog, sun light on actors, sky and",
                 "which baked vertex colours (time of day) show at each hour.",
                 "Pick them in Level > Settings > Visuals. Built into the game (full build)."):
        r = layout.row(); r.enabled = False; r.scale_y = 0.7
        r.label(text=line)
    head, body = layout.panel("og_moods_funcs", default_closed=True)
    head.label(text=f"Mood Functions ({len(sc.og_mood_funcs)})")
    if body is not None:
        r = body.row(); r.enabled = False; r.scale_y = 0.7
        r.label(text="Runs every frame: mixes the mood by the hour, adds effects", icon="INFO")
        for i, f in enumerate(sc.og_mood_funcs):
            _draw_func(body, f, i, issues)
        body.operator("og.mood_add", text="Add Mood Function", icon="ADD").kind = "func"
    head, body = layout.panel("og_moods_list", default_closed=False)
    head.label(text=f"Moods ({len(sc.og_moods)})")
    if body is not None:
        for i, m in enumerate(sc.og_moods):
            _draw_mood(body, m, i, issues)
        body.operator("og.mood_add", text="Add Mood", icon="ADD").kind = "mood"


class OG_PT_Moods(bpy.types.Panel):
    bl_label = "🌤  Moods"
    bl_idname = "OG_PT_moods"
    bl_order = 6
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "OpenGOAL"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        draw(self.layout, ctx)


CLASSES = (OGMoodTimeSlot, OGMoodFogSlot, OGMoodLightSlot, OGMoodSunSlot, OGMood, OGMoodFunc,
           OG_OT_MoodAdd, OG_OT_MoodRemove, OG_OT_MoodDuplicate, OG_OT_MoodTemplate, OG_OT_MoodPreset,
           OG_OT_LevelUseMood, OG_OT_LevelUseMoodFunc, OG_PT_Moods)


def register_props():
    bpy.types.Scene.og_moods = CollectionProperty(type=OGMood)
    bpy.types.Scene.og_mood_funcs = CollectionProperty(type=OGMoodFunc)


def unregister_props():
    for p in ("og_moods", "og_mood_funcs"):
        if hasattr(bpy.types.Scene, p):
            delattr(bpy.types.Scene, p)
