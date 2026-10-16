"""Level settings kept on the level collection (Collection.og_level).

The level-load-info fields written into level-info.gc that used to be
hardcoded (mood-func, ocean, sun-fade, bsphere, tasks, load-commands,
priority, wait-for-load ...) and the .jsonc collision options. Older
settings (name, index, mood, music ...) still live in the collection's
custom properties (collections.py _LEVEL_COL_DEFAULTS).
"""
from __future__ import annotations

import bpy
from bpy.props import (StringProperty, BoolProperty, IntProperty, FloatProperty,
                       EnumProperty, PointerProperty, CollectionProperty)

from . import db as _db
from .properties import OGCommandRow

# vanilla level-info.gc values
MOOD_FUNCS = ("citadel", "darkcave", "default", "finalboss", "firecanyon", "jungle", "jungleb",
              "lavatube", "maincave", "misty", "ogre", "robocave", "rolling", "snow", "sunken",
              "swamp", "training", "village1", "village2", "village3")
MOOD_FUNC_ITEMS = ([("AUTO", "Same as mood", "The mood's own update-mood-* function")]
                   + [(f, f"update-mood-{f}", f"'update-mood-{f}") for f in MOOD_FUNCS]
                   + [("CUSTOM", "Custom", "Type a function name")])
OCEAN_ITEMS = [
    ("NONE", "None", "No ocean (#f)"),
    ("village1", "Village 1", "'*ocean-map-village1* (Sandover, beach, misty ...)"),
    ("village2", "Village 2", "'*ocean-map-village2* (Rock Village, rolling)"),
    ("sunken", "Sunken", "'*ocean-map-sunken*"),
    ("CUSTOM", "Custom", "Type an ocean-map symbol"),
]


class OGTaskRow(bpy.types.PropertyGroup):
    task: StringProperty(name="Task", default="none", description="A game task of this level (vanilla or custom)")


def _bsphere_poll(self, ob):
    return ob.type == "EMPTY"


class OGLevelSettings(bpy.types.PropertyGroup):
    menu_name: StringProperty(
        name="Menu Name", default="",
        description="Name shown in the game's menu and text popups (kept for the tasks / menu work; not exported yet)")
    mood_custom: StringProperty(name="Mood", default="",
                                description="Mood symbol, e.g. *village1-mood* (or just village1)")
    sky_custom: StringProperty(name="Sky", default="",
                               description="Level whose sky is used, as the .jsonc \"sky\" (e.g. village1)")
    mood_func: EnumProperty(name="Mood Function", items=MOOD_FUNC_ITEMS, default="AUTO",
                            description="update-mood-* function run every frame for the mood")
    mood_func_custom: StringProperty(name="Function", default="", description="e.g. update-mood-village1")
    ocean: EnumProperty(name="Ocean", items=OCEAN_ITEMS, default="NONE",
                        description="Ocean map drawn with the level")
    ocean_custom: StringProperty(name="Ocean Map", default="", description="e.g. *ocean-map-village1*")
    sun_fade: FloatProperty(name="Sun Fade", default=1.0, min=0.0, max=1.0, subtype="FACTOR",
                            description="How much of the sun is drawn (the mood / time of day code fades it with this)")
    bsphere: PointerProperty(
        name="Bounding Sphere", type=bpy.types.Object, poll=_bsphere_poll,
        description="Empty (sphere): its position and size (display size x scale) are the level's bsphere. "
                    "The camera code uses it to find the level you're nearest to, which drives mood and sky "
                    "blending between levels. Empty field = computed from the checkpoints")
    tasks: CollectionProperty(type=OGTaskRow)
    load_cmds: CollectionProperty(type=OGCommandRow)
    alt_load_cmds: CollectionProperty(type=OGCommandRow)
    priority: IntProperty(name="Priority", default=100, min=0, max=1000,
                          description="Which of two loaded levels counts as the main one (lower wins). Vanilla: 100, "
                                      "some 200")
    wait_for_load: BoolProperty(name="Wait For Load", default=True,
                                description="Wait until the level is fully loaded before it's displayed")
    wall_angle: FloatProperty(name="Automatic Wall Angle", default=45.0, min=-1.0, max=90.0,
                              description="Faces steeper than this angle are walls (Jak can't stand on them). -1 = off")
    double_sided: BoolProperty(name="Double Sided Collision", default=False,
                               description="Collide with both sides of every face. Doubles the collision mesh")
    show_visuals: BoolProperty(name="Visuals", default=False)
    show_gameplay: BoolProperty(name="Gameplay", default=False)
    show_sound: BoolProperty(name="Sound & Music", default=False)
    show_others: BoolProperty(name="Others", default=False)
    show_commands: BoolProperty(name="Commands", default=False)


def settings(col):
    return col.og_level if col is not None else None


def mood_name(col):
    """The level's mood name (village1, or the custom one without *...-mood*)."""
    m = str(col.get("og_mood", "village1") or "village1") if col is not None else "village1"
    if m == "custom":
        v = col.og_level.mood_custom.strip().lstrip("'")
        if v.startswith("*") and v.endswith("-mood*"):
            v = v[1:-len("-mood*")]
        return v or "village1"
    return m


def mood_value(col):
    """level-info :mood symbol."""
    m = str(col.get("og_mood", "village1") or "village1") if col is not None else "village1"
    if m == "custom":
        v = col.og_level.mood_custom.strip().lstrip("'")
        if v.startswith("*"):
            return f"'{v}"
    return f"'*{mood_name(col)}-mood*"


def mood_func_value(s, mood_default):
    if s is None or s.mood_func == "AUTO":
        return f"'update-mood-{mood_default}"
    if s.mood_func == "CUSTOM":
        v = s.mood_func_custom.strip().lstrip("'")
        return f"'{v}" if v else f"'update-mood-{mood_default}"
    return f"'update-mood-{s.mood_func}"


def ocean_value(s):
    if s is None or s.ocean == "NONE":
        return "#f"
    if s.ocean == "CUSTOM":
        v = s.ocean_custom.strip().lstrip("'")
        return f"'{v}" if v else "#f"
    return f"'*ocean-map-{s.ocean}*"


def auto_tasks(s):
    """[(name, id)] of the custom tasks set to this level (added to its tasks)."""
    from .tasks import settings
    col = s.id_data if s is not None else None
    ts = settings()
    if col is None or not ts.enabled:
        return []
    return [(t.name, t.task_id) for t in ts.tasks if t.name and t.level == col.name]


def tasks_value(s):
    """level-info :tasks: the custom tasks of the level, then the listed ones."""
    if s is None:
        return "'()"
    from .tasks import task_value
    nums = [i for _n, i in auto_tasks(s)]
    for v in (task_value(r.task) for r in s.tasks):
        if v and v not in nums:
            nums.append(v)
    return f"'({' '.join(str(n) for n in nums)})" if nums else "'()"


def bsphere_value(s):
    """(new 'static 'sphere ...) from the linked empty, None when not set."""
    ob = s.bsphere if s is not None else None
    if ob is None:
        return None
    p = ob.matrix_world.translation
    r = ob.empty_display_size * max(ob.matrix_world.to_scale())
    gx, gy, gz = p.x, p.z, -p.y          # Blender -> game axes
    return (f"(new 'static 'sphere :x {round(gx * 4096.0, 1)} :y {round(gy * 4096.0, 1)}"
            f" :z {round(gz * 4096.0, 1)} :w {round(r * 4096.0, 1)})")


class OG_OT_LevelTaskAdd(bpy.types.Operator):
    """Add a task of this level"""
    bl_idname = "og.level_task_add"
    bl_label = "Add Task"
    bl_options = {"UNDO"}

    def execute(self, ctx):
        from .collections import _active_level_col
        col = _active_level_col(ctx.scene)
        if col is None:
            return {"CANCELLED"}
        col.og_level.tasks.add()
        return {"FINISHED"}


class OG_OT_LevelTaskRemove(bpy.types.Operator):
    """Remove this task"""
    bl_idname = "og.level_task_remove"
    bl_label = "Remove Task"
    bl_options = {"UNDO"}
    index: IntProperty()

    def execute(self, ctx):
        from .collections import _active_level_col
        col = _active_level_col(ctx.scene)
        if col is None or not (0 <= self.index < len(col.og_level.tasks)):
            return {"CANCELLED"}
        col.og_level.tasks.remove(self.index)
        return {"FINISHED"}


CLASSES = (OGTaskRow, OGLevelSettings, OG_OT_LevelTaskAdd, OG_OT_LevelTaskRemove)


def register_props():
    bpy.types.Collection.og_level = PointerProperty(type=OGLevelSettings)


def unregister_props():
    if hasattr(bpy.types.Collection, "og_level"):
        del bpy.types.Collection.og_level
