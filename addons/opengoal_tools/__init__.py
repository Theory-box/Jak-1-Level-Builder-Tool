bl_info = {
    "name": "OpenGOAL Level Tools",
    "author": "John Cheathem",
    "version": (2026, 5, 23),
    "blender": (4, 4, 0),
    "location": "View3D > N-Panel > OpenGOAL",
    "description": "Jak 1 level export, actor placement, build and launch tools",
    "category": "Development",
}

import bpy, os, re, json, socket, subprocess, threading, time, math, mathutils
from pathlib import Path
from bpy.props import (StringProperty, BoolProperty, IntProperty,
                       EnumProperty, PointerProperty, FloatProperty,
                       CollectionProperty)
from bpy.types import Panel, Operator, PropertyGroup, AddonPreferences

from .data import (
    AGGRO_EVENT_ENUM_ITEMS,
    ALL_SFX_ITEMS,
    CRATE_ITEMS,
    CRATE_PICKUP_ITEMS,
    ENEMY_ENUM_ITEMS,
    ENTITY_DEFS,
    ENTITY_ENUM_ITEMS,
    ENTITY_WIKI,
    ETYPE_AG,
    ETYPE_CODE,
    ETYPE_EXTRAS_AG,
    IS_PROP_TYPES,
    LEVEL_BANKS,
    LUMP_REFERENCE,
    LUMP_TYPE_ITEMS,
    NAV_UNSAFE_TYPES,
    NEEDS_PATHB_TYPES,
    NEEDS_PATH_TYPES,
    NPC_ENUM_ITEMS,
    PICKUP_ENUM_ITEMS,
    PLATFORM_ENUM_ITEMS,
    PROP_ENUM_ITEMS,
    SBK_SOUNDS,
    _LUMP_HARDCODED_KEYS,
    _actor_get_link,
    _actor_has_links,
    _actor_link_slots,
    _actor_links,
    _actor_remove_link,
    _actor_set_link,
    _aggro_event_id,
    _build_actor_link_lumps,
    _lump_ref_for_etype,
    _parse_lump_row,
    needed_tpages,
    pat_events,
    pat_modes,
    pat_surfaces,
)
from .collections import (
    _COL_PATH_SPAWNABLE_ENEMIES, _COL_PATH_SPAWNABLE_PLATFORMS,
    _COL_PATH_SPAWNABLE_PROPS, _COL_PATH_SPAWNABLE_NPCS,
    _COL_PATH_SPAWNABLE_PICKUPS, _COL_PATH_TRIGGERS, _COL_PATH_CAMERAS,
    _COL_PATH_SPAWNS, _COL_PATH_SOUND_EMITTERS, _COL_PATH_GEO_SOLID,
    _COL_PATH_GEO_COLLISION, _COL_PATH_GEO_VISUAL, _COL_PATH_GEO_REFERENCE,
    _COL_PATH_WAYPOINTS, _COL_PATH_NAVMESHES, _COL_PATH_EXPORT_AS,
    _ENTITY_CAT_TO_COL_PATH, _LEVEL_COL_DEFAULTS,
    _all_level_collections, _active_level_col, _col_is_no_export,
    _recursive_col_objects, _level_objects, _ensure_sub_collection,
    _link_object_to_sub_collection, _col_path_for_entity, _classify_object,
    _get_level_prop, _set_level_prop, _active_level_items,
    _set_blender_active_collection, _get_death_plane, _set_death_plane,
    _on_active_level_changed,
)
from .export import (
    # Navmesh geometry
    _navmesh_compute, _navmesh_to_goal,
    # Core collect / write pipeline
    _canonical_actor_objects, _collect_navmesh_actors,
    _camera_aabb_to_planes, collect_aggro_triggers, collect_cameras,
    collect_spawns, collect_actors, collect_ambients, collect_nav_mesh_geometry,
    needed_ags, needed_code, write_jsonc, write_gd, _make_continues,
    patch_level_info, patch_game_gp, discover_custom_levels,
    remove_level, export_glb,
    # Actor-type predicates
    _actor_uses_waypoints, _actor_uses_navmesh, _actor_is_platform,
    _actor_is_launcher, _actor_is_spawner, _actor_is_enemy,
    _actor_supports_aggro_trigger,
    # Volume link helpers
    _vol_links, _vol_link_targets, _vol_has_link_to, _rename_vol_for_links,
    _vols_linking_to, _vol_get_link_to, _vol_remove_link_to, _classify_target,
    _clean_orphaned_vol_links,
    # Name / path helpers used by operators and panels
    _nick, _iso, _lname, _ldir, _goal_src, _level_info, _game_gp,
    _levels_dir, _entity_gc,
)
from .build import (
    _EXE, GOALC_PORT, GOALC_TIMEOUT,
    _BUILD_STATE, _PLAY_STATE,
    _exe_root, _data_root, _data, _gk, _goalc,
    _user_dir, kill_gk, launch_gk,
    goalc_send, goalc_ok, launch_goalc,
    _bg_build, _bg_play, _bg_geo_rebuild, _bg_build_and_play,
)
from .properties import (
    OGPreferences, OGProperties,
    OGLumpRow, OG_OT_AddLumpRow, OG_OT_RemoveLumpRow,
    OG_UL_LumpRows, OGActorLink, OGVolLink, OGAuditResult, OGGoalCodeRef,
    OGSpawnListRow, OGSpawnFavorite,
    OGWaypointSource,
)
from .spawn_items import (
    populate_spawn_list, register_handlers as _spawn_register_handlers,
    unregister_handlers as _spawn_unregister_handlers,
)
from .operators import ALL_CLASSES as _OPS_CLASSES
from .operators.misc import _draw_mat
from .panels import ALL_CLASSES as _PANELS_CLASSES

from .utils import _preview_collections, _load_previews, _unload_previews
from . import model_preview as _mp
from .textures import (
    TEXTURING_CLASSES,
    register_texturing, unregister_texturing,
)

# bpy.utils.previews is the correct Blender API for custom images in panels.
# icon_id is just an integer texture lookup — zero overhead in draw().


# ---------------------------------------------------------------------------
# REGISTER / UNREGISTER
# ---------------------------------------------------------------------------

classes = (
    *_OPS_CLASSES,
    OGLumpRow,
    OG_OT_AddLumpRow,
    OG_OT_RemoveLumpRow,
    OGActorLink,
    OGVolLink,
    OGGoalCodeRef,
    OGAuditResult,
    OGSpawnListRow,
    OGSpawnFavorite,
    OGWaypointSource,
    OGPreferences, OGProperties,
    OG_UL_LumpRows,
    *TEXTURING_CLASSES,
    *_PANELS_CLASSES,
)

def register():
    _load_previews()
    _mp.register_handler()
    register_texturing()
    for cls in classes:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
        bpy.utils.register_class(cls)
    bpy.types.Scene.og_props = PointerProperty(type=OGProperties)

    # Audit results — registered after OGAuditResult is in classes tuple.
    bpy.types.Scene.og_audit_results       = bpy.props.CollectionProperty(type=OGAuditResult)
    bpy.types.Scene.og_audit_results_index = bpy.props.IntProperty(name="Active Audit Result", default=0)

    bpy.types.Material.set_invisible    = bpy.props.BoolProperty(name="Invisible")
    bpy.types.Material.set_collision    = bpy.props.BoolProperty(name="Apply Collision Properties")
    bpy.types.Material.ignore           = bpy.props.BoolProperty(name="ignore")
    bpy.types.Material.noedge           = bpy.props.BoolProperty(name="No-Edge")
    bpy.types.Material.noentity         = bpy.props.BoolProperty(name="No-Entity")
    bpy.types.Material.nolineofsight    = bpy.props.BoolProperty(name="No-LOS")
    bpy.types.Material.nocamera         = bpy.props.BoolProperty(name="No-Camera")
    bpy.types.Material.collide_material = bpy.props.EnumProperty(items=pat_surfaces, name="Material")
    bpy.types.Material.collide_event    = bpy.props.EnumProperty(items=pat_events,   name="Event")
    bpy.types.Material.collide_mode     = bpy.props.EnumProperty(items=pat_modes,    name="Mode")
    bpy.types.MATERIAL_PT_custom_props.prepend(_draw_mat)

    bpy.types.Object.set_invisible         = bpy.props.BoolProperty(name="Invisible")
    bpy.types.Object.set_collision         = bpy.props.BoolProperty(name="Apply Collision Properties")
    bpy.types.Object.enable_custom_weights = bpy.props.BoolProperty(name="Use Custom Bone Weights")
    bpy.types.Object.copy_eye_draws        = bpy.props.BoolProperty(name="Copy Eye Draws")
    bpy.types.Object.copy_mod_draws        = bpy.props.BoolProperty(name="Copy Mod Draws")
    bpy.types.Object.ignore                = bpy.props.BoolProperty(name="ignore")
    bpy.types.Object.noedge                = bpy.props.BoolProperty(name="No-Edge")
    bpy.types.Object.noentity              = bpy.props.BoolProperty(name="No-Entity")
    bpy.types.Object.nolineofsight         = bpy.props.BoolProperty(name="No-LOS")
    bpy.types.Object.nocamera              = bpy.props.BoolProperty(name="No-Camera")
    bpy.types.Object.collide_material      = bpy.props.EnumProperty(items=pat_surfaces, name="Material")
    bpy.types.Object.collide_event         = bpy.props.EnumProperty(items=pat_events,   name="Event")
    bpy.types.Object.collide_mode          = bpy.props.EnumProperty(items=pat_modes,    name="Mode")

    # Trigger volume link collection — registered after OGVolLink is in classes tuple.
    # Each VOL_ mesh holds a list of (target_name, behaviour) entries.
    bpy.types.Object.og_vol_links          = bpy.props.CollectionProperty(type=OGVolLink)

    # Actor entity links — registered after OGActorLink is in classes tuple.
    # Each ACTOR_ empty holds a list of (lump_key, slot_index, target_name) entries.
    bpy.types.Object.og_actor_links        = bpy.props.CollectionProperty(type=OGActorLink)

    # Custom lump rows — registered after OGLumpRow is in classes tuple.
    # Each ACTOR_ empty holds a list of (key, ltype, value) assisted lump entries.
    bpy.types.Object.og_lump_rows          = bpy.props.CollectionProperty(type=OGLumpRow)
    bpy.types.Object.og_lump_rows_index    = bpy.props.IntProperty(name="Active Lump Row", default=0)

    # Reorderable waypoint sources — registered after OGWaypointSource is in
    # the classes tuple. Each ACTOR_ empty holds an ordered list of links to
    # empties (single waypoint) or curves (each control point is a waypoint).
    # When the collection is empty, export falls back to the legacy
    # `<actor>_wp_NN` name-grep so existing levels keep working unchanged.
    bpy.types.Object.og_waypoint_sources       = bpy.props.CollectionProperty(type=OGWaypointSource)
    bpy.types.Object.og_waypoint_sources_index = bpy.props.IntProperty(
        name="Active Waypoint Source", default=0)
    bpy.types.Object.og_waypoint_pingpong      = bpy.props.BoolProperty(
        name="Ping-pong",
        description="Walk the path forward, then backward — A→B→C→B→A→B→... "
                    "Implemented by emitting the reversed points after the "
                    "forward path; the engine's modulo walk handles the rest.",
        default=False,
    )

    # GOAL code injection — registered after OGGoalCodeRef is in classes tuple.
    # Each ACTOR_ empty can reference a Blender text block to inject into obs.gc.
    bpy.types.Object.og_goal_code_ref      = bpy.props.PointerProperty(type=OGGoalCodeRef)

    # Vertex-export: mesh objects tagged with an entity type export each vertex as an actor.
    bpy.types.Object.og_vertex_export_etype  = bpy.props.StringProperty(name="Export As Entity", default="")
    bpy.types.Object.og_vertex_export_search = bpy.props.StringProperty(name="", default="")

    bpy.types.Collection.og_no_export      = bpy.props.BoolProperty(
        name="Exclude from Export",
        description="When enabled, this collection and its contents are excluded from level export",
        default=False)

    # Unified spawn picker — register the load_post handler so freshly-loaded
    # blend files get their spawn list populated. The initial population for
    # any already-open scenes has to be deferred because bpy.data is wrapped
    # in _RestrictData during register() and bpy.data.scenes is inaccessible.
    # A zero-delay timer fires on the next tick when restrictions are lifted.
    _spawn_register_handlers()

    def _deferred_populate_spawn_lists():
        try:
            for _scene in bpy.data.scenes:
                populate_spawn_list(_scene)
        except Exception:
            # If the addon was already unregistered before this fired, or any
            # other unexpected state — fail silently. load_post will catch
            # the next scene load anyway.
            pass
        return None  # one-shot; don't re-schedule

    bpy.app.timers.register(_deferred_populate_spawn_lists, first_interval=0.0)

def unregister():
    _spawn_unregister_handlers()
    _unload_previews()
    _mp.unregister_handler()
    unregister_texturing()
    bpy.types.MATERIAL_PT_custom_props.remove(_draw_mat)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    if hasattr(bpy.types.Scene, "og_props"):
        del bpy.types.Scene.og_props
    if hasattr(bpy.types.Scene, "og_audit_results"):
        del bpy.types.Scene.og_audit_results
    if hasattr(bpy.types.Scene, "og_audit_results_index"):
        del bpy.types.Scene.og_audit_results_index
    for a in ("set_invisible","set_collision","ignore","noedge","noentity",
              "nolineofsight","nocamera","collide_material","collide_event","collide_mode"):
        try: delattr(bpy.types.Material, a)
        except Exception: pass
    for a in ("set_invisible","set_collision","ignore","noedge","noentity",
              "nolineofsight","nocamera","collide_material","collide_event","collide_mode",
              "enable_custom_weights","copy_eye_draws","copy_mod_draws","og_vol_links",
              "og_actor_links","og_lump_rows","og_lump_rows_index","og_goal_code_ref",
              "og_vertex_export_etype","og_vertex_export_search",
              "og_waypoint_sources","og_waypoint_sources_index","og_waypoint_pingpong"):
        try: delattr(bpy.types.Object, a)
        except Exception: pass
    try: delattr(bpy.types.Collection, "og_no_export")
    except Exception: pass

if __name__ == "__main__":
    register()
