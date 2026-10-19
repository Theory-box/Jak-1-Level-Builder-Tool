# ---------------------------------------------------------------------------
# actor_fields.py — OpenGOAL Level Tools
#
# Data-driven per-actor settings panel. Reads the actor's `fields[]` schema
# from the game database (jak1_game_database.jsonc) and draws UI for each
# field automatically. Replaces many of the bespoke OG_PT_Actor* panels.
#
# A field in the DB looks like:
#   {
#     "key":       "og_orbit_scale",
#     "label":     "Orbit scale",
#     "type":      "float" | "int" | "bool" | "enum" | "string" | "vector3" | "task",
#     "default":   ...,
#     "lump":      { "key": "scale", "type": "float" },   (informational)
#     "write_if":  "always" | "if_true" | "if_nonzero" | ...,
#     "choices":   [...]  or "CrateTypes" / "GameTasks" / ... (enums only)
#     "visible_if": { other_field_key: expected_value },  (optional)
#     "note":      "Extra info text shown below the input.",  (optional)
#   }
#
# Adding an actor to the generic panel requires only that its `fields[]` in the
# DB match its og_* Blender props. To give an actor a BESPOKE panel instead, set
# `"panel": "<id>"` on it in the DB and have that panel's poll check
# db.actor_panel(etype) == "<id>" — no hardcoded etype lists.
# ---------------------------------------------------------------------------
from __future__ import annotations
import bpy
from bpy.types import Operator, Panel
from bpy.props import StringProperty, BoolProperty

from .. import db as _db
from ..utils import _prop_row


# ═════════════════════════════════════════════════════════════════════════════
# Generic setter operators — used by the panel to write custom props
# ═════════════════════════════════════════════════════════════════════════════
_ALT_TIP = ". Alt+click: all selected actors with this setting"


def alt_targets(context, key, all_selected):
    """The active actor, plus (Alt held) every other selected actor that has
    the field `key` — like Blender's Alt+edit on regular properties."""
    obj = context.active_object
    out = [obj] if obj is not None else []
    if all_selected:
        for o in context.selected_objects:
            if o is obj or not o.name.startswith("ACTOR_") or "_wp_" in o.name:
                continue
            et = o.name.split("_", 2)[1]
            if any(f.get("key") == key for f in _db.inherited_fields(et)):
                out.append(o)
    return out


class OG_OT_SetActorEnumField(Operator):
    bl_idname = "og.set_actor_enum_field"
    bl_label = "Set Field"
    bl_description = "Set this value" + _ALT_TIP
    bl_options = {"INTERNAL", "UNDO"}

    prop_key: StringProperty()
    value: StringProperty()
    all_selected: BoolProperty(options={"SKIP_SAVE", "HIDDEN"})

    def invoke(self, context, event):
        self.all_selected = event.alt
        return self.execute(context)

    def execute(self, context):
        objs = alt_targets(context, self.prop_key, self.all_selected)
        if not objs:
            return {"CANCELLED"}
        for obj in objs:
            obj[self.prop_key] = self.value
            obj.update_tag()   # custom props don't notify the depsgraph by themselves
            _refresh_variant_preview(context, obj, self.prop_key)
        if len(objs) > 1:
            self.report({"INFO"}, f"Set on {len(objs)} actors")
        return {"FINISHED"}


def _refresh_variant_preview(context, obj, key):
    """A new variant can have its own model / offset: rebuild the preview
    (when preview models are on)."""
    from .. import model_preview as _mp
    prefs = context.preferences.addons.get("opengoal_tools")
    if not obj.name.startswith("ACTOR_") or not (prefs and prefs.preferences.preview_models):
        return
    etype = obj.name.split("_", 2)[1]
    vf = _db.variant_field(etype)
    if not vf or vf.get("key") != key:
        return
    if "_og_preview_offset_ovr" in obj:
        del obj["_og_preview_offset_ovr"]
    _mp.remove_preview(obj)
    _mp.attach_preview(context, etype, obj)


class OG_OT_InitColorField(Operator):
    """Add this colour field to the actor (with the colour picker)"""
    bl_idname = "og.init_color_field"
    bl_label = "Set Colour"
    bl_options = {"INTERNAL", "UNDO"}

    prop_key: StringProperty()

    def execute(self, context):
        obj = context.active_object
        if obj is None:
            return {"CANCELLED"}
        etype = obj.name.split("_", 2)[1] if obj.name.count("_") >= 2 else ""
        f = next((x for x in _db.inherited_fields(etype) if x.get("key") == self.prop_key), {})
        obj[self.prop_key] = list(f.get("default") or [1.0, 1.0, 1.0])
        obj.id_properties_ui(self.prop_key).update(subtype="COLOR", min=0.0, max=1.0, soft_min=0.0, soft_max=1.0)
        return {"FINISHED"}


class OG_OT_SetFieldFromZ(Operator):
    """Set this field to the active object's height (Blender Z = game height)"""
    bl_idname = "og.set_field_from_z"
    bl_label = "Set From Height"
    bl_options = {"INTERNAL", "UNDO"}

    prop_key: StringProperty()

    def execute(self, context):
        obj = context.active_object
        if obj is None:
            return {"CANCELLED"}
        obj[self.prop_key] = round(obj.matrix_world.translation.z, 4)
        return {"FINISHED"}


class OG_OT_ToggleActorBoolField(Operator):
    bl_idname = "og.toggle_actor_bool_field"
    bl_label = "Toggle Field"
    bl_description = "Toggle this setting" + _ALT_TIP
    bl_options = {"INTERNAL", "UNDO"}

    prop_key: StringProperty()
    all_selected: BoolProperty(options={"SKIP_SAVE", "HIDDEN"})

    def invoke(self, context, event):
        self.all_selected = event.alt
        return self.execute(context)

    def execute(self, context):
        obj = context.active_object
        if obj is None:
            return {"CANCELLED"}
        new = not bool(obj.get(self.prop_key, False))   # all get the active one's new state
        for o in alt_targets(context, self.prop_key, self.all_selected):
            o[self.prop_key] = new
            o.update_tag()
        return {"FINISHED"}


# ═════════════════════════════════════════════════════════════════════════════
# Resolve `choices` references against the database
# ═════════════════════════════════════════════════════════════════════════════
def _resolve_choices(choices_spec):
    """Turn a `choices` spec into a list of {value, label} dicts.

    Accepted inputs:
      * list of {value, label, ...} dicts  → returned as-is (with optional fields intact)
      * list of plain strings              → normalised into dicts
      * "CrateTypes"                       → db.crate_types()
      * "CratePickups"                     → db.crate_pickups()
      * "GameTasks"                        → db.game_tasks() (the game-task enum, none first)
      * "SoundBanks"                       → db.sound_banks()
      * "BankSFX"                          → flattened bank/sfx list
      * anything else → []
    """
    if isinstance(choices_spec, list):
        out = []
        for c in choices_spec:
            if isinstance(c, dict):
                # inline variant lists may key entries by "id"
                out.append(c if "value" in c else {**c, "value": c.get("id")})
            else:
                out.append({"value": str(c), "label": str(c)})
        return out

    if isinstance(choices_spec, str):
        if choices_spec == "CratePickups":
            return [{"value": p["id"], "label": p["label"]} for p in _db.crate_pickups()]
        if choices_spec == "GameTasks":   # already starts with none
            return [{"value": t["id"], "label": t["label"]} for t in _db.game_tasks()]
        if choices_spec == "SoundBanks":
            return [{"value": b["id"], "label": b["label"]} for b in _db.sound_banks()]
        if choices_spec in ("BankSFX", "BankSFXOrNone"):
            out = [{"value": "none", "label": "None"}] if choices_spec == "BankSFXOrNone" else []
            for bank, sounds in _db.bank_sfx().items():
                for s in sounds:
                    out.append({"value": s, "label": f"[{bank}] {s}"})
            return out
        # Generic: any top-level named table of {id/value, label} entries
        # (e.g. BridgeVariants) works without a bespoke case.
        table = _db.choices_table(choices_spec)
        if table:
            return [{"value": e.get("id", e.get("value")),
                     "label": e.get("label", e.get("id", e.get("value")))}
                    for e in table]
    return []


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════
def _field_visible(obj, field) -> bool:
    cond = field.get("visible_if")
    if not cond:
        return True
    for k, expected in cond.items():
        # A list means "any of these values" (e.g. camera fields per mode).
        if isinstance(expected, list):
            if obj.get(k) not in expected:
                return False
        elif isinstance(expected, dict) and "not" in expected:
            # {"not": v}: hidden while the field is v (unset = its default)
            if obj.get(k, expected.get("default")) == expected["not"]:
                return False
        elif obj.get(k) != expected:
            return False
    return True


def _resolve_default(field, obj, actor_info):
    """Return the display default for a field."""
    if "default" in field:
        return field["default"]
    # Per-etype defaults (e.g. lavaballoon: 3.0 vs darkecobarrel: 15.0)
    if "default_per_etype" in field and actor_info:
        per = field["default_per_etype"]
        return per.get(actor_info.get("etype"))
    return None


# ═════════════════════════════════════════════════════════════════════════════
# Draw a single field
# ═════════════════════════════════════════════════════════════════════════════
def _draw_note(layout, note: str):
    row = layout.row()
    row.enabled = False
    row.label(text=note, icon="INFO")


def _draw_enum_field(layout, obj, field):
    key = field["key"]
    label = field.get("label", key)
    choices = _resolve_choices(field.get("choices", []))
    if not choices:
        row = layout.row()
        row.alert = True
        row.label(text=f"{label}: no choices defined", icon="ERROR")
        return

    current = obj.get(key)
    if current is None:
        current = field.get("default")

    if len(choices) > 12 or field.get("dropdown"):
        # Long lists (water looks ...): a searchable dropdown.
        row = layout.row(align=True)
        row.label(text=f"{label}:")
        cur = next((c.get("label", c.get("value")) for c in choices if c.get("value") == current), str(current))
        op = row.operator("og.pick_enum_field", text=cur, icon="DOWNARROW_HLT")
        op.prop_key = key
        return

    box = layout.box()
    box.label(text=f"{label}:")
    col = box.column(align=True)
    for c in choices[:40]:  # cap the render count to avoid UI stalls
        val = c.get("value", "")
        disp = c.get("label", val)
        sub = col.row(align=True)
        icon = "RADIOBUT_ON" if current == val else "RADIOBUT_OFF"
        op = sub.operator("og.set_actor_enum_field", text=disp, icon=icon)
        op.prop_key = key
        op.value = val
    if len(choices) > 40:
        row = box.row()
        row.enabled = False
        row.label(text=f"… (+{len(choices) - 40} more, edit DB to reduce)")


def _draw_task_field(layout, obj, field):
    """Game task: a searchable picker (None, Custom..., every game task) and a
    text field for a custom task name when Custom is picked."""
    key = field["key"]
    label = field.get("label", key)
    cur = obj.get(key, field.get("default", "none")) or "none"
    from ..tasks import task_label
    row = layout.row(align=True)
    row.label(text=f"{label}:")
    op = row.operator("og.pick_task", text="Custom…" if cur == "custom" else task_label(cur), icon="VIEWZOOM")
    op.prop_key = key
    if cur == "custom":
        _prop_row(layout, obj, key + "_custom", "  Custom task:", "")


class OG_OT_PickTask(Operator):
    """Pick a game task (search by name): vanilla tasks and this .blend's custom tasks.
Alt+click: all selected actors with this setting"""
    bl_idname   = "og.pick_task"
    bl_label    = "Pick Game Task"
    bl_options  = {"REGISTER", "UNDO"}
    bl_property = "task"

    def _items(self, context):
        from ..tasks import task_choices
        # the DB list (game-task-h.gc) already starts with none; custom tasks after it
        items = [("custom", "Custom…", "Type a task name, number or (GOAL expression)")]
        items += [(v, lab if v in ("none", lab.split()[0]) else f"{lab}  ({v})", v)
                  for v, lab in task_choices(context.scene)]
        items = [(a, b, c, i) for i, (a, b, c) in enumerate(items)]
        if items != _TASK_ITEMS:
            _TASK_ITEMS[:] = items
        return _TASK_ITEMS

    prop_key: StringProperty(options={"SKIP_SAVE"})
    # set for a property of a property group (draw_task_pick): the owner is
    # scene/object <id_name> . <data_path>; else the active actor's custom prop
    data_path: StringProperty(options={"SKIP_SAVE", "HIDDEN"})
    id_name: StringProperty(options={"SKIP_SAVE", "HIDDEN"})
    id_kind: StringProperty(options={"SKIP_SAVE", "HIDDEN"})
    all_selected: BoolProperty(options={"SKIP_SAVE", "HIDDEN"})
    task:     bpy.props.EnumProperty(name="Task", items=_items)

    def invoke(self, context, event):
        self.all_selected = event.alt
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        if self.data_path:
            ids = {"SCENE": bpy.data.scenes, "COLLECTION": bpy.data.collections}.get(self.id_kind, bpy.data.objects)
            idb = ids.get(self.id_name)
            try:
                owner = idb.path_resolve(self.data_path) if idb is not None else None
            except ValueError:
                owner = None
            if owner is None:
                return {"CANCELLED"}
            from ..tasks import is_custom_value
            if self.task != "custom":
                setattr(owner, self.prop_key, self.task)
            elif not is_custom_value(getattr(owner, self.prop_key)):
                setattr(owner, self.prop_key, "")          # empty = Custom: its text field shows
            for a in context.screen.areas if context.screen else ():
                a.tag_redraw()
            return {"FINISHED"}
        obj = context.active_object
        if obj is None or not self.prop_key:
            return {"CANCELLED"}
        for o in alt_targets(context, self.prop_key, self.all_selected):
            o[self.prop_key] = self.task
            o.update_tag()
            if self.task == "custom" and (self.prop_key + "_custom") not in o:
                o[self.prop_key + "_custom"] = obj.get(self.prop_key + "_custom", "")
        return {"FINISHED"}


_TASK_ITEMS: list = []   # search-popup items must stay referenced


class OG_OT_PickEnumField(Operator):
    """Pick a value from a long list (search by name). Alt+click: all selected actors with this setting"""
    bl_idname   = "og.pick_enum_field"
    bl_label    = "Pick Value"
    bl_options  = {"REGISTER", "UNDO"}
    bl_property = "value"

    def _items(self, context):
        obj = context.active_object
        et = obj.name.split("_", 2)[1] if obj and obj.name.count("_") >= 2 else ""
        f = next((x for x in _db.inherited_fields(et) if x.get("key") == self.prop_key), None)
        items = [(c.get("value", ""), c.get("label", c.get("value", "")), "")
                 for c in _resolve_choices((f or {}).get("choices", []))]
        _ENUM_ITEMS[:] = [(a, b, c, i) for i, (a, b, c) in enumerate(items or [("NONE", "-", "")])]
        return _ENUM_ITEMS

    prop_key: StringProperty(options={"SKIP_SAVE"})
    all_selected: BoolProperty(options={"SKIP_SAVE", "HIDDEN"})
    value:    bpy.props.EnumProperty(name="Value", items=_items)

    def invoke(self, context, event):
        self.all_selected = event.alt
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        if not self.prop_key or self.value == "NONE":
            return {"CANCELLED"}
        # same path as the radio buttons (variant preview refresh ...)
        return bpy.ops.og.set_actor_enum_field(prop_key=self.prop_key, value=self.value, all_selected=self.all_selected)


_ENUM_ITEMS: list = []


def _draw_bool_field(layout, obj, field):
    key = field["key"]
    label = field.get("label", key)
    val = bool(obj.get(key, field.get("default", False)))
    box = layout.box()
    icon = "CHECKBOX_HLT" if val else "CHECKBOX_DEHLT"
    op = box.operator("og.toggle_actor_bool_field", text=label, icon=icon)
    op.prop_key = key


def _draw_vector3_field(layout, obj, field):
    key = field["key"]
    label = field.get("label", key)
    default = field.get("default")
    if not isinstance(default, list) or len(default) != 3:
        default = [0.0, 0.0, 0.0]
    col = layout.column(align=True)
    col.label(text=f"{label}:")
    for axis, dval in zip("xyz", default):
        _prop_row(col, obj, f"{key}_{axis}", f"  {axis.upper()}:", dval)


def _draw_field(layout, obj, field, actor_info=None):
    if not _field_visible(obj, field):
        return

    ftype = field.get("type", "string")
    label = field.get("label", field["key"])
    default = _resolve_default(field, obj, actor_info)

    if ftype == "enum":
        _draw_enum_field(layout, obj, field)
    elif ftype == "task":
        _draw_task_field(layout, obj, field)
    elif ftype == "bool":
        _draw_bool_field(layout, obj, field)
    elif ftype == "vector3":
        _draw_vector3_field(layout, obj, field)
    elif ftype == "color":
        row = layout.row(align=True)
        row.label(text=f"{label}:")
        if field["key"] in obj:
            row.prop(obj, f'["{field["key"]}"]', text="")
        else:
            op = row.operator("og.init_color_field", text="Set colour", icon="COLOR")
            op.prop_key = field["key"]
    elif ftype == "object_ref":
        _draw_object_ref(layout, obj, field, label)
    else:
        # float / int / string — _prop_row handles all three
        _prop_row(layout, obj, field["key"], f"{label}:",
                  default if default is not None else 0)
        # "from_location": "z" -> button that copies the object's Blender Z
        # (game height) into the field (e.g. water heights).
        if field.get("from_location") == "z":
            op = layout.operator("og.set_field_from_z", text="Set to this actor's height", icon="EMPTY_SINGLE_ARROW")
            op.prop_key = field["key"]

    if field.get("note"):
        _draw_note(layout, field["note"])


# ═════════════════════════════════════════════════════════════════════════════
# The generic panel
# ═════════════════════════════════════════════════════════════════════════════

# Which panels an actor shows comes from its DB "panels" list (and its
# parents'), read via db.has_panel() / db.actor_panel(). No etype lists.


class OG_PT_ActorFields(Panel):
    """Data-driven per-actor settings panel.

    Reads the actor's fields[] schema from the game database and draws UI
    for each field automatically. Replaces most of the former per-actor
    OG_PT_Actor* panels.
    """
    bl_label       = "Actor Settings"
    bl_idname      = "OG_PT_actor_fields"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_order       = 10
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        # Container for all per-actor settings (its sub-panels + generic fields).
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name:
            return False
        parts = sel.name.split("_", 2)
        return len(parts) >= 3 and parts[0] == "ACTOR"

    def draw_header(self, ctx):
        from ..required import draw_header_count
        draw_header_count(self.layout, ctx.active_object)

    def draw(self, ctx):
        sel = ctx.active_object
        parts = sel.name.split("_", 2)
        etype = parts[1]
        # The generic field list is the "custom-fields" panel; actors with a
        # bespoke panel keep it hidden ("show-panel": false) and this container
        # just parents their sub-panels.
        actor = _db.find_actor(etype)
        if not actor:
            self.layout.label(text=f"No DB entry for {etype!r}", icon="ERROR")
            return
        # Include etype on actor_info dict so per-etype defaults work for
        # shared field groups (e.g. lavaballoon=3.0 vs darkecobarrel=15.0)
        actor_info = {"etype": etype, **actor}
        if _db.has_panel(etype, "custom-fields"):
            fields = [f for f in _db.ui_fields(etype) if f.get("show-field") is not False]   # DB: hidden but still exported
            done = set()
            for field in fields:
                grp = field.get("group")
                if not grp:
                    _draw_field(self.layout, sel, field, actor_info)
                elif grp not in done:
                    # "group": fields drawn together in a collapsible sub menu;
                    # the first one's "group_label" / "group_note" head it.
                    done.add(grp)
                    title, note = field.get("group_label", grp), field.get("group_note")
                    if hasattr(self.layout, "panel"):
                        header, body = self.layout.panel(f"og_fields_{grp}", default_closed=True)
                        header.label(text=title)
                    else:
                        body = self.layout.box(); body.label(text=title)
                    if body is None:
                        continue
                    if note:
                        body.label(text=note, icon="INFO")
                    for f in fields:
                        if f.get("group") == grp:
                            _draw_field(body, sel, f, actor_info)
        # Small DB panels with no hand-written Blender panel ("draw": "generic").
        for pid, pt in _db.generic_panels(etype):
            box = self.layout.box()
            box.label(text=pt.get("label", pid))
            for field in _db.panel_fields(etype, pid, visible_only=True):
                _draw_field(box, sel, field, actor_info)


# Exported registry for __init__.py
# ── object reference fields: pick an object from a list, or add an empty ─────

def _objref_kind(field):
    """The object type an object_ref field takes: its "pick" option (EMPTY /
    CAMERA), else EMPTY."""
    return str(field.get("pick", "EMPTY")).upper()


def _objref_ok(o, kind):
    if kind == "CAMERA":
        return o.type == "CAMERA" and o.name.startswith("CAMERA_")
    return o.type == kind


def _draw_object_ref(layout, obj, field, label):
    key = field["key"]
    kind = _objref_kind(field)
    name = str(obj.get(key, "") or "")
    box = layout.box()
    box.label(text=label, icon="OUTLINER_OB_CAMERA" if kind == "CAMERA" else "EMPTY_AXIS")
    row = box.row(align=True)
    tgt = bpy.data.objects.get(name) if name else None
    if tgt is not None:
        row.label(text=tgt.name, icon="CHECKMARK")
        row.operator("og.select_and_frame", text="", icon="VIEWZOOM").obj_name = tgt.name
        op = row.operator("og.objref_set", text="", icon="X")
        op.prop_key, op.value = key, ""
    elif name:
        row.alert = True
        row.label(text=f"missing: {name}", icon="ERROR")
        op = row.operator("og.objref_set", text="", icon="X")
        op.prop_key, op.value = key, ""
    row = box.row(align=True)
    op = row.operator("og.objref_pick", text="Pick" if tgt is None else "Change", icon="VIEWZOOM")
    op.prop_key, op.kind = key, kind
    if kind == "EMPTY":
        op = row.operator("og.objref_add_empty", text="Add Empty at Cursor", icon="ADD")
        op.prop_key, op.label = key, label


_OBJREF_ITEMS: list = []


def _objref_items(self, ctx):
    _OBJREF_ITEMS[:] = [(o.name, o.name, "", "OUTLINER_OB_CAMERA" if self.kind == "CAMERA" else "EMPTY_AXIS", i)
                        for i, o in enumerate(sorted((o for o in ctx.scene.objects if _objref_ok(o, self.kind)
                                                      and not o.name.startswith(("ACTOR_", "AMBIENT_"))),
                                                     key=lambda o: o.name))] or [("", "(none in the scene)", "", "ERROR", 0)]
    return _OBJREF_ITEMS


class OG_OT_ObjrefPick(Operator):
    """Pick the object for this field (search)"""
    bl_idname = "og.objref_pick"
    bl_label = "Pick Object"
    bl_options = {"REGISTER", "UNDO"}
    bl_property = "pick"
    prop_key: StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    kind: StringProperty(default="EMPTY", options={"HIDDEN", "SKIP_SAVE"})
    pick: bpy.props.EnumProperty(name="Object", items=_objref_items)

    def invoke(self, ctx, event):
        ctx.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, ctx):
        o = ctx.active_object
        if o is None or not self.pick:
            return {"CANCELLED"}
        o[self.prop_key] = self.pick
        return {"FINISHED"}


class OG_OT_ObjrefSet(Operator):
    """Clear this field"""
    bl_idname = "og.objref_set"
    bl_label = "Clear"
    bl_options = {"REGISTER", "UNDO"}
    prop_key: StringProperty()
    value: StringProperty()

    def execute(self, ctx):
        o = ctx.active_object
        if o is None:
            return {"CANCELLED"}
        o[self.prop_key] = self.value
        return {"FINISHED"}


class OG_OT_ObjrefAddEmpty(Operator):
    """Add an empty at the 3D cursor (in the actor's collection) and link it to this field"""
    bl_idname = "og.objref_add_empty"
    bl_label = "Add Empty"
    bl_options = {"REGISTER", "UNDO"}
    prop_key: StringProperty()
    label: StringProperty()

    def execute(self, ctx):
        o = ctx.active_object
        if o is None:
            return {"CANCELLED"}
        import re as _re
        base = o.name[6:] if o.name.startswith("ACTOR_") else o.name
        e = bpy.data.objects.new(f"{base}_{_re.sub(r'[^A-Za-z0-9]+', '_', self.label).strip('_').lower() or 'point'}", None)
        e.empty_display_type = "ARROWS"           # shows its rotation (facing)
        e.empty_display_size = 1.0
        e.show_name = True
        e.location = ctx.scene.cursor.location
        for c in o.users_collection:
            c.objects.link(e)
        o[self.prop_key] = e.name
        return {"FINISHED"}


CLASSES = (
    OG_OT_ObjrefPick,
    OG_OT_ObjrefSet,
    OG_OT_ObjrefAddEmpty,
    OG_OT_PickTask,
    OG_OT_PickEnumField,
    OG_OT_SetActorEnumField,
    OG_OT_SetFieldFromZ,
    OG_OT_InitColorField,
    OG_OT_ToggleActorBoolField,
    OG_PT_ActorFields,
)
