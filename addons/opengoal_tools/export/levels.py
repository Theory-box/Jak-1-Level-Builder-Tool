# ───────────────────────────────────────────────────────────────────────
# export/levels.py — OpenGOAL Level Tools
#
# Custom-level lifecycle: discover on disk, remove from the project, compute per-level code/art dependencies for DGO inclusion.
# ───────────────────────────────────────────────────────────────────────

from __future__ import annotations

import bpy, os, re, json, math, mathutils
from pathlib import Path
from ..data import (
    ENTITY_DEFS, ETYPE_CODE, ETYPE_TPAGES, ETYPE_AG, ETYPE_EXTRAS_AG, VERTEX_EXPORT_TYPES,
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
    _game_gp,
    log,
    _goal_src,
    _level_info,
    _load_boundary_data,
    _levels_dir,
    _nick,
)


# Cross-module imports (siblings in the export package)


def needed_ags(actors):
    """Entity-own art groups (the visible mesh/skel for each actor).

    Used both by write_jsonc (drives merc extraction in goalc's build_level)
    and write_gd (drives DGO bundling). Animation-only art groups required
    by target/shared code (e.g. eichar-pole+0-ag for swingpole interactions)
    go through needed_extras_ags() instead — they must NOT appear in the
    JSONC art_groups field, because find_art_groups in build_level.cpp will
    try to extract merc data from them and they have none.
    """
    seen, r = set(), []
    for a in actors:
        # A variant may override the actor's art group (e.g. per-bridge variant).
        ags = [a["art_group"]] if a.get("art_group") else ETYPE_AG.get(a["etype"], [])
        for g in ags:
            if g and g not in seen:
                seen.add(g); r.append(g)
    return r

def needed_extras_ags(actors):
    """Extra art groups Jak/target needs bundled when these entities are
    in the level. Goes only into the .gd (DGO contents), NOT the JSONC.

    Example: swingpole. Vanilla SWA/SNO/ROB DGOs bundle eichar-pole+0-ag.go
    because target-pole-cycle plays eichar-pole-cycle-ja (lives in that
    +0-ag, not in eichar-ag). Without it, the anim symbol doesn't link,
    evaluate-joint-control fires 'dummy-19 bad' / process-drawable-art-error,
    and Jak goes invisible / the game crashes.
    """
    seen, r = set(), []
    for a in actors:
        extras = list(ETYPE_EXTRAS_AG.get(a["etype"], [])) + list(a.get("extra_art_groups", []))
        for g in extras:
            if g and g not in seen:
                seen.add(g); r.append(g)
    return r

def needed_code(actors):
    """Return list of (o_file, gc_path, dep) for enemy types not in GAME.CGO.

    o_only=True entries: inject .o into custom DGO only — vanilla game.gp already
    has the goal-src line so we must not duplicate it (causes 'duplicate defstep').

    Returns list of (o_file, gc_path_or_None, dep_or_None).
    write_gd() uses o_file for DGO injection.
    patch_game_gp() skips entries where gc_path is None.
    """
    seen, r = set(), []
    for a in actors:
        etype = a["etype"]
        info = ETYPE_CODE.get(etype)
        if info and not info.get("in_game_cgo"):
            o = info["o"]
            if o not in seen:
                seen.add(o)
                if info.get("o_only"):
                    r.append((o, None, None))
                else:
                    r.append((o, info["gc"], info.get("dep", "process-drawable")))
        # Variant extra code (e.g. snow bridge -> target-ice.o). DGO-only:
        # goal-src is already in game.gp, so inject the .o with no gc line.
        for o in a.get("extra_code", []):
            if o and o not in seen:
                seen.add(o)
                r.append((o, None, None))
    return r

def discover_custom_levels():
    """Scan the filesystem and game.gp to find all custom levels.

    Returns a list of dicts:
      name        - level name (folder name)
      has_glb     - .glb exists
      has_jsonc   - .jsonc exists
      has_obs     - obs.gc exists
      has_gp      - entry found in game.gp
      conflict    - True if multiple levels share the same DGO nick
      nick        - 3-char nickname
      dgo         - DGO filename
    """
    levels_dir = _levels_dir()
    goal_levels = _goal_src() / "levels"
    gp_path = _game_gp()

    # Read game.gp entries
    gp_names = set()
    if gp_path.exists():
        txt = gp_path.read_text(encoding="utf-8")
        for m in re.finditer(r'\(build-custom-level "([^"]+)"\)', txt):
            gp_names.add(m.group(1))

    # Scan custom_assets/jak1/levels/
    found = {}
    if levels_dir.exists():
        for d in sorted(levels_dir.iterdir()):
            if not d.is_dir():
                continue
            name = d.name
            nick = _nick(name)
            dgo  = f"{nick.upper()}.DGO"
            found[name] = {
                "name":      name,
                "has_glb":   (d / f"{name}.glb").exists(),
                "has_jsonc": (d / f"{name}.jsonc").exists(),
                "has_gd":    (d / f"{nick}.gd").exists(),
                "has_obs":   (goal_levels / name / f"{name}-obs.gc").exists(),
                "has_gp":    name in gp_names,
                "nick":      nick,
                "dgo":       dgo,
                "conflict":  False,
            }

    # Detect DGO nickname conflicts
    nick_to_names = {}
    for info in found.values():
        nick_to_names.setdefault(info["dgo"], []).append(info["name"])
    for names in nick_to_names.values():
        if len(names) > 1:
            for n in names:
                found[n]["conflict"] = True

    return list(found.values())

def remove_level(name):
    """Remove all files for a custom level and clean game.gp.

    Deletes:
      custom_assets/jak1/levels/<name>/   (entire folder)
      goal_src/jak1/levels/<name>/        (entire folder)

    Removes from game.gp:
      (build-custom-level "<name>")
      (custom-level-cgo ...)
      (goal-src "levels/<name>/...")

    Returns list of log messages.
    """
    import shutil
    msgs = []

    # Delete custom_assets folder
    assets_dir = _levels_dir() / name
    if assets_dir.exists():
        shutil.rmtree(assets_dir)
        msgs.append(f"Deleted {assets_dir}")
    else:
        msgs.append(f"(not found) {assets_dir}")

    # Delete goal_src levels folder
    goal_dir = _goal_src() / "levels" / name
    if goal_dir.exists():
        shutil.rmtree(goal_dir)
        msgs.append(f"Deleted {goal_dir}")
    else:
        msgs.append(f"(not found) {goal_dir}")

    msgs += _strip_level_registrations(name)
    return msgs


def _strip_level_registrations(name):
    """Strip a level's build registrations (level-info.gc, game.gp,
    load-boundary-data.gc) WITHOUT touching any files on disk.

    Shared by remove_level (which also deletes the folders) and by
    prune_orphaned_levels (which only un-registers levels whose files are
    already gone). Returns list of log messages.
    """
    msgs = []

    # Patch level-info.gc — strip the define block and cons! entry
    li_path = _level_info()
    if li_path.exists():
        txt = li_path.read_text(encoding="utf-8")
        new_txt = re.sub(
            rf"\n\(define {re.escape(name)}\b.*?\(cons!.*?'{re.escape(name)}\)\n",
            "", txt, flags=re.DOTALL)
        if new_txt != txt:
            li_path.write_text(new_txt, encoding="utf-8")
            msgs.append(f"Cleaned level-info.gc entry for '{name}'")
        else:
            msgs.append(f"level-info.gc had no entry for '{name}'")
    else:
        msgs.append("level-info.gc not found")

    # Patch game.gp — strip all entries for this level
    gp_path = _game_gp()
    if gp_path.exists():
        raw  = gp_path.read_bytes()
        crlf = b"\r\n" in raw
        txt  = raw.decode("utf-8").replace("\r\n", "\n")
        before = txt

        nick = _nick(name)
        txt = re.sub(r'\(build-custom-level "' + re.escape(name) + r'"\)\n', '', txt)
        txt = re.sub(r'\(custom-level-cgo "[^"]*" "' + re.escape(name) + r'/[^"]+\"\)\n', '', txt)
        txt = re.sub(r'\(goal-src "levels/' + re.escape(name) + r'/[^"]+\"[^)]*\)\n', '', txt)

        if txt != before:
            if crlf:
                txt = txt.replace("\n", "\r\n")
            gp_path.write_bytes(txt.encode("utf-8"))
            msgs.append(f"Cleaned game.gp entries for '{name}'")
        else:
            msgs.append(f"game.gp had no entries for '{name}'")
    else:
        msgs.append("game.gp not found")

    # Strip this level's custom load-boundary block (matches patch_load_boundaries markers)
    lb_path = _load_boundary_data()
    if lb_path.exists():
        txt = lb_path.read_text(encoding="utf-8")
        begin = f";; ===== OG CUSTOM BOUNDARIES: {name} ====="
        end   = f";; ===== END OG CUSTOM BOUNDARIES: {name} ====="
        new_txt = re.sub(rf"\n{re.escape(begin)}.*?{re.escape(end)}\n", "\n", txt, flags=re.DOTALL)
        if new_txt != txt:
            lb_path.write_text(new_txt, encoding="utf-8")
            msgs.append(f"Cleaned load-boundary-data.gc block for '{name}'")
        else:
            msgs.append(f"load-boundary-data.gc had no boundaries for '{name}'")

    return msgs


def prune_orphaned_levels():
    """Self-heal the build: drop registrations for any custom level whose
    generated files no longer exist on disk.

    Scans game.gp for (custom-level-cgo ...) entries and, for each, checks that
    both the referenced .gd (custom_assets) and the level's -obs.gc (goal_src)
    still exist. If either is missing, the level's registrations are stripped
    from game.gp / level-info.gc / load-boundary-data.gc so (mi) won't choke on
    a file the user deleted by hand. Does NOT delete any files. Idempotent.

    Returns list of pruned level names.
    """
    gp_path = _game_gp()
    if not gp_path.exists():
        return []
    try:
        txt = gp_path.read_bytes().decode("utf-8", errors="ignore").replace("\r\n", "\n")
    except Exception:
        return []

    pruned = []
    for m in re.finditer(r'\(custom-level-cgo "[^"]*" "([^"/]+)/([^"]+)"\)', txt):
        name, gd_rel = m.group(1), m.group(2)
        if name in pruned:
            continue
        gd_path  = _levels_dir() / name / gd_rel
        obs_path = _goal_src() / "levels" / name / f"{name}-obs.gc"
        if (not gd_path.exists()) or (not obs_path.exists()):
            _strip_level_registrations(name)
            pruned.append(name)
            log(f"[prune] '{name}' files missing — removed stale build registration")
    return pruned
