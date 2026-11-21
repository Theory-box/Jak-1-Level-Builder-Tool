# ───────────────────────────────────────────────────────────────────────
# export/paths.py — OpenGOAL Level Tools
#
# File-path helpers + log wrapper.
# Everything here reads the addon's preferences to resolve where the target jak-project tree lives.
# ───────────────────────────────────────────────────────────────────────

from __future__ import annotations

from ..collections import clean_level_name
import bpy, os, re, json, math, mathutils
from pathlib import Path
from ..collections import (
    _get_level_prop, _level_objects,
    _active_level_col, _classify_object, _col_path_for_entity,
    _ensure_sub_collection, _recursive_col_objects,
    _COL_PATH_WAYPOINTS, _COL_PATH_NAVMESHES,
)
from ..collections import _active_level_col


# Cross-module imports (siblings in the export package)


def _data_root():
    from .. import paths_core as _pc
    return _pc.data_root()

def _data():
    from .. import paths_core as _pc
    return _pc.data()

def _levels_dir(): return _data() / "custom_assets" / "jak1" / "levels"

def _goal_src():   return _data() / "goal_src" / "jak1"

def _level_info(): return _goal_src() / "engine" / "level" / "level-info.gc"

def _load_boundary_data(): return _goal_src() / "engine" / "level" / "load-boundary-data.gc"

def _game_gp():    return _goal_src() / "game.gp"

def _ldir(name):   return _levels_dir() / name

def _entity_gc():  return _goal_src() / "engine" / "entity" / "entity.gc"

def _lname(ctx):
    col = _active_level_col(ctx.scene)
    if col is not None:
        return clean_level_name(col.get("og_level_name", ""))
    return ctx.scene.og_props.level_name.strip().lower().replace(" ","-")

def _nick(n):      return n.replace("-","")[:3].lower()

def _iso(n):       return n.replace("-","").upper()[:8]

def log(m):        print(f"[OpenGOAL] {m}")
