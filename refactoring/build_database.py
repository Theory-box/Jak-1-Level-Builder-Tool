#!/usr/bin/env python3
"""
build_database.py — Assembles jak1_game_database.jsonc from the current addon sources.

Run:
    cd <repo root>
    python3 refactoring/build_database.py

Output:
    refactoring/jak1_game_database.jsonc

Re-run after any addon-side data change to rebuild. The idea is that once the
reference file is the source of truth (post-rewire), this script and the old
addon data will be deleted — but during the migration window, being able to
deterministically regenerate the file from the current sources keeps us safe.
"""
from __future__ import annotations
import ast
import json
import re
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
ADDON = REPO / "addons" / "opengoal_tools"
OUT = REPO / "refactoring" / "jak1_game_database.jsonc"


# ═════════════════════════════════════════════════════════════════════════════
# STEP 1 — Load raw tables from data.py
# ═════════════════════════════════════════════════════════════════════════════
def load_data_py() -> dict:
    """Load the PRE-MIGRATION data.py (from git HEAD at migration time).

    After the rewire, data.py is a thin shim that imports from db.py, which
    creates a chicken-and-egg if we try to exec it directly. The pristine
    data.py lives in git history at the commit immediately before migration.

    We try three sources, in order:
      1. Local git: the commit tagged `pre-migration-data` (if present)
      2. Local git: latest commit where addons/opengoal_tools/data.py doesn't
         contain `from . import db` (auto-detected).
      3. Current filesystem version (works if someone runs this before
         data.py is shimified).
    """
    import subprocess
    ns: dict[str, Any] = {"__name__": "data", "__builtins__": __builtins__}
    # Strategy 1 — tag
    try:
        src = subprocess.check_output(
            ["git", "-C", str(REPO), "show",
             "pre-migration-data:addons/opengoal_tools/data.py"],
            stderr=subprocess.DEVNULL,
        ).decode()
        exec(src, ns)
        return ns
    except Exception:
        pass
    # Strategy 2 — walk history, pick first commit where data.py is the pure-data version
    try:
        log = subprocess.check_output(
            ["git", "-C", str(REPO), "log", "--format=%H", "--",
             "addons/opengoal_tools/data.py"],
            stderr=subprocess.DEVNULL,
        ).decode().split()
        for sha in log:
            src = subprocess.check_output(
                ["git", "-C", str(REPO), "show",
                 f"{sha}:addons/opengoal_tools/data.py"],
                stderr=subprocess.DEVNULL,
            ).decode()
            if "from . import db" not in src and "ENTITY_DEFS = {" in src:
                exec(src, ns)
                return ns
    except Exception:
        pass
    # Strategy 3 — filesystem (only works pre-shim)
    src = (ADDON / "data.py").read_text()
    if "from . import db" in src:
        raise RuntimeError(
            "data.py is now a shim over db.py — can't be re-exec'd directly. "
            "Tag the last pre-migration commit as 'pre-migration-data' or "
            "rebuild using the original data.py source."
        )
    exec(src, ns)
    return ns


# ═════════════════════════════════════════════════════════════════════════════
# STEP 2 — Extract specific literal assignments from files that import bpy
# ═════════════════════════════════════════════════════════════════════════════
def extract_literal(path: Path, name: str) -> Any:
    """Find a top-level `<name> = <literal>` in a Python file and return the literal."""
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == name:
                    return ast.literal_eval(node.value)
    raise KeyError(f"{name} not found in {path.name}")


# ═════════════════════════════════════════════════════════════════════════════
# STEP 3 — Per-actor custom fields (from audit v2 §B.5)
# ═════════════════════════════════════════════════════════════════════════════
# Each entry: etype(s) → list of field definitions.
# A field: {key, label, type, default, lump, write_if, [choices for enum]}
# `lump` may be omitted when the field maps to a bit in a shared bitfield (use
# `lump_bit` instead: {key, type, bit_value}).
#
# Write conditions:
#   "always"          — always emit the lump
#   "if_true"         — only when bool == True
#   "if_nonzero"      — only when numeric != 0 (or 0.0)
#   "if_not_default"  — only when value != the default
#   "if_positive"     — only when value > 0
#   "if_nonneg"       — only when value >= 0
#   "if_non_empty"    — only when string is non-empty
#   "if_not_none"     — only when enum value != "none"
PER_ACTOR_FIELDS: dict[str | tuple[str, ...], list[dict]] = {
    "fuel-cell": [
        {"key": "og_cell_skip_jump", "label": "Skip jump animation", "type": "bool",
         "default": False, "lump": {"key": "options", "type": "uint32"},
         "value_if_true": 4, "write_if": "if_true"},
    ],
    "crate": [
        {"key": "og_crate_type", "label": "Crate Type", "type": "enum",
         "default": "steel",
         "choices": "CrateTypes",  # references top-level CrateTypes section
         "lump": {"key": "crate-type", "type": "symbol_literal"},
         "write_if": "always"},
        {"key": "og_crate_pickup", "label": "Pickup", "type": "enum",
         "default": "money",
         "choices": "CratePickups",
         "lump": {"key": "eco-info", "type": "eco-info-picker",
                  "pairs_with": "og_crate_pickup_amount"},
         "write_if": "if_not_none"},
        {"key": "og_crate_pickup_amount", "label": "Amount", "type": "int",
         "default": 1, "min": 1, "max": 99,
         "note": "Forced to 1 when pickup == buzzer (engine always spawns 1 scout fly)."},
    ],
    "dark-crystal": [
        {"key": "og_crystal_underwater", "label": "Underwater variant", "type": "bool",
         "default": False, "lump": {"key": "mode", "type": "int32"},
         "value_if_true": 1, "write_if": "if_true"},
    ],
    "plat-flip": [
        {"key": "og_flip_sync_pct", "label": "Sync phase offset", "type": "float",
         "default": 0.0, "min": 0.0, "max": 1.0,
         "lump": {"key": "sync-percent", "type": "float"},
         "write_if": "if_nonzero"},
        {"key": "og_flip_delay_down", "label": "Delay — down (s)", "type": "float",
         "default": 2.0, "min": 0.0,
         "lump": {"key": "delay", "type": "float", "slot": 0},
         "write_if": "always"},
        {"key": "og_flip_delay_up", "label": "Delay — up (s)", "type": "float",
         "default": 2.0, "min": 0.0,
         "lump": {"key": "delay", "type": "float", "slot": 1},
         "write_if": "always"},
    ],
    ("eco-door", "jng-iris-door", "sidedoor", "rounddoor"): [
        {"key": "og_door_auto_close", "label": "Auto-close", "type": "bool",
         "default": False,
         "lump_bit": {"key": "flags", "type": "uint32", "bit_value": 4},
         "write_if": "if_true"},
        {"key": "og_door_one_way", "label": "One-way", "type": "bool",
         "default": False,
         "lump_bit": {"key": "flags", "type": "uint32", "bit_value": 8},
         "write_if": "if_true"},
        {"key": "og_door_starts_open", "label": "Starts open", "type": "bool",
         "default": False,
         "lump": {"key": "perm-status", "type": "uint32"},
         "value_if_true": 64, "write_if": "if_true"},
        # NOTE: ecdf00 bit (value 1) is auto-set when state-actor link is present.
        # That's not a user-facing field — it's export-time logic; stays in code.
    ],
    "sun-iris-door": [
        {"key": "og_door_proximity", "label": "Opens on proximity", "type": "bool",
         "default": False, "lump": {"key": "proximity", "type": "uint32"},
         "value_if_true": 1, "write_if": "if_true"},
        {"key": "og_door_timeout", "label": "Auto-close timeout (s)", "type": "float",
         "default": 0.0, "min": 0.0,
         "lump": {"key": "timeout", "type": "float"},
         "write_if": "if_positive"},
    ],
    "basebutton": [
        {"key": "og_button_timeout", "label": "Auto-release timeout (s)", "type": "float",
         "default": 0.0, "min": 0.0,
         "lump": {"key": "timeout", "type": "float"},
         "write_if": "if_positive"},
    ],
    "water-vol": [
        {"key": "og_water_surface", "label": "Surface Y (world)", "type": "float",
         "default_from": "mesh_ymax",
         "lump": {"key": "water-height", "type": "water-height", "slot": 0},
         "write_if": "always"},
        {"key": "og_water_wade", "label": "Wade depth (m)", "type": "float",
         "default": 0.5, "min": 0.0,
         "lump": {"key": "water-height", "type": "water-height", "slot": 1},
         "write_if": "always"},
        {"key": "og_water_swim", "label": "Swim depth (m)", "type": "float",
         "default": 1.0, "min": 0.0,
         "lump": {"key": "water-height", "type": "water-height", "slot": 2},
         "write_if": "always"},
        {"key": "og_water_bottom", "label": "Bottom Y (world)", "type": "float",
         "default_from": "mesh_ymin",
         "note": "Defines the kill-floor for the volume; not a direct lump field — consumed by the vol plane geometry."},
        {"key": "og_water_attack", "label": "Attack event", "type": "enum",
         "default": "drown",
         "choices": [
             {"value": "drown",       "label": "Drown"},
             {"value": "endlessfall", "label": "Endless fall"},
         ],
         "lump": {"key": "attack-event", "type": "symbol"},
         "write_if": "always"},
    ],
    "launcherdoor": [
        {"key": "og_continue_name", "label": "Continue point name", "type": "string",
         "default": "",
         "lump": {"key": "continue-name", "type": "string"},
         "write_if": "if_non_empty"},
    ],
    ("launcher", "springbox"): [
        {"key": "og_spring_height", "label": "Spring height (m)", "type": "float",
         "default": -1.0,
         "lump": {"key": "spring-height", "type": "meters"},
         "write_if": "if_nonneg"},
    ],
    "launcher": [
        {"key": "og_launcher_dest", "label": "Destination object", "type": "object_ref",
         "default": "",
         "lump": {"key": "alt-vector", "type": "vector",
                  "pairs_with": "og_launcher_fly_time"},
         "note": "xyz of alt-vector is the resolved location of the destination object.",
         "write_if": "if_object_found"},
        {"key": "og_launcher_fly_time", "label": "Fly time (s)", "type": "float",
         "default": -1.0,
         "note": "w component of alt-vector = fly_time_seconds × 300 (engine frames)."},
    ],
    ("swamp-bat", "yeti", "villa-starfish", "swamp-rat-nest"): [
        {"key": "og_num_lurkers", "label": "Child count", "type": "int",
         "default": -1, "min": -1,
         "lump": {"key": "num-lurkers", "type": "int32"},
         "write_if": "if_nonneg"},
    ],
    "orb-cache-top": [
        {"key": "og_orb_count", "label": "Orbs inside", "type": "int",
         "default": 20, "min": 1,
         "lump": {"key": "orb-cache-count", "type": "int32"},
         "write_if": "always"},
    ],
    "whirlpool": [
        {"key": "og_whirl_speed", "label": "Speed base", "type": "float",
         "default": 0.3,
         "lump": {"key": "speed", "type": "float", "slot": 0},
         "write_if": "always"},
        {"key": "og_whirl_var", "label": "Speed variance", "type": "float",
         "default": 0.1,
         "lump": {"key": "speed", "type": "float", "slot": 1},
         "write_if": "always"},
    ],
    "ropebridge": [
        {"key": "og_bridge_variant", "label": "Bridge Variant", "type": "enum",
         "default": "ropebridge-32",
         "choices": [
             {"value": "ropebridge-32",  "label": "Rope Bridge 32m"},
             {"value": "ropebridge-36",  "label": "Rope Bridge 36m"},
             {"value": "ropebridge-52",  "label": "Rope Bridge 52m"},
             {"value": "ropebridge-70",  "label": "Rope Bridge 70m"},
             {"value": "snow-bridge-36", "label": "Snow Bridge 36m"},
             {"value": "vil3-bridge-36", "label": "Village3 Bridge 36m"},
         ],
         "lump": {"key": "art-name", "type": "symbol"},
         "write_if": "always"},
    ],
    "orbit-plat": [
        {"key": "og_orbit_scale", "label": "Orbit scale", "type": "float",
         "default": 1.0,
         "lump": {"key": "scale", "type": "float"},
         "write_if": "if_not_default"},
        {"key": "og_orbit_timeout", "label": "Orbit timeout (s)", "type": "float",
         "default": 10.0,
         "lump": {"key": "timeout", "type": "float"},
         "write_if": "if_not_default"},
    ],
    "square-platform": [
        {"key": "og_sq_down", "label": "Down travel (m)", "type": "float",
         "default": -2.0,
         "lump": {"key": "distance", "type": "float", "slot": 0, "scale": 4096},
         "write_if": "always"},
        {"key": "og_sq_up", "label": "Up travel (m)", "type": "float",
         "default": 4.0,
         "lump": {"key": "distance", "type": "float", "slot": 1, "scale": 4096},
         "write_if": "always"},
    ],
    "caveflamepots": [
        {"key": "og_flame_shove", "label": "Shove force (m)", "type": "float",
         "default": 2.0,
         "lump": {"key": "shove", "type": "meters"}, "write_if": "always"},
        {"key": "og_flame_period", "label": "Cycle period (s)", "type": "float",
         "default": 4.0,
         "lump": {"key": "cycle-speed", "type": "float", "slot": 0},
         "write_if": "always"},
        {"key": "og_flame_phase", "label": "Cycle phase", "type": "float",
         "default": 0.0,
         "lump": {"key": "cycle-speed", "type": "float", "slot": 1},
         "write_if": "always"},
        {"key": "og_flame_pause", "label": "Cycle pause (s)", "type": "float",
         "default": 2.0,
         "lump": {"key": "cycle-speed", "type": "float", "slot": 2},
         "write_if": "always"},
    ],
    "shover": [
        {"key": "og_shover_force", "label": "Shove force (m)", "type": "float",
         "default": 3.0,
         "lump": {"key": "shove", "type": "meters"},
         "write_if": "always"},
        {"key": "og_shover_rot", "label": "Rotation offset (°)", "type": "float",
         "default": 0.0,
         "lump": {"key": "rotoffset", "type": "degrees"},
         "write_if": "if_nonzero"},
    ],
    ("lavaballoon", "darkecobarrel"): [
        {"key": "og_move_speed", "label": "Move speed (m/s)", "type": "float",
         "default_per_etype": {"lavaballoon": 3.0, "darkecobarrel": 15.0},
         "lump": {"key": "speed", "type": "meters"},
         "write_if": "always"},
    ],
    "windturbine": [
        {"key": "og_turbine_particles", "label": "Particles on", "type": "bool",
         "default": False,
         "lump": {"key": "particle-select", "type": "uint32"},
         "value_if_true": 1, "write_if": "if_true"},
    ],
    "caveelevator": [
        {"key": "og_elevator_mode", "label": "Mode", "type": "int",
         "default": 0, "min": 0,
         "lump": {"key": "mode", "type": "uint32"},
         "write_if": "if_nonzero"},
        {"key": "og_elevator_rot", "label": "Rotation offset (°)", "type": "float",
         "default": 0.0,
         "lump": {"key": "rotoffset", "type": "degrees"},
         "write_if": "if_nonzero"},
    ],
    "mis-bone-bridge": [
        {"key": "og_bone_bridge_anim", "label": "Animation index", "type": "int",
         "default": 0, "min": 0,
         "lump": {"key": "animation-select", "type": "uint32"},
         "write_if": "if_nonzero"},
    ],
    ("breakaway-left", "breakaway-mid", "breakaway-right"): [
        {"key": "og_breakaway_h1", "label": "Height 1", "type": "float",
         "default": 0.0,
         "lump": {"key": "height-info", "type": "float", "slot": 0,
                  "pairs_with": "og_breakaway_h2"},
         "write_if": "if_any_nonzero"},
        {"key": "og_breakaway_h2", "label": "Height 2", "type": "float",
         "default": 0.0,
         "lump": {"key": "height-info", "type": "float", "slot": 1}},
    ],
    "sunkenfisha": [
        {"key": "og_fish_count", "label": "Fish count", "type": "int",
         "default": 1, "min": 1,
         "lump": {"key": "count", "type": "uint32"},
         "write_if": "if_not_default"},
    ],
    "sharkey": [
        {"key": "og_shark_scale", "label": "Scale", "type": "float", "default": 1.0,
         "lump": {"key": "scale", "type": "float"}, "write_if": "if_not_default"},
        {"key": "og_shark_delay", "label": "Delay (s)", "type": "float", "default": 1.0,
         "lump": {"key": "delay", "type": "float"}, "write_if": "always"},
        {"key": "og_shark_distance", "label": "Alert distance (m)", "type": "float",
         "default": 30.0,
         "lump": {"key": "distance", "type": "meters"}, "write_if": "always"},
        {"key": "og_shark_speed", "label": "Speed (m/s)", "type": "float", "default": 12.0,
         "lump": {"key": "speed", "type": "meters"}, "write_if": "always"},
    ],
    ("oracle", "pontoon"): [
        {"key": "og_alt_task", "label": "Linked Task", "type": "enum",
         "default": "none",
         "choices": "GameTasks",
         "lump": {"key": "alt-task", "type": "enum-uint32",
                  "format": "(game-task {value})"},
         "write_if": "if_not_none"},
    ],
}


# ═════════════════════════════════════════════════════════════════════════════
# STEP 4 — Parent hierarchy (minimal — v2 addendum §C.Q4)
# ═════════════════════════════════════════════════════════════════════════════
# Every actor has exactly one parent. The parent contributes default link slots
# and default lumps that every child inherits. Universal lumps (vis-dist,
# idle-distance, etc.) belong to the root-most parent.
PARENTS = [
    {
        "etype": "process-drawable",
        "parent": None,  # root
        "description": "Root type for all spawnable entities.",
        "links": {
            "need_task": False, "need_path": False, "need_nav": False, "need_enemy": False,
            "need_vol": False, "need_alt": False, "need_prev": False, "need_next": False,
            "need_sync": False, "need_eco-info": False, "need_pathb": False,
        },
        "lumps": [
            # The 8 universal lumps (UNIVERSAL_LUMPS in data.py)
            {"key": "vis-dist",      "type": "meters",    "description": "Distance at which entity stays active/visible. Enemies default 200m."},
            {"key": "idle-distance", "type": "meters",    "description": "Player must be closer than this to wake the enemy. Default 80m."},
            {"key": "shadow-mask",   "type": "uint32",    "description": "Which shadow layers render for this entity. e.g. 255 = all."},
            {"key": "light-index",   "type": "uint32",    "description": "Index into the level's light array. Controls entity illumination."},
            {"key": "lod-dist",      "type": "meters",    "description": "Distance threshold for LOD switching. Array of floats per LOD level."},
            {"key": "texture-bucket","type": "int32",     "description": "Texture bucket for draw calls. Default 1."},
            {"key": "options",       "type": "enum-uint32","description": "fact-options bitfield e.g. '(fact-options has-power-cell)'."},
            {"key": "visvol",        "type": "vector4m",  "description": "Visibility bounding box — two vector4m entries (min corner, max corner)."},
        ],
    },
    {
        "etype": "nav-enemy",
        "parent": "process-drawable",
        "description": "Enemy that uses nav-mesh pathfinding. Requires a navmesh + a patrol path.",
        "links": {
            "need_path": True,
            "need_nav": True,
            "need_enemy": True,
        },
        "link_desc": {
            "desc_path":  "REQUIRED. Path indicates the patrol line.",
            "desc_nav":   "REQUIRED. Nav-mesh defines where the enemy is able to walk.",
            "desc_enemy": "Controls the AI of the enemy.",
        },
        "lumps": [
            # Enemy-universal lumps (LUMP_REFERENCE["_enemy"] sentinel in data.py)
            {"key": "nav-mesh-sphere", "type": "vector4m", "description": "Fallback nav sphere: 'x y z radius_m'. Auto-injected for nav-unsafe enemies."},
            {"key": "nav-max-users",   "type": "int32",    "description": "Max nav-control users sharing this navmesh. Default 32."},
        ],
    },
    {
        "etype": "prop",
        "parent": "process-drawable",
        "description": "Decorative only. No AI, no combat, idle animation only.",
        "links": {},
        "lumps": [],
    },
    {
        "etype": "eco-collectable",
        "parent": "process-drawable",
        "description": "Pickups (orbs, eco, scout flies, fuel cells). Picked up on contact.",
        "links": {
            "need_eco-info": True,
        },
        "lumps": [],
    },
]


# ═════════════════════════════════════════════════════════════════════════════
# STEP 5 — Helpers to derive per-actor data from ai_type / cat
# ═════════════════════════════════════════════════════════════════════════════
def parent_for(etype: str, info: dict) -> str:
    """Pick the reference-file Parent for an actor based on its ai_type and cat."""
    ai = info.get("ai_type", "prop")
    cat = info.get("cat", "")
    if cat == "Pickups":
        return "eco-collectable"
    return ai  # "nav-enemy" | "process-drawable" | "prop"


def links_for_actor(info: dict) -> dict:
    """Derive the explicit `links` block for an actor. These are UI-availability
    booleans (which waypoint/nav/etc. menus to show), NOT runtime-required flags.

    Runtime-required flags (needs_path, needs_pathb, needs_sync, needs_notice_dist)
    live at the top level of the actor record so they're clearly distinct from
    UI-availability. The old code conflated these — we keep them separate now."""
    links: dict = {}
    # Nav-enemies show the waypoint + nav-mesh pickers in the UI regardless of
    # whether a path is runtime-required. needs_path at the top level is the
    # runtime-required signal.
    if info.get("ai_type") == "nav-enemy":
        links["need_path"] = True
        links["need_nav"] = True
    # Explicit legacy flags propagate into UI visibility too
    if info.get("needs_pathb"):
        links["need_pathb"] = True
    if info.get("needs_sync"):
        links["need_sync"] = True
    # Enemy link UI shown for all Enemies/Bosses
    if info.get("cat") in ("Enemies", "Bosses"):
        links["need_enemy"] = True
    return links


# ═════════════════════════════════════════════════════════════════════════════
# STEP 6 — Assembler
# ═════════════════════════════════════════════════════════════════════════════
def build_database() -> dict:
    data = load_data_py()
    panels_path = ADDON / "panels.py"
    textures_path = ADDON / "textures.py"

    # Parse panels.py / textures.py literals
    ropebridge_variants = extract_literal(panels_path, "_ROPEBRIDGE_VARIANTS")
    game_tasks_common = extract_literal(panels_path, "_GAME_TASKS_COMMON")
    tpage_groups = extract_literal(textures_path, "TPAGE_GROUPS")

    db: dict = {}

    # ── Engine ──────────────────────────────────────────────────────────────
    db["Engine"] = {
        "game_id": "jak1",
        "description": "OpenGOAL engine constants. Shared across Jak titles — "
                       "keep in sync if we ever add a Jak 2 database.",
        "meter_scale": 4096,
        "degree_scale": 182.044,
        "goal_src_subdir":     "goal_src/jak1",
        "custom_assets_subdir": "custom_assets/jak1",
        "decompiler_out_subdir": "decompiler_out/jak1",
    }

    # ── Categories ──────────────────────────────────────────────────────────
    db["Categories"] = [
        {"id": "Enemies",   "label": "Enemies",   "collection_path": ["Spawnables", "Enemies"]},
        {"id": "Bosses",    "label": "Bosses",    "collection_path": ["Spawnables", "Enemies"]},
        {"id": "NPCs",      "label": "NPCs",      "collection_path": ["Spawnables", "NPCs"]},
        {"id": "Pickups",   "label": "Pickups",   "collection_path": ["Spawnables", "Pickups"]},
        {"id": "Platforms", "label": "Platforms", "collection_path": ["Spawnables", "Platforms"]},
        {"id": "Props",     "label": "Props",     "collection_path": ["Spawnables", "Props & Objects"]},
        {"id": "Objects",   "label": "Objects",   "collection_path": ["Spawnables", "Props & Objects"]},
        {"id": "Debug",     "label": "Debug",     "collection_path": ["Spawnables", "Props & Objects"]},
        {"id": "Hidden",    "label": "Hidden",    "collection_path": None,
         "note": "Not shown in the spawn picker — use for parent types or deprecated entries."},
    ]

    # ── Defaults (always-available assets) ──────────────────────────────────
    # Pulled implicitly from ETYPE_CODE entries with in_game_cgo=True plus
    # inspection of what the export code treats as 'no need to inject'.
    db["Defaults"] = {
        "note": "Assets that are always loaded by the engine. Actors listing these "
                "in their 'code'/'art_group'/'tpages' fields will NOT get them injected.",
        "in_game_cgo_etypes": sorted([e for e, v in data["ETYPE_CODE"].items()
                                      if v.get("in_game_cgo")]),
        "global_tpage_groups": sorted(data["GLOBAL_TPAGE_GROUPS"]),
    }

    # ── Levels ──────────────────────────────────────────────────────────────
    level_tpages = {
        "village1":   data["VILLAGE1_TPAGES"],
        "village2":   data["VILLAGE2_TPAGES"],
        "village3":   data["VILLAGE3_TPAGES"],
        "training":   data["TRAINING_TPAGES"],
        "beach":      data["BEACH_TPAGES"],
        "jungle":     data["JUNGLE_TPAGES"],
        "jungleb":    data["JUNGLEB_TPAGES"],
        "swamp":      data["SWAMP_TPAGES"],
        "snow":       data["SNOW_TPAGES"],
        "sunken":     data["SUNKEN_TPAGES"],
        "sub":        data["SUB_TPAGES"],
        "maincave":   data["CAVE_TPAGES"],
        "robocave":   data["ROBOCAVE_TPAGES"],
        "darkcave":   data["DARK_TPAGES"],
        "ogre":       data["OGRE_TPAGES"],
        "misty":      data["MISTY_TPAGES"],
        "lavatube":   data["LAVATUBE_TPAGES"],
        "firecanyon": data["FIRECANYON_TPAGES"],
        "rolling":    data["ROLLING_TPAGES"],
        "finalboss":  data["FINALBOSS_TPAGES"],
        "citadel":    data["CITADEL_TPAGES"],
    }
    # Texture browser group (id → label + folder prefixes)
    tex_by_level = {}
    for (gid, label, prefixes) in tpage_groups:
        tex_by_level[gid] = {"id": gid, "label": label, "folder_prefixes": prefixes}

    music_flava = data["MUSIC_FLAVA_TABLE"]
    sbk_sounds = data["SBK_SOUNDS"]
    global_tpage_groups_lower = {g.lower() for g in data["GLOBAL_TPAGE_GROUPS"]}

    levels = []
    for name, tpages in level_tpages.items():
        lvl = {
            "name": name,
            "tpages": list(tpages),
            "music_flavas": list(music_flava.get(name, ["default"])),
            "sbk_sounds": list(sbk_sounds.get(name, [])),
        }
        # Village1/2/3 + Training are in GLOBAL_TPAGE_GROUPS — their tpages are
        # effectively always loaded and don't count against the 2-group heap budget.
        if name in global_tpage_groups_lower:
            lvl["always_loaded_tpage_group"] = True
        levels.append(lvl)
    db["Levels"] = levels
    db["Levels_notes"] = (
        "Sound-bank/music-bank enum values live in SoundBanks (which doubles as "
        "both music and SFX bank list — they share the same namespace). "
        "Per-level mood, mood-func, priority, sky/ocean flags are NOT yet extracted "
        "— see export.py patch_level_info() which hardcodes them. Track for Pass 2."
    )

    # ── Level Collection Schema ─────────────────────────────────────────────
    # Blender-side custom properties that define a level collection.
    # Drives the addon's `New Level` creation + level-property panel.
    db["LevelCollectionSchema"] = {
        "description": "Custom properties stored on a level's top-level Blender "
                       "collection. Set when the user clicks 'New Level'; read "
                       "at export time to drive patch_level_info.",
        "marker_property": "og_is_level",
        "property_map": {
            # blender_prop_key → OGProperties attribute name
            "og_level_name":        "level_name",
            "og_base_id":           "base_id",
            "og_bottom_height":     "bottom_height",
            "og_vis_nick_override": "vis_nick_override",
            "og_sound_bank_1":      "sound_bank_1",
            "og_sound_bank_2":      "sound_bank_2",
            "og_music_bank":        "music_bank",
        },
        "defaults": {
            "og_is_level":          True,
            "og_level_name":        "my-level",
            "og_base_id":           10000,
            "og_bottom_height":     -20.0,
            "og_vis_nick_override": "",
            "og_sound_bank_1":      "none",
            "og_sound_bank_2":      "none",
            "og_music_bank":        "none",
        },
        "sub_collection_paths": {
            # Logical name → nested collection path
            "spawnable_enemies":   ["Spawnables", "Enemies"],
            "spawnable_platforms": ["Spawnables", "Platforms"],
            "spawnable_props":     ["Spawnables", "Props & Objects"],
            "spawnable_npcs":      ["Spawnables", "NPCs"],
            "spawnable_pickups":   ["Spawnables", "Pickups"],
            "triggers":            ["Triggers"],
            "cameras":             ["Cameras"],
            "spawns":              ["Spawns"],
            "sound_emitters":      ["Sound Emitters"],
            "water_volumes":       ["Water Volumes"],
            "geometry_solid":      ["Geometry", "Solid"],
            "geometry_collision":  ["Geometry", "Collision Only"],
            "geometry_visual":     ["Geometry", "Visual Only"],
            "geometry_reference":  ["Geometry", "Reference"],
            "waypoints":           ["Waypoints"],
            "navmeshes":           ["NavMeshes"],
            "export_as":           ["Export As"],
        },
    }

    # ── Texture Groups (standalone — for the texture browser UI) ────────────
    db["TextureGroups"] = [
        {"id": gid, "label": label, "folder_prefixes": prefixes}
        for (gid, label, prefixes) in tpage_groups
    ]

    # ── Audio ───────────────────────────────────────────────────────────────
    db["SoundBanks"] = [{"id": b[0], "label": b[1]} for b in data["LEVEL_BANKS"]]
    db["MusicBanks"] = [
        {"bank": bank, "flavas": list(flavas)}
        for bank, flavas in music_flava.items()
    ]
    # BankSFX — we derive ALL_SFX_ITEMS at addon load from this, per user decision.
    db["BankSFX"] = {bank: list(sounds) for bank, sounds in sbk_sounds.items()}
    db["BankSFX_notes"] = (
        "The addon builds a flat enum (id, label, desc, index) at load time by "
        "iterating BankSFX. Label format: '[<BankTitle>] <sound>'. "
        "The 'common' bank is large (~300 sounds); preserve ordering within each bank."
    )

    # ── Crate types & pickups ───────────────────────────────────────────────
    db["CrateTypes"] = [
        {"id": t[0], "label": t[1]} for t in data["CRATE_ITEMS"]
    ]
    db["CratePickups"] = [
        {"id": p[0], "label": p[1], "engine_string": p[2],
         "icon": p[3], "supports_multi_amount": p[4]}
        for p in data["CRATE_PICKUP_ITEMS"]
    ]

    # ── Game tasks ──────────────────────────────────────────────────────────
    db["GameTasks"] = [{"id": t[0], "label": t[1]} for t in game_tasks_common]
    db["GameTasks_notes"] = (
        "Curated 'common' subset of Jak 1 game tasks. The engine supports many more "
        "via the (game-task <name>) enum; this list is the set exposed in the oracle/"
        "pontoon alt-task picker. Full enum lives in goal_src/jak1/engine/game/task/"
        "game-task.gc — expand later if needed."
    )

    # ── PAT collision enums ─────────────────────────────────────────────────
    db["PAT"] = {
        "surfaces": [{"id": s[0], "label": s[1], "value": s[3]} for s in data["pat_surfaces"]],
        "events":   [{"id": e[0], "label": e[1], "value": e[3]} for e in data["pat_events"]],
        "modes":    [{"id": m[0], "label": m[1], "value": m[3]} for m in data["pat_modes"]],
    }

    # ── Lump system ─────────────────────────────────────────────────────────
    db["LumpTypes"] = [
        {"id": t[0], "label": t[1], "description": t[2]}
        for t in data["LUMP_TYPE_ITEMS"]
    ]
    db["HardcodedLumpKeys"] = sorted(data["_LUMP_HARDCODED_KEYS"])
    db["HardcodedLumpKeys_notes"] = (
        "Keys the exporter always sets automatically. Manual lump rows targeting "
        "these emit a warning but aren't blocked — manual value takes priority."
    )

    # ── Aggro events ────────────────────────────────────────────────────────
    db["AggroEvents"] = [
        {"id": e[0], "label": e[1], "description": e[2]}
        for e in data["AGGRO_TRIGGER_EVENTS"]
    ]

    # ── Parents ─────────────────────────────────────────────────────────────
    db["Parents"] = PARENTS

    # ── Actors (the big one) ────────────────────────────────────────────────
    # Flatten the tuple-keyed fields dict into per-etype
    fields_by_etype: dict[str, list] = {}
    for k, fields in PER_ACTOR_FIELDS.items():
        etypes = (k,) if isinstance(k, str) else k
        for et in etypes:
            fields_by_etype.setdefault(et, []).extend(fields)

    actors = []
    lump_ref = data["LUMP_REFERENCE"]
    actor_link_defs = data["ACTOR_LINK_DEFS"]
    etype_tpages = data["ETYPE_TPAGES"]
    etype_code = data["ETYPE_CODE"]
    entity_wiki = data["ENTITY_WIKI"]

    for etype, info in data["ENTITY_DEFS"].items():
        a: dict = {
            "etype": etype,
            "label": info["label"],
            "category": info["cat"],
            "parent": parent_for(etype, info),
        }
        # Description from ENTITY_WIKI if present
        wiki = entity_wiki.get(etype)
        if wiki and wiki.get("desc"):
            a["description"] = wiki["desc"]

        # Asset references
        if info.get("ag"):          a["art_group"] = info["ag"]
        if info.get("tpage_group"): a["tpage_group"] = info["tpage_group"]
        if etype in etype_tpages:   a["tpages"] = list(etype_tpages[etype])
        if etype in etype_code:     a["code"] = dict(etype_code[etype])
        if info.get("glb"):         a["glb"] = info["glb"]

        # Behaviour flags (only non-default)
        if info.get("is_prop"):            a["is_prop"] = True
        if info.get("nav_safe") is False:  a["nav_safe"] = False

        # Runtime-required flags — top level, distinct from `links` (UI show/hide)
        if info.get("needs_path"):         a["needs_path"] = True
        if info.get("needs_pathb"):        a["needs_pathb"] = True
        if info.get("needs_sync"):         a["needs_sync"] = True
        if info.get("needs_notice_dist"):  a["needs_notice_dist"] = True

        # Links (UI-show booleans — derived from cat + ai_type + flags)
        links = links_for_actor(info)
        if links:
            a["links"] = links

        # Link slots (from ACTOR_LINK_DEFS — multi-slot reference links)
        if etype in actor_link_defs:
            slots = []
            for (lump_key, slot_idx, label, accepted, required) in actor_link_defs[etype]:
                slots.append({
                    "lump_key": lump_key,
                    "slot": slot_idx,
                    "label": label,
                    "accepts": list(accepted),
                    "required": required,
                })
            if slots:
                a["link_slots"] = slots

        # Lumps (from LUMP_REFERENCE — the full doc list for this actor)
        if etype in lump_ref:
            a["lumps"] = [
                {"key": k, "type": t, "description": d}
                for (k, t, d) in lump_ref[etype]
            ]

        # Fields (per-actor custom UI + export mapping)
        if etype in fields_by_etype:
            a["fields"] = fields_by_etype[etype]

        # Viewport display (color + shape for the empty's display)
        if "color" in info:
            a["color"] = list(info["color"])
        if "shape" in info:
            a["shape"] = info["shape"]

        # Vertex export exclusion
        if etype in data["_VERTEX_EXPORT_EXCLUDE"]:
            a["vertex_export"] = False

        actors.append(a)

    db["Actors"] = actors

    # ── Orphan actors (in ACTOR_LINK_DEFS or ENTITY_WIKI, not in ENTITY_DEFS) ─
    # These etypes are referenced at runtime (they're valid link targets or
    # have wiki docs) but never spawn via the main picker. Preserve them so
    # lookups don't fail; tag with "spawnable": false.
    entity_etypes = set(data["ENTITY_DEFS"].keys())
    link_orphans = set(actor_link_defs.keys()) - entity_etypes
    wiki_orphans = set(entity_wiki.keys()) - entity_etypes
    all_orphans = link_orphans | wiki_orphans
    orphan_entries: list[dict] = []
    for etype in sorted(all_orphans):
        entry: dict = {
            "etype": etype,
            "label": etype.replace("-", " ").title(),
            "category": "Hidden",
            "parent": "process-drawable",
            "spawnable": False,
        }
        if etype in entity_wiki and entity_wiki[etype].get("desc"):
            entry["description"] = entity_wiki[etype]["desc"]
        if etype in actor_link_defs:
            slots = []
            for (lump_key, slot_idx, label, accepted, required) in actor_link_defs[etype]:
                slots.append({
                    "lump_key": lump_key,
                    "slot": slot_idx,
                    "label": label,
                    "accepts": list(accepted),
                    "required": required,
                })
            if slots:
                entry["link_slots"] = slots
        if etype in lump_ref:
            entry["lumps"] = [
                {"key": k, "type": t, "description": d}
                for (k, t, d) in lump_ref[etype]
            ]
        orphan_entries.append(entry)
    db["OrphanEtypes"] = orphan_entries
    db["OrphanEtypes_notes"] = (
        "Etypes referenced by ACTOR_LINK_DEFS or ENTITY_WIKI that aren't in the "
        "main Actors list (non-spawnable link targets, wiki-only entries). "
        "Keep these so link resolution and docs lookups work. spawnable=False "
        "by default — they never appear in the spawn picker."
    )

    # ── AllSFX — full legacy ALL_SFX_ITEMS preserved verbatim ───────────────
    # Initial plan was to derive from BankSFX, but the old list has 577 sounds
    # not present in any SBK bank, plus bank-disambiguation suffixes like
    # `accordian-pump__jungle`. Preserve verbatim.
    db["AllSFX"] = [
        {"id": s[0], "label": s[1], "index": s[3]}
        for s in data["ALL_SFX_ITEMS"]
    ]
    db["AllSFX_notes"] = (
        "Full flat SFX enum. NOT derived from BankSFX — the two lists are "
        "overlapping but neither is a superset. Some IDs use `__<bank>` "
        "suffixes to disambiguate same-named sounds across banks. "
        "Both lists must be preserved."
    )

    # ── VertexExportTypes (mesh-only props, separate from spawnable Actors) ──
    # VERTEX_EXPORT_TYPES holds decorative mesh props that can be vertex-lit
    # exported but aren't part of the main spawn picker. Same field shape as
    # ENTITY_DEFS (many are just aliases for props already in Actors, repeated
    # here to appear in the vertex-export workflow).
    vx = data.get("VERTEX_EXPORT_TYPES", {})
    db["VertexExportTypes"] = []
    for etype, info in vx.items():
        entry: dict = {"etype": etype, "label": info.get("label", etype)}
        if info.get("cat"):   entry["category"] = info["cat"]
        if info.get("ag"):    entry["art_group"] = info["ag"]
        if info.get("glb"):   entry["glb"] = info["glb"]
        if "color" in info:   entry["color"] = list(info["color"])
        if "shape" in info:   entry["shape"] = info["shape"]
        db["VertexExportTypes"].append(entry)
    db["VertexExportTypes_notes"] = (
        "Mesh-only props usable by the vertex-lit export workflow. Some overlap "
        "with entries in Actors (same etype, repeated here); entries unique to "
        "this list (e.g. 'dark-plant', 'evilplant' — wait, those ARE in Actors…) "
        "are purely decorative and not spawnable via the normal picker. "
        "Note: etypes in VertexExportExcludedEtypes (top-level) cannot be "
        "vertex-exported regardless of whether they appear here."
    )
    db["VertexExportExcludedEtypes"] = sorted(data["_VERTEX_EXPORT_EXCLUDE"])

    # ── Non-actor object types (cameras, sound emitters, music zones, checkpoints) ──
    # From audit v2 §B.6
    db["ObjectTypes"] = [
        {
            "prefix": "CAMERA",
            "label": "Camera",
            "description": "Cutscene / level camera. Companion objects named "
                           "<CAMERA>_ALIGN and <CAMERA>_PIVOT drive standoff/orbit modes.",
            "fields": [
                {"key": "og_cam_mode", "label": "Mode", "type": "enum",
                 "default": "fixed",
                 "choices": [
                     {"value": "fixed",    "label": "Fixed"},
                     {"value": "standoff", "label": "Standoff (uses _ALIGN helper)"},
                     {"value": "orbit",    "label": "Orbit (uses _PIVOT helper)"},
                 ]},
                {"key": "og_cam_interp", "label": "Interp time (s)", "type": "float",
                 "default": 1.0,
                 "lump": {"key": "interpTime", "type": "float"}, "write_if": "always"},
                {"key": "og_cam_fov", "label": "FOV (°)", "type": "float",
                 "default": 0.0,
                 "lump": {"key": "fov", "type": "degrees"}, "write_if": "if_positive"},
                {"key": "og_cam_look_at", "label": "Look-at object", "type": "object_ref",
                 "default": "",
                 "lump": {"key": "interesting", "type": "vector3m"},
                 "write_if": "if_object_found"},
            ],
        },
        {
            "prefix": "AMBIENT",
            "variant": "sound_emitter",
            "label": "Sound Emitter",
            "description": "Looping or one-shot SFX point source. Set og_sound_name to "
                           "classify as a sound emitter (vs. music zone).",
            "fields": [
                {"key": "og_sound_name", "label": "Sound", "type": "enum",
                 "choices": "BankSFX",  # picker is bank-filtered
                 "lump": {"key": "effect-name", "type": "symbol"}, "write_if": "always"},
                {"key": "og_sound_mode", "label": "Mode", "type": "enum",
                 "default": "loop",
                 "choices": [
                     {"value": "loop",    "label": "Loop"},
                     {"value": "oneshot", "label": "One-shot interval"},
                 ]},
                {"key": "og_sound_radius", "label": "Radius (m)", "type": "float",
                 "default": 15.0},
                {"key": "og_cycle_min", "label": "Interval base (s)", "type": "float",
                 "default": 5.0, "visible_if": {"og_sound_mode": "oneshot"}},
                {"key": "og_cycle_rnd", "label": "Interval random (s)", "type": "float",
                 "default": 2.0, "visible_if": {"og_sound_mode": "oneshot"}},
            ],
        },
        {
            "prefix": "AMBIENT",
            "variant": "music_zone",
            "label": "Music Zone",
            "description": "Zone-based music override. Set og_music_bank to classify "
                           "as a music zone (vs. sound emitter).",
            "fields": [
                {"key": "og_music_bank", "label": "Bank", "type": "enum",
                 "choices": "SoundBanks",
                 "lump": {"key": "music", "type": "symbol"}, "write_if": "always"},
                {"key": "og_music_flava", "label": "Flava", "type": "enum",
                 "default": "default",
                 "choices": "MusicBanks_flavas_for_selected_bank",
                 "lump": {"key": "flava", "type": "float",
                          "format": "index_in_MUSIC_FLAVA_TABLE"},
                 "write_if": "always"},
                {"key": "og_music_priority", "label": "Priority", "type": "float",
                 "default": 10.0,
                 "lump": {"key": "priority", "type": "float"}, "write_if": "always"},
                {"key": "og_music_radius", "label": "Radius (m)", "type": "float",
                 "default": 40.0},
            ],
        },
        {
            "prefix": "CHECKPOINT",
            "label": "Checkpoint / Continue Point",
            "description": "Mid-level checkpoint / continue spawn location.",
            "fields": [
                {"key": "og_checkpoint_radius", "label": "Radius (m)", "type": "float",
                 "default": 3.0},
                {"key": "og_continue_name", "label": "Continue name", "type": "string",
                 "default": ""},
            ],
        },
    ]

    return db


# ═════════════════════════════════════════════════════════════════════════════
# STEP 7 — Serialize to JSONC with top-of-file and section comments
# ═════════════════════════════════════════════════════════════════════════════
HEADER = """\
// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                   JAK 1 LEVEL BUILDER — GAME DATABASE                     ║
// ║                                                                           ║
// ║ Single source of truth for all game-specific data consumed by the addon.  ║
// ║ At addon load time every UI list, enum, lump reference, and export rule   ║
// ║ is populated from this file.                                              ║
// ║                                                                           ║
// ║ Auto-generated by refactoring/build_database.py. Don't hand-edit during   ║
// ║ the migration window — edit the addon's data.py and re-run the builder.   ║
// ║ Post-migration (once the rewire lands), this file becomes the source and  ║
// ║ build_database.py gets deleted.                                           ║
// ╚═══════════════════════════════════════════════════════════════════════════╝
//
// SECTIONS (in order):
//   Engine                   — shared OpenGOAL constants (meter scale, subdir names)
//   Categories               — spawn-picker groupings + collection paths
//   Defaults                 — assets always loaded by the engine (skip injection)
//   Levels                   — per-level tpages, music flavas, SFX banks
//   Levels_notes             — followups tracked for a later pass
//   LevelCollectionSchema    — Blender-side level collection structure + defaults
//   TextureGroups            — texture-browser filter groups
//   SoundBanks               — level sound/music bank IDs
//   MusicBanks               — per-bank flava variants
//   BankSFX                  — SFX names per bank (flat enum derived at addon load)
//   BankSFX_notes            — derivation rules
//   CrateTypes               — crate material enum
//   CratePickups             — valid pickups inside a crate
//   GameTasks                — common game-task enum for the oracle/pontoon picker
//   GameTasks_notes          — source + expansion notes
//   PAT                      — collision surface/event/mode enums
//   LumpTypes                — res-lump value type registry
//   HardcodedLumpKeys        — lump keys the exporter always sets
//   HardcodedLumpKeys_notes  — manual-override behaviour
//   AggroEvents              — trigger events for enemy aggro scripting
//   Parents                  — minimal parent hierarchy (nav-enemy, process-drawable, …)
//   Actors                   — every spawnable entity with fields + lumps + links
//   OrphanEtypes             — non-spawnable etypes (link targets, wiki-only entries)
//   AllSFX                   — full flat SFX enum (preserved verbatim, legacy)
//   VertexExportTypes        — mesh-only props for vertex-lit export
//   VertexExportTypes_notes  — overlap + exclusion rules
//   VertexExportExcludedEtypes — etypes that cannot be vertex-exported
//   ObjectTypes              — non-actor placeables (cameras, sound emitters, checkpoints)

"""


def serialize_jsonc(db: dict) -> str:
    """Serialize the database dict as JSONC. Insert section headers as comments."""
    body = json.dumps(db, indent=2, ensure_ascii=False)
    lines = body.split("\n")
    out: list[str] = [HEADER.rstrip()]
    # First line of body is `{` — emit it.
    out.append(lines[0])
    # For every subsequent top-level key (exactly two leading spaces, `"Key":`),
    # emit a blank line + comment header before it.
    for line in lines[1:]:
        m = re.match(r'^  "([^"]+)":', line)
        if m:
            key = m.group(1)
            bar = "─" * max(1, 60 - len(key))
            out.append("")
            out.append(f"  // ── {key} {bar}")
        out.append(line)
    return "\n".join(out) + "\n"


# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════
def main() -> None:
    db = build_database()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(serialize_jsonc(db))
    # Stats
    n_actors = len(db["Actors"])
    n_fields = sum(len(a.get("fields", [])) for a in db["Actors"])
    n_lumps = sum(len(a.get("lumps", [])) for a in db["Actors"])
    n_links = sum(len(a.get("link_slots", [])) for a in db["Actors"])
    n_sfx = sum(len(v) for v in db["BankSFX"].values())
    print(f"Wrote {OUT}")
    print(f"  Actors: {n_actors}")
    print(f"  Per-actor fields: {n_fields}")
    print(f"  Per-actor lump entries: {n_lumps}")
    print(f"  Per-actor link slots: {n_links}")
    print(f"  BankSFX total (flat enum size): {n_sfx}")
    print(f"  File size: {OUT.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
