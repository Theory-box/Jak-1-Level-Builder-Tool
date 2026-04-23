# ───────────────────────────────────────────────────────────────────────
# export/predicates.py — OpenGOAL Level Tools
#
# Actor-type predicates: small checks on an actor's etype and metadata.
# Used by scene.py and actors.py to branch by category without hardcoding etype lists.
# ───────────────────────────────────────────────────────────────────────

from __future__ import annotations

import bpy, os, re, json, math, mathutils
from pathlib import Path
from ..data import (
    ENTITY_DEFS, ETYPE_CODE, ETYPE_TPAGES, ETYPE_AG, VERTEX_EXPORT_TYPES,
    NAV_UNSAFE_TYPES, NEEDS_PATH_TYPES, NEEDS_PATHB_TYPES, IS_PROP_TYPES,
    needed_tpages, LUMP_REFERENCE, ACTOR_LINK_DEFS,
    _lump_ref_for_etype, _actor_link_slots, _actor_has_links,
    _actor_links, _actor_get_link, _actor_set_link,
    _actor_remove_link, _build_actor_link_lumps,
    _parse_lump_row, _aggro_event_id, AGGRO_TRIGGER_EVENTS,
    _LUMP_HARDCODED_KEYS, _is_custom_type,
)
from ..collections import (
    _get_level_prop, _level_objects,
    _active_level_col, _classify_object, _col_path_for_entity,
    _ensure_sub_collection, _recursive_col_objects,
    _COL_PATH_WAYPOINTS, _COL_PATH_NAVMESHES,
)
from ..collections import (
    _COL_PATH_SPAWNABLE_ENEMIES, _COL_PATH_SPAWNABLE_PLATFORMS,
    _COL_PATH_SPAWNABLE_PROPS, _COL_PATH_SPAWNABLE_NPCS,
    _COL_PATH_SPAWNABLE_PICKUPS, _COL_PATH_TRIGGERS, _COL_PATH_CAMERAS,
    _COL_PATH_SPAWNS, _COL_PATH_SOUND_EMITTERS, _COL_PATH_GEO_SOLID,
    _COL_PATH_GEO_COLLISION, _COL_PATH_GEO_VISUAL, _COL_PATH_GEO_REFERENCE,
    _COL_PATH_WAYPOINTS, _COL_PATH_NAVMESHES,
    _ENTITY_CAT_TO_COL_PATH, _LEVEL_COL_DEFAULTS,
    _all_level_collections, _active_level_col, _col_is_no_export,
    _recursive_col_objects, _level_objects, _ensure_sub_collection,
    _link_object_to_sub_collection, _col_path_for_entity, _classify_object,
    _get_level_prop, _set_level_prop, _active_level_items,
    _set_blender_active_collection, _get_death_plane, _set_death_plane,
    _on_active_level_changed,
)


# Cross-module imports (siblings in the export package)


def _canonical_actor_objects(scene, objects=None):
    """
    Single source of truth for actor ordering and AID assignment.
    Both collect_actors and _collect_navmesh_actors must use this so
    idx values — and therefore AIDs — are guaranteed to match.
    Sorted by name for full determinism regardless of Blender object order.
    Excludes waypoints (_wp_, _wpb_) and non-EMPTY objects.

    If objects is provided, scans that list instead of scene.objects.
    """
    source = objects if objects is not None else scene.objects
    actors = []
    for o in source:
        if not (o.name.startswith("ACTOR_") and o.type == "EMPTY"):
            continue
        if "_wp_" in o.name or "_wpb_" in o.name:
            continue
        if len(o.name.split("_", 2)) < 3:
            continue
        actors.append(o)
    actors.sort(key=lambda o: o.name)
    return actors

def _actor_uses_waypoints(etype):
    """True if this entity type can use waypoints (path lump or nav patrol)."""
    info = ENTITY_DEFS.get(etype, {})
    return (not info.get("nav_safe", True)    # nav-enemy — optional patrol path
            or info.get("needs_path", False)  # process-drawable that requires path
            or info.get("needs_pathb", False)
            or info.get("needs_sync", False)) # sync platform — path drives movement

def _actor_uses_navmesh(etype):
    """True if this entity type needs a nav-mesh link in entity.gc.
    Covers two cases:
    - nav-enemy subclasses (lookup via ai_type)
    - platforms/actors that call nav-control-method-16 at runtime
      (orbit-plat, square-platform, sharkey, sunkenfisha — flagged
      requires_navmesh in the DB)"""
    info = ENTITY_DEFS.get(etype, {})
    return info.get("ai_type") == "nav-enemy" or bool(info.get("requires_navmesh"))

def _actor_is_platform(etype):
    """True if this entity is in the Platforms category."""
    return ENTITY_DEFS.get(etype, {}).get("cat") == "Platforms"

_LAUNCHER_TYPES = {"launcher", "springbox"}

def _actor_is_launcher(etype):
    """True if this entity is a launcher or springbox (spring-height lump)."""
    return etype in _LAUNCHER_TYPES

_SPAWNER_TYPES = {"swamp-bat", "yeti", "villa-starfish", "swamp-rat-nest"}

def _actor_is_spawner(etype):
    """True if this entity spawns child enemies (num-lurkers lump)."""
    return etype in _SPAWNER_TYPES

def _actor_is_enemy(etype):
    """True if this entity is in the Enemies or Bosses category.
    Enemies/bosses inherit fact-info-enemy, which reads idle-distance from
    the entity's res-lump on construction (engine: fact-h.gc line 191).
    Engine default is 80 meters.
    """
    return ENTITY_DEFS.get(etype, {}).get("cat") in ("Enemies", "Bosses")

def _actor_supports_aggro_trigger(etype):
    """True if this enemy responds to 'cue-chase / 'cue-patrol / 'go-wait-for-cue.
    Only nav-enemies have these handlers (engine: nav-enemy.gc line 142).
    Process-drawable enemies (junglesnake, bully, yeti, mother-spider, etc.)
    do NOT respond to these events — silently doing nothing if sent.
    """
    return _actor_uses_navmesh(etype)

def _classify_target(target_name):
    """Return one of 'camera', 'checkpoint', 'enemy', 'custom', or '' for an unknown target."""
    if target_name.startswith("CAMERA_"):
        return "camera"
    if target_name.startswith("CHECKPOINT_") and not target_name.endswith("_CAM"):
        return "checkpoint"
    if target_name.startswith("ACTOR_") and "_wp_" not in target_name and "_wpb_" not in target_name:
        parts = target_name.split("_", 2)
        if len(parts) >= 3:
            if _actor_supports_aggro_trigger(parts[1]):
                return "enemy"
            if _is_custom_type(parts[1]):
                return "custom"
    return ""
