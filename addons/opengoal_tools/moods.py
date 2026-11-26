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


_CURVE_FIXED = {"NONE": 0, "LEVEL": 1}           # 0: what a new mood has


def _match_curve_items(self, ctx):
    """No curve, Light Baking's curve, then the bake curve presets (the saved ones too)."""
    from .bake import _preset_items
    out = [("NONE", "No curve", "The suns / worlds as they are", 0),
           ("LEVEL", "Light Baking's curve", "The curve Light Baking uses for this level (Bake options), if on", 1)]
    out += [(a, b, c, n + 2) for a, b, c, n in _preset_items(self, ctx)]
    _ITEMS.setdefault("mcurve", [])[:] = out
    return _ITEMS["mcurve"]


def _match_curve_update(self, ctx):
    """A preset: into this mood's own curve (made when needed)."""
    if self.match_curve in _CURVE_FIXED:
        return
    from .bake import _apply_preset
    if self.match_curve_ng is None:
        from .vc_effects import new_curve
        self.match_curve_ng = new_curve(f"OG Mood Curve {self.name}", "LINEAR")
    if self.match_curve != "CUSTOM":
        _apply_preset(self.match_curve_ng, self.match_curve)


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
    match_curve: EnumProperty(name="Curve", items=_match_curve_items, update=_match_curve_update,
                              description="The curve your baked vertex colours went through (Light Baking's, or an "
                                          "Effects After Bake curve): the actor light goes through it too, so it "
                                          "matches the geometry at every time of day")
    match_curve_factor: FloatProperty(name="Factor", default=1.0, min=0.0, max=1.0, subtype="FACTOR")
    match_curve_ng: PointerProperty(type=bpy.types.NodeTree, name="Curve")


# ── mood function effects ──────────────────────────────────────────────────

EFFECTS = (
    ("flicker", "Flicker", "Fires / lamps: the slots' light flares up at random, one slot at a time (1-4 slots)"),
    ("pulse", "Pulse", "A slow glow going up and down, always or at night only"),
    ("lightning", "Lightning + thunder", "Storm flashes on sky and palette slots, with the thunder sound "
                                         "(needs a sky with flash textures, like Rock Village's)"),
    ("lava", "Lava glow", "A flickering glow from below on actors, and 4 slots cross-fading at random"),
    ("caustics", "Caustics", "Underwater shimmer: 4 slots cycling"),
    ("actor", "Triggered slot", "The slot follows Light switch actors (and the game's actors that set its "
                                "palette fade control: cave crystals ...): switchable lights"),
    ("fog_pitch", "Fog by camera pitch", "Looking up, the fog fades toward a colour and clears (like Boggy Swamp)"),
    ("fog_breath", "Fog breathing", "The fog distances slowly go in and out"),
)
EFFECT_LABEL = {k: l for k, l, _d in EFFECTS}
# shown in each effect's box: how it works, then what it is good for
EFFECT_HELP = {
    "flicker": ("The slots stay at Base; now and then one of them flares up",
                "(a short random bump, up to Base + Strength), like the game's fires.",
                "For: torches, campfires, lamps, candles, glowing embers."),
    "pulse": ("The slot's strength goes up and down around Base by Up / down,",
              "one wave every Period. Night only: on 19:00-7:00, an hour's fade each side.",
              "For: glowing plants or crystals, beacons, slow neon, street lamps at night."),
    "lightning": ("Now and then a flash: the sky slots switch to their flash textures and the",
                  "palette slots light up (their lights entry also lights actors), then thunder.",
                  "For: storms. Distant: rarer, quieter, only the sky flashes."),
    "lava": ("Actors get a flickering coloured light from below, and the 4 slots",
             "cross-fade at random (each slot a different bake of the glow).",
             "For: lava, hot pits, furnaces, magic pools under the player."),
    "caustics": ("The 4 slots take turns, fading one into the next, over and over.",
                 "Bake the same water light pattern 4 times, a little moved each time.",
                 "For: light rippling under water, reflections on walls near water."),
    "actor": ("The slot follows its palette fade control: a Light switch (or the game's",
              "cave crystals) turns it on and off, fading. Off: the slot is dark.",
              "For: light switches, lights a button turns on, lit when a door opens."),
    "fog_pitch": ("Looking up, the fog moves toward the colour and gets clearer;",
                  "looking ahead or down it is the mood's fog.",
                  "For: a thick swamp or cave fog that opens up toward the sky."),
    "fog_breath": ("The fog start / end distances go between Nearest and Farthest",
                   "(times the mood's), one wave every Period.",
                   "For: slowly moving mist, a sandstorm, breathing dark-eco fog."),
}
SHAPES = [("sine", "Smooth", "A smooth wave"), ("triangle", "Linear", "Goes in and out at a steady speed"),
          ("wander", "Wander", "Two waves mixed: irregular, like the weather")]


class OGMoodEffect(bpy.types.PropertyGroup):
    kind: EnumProperty(name="Effect", items=[(k, l, d) for k, l, d in EFFECTS])
    enabled: BoolProperty(name="On", default=True)
    expanded: BoolProperty(default=True)
    slot: IntProperty(name="Slot", default=5, min=0, max=7, description="The (first) palette slot this effect uses")
    count: IntProperty(name="Slots", default=1, min=1, max=4, description="How many slots, from the first one")
    base: FloatProperty(name="Base", default=0.5, min=0.0, soft_max=2.0, description="The slot's strength when calm (1 = full)")
    strength: FloatProperty(name="Strength", default=0.5, min=0.0, soft_max=2.0, description="How much it adds at its peak")
    speed: FloatProperty(name="Speed", default=1.0, min=0.05, soft_max=10.0, description="1 = the game's speed")
    period: FloatProperty(name="Period (s)", default=4.27, min=0.1, soft_max=60.0, description="Seconds for one wave")
    phase: FloatProperty(name="Phase", default=0.0, min=0.0, max=1.0, subtype="FACTOR",
                         description="Where in its wave it starts (offset pulses so they don't move together)")
    night_only: BoolProperty(name="Night only", default=False,
                             description="On from 19:00 to 7:00, fading in / out over an hour")
    sky_slot: IntProperty(name="Sky slot", default=2, min=0, max=7, description="First sky texture slot that flashes")
    quiet: BoolProperty(name="Distant", default=False,
                        description="Far away storm: rarer, quieter thunder, only the sky flashes (no palette slots)")
    color: FloatVectorProperty(name="Colour", subtype="COLOR", size=3, min=0.0, max=1.0, default=(1.0, 0.364, 0.0))
    drive_slots: BoolProperty(name="Cross-fade 4 slots", default=True, description="Off: only the glow on actors")
    amount: FloatProperty(name="Colour amount", default=0.5, min=0.0, max=1.0, subtype="FACTOR",
                          description="How far the fog goes toward the colour when looking straight up")
    clear: FloatProperty(name="Clearing", default=0.666, min=0.0, max=1.0, subtype="FACTOR",
                         description="How much the fog clears when looking straight up")
    dist_min: FloatProperty(name="Nearest", default=0.75, min=0.05, soft_max=4.0,
                            description="Fog start / end times this at the nearest")
    dist_max: FloatProperty(name="Farthest", default=1.25, min=0.05, soft_max=4.0,
                            description="Fog start / end times this at the farthest")
    shape: EnumProperty(name="Shape", items=SHAPES, default="sine")


EFFECT_DEFAULTS = {
    "flicker": dict(slot=4, count=4, base=0.333, strength=0.5),
    "pulse": dict(slot=5, base=0.875, strength=0.25, period=4.27),
    "lightning": dict(slot=2, count=2, sky_slot=2),
    "lava": dict(slot=4, strength=1.0),
    "caustics": dict(slot=4),
    "actor": dict(slot=1),
    "fog_pitch": dict(color=(0.0, 32 / 255, 48 / 255)),
    "fog_breath": dict(period=20.0),
}


def effect_slots(e):
    """Palette slots an effect writes."""
    if e.kind in ("pulse", "actor"):
        return [e.slot]
    if e.kind == "flicker":
        return list(range(e.slot, e.slot + e.count))
    if e.kind == "lightning":
        return [] if e.quiet else list(range(e.slot, e.slot + e.count))
    if e.kind == "lava":
        return list(range(e.slot, e.slot + 4)) if e.drive_slots else []
    if e.kind == "caustics":
        return list(range(e.slot, e.slot + 4))
    return []


TIME_MODES = [("normal", "Normal", "The game's clock"),
              ("lock", "Lock time", "While Jak is in the level, the game's clock stays at this hour (sun, moon and "
                                    "sky too); it goes on from there when he leaves"),
              ("speed", "Time speed", "While Jak is in the level, the game's clock runs this many times faster / "
                                      "slower (sun, moon and sky too)")]


class OGMoodFunc(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="", description="The function is update-mood-<name> in the game")
    export: BoolProperty(name="Export", default=True)
    expanded: BoolProperty(default=True)
    effects: CollectionProperty(type=OGMoodEffect)
    time_mode: EnumProperty(name="Time", items=TIME_MODES, default="normal")
    lock_hour: FloatProperty(name="Hour", default=12.0, min=0.0, max=23.99, description="The hour the mood shows")
    time_speed: FloatProperty(name="Speed", default=1.0, min=0.0, soft_max=10.0,
                              description="2 = twice as fast, 0.5 = half, 0 = stopped at the hour Jak came in")


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


def match_curve_fn(m, col):
    """The Match level lighting curve as f(channel, value) or None. Baked layers store sRGB
    and the game gets them back linear: game = linear(curve(sRGB(light))); the actor light
    goes the same way (values above 1 keep going up past the curve's end)."""
    from .bake import curve_luts, curve_mapping as level_mapping
    from .vc_effects import curve_mapping
    if m.match_curve == "NONE":
        return None
    if m.match_curve == "LEVEL":
        if col is None or not col.og_bake.use_curve:
            return None
        mapping, factor = level_mapping(col), col.og_bake.curve_factor
    else:
        mapping, factor = curve_mapping(m.match_curve_ng), m.match_curve_factor
    if mapping is None or factor <= 0:
        return None
    import numpy as np
    from .palette import _to_linear, _to_srgb
    xs, luts = curve_luts(mapping)

    def f(ci, x):
        xc = min(1.0, max(0.0, x))
        s = float(_to_srgb(np.array([xc]))[0])
        mapped = float(_to_linear(np.array([np.interp(s, xs, luts[ci])]))[0]) + (x - xc)
        return x + (mapped - x) * factor
    return f


def level_lighting(m, scene, values=True):
    """Per slot (8): what the level's Time of day gives it, or None: {dir, color, sun} from
    the time's first sun (by name) in its light collection, {ambient, fog} from its world.
    With a curve: ambient = f(world), light = f(world + sun) - f(world) (the lit side of an
    actor gets what a lit wall got). values=False: only which keys (no curve, for the panel)."""
    out = [None] * 8
    col = match_col(m, scene) if m.match_level else None
    if col is None:
        return out
    from .bake import tod_times
    s = m.match_strength
    fn = match_curve_fn(m, col) if values else None
    level_curve = m.match_curve == "LEVEL"
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
        if fn is not None and not (level_curve and t.ignore_curve):
            a = d.get("ambient", (0.0, 0.0, 0.0))
            fa = tuple(fn(ci, a[ci]) for ci in range(3))
            if "color" in d:
                d["color"] = tuple(max(0.0, fn(ci, a[ci] + d["color"][ci]) - fa[ci]) for ci in range(3))
            if "ambient" in d:
                d["ambient"] = fa
        out[k] = d or None
    return out


def table_source(m, kind):
    """Where a table comes from at export: matching makes lights / sun (and fog) custom."""
    if m.match_level and (kind in ("lights", "sun") or kind == "fog" and m.match_fog):
        return "custom"
    return getattr(m, f"{kind}_from")


# ── which level uses what ──────────────────────────────────────────────────

def level_mood(scene, col):
    """This file's mood a level uses (or None)."""
    if col is None or str(col.get("og_mood", "")) != "custom":
        return None
    v = col.og_level.mood_custom.strip().lstrip("'")
    return next((m for m in scene.og_moods if f"*{clean(m.name)}*" == v), None)


def level_func(scene, col):
    """This file's mood function a level uses (or None)."""
    if col is None or col.og_level.mood_func != "CUSTOM":
        return None
    v = col.og_level.mood_func_custom.strip().lstrip("'")
    return next((f for f in scene.og_mood_funcs if f"update-mood-{clean(f.name)}" == v), None)


def timeline_slots(m):
    """Slots the mood's own timeline lights (palette hours from the timeline)."""
    if m is None or m.palette_interp != "timeline":
        return set()
    if m.time_preset == "fixed":
        return {m.fixed_slot}
    return {k for k, t in enumerate(m.times) if t.enabled}


def slot_uses(scene, col):
    """8 labels: what the level's mood function / mood use each slot for ('' = nothing known)."""
    out = [[] for _ in range(8)]
    f = level_func(scene, col)
    for e in (f.effects if f else ()):
        if e.enabled:
            for s in effect_slots(e):
                if s < 8:
                    out[s].append(EFFECT_LABEL[e.kind])
    m = level_mood(scene, col)
    for s in timeline_slots(m):
        out[s].insert(0, "time" if m.time_preset == "fixed" else f"time {m.times[s].hour}:00")
    return [", ".join(x) for x in out]


def level_conflicts(scene, col):
    """Slots the level's mood uses for time that its function also uses for an effect."""
    f = level_func(scene, col)
    used = {s for e in (f.effects if f else ()) if e.enabled for s in effect_slots(e)}
    return sorted(used & timeline_slots(level_mood(scene, col)))


def effect_overlaps(f):
    """[(slot, [effect labels])] used by two effects of the function (or past slot 7)."""
    seen = {}
    for e in f.effects:
        if e.enabled:
            for s in effect_slots(e):
                seen.setdefault(s, []).append(EFFECT_LABEL[e.kind])
    return [(s, l) for s, l in sorted(seen.items()) if len(l) > 1 or s > 7]


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
        if getattr(dst, "match_curve_ng", None) is not None:
            dst.match_curve_ng = src.match_curve_ng.copy()
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


class OG_OT_MoodFxAdd(bpy.types.Operator):
    """Add an effect to this mood function"""
    bl_idname = "og.mood_fx_add"
    bl_label = "Add Effect"
    bl_options = {"REGISTER", "UNDO"}
    index: IntProperty(options={"HIDDEN"})
    kind: EnumProperty(name="Effect", items=[(k, l, d) for k, l, d in EFFECTS])

    def execute(self, ctx):
        f = ctx.scene.og_mood_funcs[self.index]
        e = f.effects.add()
        e.kind = self.kind
        for k, v in EFFECT_DEFAULTS.get(self.kind, {}).items():
            setattr(e, k, v)
        return {"FINISHED"}


class OG_OT_MoodFxRemove(bpy.types.Operator):
    """Remove this effect"""
    bl_idname = "og.mood_fx_remove"
    bl_label = "Remove Effect"
    bl_options = {"REGISTER", "UNDO"}
    index: IntProperty(options={"HIDDEN"})
    fx: IntProperty(options={"HIDDEN"})

    def execute(self, ctx):
        f = ctx.scene.og_mood_funcs[self.index]
        if 0 <= self.fx < len(f.effects):
            f.effects.remove(self.fx)
        return {"FINISHED"}


# The game's mood functions as effects (mood.gc). Parts tied to vanilla places / tasks
# (houses' light zones, the warehouse, the eggtop task, the citadel shield ...) are left out.
_FLICK = dict(kind="flicker", count=4, base=0.333, strength=0.5)
_PULSE = dict(kind="pulse", base=0.875, strength=0.25, period=4.27, phase=0.125)
FUNC_TEMPLATES = {
    "default": ("Time of day only", []),
    "village1": ("Sandover: lamps flicker on slot 5", [dict(_FLICK, slot=5, count=1, base=0.5)]),
    "misty": ("Misty Island: fires on 2-5, two glowing lights on 6 / 7 (vanilla: near the warehouse)",
              [dict(_FLICK, slot=2), dict(_PULSE, slot=6), dict(_PULSE, slot=7)]),
    "village2": ("Rock Village: fires on 4-7, storm on sky / palette 2-3",
                 [dict(_FLICK, slot=4), dict(kind="lightning", sky_slot=2, count=2, slot=2)]),
    "swamp": ("Boggy Swamp: fires on 4-7, storm on 2-3, fog clears looking up",
              [dict(_FLICK, slot=4), dict(kind="lightning", sky_slot=2, count=2, slot=2), dict(kind="fog_pitch")]),
    "jungle": ("Jungle: slot 5 glows (vanilla: once the eggtop is done)", [dict(_PULSE, slot=5)]),
    "sunken": ("Lost Precursor City: slot 2 glows, caustics on 4-7, slot 3 by actors (dark eco water)",
               [dict(_PULSE, slot=2), dict(kind="caustics", slot=4), dict(kind="actor", slot=3)]),
    "rolling": ("Precursor Basin: night lights on 4-7, a distant storm on sky 2-3",
                [dict(_PULSE, slot=4, night_only=True, phase=0.125), dict(_PULSE, slot=5, night_only=True, phase=0.0),
                 dict(_PULSE, slot=6, night_only=True, phase=0.375), dict(_PULSE, slot=7, night_only=True, phase=0.25),
                 dict(kind="lightning", sky_slot=2, count=2, slot=2, quiet=True)]),
    "firecanyon": ("Fire Canyon: lava glow on 4-7", [dict(kind="lava", slot=4)]),
    "training": ("Geyser Rock: slot 5 glows at night", [dict(_PULSE, slot=5, night_only=True)]),
    "maincave": ("Spider Cave: fires on 4-7, crystals on 1 / 2 (the mood: Fixed slot 0)",
                 [dict(_FLICK, slot=4), dict(kind="actor", slot=1), dict(kind="actor", slot=2)]),
    "darkcave": ("Spider Cave (dark): crystals on 1-7 (the mood: Fixed slot 0)",
                 [dict(kind="actor", slot=s) for s in range(1, 8)]),
    "robocave": ("Spider Cave (robot): fires on 4-7 (the mood: Fixed slot 0)", [dict(_FLICK, slot=4)]),
    "snow": ("Snowy Mountain: fires on 4-6, slot 7 glows (vanilla: after the eggtop)",
             [dict(_FLICK, slot=4, count=3, base=0.45), dict(_PULSE, slot=7)]),
    "village3": ("Volcanic Crater: fires on 4-6", [dict(_FLICK, slot=4, count=3, base=0.5)]),
    "lavatube": ("Lava Tube: slot 2 by actors (energy), slot 1 glows, lava on 4-7 (the mood: Fixed slot 0)",
                 [dict(kind="actor", slot=2), dict(_PULSE, slot=1), dict(kind="lava", slot=4)]),
    "citadel": ("Citadel: slots 3 / 7 by actors, fires on 4-6, slot 1 glows (the mood: Fixed slot 0)",
                [dict(kind="actor", slot=3), dict(_FLICK, slot=4, count=3, base=0.45), dict(_PULSE, slot=1),
                 dict(kind="actor", slot=7)]),
    "ogre": ("Mountain Pass: storm on sky 2-3 / palette 4-5", [dict(kind="lightning", sky_slot=2, count=2, slot=4)]),
}


def load_func_template(f, name):
    f.effects.clear()
    for d in FUNC_TEMPLATES[name][1]:
        e = f.effects.add()
        e.kind = d["kind"]
        for k, v in {**EFFECT_DEFAULTS.get(d["kind"], {}), **d}.items():
            if k != "kind":
                setattr(e, k, v)
        e.expanded = False


def _func_template_items(self, ctx):
    out = [(k, f"{k} (game)", v[0]) for k, v in FUNC_TEMPLATES.items()]
    _ITEMS.setdefault("ftpl", [])[:] = [(a, b, c, i) for i, (a, b, c) in enumerate(out)]
    return _ITEMS["ftpl"]


class OG_OT_MoodFuncTemplate(bpy.types.Operator):
    """Replace this function's effects with the ones a game mood function uses"""
    bl_idname = "og.mood_func_template"
    bl_label = "Function Template"
    bl_options = {"REGISTER", "UNDO"}
    bl_property = "pick"
    index: IntProperty(options={"HIDDEN"})
    pick: EnumProperty(name="Function", items=_func_template_items)

    def invoke(self, ctx, event):
        ctx.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, ctx):
        f = ctx.scene.og_mood_funcs[self.index]
        load_func_template(f, self.pick)
        self.report({"INFO"}, f"update-mood-{clean(f.name)}: {FUNC_TEMPLATES[self.pick][0]}")
        return {"FINISHED"}


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


def _show_mood(scene, m):
    """Open this mood's block in the Moods panel (the others folded)."""
    for x in scene.og_moods:
        x.expanded = x == m
    m.show_fog = True


def make_level_mood(ctx, col):
    """A custom mood copying the level's current (game) mood, used by the level."""
    from .level_settings import mood_name
    vanilla = _db.vanilla_moods().get("moods", {})
    src = mood_name(col)
    base = _level_name(ctx)
    names = {m.name for m in ctx.scene.og_moods}
    m = ctx.scene.og_moods.add()
    m.name = (f"{base}-mood" if f"{base}-mood" not in names
              else next(f"{base}-mood-{k}" for k in range(2, 99) if f"{base}-mood-{k}" not in names))
    apply_preset(m, "all")
    load_vanilla(m, src if src in vanilla else "village1")
    ctx.scene.og_props.mood = "custom"
    col.og_level.mood_custom = f"*{clean(m.name)}*"
    _show_mood(ctx.scene, m)
    return m, (src if src in vanilla else "village1")


class OG_OT_LevelEditMood(bpy.types.Operator):
    """Open the level's custom mood (fog, lights, time of day) in the Moods panel"""
    bl_idname = "og.level_edit_mood"
    bl_label = "Edit Mood"

    def execute(self, ctx):
        from .collections import _active_level_col
        m = level_mood(ctx.scene, _active_level_col(ctx.scene))
        if m is None:
            return {"CANCELLED"}
        _show_mood(ctx.scene, m)
        self.report({"INFO"}, f"*{clean(m.name)}*: open in the Moods panel (OpenGOAL tab)")
        return {"FINISHED"}


class OG_OT_LevelMakeMood(bpy.types.Operator):
    """Make a custom mood from the level's current mood (same look to start from) and use it: its fog,
    lights and time of day are then yours to change (Moods panel)"""
    bl_idname = "og.level_make_mood"
    bl_label = "Make a Custom Mood"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        from .collections import _active_level_col
        col = _active_level_col(ctx.scene)
        if col is None:
            return {"CANCELLED"}
        m, src = make_level_mood(ctx, col)
        self.report({"INFO"}, f"*{clean(m.name)}* (from {src}): open in the Moods panel")
        return {"FINISHED"}


class OG_OT_MoodFromFogOverride(bpy.types.Operator):
    """The old Fog override as a custom mood: a copy of the level's mood with the override's fog in every
    slot, used by the level (the same look); the override is turned off"""
    bl_idname = "og.mood_from_fog_override"
    bl_label = "Convert to a Custom Mood"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        from .collections import _active_level_col, _get_level_prop
        col = _active_level_col(ctx.scene)
        if col is None:
            return {"CANCELLED"}
        sc = ctx.scene
        c = tuple(_get_level_prop(sc, "og_fog_color", (0.376, 0.502, 0.627)))
        start, end = float(_get_level_prop(sc, "og_fog_start", 25.0)), float(_get_level_prop(sc, "og_fog_end", 200.0))
        fmax, fmin = float(_get_level_prop(sc, "og_fog_max", 0.95)), float(_get_level_prop(sc, "og_fog_min", 0.10))
        m = level_mood(sc, col)
        if m is None:
            m, _src = make_level_mood(ctx, col)
        else:
            _show_mood(sc, m)
        m.fog_from = "custom"
        for e in m.fog:
            e.enabled = True
            e.color = c[:3]
            e.start, e.end = start, end
            # as the override set them: max scaled to 0-255, min as it was (so the same look)
            e.clear_start, e.clear_end = fmax * 255.0, fmin
        sc.og_props.fog_override_enabled = False
        self.report({"INFO"}, f"Fog override is now *{clean(m.name)}*'s fog (Moods panel)")
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
        r = mb.row(align=True)
        r.prop(m, "match_curve")
        if m.match_curve not in _CURVE_FIXED:
            r.prop(m, "match_curve_factor", text="")
            from .vc_effects import curve_mapping
            if curve_mapping(m.match_curve_ng) is not None:
                node = next(n for n in m.match_curve_ng.nodes if n.bl_idname == "ShaderNodeRGBCurve")
                mb.template_curve_mapping(node, "mapping", type="COLOR")
        elif m.match_curve == "LEVEL" and col is not None and not col.og_bake.use_curve:
            _grey(mb, "Light Baking doesn't use a curve for this level", "INFO")
        ov = level_lighting(m, bpy.context.scene, values=False)
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
                # X / Y / Z on the left, the sphere on the right: both edit the same value
                sp = sb.split(factor=0.6)
                sp.enabled = "dir" not in got
                xyz = sp.column(align=True)
                xyz.label(text="Direction (to the light):")
                for j, ax in enumerate("XYZ"):
                    xyz.prop(e, "direction", index=j, text=ax)
                ball = sp.column()
                ball.scale_y = 4.0 / 3.0           # the sphere is 3 rows tall: grow it to the 4 rows on the left
                ball.prop(e, "direction", text="")
                field("color", "color")
                field("ambient", "ambient")
                rr = sb.row(align=True); rr.prop(e, "prt_auto")
                if not e.prt_auto:
                    rr.prop(e, "prt_color", text="")
            else:
                field("sun", "sun")
                sb.prop(e, "env")
    box.prop(m, "num_stars")


def _slots_text(e):
    s = effect_slots(e)
    if not s:
        return ""
    if len(s) == 1:
        return f"slot {s[0]} ({SLOT_NAMES[s[0]] if s[0] < 8 else '?'})"
    return f"slots {s[0]}-{s[-1]}"


def _grey(layout, text, icon="NONE"):
    h = layout.row(); h.enabled = False; h.scale_y = 0.7
    h.label(text=text, icon=icon)


def _draw_effect(layout, i, j, e):
    box = layout.box()
    r = box.row(align=True)
    r.prop(e, "expanded", text="", emboss=False, icon="TRIA_DOWN" if e.expanded else "TRIA_RIGHT")
    r.prop(e, "enabled", text="")
    r.label(text=f"{EFFECT_LABEL[e.kind]}  {_slots_text(e)}")
    op = r.operator("og.mood_fx_remove", text="", icon="X", emboss=False); op.index, op.fx = i, j
    if not e.expanded:
        return
    for line in EFFECT_HELP.get(e.kind, ()):
        _grey(box, line)
    c = box.column(align=True)
    c.enabled = e.enabled
    k = e.kind
    if k in ("flicker", "pulse", "lava", "caustics", "actor"):
        c.prop(e, "slot", text="First slot" if k in ("flicker", "lava", "caustics") else "Slot")
    if k == "flicker":
        c.prop(e, "count"); c.prop(e, "base"); c.prop(e, "strength"); c.prop(e, "speed")
    elif k == "pulse":
        c.prop(e, "base"); c.prop(e, "strength", text="Up / down"); c.prop(e, "period"); c.prop(e, "phase")
        c.prop(e, "night_only")
    elif k == "lightning":
        c.prop(e, "quiet")
        c.prop(e, "count", text="Flash slots")
        c.prop(e, "sky_slot")
        sub = c.column(align=True); sub.enabled = not e.quiet
        sub.prop(e, "slot", text="First palette slot")
        _grey(box, "Each palette slot's lights entry is also the flash light on actors", "INFO")
        _grey(box, "Needs a sky with flash textures and the thunder sound", "INFO")
    elif k == "lava":
        c.prop(e, "color"); c.prop(e, "strength"); c.prop(e, "speed"); c.prop(e, "drive_slots")
    elif k == "caustics":
        c.prop(e, "speed")
    elif k == "actor":
        _grey(box, "Use a Light switch actor (or the game's cave crystals ...) on this slot", "INFO")
    elif k == "fog_pitch":
        c.prop(e, "color"); c.prop(e, "amount"); c.prop(e, "clear")
    elif k == "fog_breath":
        r = c.row(align=True); r.prop(e, "dist_min"); r.prop(e, "dist_max")
        c.prop(e, "period"); c.prop(e, "shape")


def _draw_func(layout, f, i, issues):
    box = layout.box()
    if not _head(box, f, "func", i, f"update-mood-{clean(f.name) or '?'}", issues):
        return
    box.prop(f, "name")
    box.operator("og.mood_func_template", text="Template from a game function…", icon="PRESET").index = i
    r = box.row(align=True)
    r.prop(f, "time_mode")
    if f.time_mode == "lock":
        r.prop(f, "lock_hour")
    elif f.time_mode == "speed":
        r.prop(f, "time_speed")
    _grey(box, f"Effects ({len(f.effects)}): slots off in the mood's timeline are free for them", "INFO")
    for j, e in enumerate(f.effects):
        _draw_effect(box, i, j, e)
    for s, labels in effect_overlaps(f):
        _grey(box, f"Slot {s}: {' + '.join(labels)}" if s < 8 else f"Slot {s} doesn't exist (0-7)", "ERROR")
    box.operator_menu_enum("og.mood_fx_add", "kind", text="Add Effect", icon="ADD").index = i


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


CLASSES = (OGMoodTimeSlot, OGMoodFogSlot, OGMoodLightSlot, OGMoodSunSlot, OGMood, OGMoodEffect, OGMoodFunc,
           OG_OT_MoodFxAdd, OG_OT_MoodFxRemove, OG_OT_MoodFuncTemplate,
           OG_OT_MoodAdd, OG_OT_MoodRemove, OG_OT_MoodDuplicate, OG_OT_MoodTemplate, OG_OT_MoodPreset,
           OG_OT_LevelUseMood, OG_OT_LevelUseMoodFunc, OG_OT_LevelEditMood, OG_OT_LevelMakeMood,
           OG_OT_MoodFromFogOverride, OG_PT_Moods)


def register_props():
    bpy.types.Scene.og_moods = CollectionProperty(type=OGMood)
    bpy.types.Scene.og_mood_funcs = CollectionProperty(type=OGMoodFunc)


def unregister_props():
    for p in ("og_moods", "og_mood_funcs"):
        if hasattr(bpy.types.Scene, p):
            delattr(bpy.types.Scene, p)
