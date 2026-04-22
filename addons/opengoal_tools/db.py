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
