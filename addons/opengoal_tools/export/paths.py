# ───────────────────────────────────────────────────────────────────────
# export/paths.py — OpenGOAL Level Tools
#
# File-path helpers + log wrapper.
# Everything here reads the addon's preferences to resolve where the target jak-project tree lives.
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


def _data_root():
    import bpy as _bpy
    from pathlib import Path as _Path
    def _s(p): return p.strip().rstrip("\\").rstrip("/")
    prefs = _bpy.context.preferences.addons.get("opengoal_tools")
    if prefs:
        manual = _s(prefs.preferences.data_path)
        if manual:
            return _Path(manual)
        root = _s(getattr(prefs.preferences, "og_root_path", ""))
        # Prefer og_active_data (separate data folder), fall back to og_active_version
        dat = _s(getattr(prefs.preferences, "og_active_data", ""))
        if not dat:
            dat = _s(getattr(prefs.preferences, "og_active_version", ""))
        if root and dat:
            return _Path(root) / dat
    return _Path(".")

def _data():
    root = _data_root()
    if (root / "goal_src" / "jak1").exists():
        return root      # dev build — no data/ layer
    return root / "data" # release build

def _levels_dir(): return _data() / "custom_assets" / "jak1" / "levels"

def _goal_src():   return _data() / "goal_src" / "jak1"

def _level_info(): return _goal_src() / "engine" / "level" / "level-info.gc"

def _game_gp():    return _goal_src() / "game.gp"

def _ldir(name):   return _levels_dir() / name

def _entity_gc():  return _goal_src() / "engine" / "entity" / "entity.gc"

def _lname(ctx):
    col = _active_level_col(ctx.scene)
    if col is not None:
        return str(col.get("og_level_name", "")).strip().lower().replace(" ", "-")
    return ctx.scene.og_props.level_name.strip().lower().replace(" ","-")

def _nick(n):      return n.replace("-","")[:3].lower()

def _iso(n):       return n.replace("-","").upper()[:8]

def log(m):        print(f"[OpenGOAL] {m}")
