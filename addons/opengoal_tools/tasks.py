"""Custom tasks (Scene.og_tasks): what's saved in the .blend.

A task is a game-task number after the vanilla ones (115): its name, level,
scout-fly flag, the texts the progress menu shows, and its stages (the
task-control stage list: status + condition). The export (next step) writes
them into levels/level-tools/lt-tasks-<group>.gc. Needs mod-base (versions.py
"custom_tasks").

Several .blend files can add tasks to one game: each has its own "task
group" (default: the file name) and its own file, and new IDs skip the ones
other groups / mods / old levels already use.
"""
from __future__ import annotations

import re

import bpy
from bpy.props import (StringProperty, BoolProperty, IntProperty, EnumProperty,
                       PointerProperty, CollectionProperty)

ID_FIRST = 116          # first number after the vanilla tasks
ID_LIMIT = 254          # game-task is a uint8 and needs room for max (255)
TEXT_FIRST = 0xA00      # unused text ids (#xa00-#xeff); hints need < #x1000

STATUS_ITEMS = [  # task-status (task-control-h.gc), in order
    ("need-hint", "Need Hint", "Not known yet (scout fly / hint closes it)"),
    ("need-introduction", "Need Introduction", "Shown in the menu (name slot 1)"),
    ("need-reminder-a", "Need Reminder A", "Shown with name slot 1"),
    ("need-reminder", "Need Reminder", "Shown with name slot 2"),
    ("need-reward-speech", "Need Reward Speech", "Shown with name slot 3"),
    ("need-resolution", "Need Resolution", "Closed by collecting the task's power cell"),
]
CONDITION_ITEMS = [
    ("ALWAYS", "Always", "#t: the stage is available once the previous ones are closed"),
    ("STAGE_CLOSED", "Task stage closed", "Another task's stage is closed (task-closed?)"),
    ("CELLS", "Power cells ≥", "The player has at least N power cells"),
    ("ORBS", "Orbs ≥", "The player has at least N orbs"),
]
DONE_ITEMS = [
    ("0", "Introduced text", "Shown in the menu once the task is complete"),
    ("1", "Reminder text", "Shown in the menu once the task is complete"),
    ("2", "Resolution text", "Shown in the menu once the task is complete"),
]
# The Forgotten Lands' stage list: hint -> introduction -> reminder -> resolution
DEFAULT_STAGES = (("need-hint", True, False), ("need-introduction", False, True),
                  ("need-reminder", False, True), ("need-resolution", False, True))


def clean_name(s):
    """A game-task enum name: lowercase, a-z 0-9 and -."""
    return re.sub(r"[^a-z0-9-]+", "-", str(s).strip().lower()).strip("-")


def _levels(scene):
    from .collections import _all_level_collections
    return _all_level_collections(scene)


def _level_items(self, ctx):
    scene = ctx.scene if ctx else bpy.context.scene
    return [(c.name, str(c.get("og_level_name", c.name)), "") for c in _levels(scene)] or [("", "(no level)", "")]


def _filter_items(self, ctx):
    return [("ALL", "All tasks", "Every task of this .blend")] + list(_level_items(self, ctx))


def _task_level_get(self):
    names = [c.name for c in _levels(bpy.context.scene)]
    return names.index(self.level) if self.level in names else 0


def _task_level_set(self, i):
    names = [c.name for c in _levels(bpy.context.scene)]
    if 0 <= i < len(names):
        self.level = names[i]


def _task_name_set(self, value):
    self["name_"] = clean_name(value)


def _task_name_get(self):
    return self.get("name_", "")


class OGTaskStage(bpy.types.PropertyGroup):
    status: EnumProperty(name="Status", items=STATUS_ITEMS, default="need-introduction")
    closed_by_default: BoolProperty(name="Closed by default", default=False,
                                    description="Re-closed on a game reset (vanilla: most need-hint / need-introduction stages)")
    has_entity: BoolProperty(name="Saved", default=True,
                             description="Closing this stage is saved (task-flags has-entity)")
    condition: EnumProperty(name="Condition", items=CONDITION_ITEMS, default="ALWAYS")
    cond_task: StringProperty(name="Task", default="", description="Task whose stage must be closed (name)")
    cond_status: EnumProperty(name="Stage", items=STATUS_ITEMS, default="need-resolution")
    cond_value: IntProperty(name="Count", default=1, min=0, max=10000)


class OGTask(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", get=_task_name_get, set=_task_name_set,
                         description="game-task name (lowercase, a-z 0-9 -); also listed in the actors' task pickers")
    task_id: IntProperty(name="ID", default=ID_FIRST, min=2, max=255,
                         description="game-task number (after the vanilla 0-115)")
    level: StringProperty(name="Level", default="")
    level_pick: EnumProperty(name="Level", items=_level_items, get=_task_level_get, set=_task_level_set,
                             description="Level this task belongs to: its progress menu page")
    buzzer: BoolProperty(name="Scout fly task", default=False,
                         description="The level's scout-fly task (7 flies give its cell; the menu's fly slot)")
    text_intro: StringProperty(name="Introduced", default="",
                               description="Menu name once introduced. Empty: the next filled one. #xb11 = an existing text id, "
                                           "[level_name] = the level's Menu Name")
    text_reminder: StringProperty(name="Reminder", default="", description="Menu name at the reminder stage (same rules)")
    text_resolution: StringProperty(name="Resolution", default="", description="Menu name at the reward / resolution stage (same rules)")
    done_slot: EnumProperty(name="When complete", items=DONE_ITEMS, default="2",
                            description="Which text the menu shows once the task is complete")
    stages: CollectionProperty(type=OGTaskStage)
    expanded: BoolProperty(default=True)


class OGTaskSettings(bpy.types.PropertyGroup):
    enabled: BoolProperty(name="Custom tasks", default=False,
                          description="Export this .blend's tasks (needs mod-base)")
    group: StringProperty(name="Task group", default="",
                          description="Name of this .blend's task file (lt-tasks-<group>.gc). Empty: the .blend's file name. "
                                      "Use a different group per .blend that adds tasks to the same game")
    start_task_id: IntProperty(name="Starting task ID", default=ID_FIRST, min=2, max=ID_LIMIT,
                               description="First task ID new tasks get (raise it to keep clear of other mods' / old levels' tasks)")
    start_text_id: IntProperty(name="Starting text ID", default=TEXT_FIRST, min=0x100, max=0xFFFF,
                               description="First text id (decimal) the task names use; default #xa00. Used ids are skipped")
    filter_level: EnumProperty(name="Show", items=_filter_items, description="Show the tasks of one level, or all")
    tasks: CollectionProperty(type=OGTask)
    show_list: BoolProperty(name="Task list", default=True)
    show_settings: BoolProperty(name="Task settings", default=False)


def settings(scene=None):
    return (scene or bpy.context.scene).og_tasks


def group_name(scene=None):
    s = settings(scene)
    g = clean_name(s.group) if s.group.strip() else ""
    if not g:
        g = clean_name(bpy.path.display_name_from_filepath(bpy.data.filepath)) if bpy.data.filepath else ""
    return g or "tasks"


def next_task_id(scene=None, used=()):
    """The ID a new task gets: after the highest task of this .blend (or the
    starting ID), skipping `used` (other groups / mods / old levels)."""
    s = settings(scene)
    n = max([s.start_task_id] + [t.task_id + 1 for t in s.tasks])
    used = set(used)
    while n in used:
        n += 1
    return n


def problems(scene=None):
    """[(task index or -1, text)] for the panel / audit: duplicate names or
    IDs, IDs past the limit, tasks without a level, too many per level."""
    s = settings(scene)
    out = []
    names, ids, per_level = {}, {}, {}
    for i, t in enumerate(s.tasks):
        if not t.name:
            out.append((i, "no name"))
        elif t.name in names:
            out.append((i, f"name '{t.name}' used twice"))
        names.setdefault(t.name, i)
        if t.task_id in ids:
            out.append((i, f"ID {t.task_id} used twice"))
        ids.setdefault(t.task_id, i)
        if t.task_id > ID_LIMIT:
            out.append((i, f"ID {t.task_id} is past the limit ({ID_LIMIT})"))
        elif t.task_id < ID_FIRST:
            out.append((i, f"ID {t.task_id} is a vanilla task's number (custom tasks start at {ID_FIRST})"))
        if not t.level:
            out.append((i, "no level"))
        per_level.setdefault(t.level, []).append(i)
    for lv, idx in per_level.items():
        if lv and len(idx) > 8:
            out.append((-1, f"{lv}: {len(idx)} tasks, the progress menu shows 8 per level"))
        flies = [i for i in idx if s.tasks[i].buzzer]
        if len(flies) > 1:
            out.append((-1, f"{lv}: {len(flies)} scout-fly tasks (one per level)"))
    return out


def task_items(scene=None):
    """(id, name) of this .blend's tasks, for the actors' task pickers."""
    s = settings(scene)
    return [(t.task_id, t.name) for t in s.tasks if t.name]


# ── operators ───────────────────────────────────────────────────────────────

class OG_OT_TaskAdd(bpy.types.Operator):
    """Add a task (in the level shown, if one is picked)"""
    bl_idname = "og.task_add"
    bl_label = "Add Task"
    bl_options = {"UNDO"}

    def execute(self, ctx):
        s = settings(ctx.scene)
        new_id = next_task_id(ctx.scene)
        t = s.tasks.add()
        t.task_id = new_id
        lv = s.filter_level if s.filter_level not in ("ALL", "") else ""
        if not lv:
            from .collections import _active_level_col
            col = _active_level_col(ctx.scene)
            lv = col.name if col is not None else ""
        t.level = lv
        base = clean_name(ctx.scene.og_props.level_name if hasattr(ctx.scene.og_props, "level_name") else "task") or "task"
        n = 1
        names = {x.name for x in s.tasks}
        while f"{base}-task{n}" in names:
            n += 1
        t.name = f"{base}-task{n}"
        for status, cbd, ent in DEFAULT_STAGES:
            st = t.stages.add()
            st.status = status; st.closed_by_default = cbd; st.has_entity = ent
        return {"FINISHED"}


class OG_OT_TaskRemove(bpy.types.Operator):
    """Remove this task"""
    bl_idname = "og.task_remove"
    bl_label = "Remove Task"
    bl_options = {"UNDO"}
    index: IntProperty()

    def execute(self, ctx):
        s = settings(ctx.scene)
        if 0 <= self.index < len(s.tasks):
            s.tasks.remove(self.index)
        return {"FINISHED"}


class OG_OT_TaskStageAdd(bpy.types.Operator):
    """Add a stage to this task"""
    bl_idname = "og.task_stage_add"
    bl_label = "Add Stage"
    bl_options = {"UNDO"}
    index: IntProperty()

    def execute(self, ctx):
        s = settings(ctx.scene)
        if 0 <= self.index < len(s.tasks):
            s.tasks[self.index].stages.add()
        return {"FINISHED"}


class OG_OT_TaskStageRemove(bpy.types.Operator):
    """Remove this stage"""
    bl_idname = "og.task_stage_remove"
    bl_label = "Remove Stage"
    bl_options = {"UNDO"}
    index: IntProperty()
    stage: IntProperty()

    def execute(self, ctx):
        s = settings(ctx.scene)
        if 0 <= self.index < len(s.tasks) and 0 <= self.stage < len(s.tasks[self.index].stages):
            s.tasks[self.index].stages.remove(self.stage)
        return {"FINISHED"}


# ── panel ───────────────────────────────────────────────────────────────────

def _draw_task(layout, s, i, t, issues):
    box = layout.box()
    head = box.row(align=True)
    head.prop(t, "expanded", text="", emboss=False, icon="TRIA_DOWN" if t.expanded else "TRIA_RIGHT")
    head.label(text=f"{t.task_id}  {t.name or '(no name)'}", icon="FUND" if not t.buzzer else "GHOST_ENABLED")
    mine = [x for j, x in issues if j == i]
    if mine:
        w = head.row(); w.alert = True
        w.label(text=f"{len(mine)}⚠")
    head.operator("og.task_remove", text="", icon="X", emboss=False).index = i
    if not t.expanded:
        return
    for x in mine:
        w = box.row(); w.alert = True
        w.label(text=x, icon="ERROR")
    col = box.column(align=True)
    col.prop(t, "name")
    col.prop(t, "task_id")
    col.prop(t, "level_pick")
    col.prop(t, "buzzer")
    tb = box.column(align=True)
    tb.label(text="Texts (menu name per completion)")
    tb.prop(t, "text_intro")
    tb.prop(t, "text_reminder")
    tb.prop(t, "text_resolution")
    tb.prop(t, "done_slot")
    hint = box.row(); hint.enabled = False; hint.scale_y = 0.7
    hint.label(text="Empty: the next filled one · #xb11: a text id · [level_name]", icon="INFO")
    head, body = box.panel(f"og_task_stages_{i}", default_closed=True)
    head.label(text=f"Stages ({len(t.stages)})")
    if body is not None:
        for k, st in enumerate(t.stages):
            sb = body.box()
            r = sb.row(align=True)
            r.prop(st, "status", text="")
            op = r.operator("og.task_stage_remove", text="", icon="REMOVE")
            op.index = i; op.stage = k
            r = sb.row(align=True)
            r.prop(st, "condition", text="")
            if st.condition == "STAGE_CLOSED":
                r.prop(st, "cond_task", text="")
                r.prop(st, "cond_status", text="")
            elif st.condition in ("CELLS", "ORBS"):
                r.prop(st, "cond_value", text="")
            r = sb.row(align=True)
            r.prop(st, "closed_by_default", toggle=True)
            r.prop(st, "has_entity", toggle=True)
        body.operator("og.task_stage_add", text="Add Stage", icon="ADD").index = i


def draw_tasks(layout, ctx):
    s = settings(ctx.scene)
    from .versions import feature_status
    ok, why = feature_status("custom_tasks")
    row = layout.row()
    row.prop(s, "enabled")
    if ok is not True:
        w = layout.row(); w.alert = ok is False
        w.label(text=why or "Custom tasks need mod-base", icon="ERROR" if ok is False else "INFO")
    if not s.enabled:
        return
    layout.prop(s, "filter_level")
    issues = problems(ctx.scene)
    head, body = layout.panel("og_tasks_list", default_closed=False)
    shown = [(i, t) for i, t in enumerate(s.tasks) if s.filter_level in ("ALL", "") or t.level == s.filter_level]
    head.label(text=f"Task list ({len(shown)})")
    if body is not None:
        for i, t in shown:
            _draw_task(body, s, i, t, issues)
        body.operator("og.task_add", text="Add Task", icon="ADD")
        for j, x in issues:
            if j < 0:
                w = body.row(); w.alert = True
                w.label(text=x, icon="ERROR")
    head, body = layout.panel("og_tasks_settings", default_closed=True)
    head.label(text="Task settings")
    if body is not None:
        body.prop(s, "group")
        hint = body.row(); hint.enabled = False
        hint.label(text=f"File: lt-tasks-{group_name(ctx.scene)}.gc", icon="FILE_SCRIPT")
        body.prop(s, "start_task_id")
        body.prop(s, "start_text_id")
        hint = body.row(); hint.enabled = False
        hint.label(text=f"= #x{s.start_text_id:x}  (#xa00-#xeff are free in the vanilla game)", icon="INFO")


class OG_PT_Tasks(bpy.types.Panel):
    bl_label = "✔  Tasks"
    bl_idname = "OG_PT_tasks"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "OpenGOAL"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        draw_tasks(self.layout, ctx)


CLASSES = (OGTaskStage, OGTask, OGTaskSettings, OG_OT_TaskAdd, OG_OT_TaskRemove,
           OG_OT_TaskStageAdd, OG_OT_TaskStageRemove, OG_PT_Tasks)


def register_props():
    bpy.types.Scene.og_tasks = PointerProperty(type=OGTaskSettings)


def unregister_props():
    if hasattr(bpy.types.Scene, "og_tasks"):
        del bpy.types.Scene.og_tasks
