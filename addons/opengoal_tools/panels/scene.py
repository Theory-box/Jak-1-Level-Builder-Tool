# ───────────────────────────────────────────────────────────────────────
# panels/scene.py — OpenGOAL Level Tools
#
# Panels for non-actor scene objects: cameras, triggers, music zones, checkpoints, cam anchors, nav-mesh info, volume links, water meshes, ambient emitters.
#
# Auto-generated from the original panels.py by the refactor split.
# Edit freely — this is no longer a generated file.
# ───────────────────────────────────────────────────────────────────────

from __future__ import annotations

import bpy
from bpy.types import Panel, Operator
from pathlib import Path
from ..data import (
    ENTITY_DEFS, ENTITY_WIKI, ENTITY_ENUM_ITEMS, ENEMY_ENUM_ITEMS, VERTEX_EXPORT_TYPES,
    PROP_ENUM_ITEMS, NPC_ENUM_ITEMS, PICKUP_ENUM_ITEMS, PLATFORM_ENUM_ITEMS,
    CRATE_ITEMS, CRATE_PICKUP_ITEMS, ALL_SFX_ITEMS, SBK_SOUNDS, LEVEL_BANKS,
    LUMP_REFERENCE, ACTOR_LINK_DEFS, LUMP_TYPE_ITEMS,
    ETYPE_AG,
    _lump_ref_for_etype, _actor_link_slots, _actor_has_links,
    _actor_links, _actor_get_link, AGGRO_TRIGGER_EVENTS,
    _parse_lump_row, _LUMP_HARDCODED_KEYS,
    GLOBAL_TPAGE_GROUPS, _is_custom_type,
)
from ..collections import (
    _get_level_prop, _set_level_prop, _level_objects, _active_level_col,
    _all_level_collections, _classify_object, _col_path_for_entity,
    _recursive_col_objects, _ensure_sub_collection, _link_object_to_sub_collection,
    _COL_PATH_NAVMESHES, _COL_PATH_WAYPOINTS, _COL_PATH_EXPORT_AS,
    _COL_PATH_TRIGGERS, _COL_PATH_CAMERAS, _COL_PATH_SOUND_EMITTERS,
    _COL_PATH_SPAWNABLE_ENEMIES, _COL_PATH_GEO_SOLID,
)
from ..export import (
    _nick, _iso, _lname, _ldir, _goal_src, _level_info, _game_gp,
    _levels_dir, _entity_gc,
    _actor_uses_waypoints, _actor_uses_navmesh,
    _actor_is_platform, _actor_is_launcher, _actor_is_spawner,
    _actor_is_enemy, _actor_supports_aggro_trigger,
    _vol_links, _vols_linking_to, _classify_target,
    _vol_get_link_to, _vol_has_link_to,
    collect_cameras, collect_aggro_triggers, log,
)
from ..build import (
    _EXE, _BUILD_STATE, _PLAY_STATE, goalc_ok, kill_gk,
    _exe_root, _data_root, _data, _goalc, _gk, _user_dir,
)
from ..properties import OGLumpRow, OG_UL_LumpRows
from ..utils import (
    _is_linkable, _is_aggro_target, _vol_for_target,
    _ENEMY_CATS, _NPC_CATS, _PICKUP_CATS, _PROP_CATS,
    _draw_platform_settings, _header_sep, _draw_entity_sub,
    _draw_wiki_preview, _prop_row,
    _preview_collections, _load_previews, _unload_previews,
)
from .. import model_preview as _mp
from ..audit import run_audit


from .selected import (
    _draw_selected_checkpoint,
    _draw_selected_emitter,
    _draw_selected_music_zone,
    _draw_selected_camera,
    _draw_selected_cam_anchor,
    _draw_selected_volume,
    _draw_selected_navmesh,
)

class OG_PT_WaterMesh(Panel):
    bl_label       = "💧  Water Volume Settings"
    bl_idname      = "OG_PT_water_mesh"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        return sel and sel.type == "MESH" and sel.name.startswith("WATER_")

    def draw(self, ctx):
        layout = self.layout
        sel    = ctx.active_object

        # Sync button first — most common first action
        layout.operator("og.sync_water_from_mesh", text="Sync Heights from Mesh Top/Bottom",
                        icon="OBJECT_ORIGIN").mesh_name = sel.name

        box = layout.box()
        box.label(text="Water Heights (world Y)", icon="MOD_OCEAN")

        # surface and bottom are absolute world Y
        # wade and swim are DEPTHS below surface (small positive values like 0.5, 1.0)
        surface = float(sel.get("og_water_surface", sel.location.z))
        wade    = float(sel.get("og_water_wade",    0.5))
        swim    = float(sel.get("og_water_swim",    1.0))
        bottom  = float(sel.get("og_water_bottom",  surface - 5.0))

        col = box.column(align=True)
        _prop_row(col, sel, "og_water_surface", "Surface Y:",          surface)
        _prop_row(col, sel, "og_water_wade",    "Wade depth (m below):", wade)
        _prop_row(col, sel, "og_water_swim",    "Swim depth (m below):", swim)
        _prop_row(col, sel, "og_water_bottom",  "Bottom Y:",             bottom)

        # Sanity readout
        sub = box.column(align=True)
        sub.enabled = False
        sub.label(text=f"  Wades at {wade:.2f}m below surface  (Y={surface-wade:.2f})", icon="INFO")
        sub.label(text=f"  Swims at {swim:.2f}m below surface  (Y={surface-swim:.2f})")
        sub.label(text=f"  Kill floor: Y={bottom:.2f}m")

        # Damage type
        box2 = layout.box()
        box2.label(text="Damage Type", icon="GHOST_ENABLED")
        attack = str(sel.get("og_water_attack", "drown"))
        row = box2.row(align=True)
        for opt in ["drown", "lava", "dark-eco-pool", "heat", "drown-death"]:
            r = row.row()
            r.enabled = (attack != opt)
            op = r.operator("og.set_water_attack", text=opt)
            op.mesh_name  = sel.name
            op.attack_val = opt



class OG_PT_CheckpointSettings(Panel):
    bl_label       = "Checkpoint Settings"
    bl_idname      = "OG_PT_checkpoint_settings"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        return (sel is not None
                and sel.name.startswith("CHECKPOINT_")
                and not sel.name.endswith("_CAM"))

    def draw(self, ctx):
        _draw_selected_checkpoint(self.layout, ctx.active_object, ctx.scene)



class OG_PT_AmbientEmitter(Panel):
    bl_label       = "Sound Emitter"
    bl_idname      = "OG_PT_ambient_emitter"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        # Only sound emitters (AMBIENT_snd*), not music zones (AMBIENT_mus*)
        return (sel is not None
                and sel.name.startswith("AMBIENT_")
                and not sel.name.startswith("AMBIENT_mus"))

    def draw(self, ctx):
        _draw_selected_emitter(self.layout, ctx.active_object)



class OG_PT_MusicZone(Panel):
    bl_label       = "Music Zone"
    bl_idname      = "OG_PT_music_zone"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        return sel is not None and sel.name.startswith("AMBIENT_mus")

    def draw(self, ctx):
        _draw_selected_music_zone(self.layout, ctx.active_object)



class OG_PT_CameraSettings(Panel):
    bl_label       = "Camera Settings"
    bl_idname      = "OG_PT_camera_settings"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        return (sel is not None
                and sel.name.startswith("CAMERA_")
                and sel.type == "CAMERA")

    def draw(self, ctx):
        _draw_selected_camera(self.layout, ctx.active_object, ctx.scene)



class OG_PT_CamAnchorInfo(Panel):
    bl_label       = "Anchor Info"
    bl_idname      = "OG_PT_cam_anchor_info"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        return sel is not None and sel.name.endswith("_CAM")

    def draw(self, ctx):
        _draw_selected_cam_anchor(self.layout, ctx.active_object, ctx.scene)



class OG_PT_VolumeLinks(Panel):
    bl_label       = "Volume Links"
    bl_idname      = "OG_PT_volume_links"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        return sel is not None and sel.name.startswith("VOL_")

    def draw(self, ctx):
        _draw_selected_volume(self.layout, ctx.active_object, ctx.scene)



class OG_PT_NavmeshInfo(Panel):
    bl_label       = "Navmesh Info"
    bl_idname      = "OG_PT_navmesh_info"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        return (sel is not None
                and sel.type == "MESH"
                and (sel.get("og_navmesh") or sel.name.startswith("NAVMESH_")))

    def draw(self, ctx):
        _draw_selected_navmesh(self.layout, ctx.active_object)



CLASSES = (
    OG_PT_WaterMesh,
    OG_PT_CheckpointSettings,
    OG_PT_AmbientEmitter,
    OG_PT_MusicZone,
    OG_PT_CameraSettings,
    OG_PT_CamAnchorInfo,
    OG_PT_VolumeLinks,
    OG_PT_NavmeshInfo,
)
