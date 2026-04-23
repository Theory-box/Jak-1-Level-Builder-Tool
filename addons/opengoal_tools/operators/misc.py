# ───────────────────────────────────────────────────────────────────────
# operators/misc.py — OpenGOAL Level Tools
#
# Camera setters + nudge operators + selection/deletion helpers + misc utilities.
# ───────────────────────────────────────────────────────────────────────

from __future__ import annotations

import bpy, os, re, json, subprocess, threading, time, math, mathutils
from pathlib import Path
from bpy.props import (StringProperty, BoolProperty, IntProperty,
                       EnumProperty, FloatProperty, CollectionProperty)
from bpy.types import Operator
from ..data import (
    ENTITY_DEFS, ENTITY_ENUM_ITEMS, ENEMY_ENUM_ITEMS, PROP_ENUM_ITEMS,
    NPC_ENUM_ITEMS, PICKUP_ENUM_ITEMS, PLATFORM_ENUM_ITEMS, CRATE_ITEMS, CRATE_PICKUP_ITEMS,
    ALL_SFX_ITEMS, SBK_SOUNDS, LEVEL_BANKS, LUMP_REFERENCE, ACTOR_LINK_DEFS,
    MUSIC_FLAVA_TABLE,
    NAV_UNSAFE_TYPES, NEEDS_PATH_TYPES, NEEDS_PATHB_TYPES, IS_PROP_TYPES,
    ETYPE_AG, ETYPE_CODE,
    needed_tpages, _lump_ref_for_etype, _actor_link_slots, _actor_has_links,
    _actor_links, _actor_get_link, _actor_set_link, _actor_remove_link,
    _build_actor_link_lumps, _parse_lump_row, _LUMP_HARDCODED_KEYS,
    _aggro_event_id, AGGRO_EVENT_ENUM_ITEMS, LUMP_TYPE_ITEMS,
    UNIVERSAL_LUMPS, _is_custom_type,
)
from ..collections import (
    _get_level_prop, _set_level_prop, _level_objects, _active_level_col,
    _all_level_collections, _ensure_sub_collection, _classify_object,
    _col_path_for_entity, _link_object_to_sub_collection,
    _recursive_col_objects, _COL_PATH_WAYPOINTS, _COL_PATH_NAVMESHES,
    _COL_PATH_TRIGGERS, _COL_PATH_CAMERAS, _COL_PATH_SPAWNS,
    _COL_PATH_SOUND_EMITTERS, _COL_PATH_SPAWNABLE_ENEMIES,
    _COL_PATH_SPAWNABLE_PLATFORMS, _COL_PATH_SPAWNABLE_PROPS,
    _COL_PATH_SPAWNABLE_NPCS, _COL_PATH_SPAWNABLE_PICKUPS,
    _COL_PATH_GEO_SOLID, _COL_PATH_WATER,
    _set_blender_active_collection, _LEVEL_COL_DEFAULTS,
)
from ..export import (
    _nick, _iso, _lname, _ldir, _goal_src, _level_info, _game_gp,
    _levels_dir, _entity_gc, _actor_uses_waypoints, _actor_uses_navmesh,
    _actor_is_platform, _actor_is_launcher, _actor_is_spawner,
    _actor_is_enemy, _actor_supports_aggro_trigger,
    _vol_links, _vol_link_targets, _vol_has_link_to, _rename_vol_for_links,
    _vols_linking_to, _vol_get_link_to, _vol_remove_link_to,
    _classify_target, _clean_orphaned_vol_links, log, collect_actors,
    collect_spawns, collect_ambients, needed_ags, needed_code,
    patch_level_info, patch_game_gp, discover_custom_levels, remove_level,
    export_glb,
)
from ..build import (
    _EXE, _BUILD_STATE, _PLAY_STATE, _GEO_REBUILD_STATE, _BUILD_PLAY_STATE, _exe_root, _data_root, _data,
    _gk, _goalc, _user_dir, kill_gk, launch_gk, goalc_send, goalc_ok,
    launch_goalc, _bg_build, _bg_play, _bg_geo_rebuild, _bg_build_and_play,
)
from ..properties import OGLumpRow, OGActorLink, OGVolLink, OGProperties
from ..utils import (
    _is_linkable, _is_aggro_target, _vol_for_target,
    _ENEMY_CATS, _NPC_CATS, _PICKUP_CATS, _PROP_CATS,
    _draw_platform_settings, _header_sep, _draw_entity_sub,
    _draw_wiki_preview,
)
from .. import model_preview as _mp
import re as _re


def _flava_items_for_active(self, context):
    """Dynamic items callback — flavas for whatever bank the selected object has."""
    sel  = context.active_object if context else None
    bank = sel.get("og_music_bank", "village1") if sel else "village1"
    flavas = MUSIC_FLAVA_TABLE.get(bank, ["default"])
    return [(f, f, "", i) for i, f in enumerate(flavas)]

class OG_OT_SelectAndFrame(Operator):
    """Make an object active, select it, and frame it in the viewport."""
    bl_idname = "og.select_and_frame"
    bl_label  = "View"
    bl_description = "Select this object and frame it in the viewport"

    obj_name: bpy.props.StringProperty()

    def execute(self, ctx):
        obj = ctx.scene.objects.get(self.obj_name)
        if not obj:
            self.report({"ERROR"}, f"Object '{self.obj_name}' not found")
            return {"CANCELLED"}
        # Deselect all, select and make active
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        ctx.view_layer.objects.active = obj
        # Frame in viewport
        bpy.ops.view3d.view_selected()
        return {"FINISHED"}

class OG_OT_DeleteObject(Operator):
    """Delete an object by name, also cleaning up any linked volumes."""
    bl_idname = "og.delete_object"
    bl_label  = "Delete"
    bl_description = "Delete this object (volumes linked to it will be unlinked)"

    obj_name: bpy.props.StringProperty()

    def execute(self, ctx):
        obj = ctx.scene.objects.get(self.obj_name)
        if not obj:
            self.report({"ERROR"}, f"Object '{self.obj_name}' not found")
            return {"CANCELLED"}
        # Clean any link entries pointing to this object before deleting it.
        # Volumes themselves stay (orphaned) — user decision per design discussion.
        for o in _level_objects(ctx.scene):
            if o.type == "MESH" and o.name.startswith("VOL_"):
                _vol_remove_link_to(o, self.obj_name)
        # Remove preview mesh children (model previews parented to this actor)
        _mp.remove_preview(obj)
        # Also delete associated _CAM, _ALIGN, _PIVOT, _LOOK_AT empties for cameras
        suffixes = ["_CAM", "_ALIGN", "_PIVOT", "_LOOK_AT"]
        for suf in suffixes:
            associated = ctx.scene.objects.get(self.obj_name + suf)
            if associated:
                bpy.data.objects.remove(associated, do_unlink=True)
        # Delete the object itself
        bpy.data.objects.remove(obj, do_unlink=True)
        self.report({"INFO"}, f"Deleted '{self.obj_name}'")
        return {"FINISHED"}

class OG_OT_SetCamProp(Operator):
    """Set a string custom property on a CAMERA_ object."""
    bl_idname   = "og.set_cam_prop"
    bl_label    = "Set Camera Property"
    bl_options  = {"REGISTER", "UNDO"}
    cam_name:  bpy.props.StringProperty()
    prop_name: bpy.props.StringProperty()
    str_val:   bpy.props.StringProperty()
    def execute(self, ctx):
        o = ctx.scene.objects.get(self.cam_name)
        if o:
            o[self.prop_name] = self.str_val
        return {"FINISHED"}

class OG_OT_NudgeCamFloat(Operator):
    """Nudge a float custom property on a CAMERA_ object."""
    bl_idname   = "og.nudge_cam_float"
    bl_label    = "Nudge Camera Float"
    bl_options  = {"REGISTER", "UNDO"}
    cam_name:  bpy.props.StringProperty()
    prop_name: bpy.props.StringProperty()
    delta:     bpy.props.FloatProperty()
    def execute(self, ctx):
        o = ctx.scene.objects.get(self.cam_name)
        if o:
            current = float(o.get(self.prop_name, 0.0))
            o[self.prop_name] = round(max(0.0, current + self.delta), 2)
        return {"FINISHED"}

class OG_OT_NudgeFloatProp(Operator):
    """Nudge a float custom property on the active object by a fixed delta."""
    bl_idname  = "og.nudge_float_prop"
    bl_label   = "Nudge Float Property"
    bl_options = {"REGISTER", "UNDO"}

    prop_name: bpy.props.StringProperty()
    delta:     bpy.props.FloatProperty()
    val_min:   bpy.props.FloatProperty(default=-1e9)
    val_max:   bpy.props.FloatProperty(default=1e9)

    def execute(self, ctx):
        o = ctx.active_object
        if o:
            current = float(o.get(self.prop_name, 0.0))
            o[self.prop_name] = round(max(self.val_min, min(self.val_max, current + self.delta)), 4)
        return {"FINISHED"}

class OG_OT_NudgeIntProp(Operator):
    """Nudge an integer custom property on the active object by a fixed delta."""
    bl_idname  = "og.nudge_int_prop"
    bl_label   = "Nudge Int Property"
    bl_options = {"REGISTER", "UNDO"}

    prop_name: bpy.props.StringProperty()
    delta:     bpy.props.IntProperty()
    val_min:   bpy.props.IntProperty(default=-999)
    val_max:   bpy.props.IntProperty(default=9999)

    def execute(self, ctx):
        o = ctx.active_object
        if o:
            current = int(o.get(self.prop_name, 0))
            o[self.prop_name] = max(self.val_min, min(self.val_max, current + self.delta))
        return {"FINISHED"}

class OG_OT_SetLauncherDest(Operator):
    """Link a DEST_ empty as the destination for a launcher actor."""
    bl_idname  = "og.set_launcher_dest"
    bl_label   = "Set Launcher Destination"
    bl_options = {"REGISTER", "UNDO"}

    launcher_name: bpy.props.StringProperty()
    dest_name:     bpy.props.StringProperty()

    def execute(self, ctx):
        launcher = bpy.data.objects.get(self.launcher_name)
        if launcher:
            launcher["og_launcher_dest"] = self.dest_name
        return {"FINISHED"}

class OG_OT_ClearLauncherDest(Operator):
    """Clear the destination link from a launcher actor."""
    bl_idname  = "og.clear_launcher_dest"
    bl_label   = "Clear Launcher Destination"
    bl_options = {"REGISTER", "UNDO"}

    launcher_name: bpy.props.StringProperty()

    def execute(self, ctx):
        launcher = bpy.data.objects.get(self.launcher_name)
        if launcher and "og_launcher_dest" in launcher:
            del launcher["og_launcher_dest"]
        return {"FINISHED"}

class OG_OT_SyncWaterFromObject(Operator):
    """Set the water-vol surface height from the object's world Y position."""
    bl_idname  = "og.sync_water_from_object"
    bl_label   = "Sync Water Surface from Object"
    bl_options = {"REGISTER", "UNDO"}

    actor_name: bpy.props.StringProperty()

    def execute(self, ctx):
        o = bpy.data.objects.get(self.actor_name)
        if not o: return {"CANCELLED"}
        # Blender Z = game Y (up). Use location.z for the surface height.
        surface_y = round(o.location.z, 4)
        o["og_water_surface"] = surface_y
        o["og_water_wade"]    = 0.5
        o["og_water_swim"]    = 1.0
        o["og_water_bottom"]  = round(surface_y - 5.0, 4)
        self.report({"INFO"}, f"Water surface={surface_y:.2f}m  wade={surface_y-0.5:.2f}  swim={surface_y-1.0:.2f}  bottom={surface_y-5.0:.2f}")
        return {"FINISHED"}

class OG_OT_SyncWaterFromMesh(Operator):
    """Sync water surface height from the top of the WATER_ mesh bounding box."""
    bl_idname  = "og.sync_water_from_mesh"
    bl_label   = "Sync Surface from Mesh Top"
    bl_options = {"REGISTER", "UNDO"}

    mesh_name: bpy.props.StringProperty()

    def execute(self, ctx):
        import bpy
        o = bpy.data.objects.get(self.mesh_name)
        if not o or o.type != "MESH": return {"CANCELLED"}
        # World-space bounding box corners
        corners = [o.matrix_world @ v.co for v in o.data.vertices]
        ys      = [c.z for c in corners]   # Blender Z = game Y
        top_y   = round(max(ys), 4)
        bot_y   = round(min(ys), 4)
        o["og_water_surface"] = top_y
        o["og_water_wade"]    = 0.5   # depth below surface in meters
        o["og_water_swim"]    = 1.0   # depth below surface in meters
        o["og_water_bottom"]  = bot_y
        self.report({"INFO"}, f"Surface={top_y:.2f}m  wade=0.5m  swim=1.0m  bottom={bot_y:.2f}m")
        return {"FINISHED"}

def _entity_enum_for_cats(cats):
    """Return enum items filtered to the given category set, in display order."""
    return [
        (ek, ei["label"], ei.get("label",""), i)
        for i, (ek, ei) in enumerate(
            (k, v) for k, v in ENTITY_DEFS.items() if v.get("cat") in cats
        )
    ]

def _draw_mat(self, ctx):
    ob = ctx.object
    if not ob or not ob.active_material: return
    mat    = ob.active_material
    layout = self.layout
    layout.prop(mat, "set_invisible")
    layout.prop(mat, "set_collision")
    if mat.set_collision:
        layout.prop(mat, "ignore")
        layout.prop(mat, "collide_mode")
        layout.prop(mat, "collide_material")
        layout.prop(mat, "collide_event")
        layout.prop(mat, "noedge"); layout.prop(mat, "noentity")
        layout.prop(mat, "nolineofsight"); layout.prop(mat, "nocamera")


# ─── Classes to register ───────────────────────────────────────────────────
CLASSES = (
    OG_OT_SelectAndFrame,
    OG_OT_DeleteObject,
    OG_OT_SetCamProp,
    OG_OT_NudgeCamFloat,
    OG_OT_NudgeFloatProp,
    OG_OT_NudgeIntProp,
    OG_OT_SetLauncherDest,
    OG_OT_ClearLauncherDest,
    OG_OT_SyncWaterFromObject,
    OG_OT_SyncWaterFromMesh,
)
