"""Hint volumes (Level Flow): the vanilla 'hint ambient (engine/entity/ambient.gc).

An AMBIENT_hint* empty (sphere). When the camera is inside its radius the game
shows its text at the top of the screen, once per save (the text is marked as
seen). Before showing, its commands run in order: an "If" command that fails
stops the hint; "Close" commands close a task's stage. The text goes in the
.blend's text file (tasks_export), like the task names.
"""
from __future__ import annotations

import bpy
from bpy.props import StringProperty, FloatProperty, EnumProperty, IntProperty, CollectionProperty, PointerProperty

from .game_text import draw_field
from .tasks import draw_task_pick, task_value

PREFIX = "AMBIENT_hint"

# (id, label, description, hint command number: level-hint-process-cmd)
CMDS = [
    ("if-unknown", "If task hidden", "Only if the task isn't known yet (still need-hint / unknown)", 0),
    ("if-known", "If task known", "Only if the task is known (in the menu)", 1),
    ("if-resolved", "If task done", "Only if every stage of the task is closed", 2),
    ("if-need-introduction", "If at need-introduction", "Only if the task's current stage is need-introduction", 3),
    ("if-need-reminder", "If at need-reminder", "Only if the task's current stage is need-reminder", 4),
    ("if-need-reminder-a", "If at need-reminder-a", "Only if the task's current stage is need-reminder-a", 5),
    ("if-need-reward-speech", "If at need-reward-speech", "Only if the task's current stage is need-reward-speech", 6),
    ("if-at-most-need-reminder-a", "If not past need-reminder-a", "Only if the task is at need-hint .. need-reminder-a", 13),
    ("close-need-hint", "Close need-hint", "Close the task's need-hint stage (shows it in the menu)", 7),
    ("close-need-introduction", "Close need-introduction", "Close the task's need-introduction stage", 8),
    ("close-need-reminder-a", "Close need-reminder-a", "Close the task's need-reminder-a stage", 10),
    ("close-need-reminder", "Close need-reminder", "Close the task's need-reminder stage", 9),
    ("close-need-reward-speech", "Close need-reward-speech", "Close the task's need-reward-speech stage", 11),
    ("close-need-resolution", "Close need-resolution", "Close the task's need-resolution stage", 12),
]
_CMD_NUM = {c[0]: c[3] for c in CMDS}


def _radius_update(self, ctx):
    o = self.id_data
    if isinstance(o, bpy.types.Object) and o.type == "EMPTY":
        o.empty_display_size = self.radius


class OGHintCmd(bpy.types.PropertyGroup):
    cmd: EnumProperty(name="Command", items=[c[:3] for c in CMDS], default="if-unknown")
    task: StringProperty(name="Task", default="none")


class OGHint(bpy.types.PropertyGroup):
    text: StringProperty(name="Text", default="", description="Shown at the top of the screen (once per save)")
    radius: FloatProperty(name="Radius", default=10.0, min=0.5, max=500.0, unit="LENGTH", update=_radius_update,
                          description="Shown when the camera is this close")
    cmds: CollectionProperty(type=OGHintCmd)


def is_hint(o):
    return o is not None and o.type == "EMPTY" and o.name.startswith(PREFIX)


def hint_texts(scene):
    """The level hints' texts (raw), in a stable order."""
    from .export.scene import _level_objects
    return [o.og_hint.text.strip() for o in sorted(_level_objects(scene), key=lambda o: o.name)
            if is_hint(o) and o.og_hint.text.strip()]


def problems(o):
    out = []
    if not o.og_hint.text.strip():
        out.append("no text: the hint isn't exported")
    for i, c in enumerate(o.og_hint.cmds):
        if task_value(c.task) in (None, 0):
            out.append(f"command {i + 1}: pick a task")
    return out


def ambient_entry(o, text_ids):
    """The jsonc ambient of a hint, or None (no text)."""
    from .game_text import game_text
    h = o.og_hint
    tid = text_ids.get(game_text(h.text.strip()))
    if tid is None:
        return None
    cmds = []
    for c in h.cmds:
        t = task_value(c.task)
        if t:
            cmds += [_CMD_NUM[c.cmd], t]
    l = o.location
    gx, gy, gz = round(l.x, 4), round(l.z, 4), round(-l.y, 4)
    lump = {
        "name": o.name[8:].lower() or "hint",
        "type": "'hint",
        "text-id": ["uint32", tid],
        "play-mode": "'notice",
    }
    if cmds:
        lump["cmds"] = ["int32"] + cmds
    return {"trans": [gx, gy, gz, h.radius], "bsphere": [gx, gy, gz, h.radius], "lump": lump}


class OG_OT_SpawnHint(bpy.types.Operator):
    """Add a hint volume at the 3D cursor: shows a text when the camera gets close, and can
check / close task stages"""
    bl_idname = "og.spawn_hint"
    bl_label = "Add Hint"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        from .collections import _link_object_to_sub_collection, _COL_PATH_SPAWNS
        from .export.scene import _level_objects
        n = 1
        names = {o.name for o in _level_objects(ctx.scene)}
        while f"{PREFIX}{n:03d}" in names:
            n += 1
        bpy.ops.object.empty_add(type="SPHERE", location=ctx.scene.cursor.location)
        o = ctx.active_object
        o.name = f"{PREFIX}{n:03d}"
        o.show_name = True
        o.color = (1.0, 0.6, 0.1, 1.0)
        o.og_hint.radius = 10.0
        o.empty_display_size = o.og_hint.radius
        _link_object_to_sub_collection(ctx.scene, o, *_COL_PATH_SPAWNS)
        return {"FINISHED"}


class OG_OT_HintCmdAdd(bpy.types.Operator):
    """Add a command: check a task's status before showing, or close one of its stages"""
    bl_idname = "og.hint_cmd_add"
    bl_label = "Add Command"
    bl_options = {"UNDO"}

    def execute(self, ctx):
        o = ctx.active_object
        if not is_hint(o):
            return {"CANCELLED"}
        o.og_hint.cmds.add()
        return {"FINISHED"}


class OG_OT_HintCmdRemove(bpy.types.Operator):
    """Remove this command"""
    bl_idname = "og.hint_cmd_remove"
    bl_label = "Remove Command"
    bl_options = {"UNDO"}
    index: IntProperty()

    def execute(self, ctx):
        o = ctx.active_object
        if not is_hint(o) or not 0 <= self.index < len(o.og_hint.cmds):
            return {"CANCELLED"}
        o.og_hint.cmds.remove(self.index)
        return {"FINISHED"}


class OG_PT_HintVolume(bpy.types.Panel):
    bl_label = "Hint"
    bl_idname = "OG_PT_hint_volume"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "OpenGOAL"
    bl_parent_id = "OG_PT_selected_object"

    @classmethod
    def poll(cls, ctx):
        return is_hint(ctx.active_object)

    def draw(self, ctx):
        o = ctx.active_object
        h = o.og_hint
        layout = self.layout
        draw_field(layout, h, "text")
        layout.prop(h, "radius")
        box = layout.box()
        box.label(text=f"Commands ({len(h.cmds)})" if len(h.cmds) else "Commands", icon="CHECKMARK")
        for i, c in enumerate(h.cmds):
            col = box.column(align=True)
            r = col.row(align=True)
            r.prop(c, "cmd", text="")
            r.operator("og.hint_cmd_remove", text="", icon="X").index = i
            draw_task_pick(col, c, "task", "Task:")
        box.operator("og.hint_cmd_add", text="Add Command", icon="ADD")
        for x in problems(o):
            w = layout.row(); w.alert = True
            w.label(text=x, icon="ERROR")
        for line in ("Shown once per save, when the camera is inside the radius.",
                     "Commands run in order: a failed If skips the hint,",
                     "Close commands run when it shows."):
            r = layout.row(); r.enabled = False; r.scale_y = 0.6
            r.label(text=line)


CLASSES = (OGHintCmd, OGHint, OG_OT_SpawnHint, OG_OT_HintCmdAdd, OG_OT_HintCmdRemove, OG_PT_HintVolume)


def register_props():
    bpy.types.Object.og_hint = PointerProperty(type=OGHint)


def unregister_props():
    if hasattr(bpy.types.Object, "og_hint"):
        del bpy.types.Object.og_hint
