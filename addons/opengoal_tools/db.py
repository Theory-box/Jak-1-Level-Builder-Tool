# ---------------------------------------------------------------------------
# db.py — OpenGOAL Level Tools
# Game database loader. Reads jak1_game_database.jsonc and exposes the parsed
# structure plus a small set of accessors. No bpy imports — safe to import
# anywhere.
#
# This module is the single point of contact with the on-disk database file.
# Everything else in the addon that needs game data should either:
#   (a) import from .data (compatibility layer — preserves old names), or
#   (b) import DB / find_actor / find_parent from here (new, idiomatic).
#
# During the migration window (the window we're currently in), data.py is a
# thin shim built on top of this module. Post-migration, data.py gets deleted
# and all callers move to (b).
# ---------------------------------------------------------------------------
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any

# ── Path resolution ─────────────────────────────────────────────────────────
# The database lives alongside this file when the addon is installed. During
# dev we also support loading from ../../refactoring/ (the canonical source
# until rewire is complete), so editing the refactoring copy updates the addon
# live without needing to copy.
_HERE = Path(__file__).resolve().parent
_CANDIDATES = [
    _HERE / "jak1_game_database.jsonc",                          # install location
    _HERE.parent.parent / "refactoring" / "jak1_game_database.jsonc",  # dev location
]


def _resolve_db_path() -> Path:
    for p in _CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError(
        f"jak1_game_database.jsonc not found. Looked in:\n  "
        + "\n  ".join(str(p) for p in _CANDIDATES)
    )


# ── Load + parse (strip // line comments, parse JSON) ────────────────────────
_COMMENT_RE = re.compile(r'^\s*//.*$', re.MULTILINE)


def _load() -> dict:
    path = _resolve_db_path()
    text = path.read_text(encoding="utf-8")
    # Strip line comments. The database uses only // line comments (not /* */),
    # and no string values contain `//` at line start — so a simple regex works.
    stripped = _COMMENT_RE.sub('', text)
    return json.loads(stripped)


# ── Module-level cache ──────────────────────────────────────────────────────
# Loaded once at import time. Callers that want a fresh read (e.g. a
# 'Reload Database' operator) can call reload().
DB: dict = _load()


def reload() -> dict:
    """Re-read the database from disk. Returns the new DB dict.
    Primarily for dev workflows — the addon rebinds its derived tables lazily."""
    global DB
    DB = _load()
    return DB


# ═══════════════════════════════════════════════════════════════════════════
# Lookups — use these in preference to DB['Actors'][idx] etc.
# ═══════════════════════════════════════════════════════════════════════════
def actors() -> list[dict]:
    return DB["Actors"]


def parents() -> list[dict]:
    return DB["Parents"]


def object_types() -> list[dict]:
    return DB["ObjectTypes"]


def vertex_export_types() -> list[dict]:
    return DB["VertexExportTypes"]


def find_actor(etype: str) -> dict | None:
    """Return the actor record for an etype, or None if not found.
    Looks in Actors first, then OrphanEtypes (non-spawnable link targets)."""
    for a in DB["Actors"]:
        if a["etype"] == etype:
            return a
    for a in DB.get("OrphanEtypes", []):
        if a["etype"] == etype:
            return a
    return None


def all_actors_including_orphans() -> list[dict]:
    """Every actor-like record including non-spawnable orphans."""
    return DB["Actors"] + DB.get("OrphanEtypes", [])


def orphan_etypes() -> list[dict]:
    return DB.get("OrphanEtypes", [])


def all_sfx() -> list[dict]:
    return DB.get("AllSFX", [])


def find_parent(etype: str) -> dict | None:
    for p in DB["Parents"]:
        if p["etype"] == etype:
            return p
    return None


def parent_chain(etype: str) -> list[dict]:
    """Return the full parent chain for an etype, root-last.
    Example: parent_chain('babak') → [nav-enemy_dict, process-drawable_dict]"""
    chain: list[dict] = []
    actor = find_actor(etype)
    current = actor.get("parent") if actor else None
    seen: set[str] = set()
    while current and current not in seen:
        seen.add(current)
        p = find_parent(current)
        if p is None:
            break
        chain.append(p)
        current = p.get("parent")
    return chain


def inherited_links(etype: str) -> dict:
    """Merge an actor's explicit links with every parent's link defaults.
    Later entries (actor's own) override earlier ones (parent)."""
    result: dict = {}
    for p in reversed(parent_chain(etype)):  # root-first
        result.update(p.get("links", {}))
    actor = find_actor(etype)
    if actor:
        result.update(actor.get("links", {}))
    return result


def inherited_lumps(etype: str) -> list[dict]:
    """Return the combined lump reference list for an etype: parent lumps
    (root-first) then the actor's own lumps.  Matches the old
    _lump_ref_for_etype() semantics."""
    out: list[dict] = []
    for p in reversed(parent_chain(etype)):  # root-first
        out.extend(p.get("lumps", []))
    actor = find_actor(etype)
    if actor:
        out.extend(actor.get("lumps", []))
    return out


def inherited_link_descriptions(etype: str) -> dict:
    """Merge link_desc blocks from parents + actor (actor wins)."""
    result: dict = {}
    for p in reversed(parent_chain(etype)):
        result.update(p.get("link_desc", {}))
    actor = find_actor(etype)
    if actor:
        result.update(actor.get("link_desc", {}))
    return result


def inherited_fields(etype: str) -> list[dict]:
    """Combined export-schema fields[] for an etype: parent fields (root-first)
    then the actor's own, with the actor (or a nearer ancestor) overriding any
    inherited field that targets the same `key`. Const fields (no `key`) are
    always kept. Used by the schema-driven exporter (export/schema_emit.py)."""
    by_key: dict = {}
    order: list = []
    def _add(flds):
        for f in flds:
            k = f.get("key")
            if not k:                      # const field: keep, never dedupe
                k = ("__const__", id(f))
            if k not in by_key:
                order.append(k)
            by_key[k] = f
    for p in reversed(parent_chain(etype)):   # root-first
        _add(p.get("fields", []))
    actor = find_actor(etype)
    if actor:
        _add(actor.get("fields", []))
    return [by_key[k] for k in order]


def schema_export_enabled(etype: str) -> bool:
    """True if the actor or any ancestor is flagged `schema_export` — so a parent
    can switch on schema export for a whole family (e.g. enemy defaults)."""
    actor = find_actor(etype)
    if actor and actor.get("schema_export"):
        return True
    return any(p.get("schema_export") for p in parent_chain(etype))


# ═══════════════════════════════════════════════════════════════════════════
# Section accessors (stable names — prefer these over raw DB['...'])
# ═══════════════════════════════════════════════════════════════════════════
def engine() -> dict:
    return DB["Engine"]


def categories() -> list[dict]:
    return DB["Categories"]


def levels() -> list[dict]:
    return DB["Levels"]


def level(name: str) -> dict | None:
    for lvl in DB["Levels"]:
        if lvl["name"] == name:
            return lvl
    return None


def sound_banks() -> list[dict]:
    return DB["SoundBanks"]


def music_flava_table() -> dict[str, list[str]]:
    return {mb["bank"]: mb["flavas"] for mb in DB["MusicBanks"]}


def bank_sfx() -> dict[str, list[str]]:
    return DB["BankSFX"]


def crate_types() -> list[dict]:
    return DB["CrateTypes"]


def crate_pickups() -> list[dict]:
    return DB["CratePickups"]


def game_tasks() -> list[dict]:
    return DB["GameTasks"]


def pat() -> dict:
    return DB["PAT"]


def lump_types() -> list[dict]:
    return DB["LumpTypes"]


def hardcoded_lump_keys() -> list[str]:
    return DB["HardcodedLumpKeys"]


def aggro_events() -> list[dict]:
    return DB["AggroEvents"]


def defaults() -> dict:
    return DB["Defaults"]


def level_collection_schema() -> dict:
    return DB["LevelCollectionSchema"]


def texture_groups() -> list[dict]:
    return DB["TextureGroups"]


def vertex_export_excluded_etypes() -> list[str]:
    return DB["VertexExportExcludedEtypes"]


# ── Actor trait layer ───────────────────────────────────────────────────────
# Single source of truth for per-actor behavioural traits, read straight from
# the DB records. Previously these were derived in data.py (compat layer) and,
# for launcher/spawner, hardcoded as literal sets in export/predicates.py.
# Setting the flag on a DB entry is now all that's needed to give an actor the
# trait — no code edit. Predicates read via ai_type (derived from `parent`) or a
# top-level boolean flag on the actor record.

def ai_type(etype: str) -> str:
    """The actor's AI type. Derived from `parent`, except eco-collectable
    pickups which are treated as 'prop' (matches the legacy ENTITY_DEFS rule)."""
    a = find_actor(etype) or {}
    parent = a.get("parent", "prop")
    return "prop" if parent == "eco-collectable" else parent


def is_nav_safe(etype: str) -> bool:
    a = find_actor(etype) or {}
    return bool(a.get("nav_safe", True))


def needs_path(etype: str) -> bool:
    a = find_actor(etype) or {}
    return bool(a.get("needs_path"))


def needs_pathb(etype: str) -> bool:
    a = find_actor(etype) or {}
    return bool(a.get("needs_pathb"))


def needs_sync(etype: str) -> bool:
    a = find_actor(etype) or {}
    return bool(a.get("needs_sync"))


def needs_notice_dist(etype: str) -> bool:
    """Enemy variants that read a notice-distance lump on construction."""
    a = find_actor(etype) or {}
    return bool(a.get("needs_notice_dist"))


def is_prop(etype: str) -> bool:
    a = find_actor(etype) or {}
    return bool(a.get("is_prop"))


def requires_navmesh_flag(etype: str) -> bool:
    a = find_actor(etype) or {}
    return bool(a.get("requires_navmesh"))


def is_enemy(etype: str) -> bool:
    """Enemies and bosses inherit fact-info-enemy (idle-distance, vis-dist)."""
    a = find_actor(etype) or {}
    return a.get("category") in ("Enemies", "Bosses")


def is_platform(etype: str) -> bool:
    a = find_actor(etype) or {}
    return a.get("category") == "Platforms"


def is_launcher(etype: str) -> bool:
    """launcher / springbox — read spring-height (and launcher reads alt-vector).
    DB flag `is_launcher: true`."""
    a = find_actor(etype) or {}
    return bool(a.get("is_launcher"))


def spawns_lurkers(etype: str) -> bool:
    """Spawns child enemies (num-lurkers lump). DB flag `spawns_lurkers: true`."""
    a = find_actor(etype) or {}
    return bool(a.get("spawns_lurkers"))


def uses_navmesh(etype: str) -> bool:
    """nav-enemy subclasses, plus actors flagged requires_navmesh."""
    return ai_type(etype) == "nav-enemy" or requires_navmesh_flag(etype)


def uses_waypoints(etype: str) -> bool:
    """True if this actor can use waypoints (patrol path or sync-driven path)."""
    return (not is_nav_safe(etype)
            or needs_path(etype) or needs_pathb(etype) or needs_sync(etype))


# Membership sets (built once from the DB; mirror the legacy data.py constants).
def nav_unsafe_types() -> set[str]:
    return {a["etype"] for a in actors() if not a.get("nav_safe", True)}


def needs_path_types() -> set[str]:
    return {a["etype"] for a in actors() if a.get("needs_path")}


def needs_pathb_types() -> set[str]:
    return {a["etype"] for a in actors() if a.get("needs_pathb")}


def is_prop_types() -> set[str]:
    return {a["etype"] for a in actors() if a.get("is_prop")}


def launcher_types() -> set[str]:
    return {a["etype"] for a in actors() if a.get("is_launcher")}


def spawner_types() -> set[str]:
    return {a["etype"] for a in actors() if a.get("spawns_lurkers")}
