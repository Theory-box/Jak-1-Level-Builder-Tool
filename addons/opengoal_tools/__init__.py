bl_info = {
    "name": "OpenGOAL Level Tools",
    "author": "John Cheathem",
    "version": (2026, 5, 30),
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
    _cp_lev0_items, _cp_lev1_items, CP_DISP_ITEMS,
    _lb_level_items, LB_CMD_ITEMS, LB_DISP_ITEMS,
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
from . import boundary_viz as _bviz
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
    _bviz.register_handler()
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
    # Path interpolation mode. LINEAR (default) emits only the `path` lump, so
    # the engine walks the control points in straight segments — current/legacy
    # behavior, hits every waypoint exactly. SMOOTH additionally emits a
    # `path-k` knot lump, which makes curve-control actors (plat, plat-eco,
    # plat-button) load as a true cubic B-spline curve for gliding motion.
    # Note: a B-spline does NOT pass through interior waypoints — it cuts the
    # corners, touching only the first and last point. Needs >= 4 waypoints;
    # with fewer it falls back to linear at export.
    bpy.types.Object.og_path_mode = bpy.props.EnumProperty(
        name="Path Mode",
        description="How the actor moves along its waypoints. Linear hits every "
                    "waypoint with straight segments. Smooth emits a path-k knot "
                    "vector so curve-control platforms glide as a cubic B-spline "
                    "(cuts corners; needs at least 4 waypoints)",
        items=[
            ("LINEAR", "Linear", "Straight segments through every waypoint "
                                 "(only the 'path' lump is exported)"),
            ("SMOOTH", "Smooth", "Cubic B-spline gliding motion via a 'path-k' "
                                 "knot lump. Cuts corners and skips interior "
                                 "waypoints. Requires >= 4 waypoints"),
        ],
        default="LINEAR",
    )

    # GOAL code injection — registered after OGGoalCodeRef is in classes tuple.
    # Each ACTOR_ empty can reference a Blender text block to inject into obs.gc.
    bpy.types.Object.og_goal_code_ref      = bpy.props.PointerProperty(type=OGGoalCodeRef)

    # Vertex-export: mesh objects tagged with an entity type export each vertex as an actor.
    bpy.types.Object.og_vertex_export_etype  = bpy.props.StringProperty(name="Export As Entity", default="")
    bpy.types.Object.og_vertex_export_search = bpy.props.StringProperty(name="", default="")

    # Checkpoint (continue-point) level/display settings.
    # SPAWN_/CHECKPOINT_ empties export as continue-points; these drive which
    # levels are resident (and displayed) when respawning at this point.
    # Note: EnumProperty with a dynamic items callback can't take default= —
    # the first item ("self" / "none") is the effective default.
    bpy.types.Object.og_cp_lev0  = bpy.props.EnumProperty(
        name="Load Level 0", items=_cp_lev0_items,
        description="Primary level kept resident when respawning here")
    bpy.types.Object.og_cp_disp0 = bpy.props.EnumProperty(
        name="Display 0", items=CP_DISP_ITEMS, default="display",
        description="Display mode for slot 0")
    bpy.types.Object.og_cp_lev1  = bpy.props.EnumProperty(
        name="Load Level 1", items=_cp_lev1_items,
        description="Optional second resident level (e.g. an adjacent level)")
    bpy.types.Object.og_cp_lev0_custom = bpy.props.StringProperty(
        name="Level 0 Name", default="",
        description="Custom level symbol for slot 0 (used when Load Level 0 = Custom)")
    bpy.types.Object.og_cp_lev1_custom = bpy.props.StringProperty(
        name="Level 1 Name", default="",
        description="Custom level symbol for slot 1 (used when Load Level 1 = Custom)")
    bpy.types.Object.og_cp_disp1 = bpy.props.EnumProperty(
        name="Display 1", items=CP_DISP_ITEMS, default="off",
        description="Display mode for slot 1")
    bpy.types.Object.og_cp_vis_nick = bpy.props.StringProperty(
        name="Vis Nickname", default="",
        description="Vis nick set on respawn (blank = this level's nickname). "
                    "Used for music/menu context, not only visibility data")
    bpy.types.Object.og_cp_flags = bpy.props.StringProperty(
        name="Continue Flags", default="",
        description="Advanced: space-separated continue-flags symbols "
                    "(e.g. 'warp game-start'). Must exist in the build's enum")
    bpy.types.Object.og_cp_load_commands = bpy.props.StringProperty(
        name="Load Commands", default="",
        description="Advanced: raw GOAL load-commands list, e.g. "
                    "'((display foo display)). Blank = '()")

    # Load boundary (LOADBND_ mesh) settings → static-load-boundary entries.
    bpy.types.Object.og_lb_closed = bpy.props.BoolProperty(
        name="Closed Area", default=False,
        description="Closed: points are a flat horizontal polygon (area test). "
                    "Open (default): points are a polyline extruded into a wall",
        update=_bviz.lb_setting_update)
    # Wall extents (Blender metres) — exported to :top/:bot (metres * 4096) and
    # read by the OG Boundary Viz modifier. top above the floor, bot below.
    bpy.types.Object.og_lb_top = bpy.props.FloatProperty(
        name="Top", default=_bviz.DEFAULT_TOP,
        description="Top of the boundary wall, in metres (exported to :top)",
        update=_bviz.lb_setting_update)
    bpy.types.Object.og_lb_bot = bpy.props.FloatProperty(
        name="Bottom", default=_bviz.DEFAULT_BOT,
        description="Bottom of the boundary wall, in metres (exported to :bot). "
                    "Usually negative (below the floor)",
        update=_bviz.lb_setting_update)
    # Cosmetic, viewport only — never exported.
    bpy.types.Object.og_lb_flip = bpy.props.BoolProperty(
        name="Flip", default=False,
        description="Viewport only: flip the visualized wall's facing / arrows",
        update=_bviz.lb_setting_update)
    bpy.types.Object.og_lb_wireframe = bpy.props.BoolProperty(
        name="Wireframe", default=False,
        description="Viewport only: show the boundary as a wireframe (no faces)",
        update=_bviz.lb_setting_update)
    bpy.types.Object.og_lb_player = bpy.props.BoolProperty(
        name="Player Cross", default=True,
        description="Activate when the player crosses (off = camera crosses)")
    bpy.types.Object.og_lb_custom_flags = bpy.props.StringProperty(
        name="Custom Flags", default="",
        description="Advanced: extra space-separated load-boundary-flags symbols. "
                    "Must exist in the build's enum (e.g. TFL custom flags)")
    # Forward command (crossing along the plane normal).
    bpy.types.Object.og_lb_fwd_cmd  = bpy.props.EnumProperty(
        name="Forward", items=LB_CMD_ITEMS, default="none")
    bpy.types.Object.og_lb_fwd_lev0 = bpy.props.EnumProperty(
        name="Fwd Level 0", items=_lb_level_items)
    bpy.types.Object.og_lb_fwd_lev1 = bpy.props.EnumProperty(
        name="Fwd Level 1", items=_lb_level_items)
    bpy.types.Object.og_lb_fwd_disp = bpy.props.EnumProperty(
        name="Fwd Display", items=LB_DISP_ITEMS, default="display")
    bpy.types.Object.og_lb_fwd_name = bpy.props.StringProperty(
        name="Fwd Name", default="",
        description="continue-name (checkpt) or vis nick (vis)")
    # Backward command (crossing against the plane normal).
    bpy.types.Object.og_lb_bwd_cmd  = bpy.props.EnumProperty(
        name="Backward", items=LB_CMD_ITEMS, default="none")
    bpy.types.Object.og_lb_bwd_lev0 = bpy.props.EnumProperty(
        name="Bwd Level 0", items=_lb_level_items)
    bpy.types.Object.og_lb_bwd_lev1 = bpy.props.EnumProperty(
        name="Bwd Level 1", items=_lb_level_items)
    bpy.types.Object.og_lb_bwd_disp = bpy.props.EnumProperty(
        name="Bwd Display", items=LB_DISP_ITEMS, default="display")
    bpy.types.Object.og_lb_bwd_name = bpy.props.StringProperty(
        name="Bwd Name", default="",
        description="continue-name (checkpt) or vis nick (vis)")

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
    _bviz.unregister_handler()
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
              "og_cp_lev0","og_cp_disp0","og_cp_lev1","og_cp_disp1",
              "og_cp_vis_nick","og_cp_flags","og_cp_load_commands",
              "og_cp_lev0_custom","og_cp_lev1_custom",
              "og_lb_closed","og_lb_player","og_lb_custom_flags",
              "og_lb_top","og_lb_bot","og_lb_flip","og_lb_wireframe",
              "og_lb_fwd_cmd","og_lb_fwd_lev0","og_lb_fwd_lev1","og_lb_fwd_disp","og_lb_fwd_name",
              "og_lb_bwd_cmd","og_lb_bwd_lev0","og_lb_bwd_lev1","og_lb_bwd_disp","og_lb_bwd_name",
              "og_waypoint_sources","og_waypoint_sources_index","og_waypoint_pingpong",
              "og_path_mode"):
        try: delattr(bpy.types.Object, a)
        except Exception: pass
    try: delattr(bpy.types.Collection, "og_no_export")
    except Exception: pass

if __name__ == "__main__":
    register()
