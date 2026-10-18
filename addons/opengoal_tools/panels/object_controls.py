"""Object Controls: actions on the whole selection (any objects), what's
selected by kind, and the selection tools (sub-panels)."""
from __future__ import annotations

import bpy
from bpy.types import Panel, Operator
from bpy.props import StringProperty

# (category, icon) in display order; classify() picks one per object
CATEGORIES = (
    ("Actors", "OBJECT_DATA"),
    ("Waypoints", "CURVE_PATH"),
    ("Checkpoints", "EMPTY_SINGLE_ARROW"),
    ("Cameras", "CAMERA_DATA"),
    ("Trigger volumes", "MESH_CUBE"),
    ("Load boundaries", "MOD_EDGESPLIT"),
    ("Nav-meshes", "MOD_MESHDEFORM"),
    ("Ambients & hints", "SPEAKER"),
    ("Meshes", "MESH_DATA"),
    ("Previews", "HIDE_OFF"),
    ("Curves", "CURVE_DATA"),
    ("Empties", "EMPTY_AXIS"),
    ("Lights", "LIGHT"),
    ("Other", "QUESTION"),
)
_ICON = dict(CATEGORIES)
_LIST_MAX = 40          # objects listed per category


def classify(o):
    n, t = o.name, o.type
    if o.get("og_preview_mesh") or o.get("og_waypoint_preview_mesh"):
        return "Previews"
    if "_wp_" in n or "_wpb_" in n:
        return "Waypoints"
    if n.startswith("ACTOR_"):
        return "Actors"
    if n.startswith("CHECKPOINT_") and not n.endswith("_CAM"):
        return "Checkpoints"
    if t == "CAMERA" or n.endswith(("_CAM", "_ALIGN", "_PIVOT", "_LOOKAT")):
        return "Cameras"
    if n.startswith("VOL_"):
        return "Trigger volumes"
    if n.startswith("LOADBND_"):
        return "Load boundaries"
    if t == "MESH" and (n.startswith("NAVMESH_") or o.get("og_navmesh")):
        return "Nav-meshes"
    if n.startswith("AMBIENT_"):
        return "Ambients & hints"
    return {"MESH": "Meshes", "CURVE": "Curves", "EMPTY": "Empties", "LIGHT": "Lights"}.get(t, "Other")


def grouped(objs):
    """{category: [objects]} in display order (only non-empty)."""
    out = {c: [] for c, _i in CATEGORIES}
    for o in objs:
        out[classify(o)].append(o)
    return {c: sorted(v, key=lambda o: o.name) for c, v in out.items() if v}


def summary(objs):
    g = grouped(objs)
    parts = [f"{len(v)} {c}" for c, v in g.items()]
    return f"{len(objs)} selected" + (f" ({', '.join(parts)})" if parts else "")


class OG_OT_SelectionFilter(Operator):
    """Select only this object / category, or remove it from the selection"""
    bl_idname = "og.selection_filter"
    bl_label = "Selection"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}
    obj_name: StringProperty(options={"SKIP_SAVE"})
    category: StringProperty(options={"SKIP_SAVE"})
    mode: StringProperty(default="ONLY", options={"SKIP_SAVE"})      # ONLY / REMOVE

    @classmethod
    def description(cls, ctx, props):
        what = props.obj_name or f"the {props.category}"
        return f"Select only {what}" if props.mode == "ONLY" else f"Remove {what} from the selection"

    def execute(self, ctx):
        sel = list(ctx.selected_objects)
        if self.obj_name:
            target = [o for o in sel if o.name == self.obj_name]
        else:
            target = [o for o in sel if classify(o) == self.category]
        if not target:
            return {"CANCELLED"}
        if self.mode == "ONLY":
            for o in sel:
                if o not in target:
                    o.select_set(False)
            if ctx.view_layer.objects.active not in target:
                ctx.view_layer.objects.active = target[0]
        else:
            for o in target:
                o.select_set(False)
            act = ctx.view_layer.objects.active
            if act in target:
                rest = [o for o in sel if o not in target]
                ctx.view_layer.objects.active = rest[0] if rest else None
        return {"FINISHED"}


class OG_OT_DuplicateSelection(Operator):
    """Duplicate the selected objects in place (addon objects get the addon's names and their own previews)"""
    bl_idname = "og.duplicate_selection"
    bl_label = "Duplicate"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, ctx):
        return bool(ctx.selected_objects) and ctx.mode == "OBJECT"

    def execute(self, ctx):
        bpy.ops.object.duplicate()
        return {"FINISHED"}


class OG_OT_DeleteSelection(Operator):
    """Delete the selected objects (an actor's preview, helper empties and the volume links pointing at it go too)"""
    bl_idname = "og.delete_selection"
    bl_label = "Delete"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, ctx):
        return bool(ctx.selected_objects) and ctx.mode == "OBJECT"

    def execute(self, ctx):
        bpy.ops.object.delete()
        return {"FINISHED"}


class OG_PT_ObjectControls(Panel):
    bl_label = "🎛  Object Controls"
    bl_idname = "OG_PT_object_controls"
    bl_order = 3
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "OpenGOAL"

    def draw(self, ctx):
        layout = self.layout
        sel = ctx.selected_objects
        row = layout.row(align=True)
        row.enabled = bool(sel)
        row.operator("view3d.view_selected", text="Frame", icon="VIEWZOOM")
        row.operator("og.duplicate_selection", text="Duplicate", icon="DUPLICATE")
        row.operator("og.delete_selection", text="Delete", icon="TRASH")
        if not sel:
            layout.label(text="Nothing selected", icon="INFO")
            return
        head, body = layout.panel("og_selection_list", default_closed=True)
        head.label(text=summary(sel), icon="RESTRICT_SELECT_OFF")
        if body is None:
            return
        for cat, objs in grouped(sel).items():
            box = body.box()
            r = box.row(align=True)
            r.label(text=f"{cat} ({len(objs)})", icon=_ICON[cat])
            op = r.operator("og.selection_filter", text="", icon="RESTRICT_SELECT_OFF", emboss=False)
            op.category = cat; op.mode = "ONLY"
            op = r.operator("og.selection_filter", text="", icon="X", emboss=False)
            op.category = cat; op.mode = "REMOVE"
            col = box.column(align=True)
            for o in objs[:_LIST_MAX]:
                r = col.row(align=True)
                r.label(text=o.name)
                op = r.operator("og.selection_filter", text="", icon="RESTRICT_SELECT_OFF", emboss=False)
                op.obj_name = o.name; op.mode = "ONLY"
                op = r.operator("og.selection_filter", text="", icon="X", emboss=False)
                op.obj_name = o.name; op.mode = "REMOVE"
            if len(objs) > _LIST_MAX:
                r = col.row(); r.enabled = False
                r.label(text=f"… +{len(objs) - _LIST_MAX} more")


class OG_PT_SetToFloor(Panel):
    bl_label = "Set to Floor"
    bl_idname = "OG_PT_set_to_floor"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "OpenGOAL"
    bl_parent_id = "OG_PT_object_controls"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        s = ctx.scene.og_floor
        col = self.layout.column(align=True)
        col.prop(s, "offset")
        col.prop(s, "above")
        self.layout.prop(s, "align")
        self.layout.prop(s, "point", text="Meshes")
        n = len([o for o in ctx.selected_objects if not o.get("og_preview_mesh")])
        self.layout.operator("og.set_to_floor", text=f"Set {n} to Floor" if n else "Set to Floor", icon="TRIA_DOWN_BAR")
        r = self.layout.row(); r.enabled = False; r.scale_y = 0.7
        r.label(text="Ignores volumes, nav-meshes, previews and the selection", icon="INFO")


class OG_PT_DistributeAlongCurve(Panel):
    bl_label = "Distribute Along Curve"
    bl_idname = "OG_PT_distribute_along_curve"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "OpenGOAL"
    bl_parent_id = "OG_PT_object_controls"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        from ..object_tools import distribute_targets
        s = ctx.scene.og_distribute
        layout = self.layout
        r = layout.row(align=True)
        r.prop(s, "curve")
        r.operator("og.edit_distribute_curve", text="", icon="EDITMODE_HLT")
        layout.prop(s, "method")
        if s.method == "SPACING":
            layout.prop(s, "spacing")
        layout.prop(s, "align")
        n = len(distribute_targets(ctx, s.curve))
        layout.operator("og.distribute_along_curve", text=f"Distribute {n}" if n else "Distribute", icon="CURVE_PATH")
        r = layout.row(); r.enabled = False; r.scale_y = 0.7
        r.label(text="In name order; selecting a curve picks it", icon="INFO")


class OG_PT_ConvertEntities(Panel):
    bl_label = "Convert Entities"
    bl_idname = "OG_PT_convert_entities"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "OpenGOAL"
    bl_parent_id = "OG_PT_object_controls"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        from ..object_tools import convert_targets, target_label, _MODE_WORD
        s = ctx.scene.og_convert
        layout = self.layout
        layout.prop(s, "mode")
        if s.mode == "ALL":
            box = layout.box(); box.alert = True
            box.label(text="Meshes, curves ... in the selection are", icon="ERROR")
            box.label(text="DELETED and replaced by actors!")
        r = layout.row(align=True)
        r.label(text="Target actor:")
        r.operator("og.pick_convert_target", text=target_label(s.target) or "Pick…", icon="VIEWZOOM")
        n = len(convert_targets(ctx, s.mode))
        r = layout.row()
        r.scale_y = 1.2
        r.alert = s.mode == "ALL"
        tgt = target_label(s.target) or "…"
        r.operator("og.convert_entities", text=f"Convert {n} {_MODE_WORD[s.mode]} to {tgt}", icon="FILE_REFRESH")


class OG_PT_ExportDefinitions(Panel):
    bl_label = "Export Selected Definitions"
    bl_idname = "OG_PT_export_definitions"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "OpenGOAL"
    bl_parent_id = "OG_PT_object_controls"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        layout = self.layout
        layout.prop(ctx.scene.og_export_defs, "path")
        g = grouped(ctx.selected_objects)
        n = sum(len(g.get(k, ())) for k in ("Actors", "Checkpoints", "Cameras", "Load boundaries"))
        layout.operator("og.export_selected_defs", text=f"Export {n} Definition(s)" if n else "Export Definitions",
                        icon="EXPORT")
        for line in ("Actors / cameras: .jsonc entries + art groups / code (.gd)",
                     "Checkpoints: level-info.gc · Load boundaries: load-boundary-data.gc",
                     "Always copied to the clipboard; a file is rewritten, a folder gets a new file"):
            r = layout.row(); r.enabled = False; r.scale_y = 0.7
            r.label(text=line)


CLASSES = (OG_OT_SelectionFilter, OG_OT_DuplicateSelection, OG_OT_DeleteSelection, OG_PT_ObjectControls,
           OG_PT_SetToFloor, OG_PT_DistributeAlongCurve, OG_PT_ConvertEntities, OG_PT_ExportDefinitions)
