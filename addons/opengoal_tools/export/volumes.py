# ───────────────────────────────────────────────────────────────────────
# export/volumes.py — OpenGOAL Level Tools
#
# Volume (aggro/custom trigger) link helpers: find volumes linking to X, rename on link change, clean orphaned links.
# Used by scene.py when collecting triggers and by the operators when manipulating link tables.
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
from .paths import (
    log,
)


# Cross-module imports (siblings in the export package)


def _vol_aabb(vol_obj):
    """Compute the game-space AABB of a volume mesh.
    Returns (xs_min, xs_max, ys_min, ys_max, zs_min, zs_max, cx, cy, cz, radius).
    Used by all trigger build passes (camera, checkpoint, aggro).
    """
    corners = [vol_obj.matrix_world @ v.co for v in vol_obj.data.vertices]
    gc = [(c.x, c.z, -c.y) for c in corners]
    xs = [c[0] for c in gc]; ys = [c[1] for c in gc]; zs = [c[2] for c in gc]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    zmin, zmax = min(zs), max(zs)
    cx = round((xmin + xmax) / 2, 4)
    cy = round((ymin + ymax) / 2, 4)
    cz = round((zmin + zmax) / 2, 4)
    rad = round(max(xmax - xmin, ymax - ymin, zmax - zmin) / 2 + 5.0, 2)
    return (round(xmin, 4), round(xmax, 4),
            round(ymin, 4), round(ymax, 4),
            round(zmin, 4), round(zmax, 4),
            cx, cy, cz, rad)

def _vol_links(vol):
    """Return the og_vol_links CollectionProperty on a volume mesh.
    Migrates legacy single-string og_vol_link if present.
    Always safe to call — returns the live collection.
    """
    if vol is None:
        return None
    # Migration: legacy single-string format -> single-entry collection
    legacy = vol.get("og_vol_link", "")
    if legacy and len(vol.og_vol_links) == 0:
        entry = vol.og_vol_links.add()
        entry.target_name = legacy
        entry.behaviour   = "cue-chase"
        try:
            del vol["og_vol_link"]
        except Exception:
            pass
    return vol.og_vol_links

def _vol_link_targets(vol):
    """Return list of target_name strings for a volume. Migrates if needed."""
    links = _vol_links(vol)
    if links is None:
        return []
    return [e.target_name for e in links]

def _vol_has_link_to(vol, target_name):
    """True if the volume has at least one link to target_name."""
    return target_name in _vol_link_targets(vol)

def _rename_vol_for_links(vol):
    """Rename a volume mesh based on its current link count.
    0 links → VOL_<id>
    1 link  → VOL_<target_name>
    2+ links → VOL_<id>_<n>links
    Idempotent. Stores the original numeric id in og_vol_id (set on spawn).
    """
    if vol is None:
        return
    links = _vol_links(vol)
    n = len(links)
    vid = vol.get("og_vol_id", 0)
    if n == 0:
        new_name = f"VOL_{vid}"
    elif n == 1:
        new_name = f"VOL_{links[0].target_name}"
    else:
        new_name = f"VOL_{vid}_{n}links"
    if vol.name != new_name:
        vol.name = new_name

def _vols_linking_to(scene, target_name):
    """Return all VOL_ meshes that have at least one link to target_name."""
    return sorted(
        [o for o in _level_objects(scene)
         if o.type == "MESH" and o.name.startswith("VOL_")
         and _vol_has_link_to(o, target_name)],
        key=lambda o: o.name,
    )

def _vol_get_link_to(vol, target_name):
    """Return the OGVolLink entry on vol pointing at target_name, or None."""
    for entry in _vol_links(vol):
        if entry.target_name == target_name:
            return entry
    return None

def _vol_remove_link_to(vol, target_name):
    """Remove the link entry pointing at target_name from vol. Returns True if found."""
    links = _vol_links(vol)
    for i, entry in enumerate(links):
        if entry.target_name == target_name:
            links.remove(i)
            _rename_vol_for_links(vol)
            return True
    return False

def _clean_orphaned_vol_links(scene):
    """Remove link entries from VOL_ meshes whose targets no longer exist.
    Called at export time and available as a panel button.
    Returns list of (vol_name, target_name) tuples that were cleaned.
    Volume is renamed if its link count changes (or restored to VOL_<id> if empty).
    """
    cleaned = []
    for o in _level_objects(scene):
        if o.type != "MESH" or not o.name.startswith("VOL_"):
            continue
        links = _vol_links(o)
        # walk in reverse so removals don't shift indices
        i = len(links) - 1
        any_removed = False
        while i >= 0:
            tname = links[i].target_name
            if not scene.objects.get(tname):
                links.remove(i)
                cleaned.append((o.name, tname))
                log(f"  [vol] cleaned orphaned link {o.name} → '{tname}' (target deleted)")
                any_removed = True
            i -= 1
        if any_removed:
            _rename_vol_for_links(o)
    return cleaned
