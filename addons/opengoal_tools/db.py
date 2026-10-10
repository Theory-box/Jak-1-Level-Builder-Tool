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
import os
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


# ── User override ───────────────────────────────────────────────────────────
# Preferences > "Database override" picks a .jsonc that replaces the bundled
# database (edit a copy without touching / reinstalling the addon). The path
# is kept in a small settings file in Blender's user config folder, because
# this module loads before the addon preferences exist.
def settings_file() -> Path | None:
    try:
        import bpy
        return Path(bpy.utils.user_resource("CONFIG")) / "opengoal_tools_settings.json"
    except Exception:
        return None


def read_settings() -> dict:
    f = settings_file()
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f and f.exists() else {}
    except Exception:
        return {}


def write_settings(**changes) -> None:
    f = settings_file()
    if not f:
        return
    s = read_settings()
    s.update(changes)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(s, indent=2), encoding="utf-8")


# A .blend's Project Folders can name its own database. The addon passes it
# here through this environment variable (set before reloading), because the
# scene can't be read while the addon is being enabled.
BLEND_DB_ENV = "OPENGOAL_TOOLS_DB"


def _abspath(p: str) -> Path:
    try:
        import bpy
        return Path(bpy.path.abspath(p))
    except Exception:
        return Path(p)


def override_path() -> Path | None:
    """Preferences override (settings file), or None."""
    p = str(read_settings().get("db_override_path", "") or "").strip()
    return _abspath(p) if p else None


def wanted_override() -> tuple[Path | None, str]:
    """(path, source) of the database that should be loaded: the .blend's
    (env var) first, then the preferences override, else (None, "bundled")."""
    env = os.environ.get(BLEND_DB_ENV, "").strip()
    if env:
        return Path(env), "blend"
    ov = override_path()
    if ov:
        return ov, "preferences"
    return None, "bundled"


def _bundled_db_path() -> Path:
    for p in _CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError(
        f"jak1_game_database.jsonc not found. Looked in:\n  "
        + "\n  ".join(str(p) for p in _CANDIDATES)
    )


# ── Load + parse (strip // line comments, parse JSON) ────────────────────────
_COMMENT_RE = re.compile(r'^\s*//.*$', re.MULTILINE)

# What was actually loaded (shown in the preferences) and, if the override
# could not be used, why — the bundled database is used instead so the addon
# still loads.
DB_PATH: Path | None = None
DB_WANTED: Path | None = None       # override that was asked for (even if it failed)
DB_SOURCE: str = "bundled"          # "blend" / "preferences" / "bundled"
DB_OVERRIDE_ERROR: str = ""


def _parse(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    # Strip line comments. The database uses only // line comments (not /* */),
    # and no string values contain `//` at line start — so a simple regex works.
    return json.loads(_COMMENT_RE.sub('', text))


def _load() -> dict:
    global DB_PATH, DB_WANTED, DB_SOURCE, DB_OVERRIDE_ERROR
    DB_OVERRIDE_ERROR = ""
    ov, source = wanted_override()
    DB_WANTED = ov
    if ov:
        try:
            data = _parse(ov)
            DB_PATH, DB_SOURCE = ov, source
            return data
        except FileNotFoundError:
            DB_OVERRIDE_ERROR = f"Override not found: {ov}"
        except Exception as e:
            DB_OVERRIDE_ERROR = f"Override failed to load ({type(e).__name__}: {e})"
        print(f"[OpenGOAL] {DB_OVERRIDE_ERROR} - using the bundled database")
    DB_PATH, DB_SOURCE = _bundled_db_path(), "bundled"
    return _parse(DB_PATH)


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


# COMPAT: accepts the old dict / extra_code formats (docs/backward-compat.md)
def code_files(rec: dict | None) -> list[str]:
    """The .o files an actor (or variant) brings into the level DGO, in load
    order. DB format: "code": "file.o" or "code": ["dep.o", ..., "file.o"].
    Files listed in Defaults > game_gd_files are skipped at export (always
    loaded), so vanilla GAME.CGO code is listed like any other.
    Older override databases still load: {"o": ..., "o_only": ...},
    {"in_game_cgo": true} (nothing to add) and a separate "extra_code" list
    (loaded before the actor's own file)."""
    if not rec:
        return []
    c = rec.get("code")
    if isinstance(c, str):
        files = [c]
    elif isinstance(c, list):
        files = [f for f in c if isinstance(f, str)]
    elif isinstance(c, dict):
        files = [] if c.get("in_game_cgo") or not c.get("o") else [c["o"]]
    else:
        files = []
    extra = rec.get("extra_code") or []
    return [f for f in list(extra) + files if f]


def all_actors_including_orphans() -> list[dict]:
    """Every actor-like record including non-spawnable orphans."""
    return DB["Actors"] + DB.get("OrphanEtypes", [])


def orphan_etypes() -> list[dict]:
    return DB.get("OrphanEtypes", [])


def all_sfx() -> list[dict]:
    return DB.get("AllSFX", [])


def find_parent(etype: str) -> dict | None:
    """A parent record: the Parents section first, then any actor/orphan
    (actors can be parents too: plat -> plat-eco, babak -> babak-with-cannon)."""
    for p in DB["Parents"]:
        if p["etype"] == etype:
            return p
    for p in DB["Actors"] + DB.get("OrphanEtypes", []):
        if p["etype"] == etype:
            return p
    return None


def parent_chain(etype: str) -> list[dict]:
    """Return the full parent chain for an etype, nearest first (root last),
    following the game's deftype tree through Parents and actors.
    Example: parent_chain('plat-eco') → [plat, baseplat, process-drawable]"""
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


# Field / panel lump types -> the custom lump row type the "+" button picks
# (LumpTypes ids). Anything else becomes plain-text.
_REF_ROW_TYPE = {
    "meters": "meters", "degrees": "degrees", "float": "float",
    "int": "int32", "int32": "int32", "uint32": "uint32", "mode": "int32", "bool": "int32",
    "enum-int32": "enum-int32", "enum-uint32": "enum-uint32", "enum": "enum-uint32",
    "symbol": "symbol", "symbol_literal": "symbol", "string": "string", "type": "type",
    "vector": "vector", "vector4m": "vector4m", "vector3m": "vector3m", "vector-vol": "vector-vol",
    "movie-pos": "movie-pos", "water-height": "water-height", "eco-info": "eco-info",
    "cell-info": "cell-info", "buzzer-info": "buzzer-info",
}


def lump_reference(etype: str) -> list[dict]:
    """Every lump the actor can export, read from its panels / fields / link
    slots (parents included), plus "lumps" entries the DB documents with no
    panel yet. [{key, type, row_type, desc, source}] — source is the record
    (the actor or a parent etype) the lump comes from; one entry per key."""
    actor = find_actor(etype)
    chain = list(reversed(parent_chain(etype))) + ([actor] if actor else [])
    panel_src, field_src, slot_src = {}, {}, {}
    for rec in chain:
        for e in _record_panels(rec):
            pid = e.get("panel")
            if not pid:
                continue
            panel_src.setdefault(pid, rec["etype"])
            for f in e.get("fields") or []:
                if f.get("key"):
                    field_src[(pid, f["key"])] = rec["etype"]
            for s in e.get("slots") or []:
                slot_src[s.get("lump_key")] = rec["etype"]
    out: dict = {}

    def add(key, ltype, desc, src):
        if key and key not in out:
            out[key] = {"key": key, "type": ltype, "row_type": _REF_ROW_TYPE.get(ltype, "plain-text"),
                        "desc": desc, "source": src}

    # Panels / fields with "export": false are still listed (the actor reads
    # the lump; the addon just doesn't write it), marked as such.
    for pid, p in actor_panels(etype).items():
        psrc = panel_src.get(pid, etype)
        off = "" if p["export"] else "  (not exported by default)"
        if pid == "path":
            for n in ["path"] + list(p["options"].get("paths", []) or []):
                add(n, "vector4m", f"Path panel: waypoints / curve ({n})" + off, psrc)
                add(n + "-k", "float", f"Path panel: curve knots for {n}" + off, psrc)
        elif pid == "nav-mesh":
            add("nav-mesh-sphere", "vector4m", "Nav-mesh panel: static nav sphere(s) 'x y z radius'"
                + (" — exported as the fallback when no navmesh is linked" if p["options"].get("fallback-sphere") else "") + off, psrc)
        elif pid == "volume":
            add("vol", "vector-vol", "Volume panel: planes of the linked VOL_ mesh" + off, psrc)
        elif pid == "scale":
            add("scale", "float", "Scale panel: the empty's scale" + off, psrc)
        elif pid == "fact-options":
            add("options", "enum-uint32", "Options panel: fact-options bits" + off, psrc)
        elif pid == "movie-pos":
            add("movie-pos", "movie-pos", "Movie Position panel: 'x y z angle' per position" + off, psrc)
        for f in p["fields"]:
            lp = f.get("lump") if isinstance(f.get("lump"), dict) else f.get("lump_bit")
            if isinstance(lp, dict) and lp.get("key"):
                label = f.get("label", f.get("key", ""))
                foff = off or ("  (not exported by default)" if f.get("export") is False else "")
                add(lp["key"], lp.get("type") or f.get("type", ""),
                    f"{(panel_type(pid) or {}).get('label', pid)}: {label}" + (f" — {f['note']}" if f.get("note") else "") + foff,
                    field_src.get((pid, f.get("key")), psrc))
    for s in link_slots(etype):
        add(s["lump_key"], "string", f"Entity link: {s.get('label', '')}", slot_src.get(s["lump_key"], etype))
    # documented lumps no panel produces yet (nearest record first)
    for rec in reversed(chain):
        for l in rec.get("lumps") or []:
            add(l.get("key"), l.get("type", ""), l.get("description", ""), rec["etype"])
    return list(out.values())


def inherited_link_descriptions(etype: str) -> dict:
    """Merge link_desc blocks from parents + actor (actor wins)."""
    result: dict = {}
    for p in reversed(parent_chain(etype)):
        result.update(p.get("link_desc", {}))
    actor = find_actor(etype)
    if actor:
        result.update(actor.get("link_desc", {}))
    return result


# ── Panels ──────────────────────────────────────────────────────────────────
# An actor (or a Parents entry) lists the UI panels it uses:
#   "panels": [{"panel": "<PanelTypes id>", "show-panel": true,
#               "fields": [{"key": ..., <only what differs>}, ...]}, ...]
# Panels come from the parent chain (root-first) and then the actor itself —
# never from the category. The same panel id from a nearer record overrides
# "show-panel" and merges its fields by key into the panel's standard fields
# (PanelTypes[id].fields). "custom-fields" holds fully written-out fields.
# "show-panel": false keeps a panel's fields exported but hides the panel;
# "show-field": false does the same for one field. "export": false (on a
# panel or a field) hides it AND stops it being exported.
# Any other key on a panel entry is a panel option, merged the same way
# (nearer record wins), e.g. path: "required", "linear-only", "paths".

def panel_types() -> list[dict]:
    return DB.get("PanelTypes", [])


def panel_type(pid: str) -> dict:
    for p in DB.get("PanelTypes", []):
        if p.get("id") == pid:
            return p
    return {}


# COMPAT: everything after the "panels" check reads pre-panel DB keys (docs/backward-compat.md)
def _record_panels(rec: dict) -> list[dict]:
    """A record's panels list. Older override databases (separate "fields" and
    "panel" keys) are read as the equivalent panels list."""
    if not rec:
        return []
    if "panels" in rec:
        return rec.get("panels") or []
    out = []
    if rec.get("panel"):
        out.append({"panel": rec["panel"], "show-panel": True})
    if rec.get("fields"):
        out.append({"panel": "custom-fields", "show-panel": not rec.get("panel"),
                    "fields": rec["fields"]})
    # old path/sync flags
    if rec.get("needs_path") or rec.get("needs_sync") or rec.get("nav_safe") is False:
        p = {"panel": "path", "show-panel": True}
        if rec.get("needs_path"):
            p["required"] = ["path", "pathb"] if rec.get("needs_pathb") else True
        if rec.get("path_linear_only"):
            p["linear-only"] = True
        if rec.get("paths"):
            p["paths"] = rec["paths"]
        out.append(p)
    if rec.get("needs_sync"):
        out.append({"panel": "sync", "show-panel": True})
    # old link / nav / volume / launcher / water flags
    if rec.get("link_slots"):
        out.append({"panel": "actor-link", "show-panel": True, "slots": rec["link_slots"]})
    is_nav_parent = rec.get("etype") == "nav-enemy"     # the Parents entry
    if rec.get("requires_navmesh") or rec.get("nav_safe") is False or is_nav_parent:
        nm = {"panel": "nav-mesh", "show-panel": True}
        if rec.get("nav_safe") is False:
            nm["fallback-sphere"] = True
        out.append(nm)
    if is_nav_parent:
        out.append({"panel": "aggro-trigger", "show-panel": True})
    if rec.get("need_vol"):
        out.append({"panel": "volume", "show-panel": True})
    if rec.get("is_launcher"):
        out.append({"panel": "launcher", "show-panel": True})
    if rec.get("is_water"):
        out.append({"panel": "water", "show-panel": True})
    if rec.get("category") in ("Enemies", "Bosses") and "panels" not in rec:
        out.append({"panel": "activation", "show-panel": True})
        out.append({"panel": "visibility", "show-panel": True})
    if rec.get("spawns_lurkers"):
        out.append({"panel": "spawner", "show-panel": True})
    if rec.get("needs_notice_dist"):
        out.append({"panel": "notice-dist", "show-panel": True})
    return out


def _merge_fields(base: list, over: list) -> list:
    """Fields merged by key: an override dict updates the field with the same
    key (only the keys it lists); new keys and const fields (no key) append."""
    out = [dict(f) for f in base]
    idx = {f.get("key"): i for i, f in enumerate(out) if f.get("key")}
    for f in over or []:
        k = f.get("key")
        if k and k in idx:
            out[idx[k]].update(f)
        else:
            if k:
                idx[k] = len(out)
            out.append(dict(f))
    return out


def _merge_slots(base, over) -> list:
    """Link slots merged by lump: a record that lists any slot for a lump
    replaces the inherited slots of that lump (so an actor can give
    alt-actor its own label / slots), and its slots come first."""
    over = [dict(s) for s in (over or [])]
    mine = {s.get("lump_key") for s in over}
    return over + [dict(s) for s in (base or []) if s.get("lump_key") not in mine]


def actor_panels(etype: str) -> dict:
    """Resolved panels for an etype, in first-seen order:
    {panel_id: {"show": bool, "fields": [...]}}."""
    out: dict = {}
    actor = find_actor(etype)
    for rec in list(reversed(parent_chain(etype))) + ([actor] if actor else []):
        for e in _record_panels(rec):
            pid = e.get("panel")
            if not pid:
                continue
            cur = out.get(pid)
            if cur is None:
                pt = panel_type(pid)
                cur = out[pid] = {"show": True, "export": True,
                                  "fields": [dict(f) for f in pt.get("fields", [])],
                                  "options": dict(pt.get("options", {}))}
            if "show-panel" in e:
                cur["show"] = bool(e["show-panel"])
            if "export" in e:
                cur["export"] = bool(e["export"])
            cur["fields"] = _merge_fields(cur["fields"], e.get("fields"))
            for k, v in e.items():
                if k == "slots":
                    cur["options"]["slots"] = _merge_slots(cur["options"].get("slots"), v)
                elif k not in ("panel", "show-panel", "export", "fields"):
                    cur["options"][k] = v
    for p in out.values():
        if not p["export"]:
            p["show"] = False
    return out


# COMPAT: old prop names via "legacy_key" (docs/backward-compat.md)
def legacy_keys() -> dict:
    """{field key: older prop key} from PanelTypes fields' "legacy_key" —
    props saved under the old name (e.g. og_sync_wrap -> og_fop_wrap_phase)
    are read through this so old .blend files keep their values."""
    out = {}
    for p in DB.get("PanelTypes", []):
        for f in p.get("fields", []):
            if f.get("key") and f.get("legacy_key"):
                out[f["key"]] = f["legacy_key"]
    return out


def prop_getter(obj):
    """get(key, default) for an object's props that also reads legacy keys."""
    leg = legacy_keys()
    def get(k, d=None):
        if k in obj.keys():
            return obj.get(k)
        old = leg.get(k)
        if old and old in obj.keys():
            return obj.get(old)
        return d
    return get


def fact_option_names() -> dict:
    """{bit value: fact-options name} from the fact-options PanelType
    (field key og_fop_has_power_cell -> has-power-cell)."""
    out = {}
    for f in panel_type("fact-options").get("fields", []):
        lb = f.get("lump_bit") or {}
        if lb.get("key") == "options" and f.get("key", "").startswith("og_fop_"):
            out[int(lb["bit_value"])] = f.get("enum") or f["key"][len("og_fop_"):].replace("_", "-")
    return out


def options_enum_lump(value):
    """["uint32", N] options bits -> ["enum-int32", "(fact-options a b)"], the
    readable form build_level accepts (see test-zone.jsonc). Unknown bits keep
    the number form."""
    try:
        n = int(value[1]) if isinstance(value, list) and len(value) == 2 else None
    except (TypeError, ValueError):
        n = None
    if n is None or n <= 0:
        return value
    names, rest = [], n
    for bit, name in sorted(fact_option_names().items()):
        if rest & bit:
            names.append(name); rest &= ~bit
    if rest or not names:
        return value
    return ["enum-int32", "(fact-options " + " ".join(names) + ")"]


def scale_lump(etype: str, scale_xyz):
    """'scale' lump for an actor from its Blender scale (x, y, z), or None.
    Game axes: (x, z, y) — Blender Z is up. Written when the "scale" panel is
    exported and the scale isn't 1, or always with the panel's "always"
    option. 4 floats [x, y, z, 1]: vector readers (citb-plat) use all of them,
    float readers (eco-door, orbit-plat, sharkey) the first."""
    if not panel_exports(etype, "scale"):
        return None
    sx, sy, sz = (round(float(v), 4) for v in scale_xyz)
    default = all(abs(v - 1.0) < 1e-4 for v in (sx, sy, sz))
    if default and not panel_option(etype, "scale", "always", False):
        return None
    return ["float", sx, sz, sy, 1.0]


def field_drivers(etype: str) -> list[tuple[dict, dict]]:
    """[(field, driver)] for every exported field of the actor's panels that
    has a "driver" block:
      "driver": {"var": "self" | <field key> | <data path>,
                 "expression": "40 if var < 0 else var",
                 "driven": "empty_display_size", "index": -1}
    The driver is added to the actor's empty when it's spawned."""
    return [(f, f["driver"]) for f in inherited_fields(etype) if isinstance(f.get("driver"), dict)]


def has_panel(etype: str, pid: str) -> bool:
    """True if the actor (or its parent chain) shows panel `pid`."""
    p = actor_panels(etype).get(pid)
    return bool(p and p["show"])


def panel_exports(etype: str, pid: str) -> bool:
    """True if the actor has panel `pid` (shown or hidden) and it isn't
    "export": false — i.e. its data goes into the level."""
    p = actor_panels(etype).get(pid)
    return bool(p and p["export"])


def panel_option(etype: str, pid: str, key: str, default=None):
    """A panel-level option (e.g. path "linear-only") or `default`."""
    p = actor_panels(etype).get(pid)
    return p["options"].get(key, default) if p and p["export"] else default


def _field_exports(f: dict) -> bool:
    return f.get("export") is not False


def panel_fields(etype: str, pid: str, visible_only: bool = False) -> list[dict]:
    """Fields of one panel (standard + overrides), without "export": false
    ones. visible_only also drops hidden panels and "show-field": false."""
    p = actor_panels(etype).get(pid)
    if not p or not p["export"] or (visible_only and not p["show"]):
        return []
    return [f for f in p["fields"] if _field_exports(f)
            and not (visible_only and f.get("show-field") is False)]


def inherited_fields(etype: str) -> list[dict]:
    """Every exported field of every panel an etype has (shown or hidden;
    parents first, nearer records overriding by key). Used by the
    schema-driven exporter (export/schema_emit.py) and default lookups."""
    out = []
    for pid in actor_panels(etype):
        out.extend(panel_fields(etype, pid))
    return out


def custom_fields(etype: str) -> list[dict]:
    """The "custom-fields" panel's exported fields (generic Actor Settings)."""
    return panel_fields(etype, "custom-fields")


# ═══════════════════════════════════════════════════════════════════════════
# Section accessors (stable names — prefer these over raw DB['...'])
# ═══════════════════════════════════════════════════════════════════════════
def engine() -> dict:
    return DB["Engine"]


def categories() -> list[dict]:
    return DB["Categories"]


def actor_tpages(etype: str) -> list:
    """Tpage .go files an actor needs in its level's DGO: the "tpages" its
    DB entry (or the nearest parent) lists, else none. On PC the actor
    models take their textures from the level's FR3 and particles use the
    always-loaded "effects" tpage, so a tpage is only listed where an actor
    was checked in game and needs one (they fill the level heap on load)."""
    for rec in [find_actor(etype) or {}] + parent_chain(etype):
        if "tpages" in rec:
            return list(rec["tpages"] or [])
    return []


def category(cat_id: str) -> dict:
    """Category record by id ({} when the category isn't listed)."""
    for c in DB.get("Categories", []):
        if c.get("id") == cat_id:
            return c
    return {}


_FALLBACK_COLOR = (1.0, 0.5, 0.1, 1.0)


def category_color(cat_id: str) -> tuple:
    """Viewport color (RGBA) of a category. Colors are per category only."""
    c = tuple(category(cat_id).get("color") or _FALLBACK_COLOR)
    return c + (1.0,) if len(c) == 3 else c


def actor_color(etype: str) -> tuple:
    """Viewport color for an actor: its category's color (set on the empty
    and on its preview mesh)."""
    return category_color((find_actor(etype) or {}).get("category", ""))


def rotation_offset(etype: str):
    """DB "rotation_offset" [x, y, z] in degrees (the actor's own, else the
    nearest parent's), or None: the empty's starting rotation when spawned
    (export takes the empty's rotation as it is). swingpole: 90° on X, the
    game reads the pole direction from its local Y."""
    for rec in [find_actor(etype) or {}] + parent_chain(etype):
        v = rec.get("rotation_offset")
        if v:
            return tuple(float(x) for x in v)
    return None


def rotation_lock(etype: str) -> tuple:
    """DB "rotation_lock" (e.g. ["x", "y"]: only turns around Z) — the
    actor's own, else the nearest parent's. Set as Blender's rotation locks
    on spawn, after the offset; users can unlock them."""
    for rec in [find_actor(etype) or {}] + parent_chain(etype):
        v = rec.get("rotation_lock")
        if v is not None:
            return tuple(a in [x.lower() for x in v] for a in "xyz")
    return (False, False, False)


def empty_size(etype: str):
    """DB empty display size in meters, or None when unset: the actor's
    "empty_size", else the nearest parent's, else its category's. When set
    it wins over fitting the empty to the preview mesh."""
    for rec in [find_actor(etype) or {}] + parent_chain(etype):
        if rec.get("empty_size") is not None:
            return float(rec["empty_size"])
    v = category((find_actor(etype) or {}).get("category", "")).get("empty_size")
    return float(v) if v is not None else None


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
    """The crate's variant choices (defined on the crate actor)."""
    return variant_choices("crate")


def crate_pickups() -> list[dict]:
    return DB["CratePickups"]


def game_tasks() -> list[dict]:
    return DB["GameTasks"]


def task_expression(get, key: str):
    """GOAL expression for a "task" field ("(game-task jungle-eggtop)"), or
    None for no task. "custom" reads <key>_custom: a task name (wrapped in
    (game-task ...)) or a full expression in parentheses."""
    v = get(key, "none") or "none"
    if v == "custom":
        v = str(get(key + "_custom", "") or "").strip()
        if not v:
            return None
        return v if v.startswith("(") else f"(game-task {v})"
    return None if v == "none" else f"(game-task {v})"


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


def cameras() -> dict:
    """Built-in camera entity settings: modes / fields / flags."""
    return DB.get("Cameras", {})


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
    """False when the nav-mesh panel asks for the "fallback-sphere" workaround
    (nav-enemies that idle without a real navmesh get nav-mesh-sphere)."""
    return not panel_option(etype, "nav-mesh", "fallback-sphere", False)


def nav_unsafe(etype: str) -> bool:
    """Convenience inverse of is_nav_safe (mirrors the old NAV_UNSAFE_TYPES set)."""
    return not is_nav_safe(etype)


def _path_required(etype: str) -> list[str]:
    req = panel_option(etype, "path", "required", False) if panel_exports(etype, "path") else False
    if req is True:
        return ["path"]
    return [r for r in req if isinstance(r, str)] if isinstance(req, list) else []


def needs_path(etype: str) -> bool:
    """Path panel marked "required" (the actor errors without its main path)."""
    return "path" in _path_required(etype)


def needs_pathb(etype: str) -> bool:
    """Path panel "required" lists "pathb" (swamp-bat)."""
    return "pathb" in _path_required(etype)


def path_linear_only(etype: str) -> bool:
    """Path panel "linear-only": path-control reader, ignores path-k."""
    return bool(panel_option(etype, "path", "linear-only", False))


def path_names(etype: str) -> list[str]:
    """Path panel "paths": lump names offered by Add Path (e.g. path, pathb)."""
    return list(panel_option(etype, "path", "paths", []) or [])


def needs_sync(etype: str) -> bool:
    """Actor has the "sync" panel (sync lump drives its path timing)."""
    return panel_exports(etype, "sync")


def needs_notice_dist(etype: str) -> bool:
    """"notice-dist" panel (plat-eco): reads a notice-distance lump."""
    return panel_exports(etype, "notice-dist")


def is_prop(etype: str) -> bool:
    a = find_actor(etype) or {}
    return bool(a.get("is_prop"))


def requires_navmesh_flag(etype: str) -> bool:
    """Actor has the nav-mesh panel (from its parent or its own entry)."""
    return panel_exports(etype, "nav-mesh")


def is_enemy(etype: str) -> bool:
    """fact-info-enemy readers (idle-distance): the "activation" panel.
    Never from the category."""
    return panel_exports(etype, "activation")


def is_platform(etype: str) -> bool:
    a = find_actor(etype) or {}
    return a.get("category") == "Platforms"


def is_launcher(etype: str) -> bool:
    """launcher / springbox — read spring-height (and launcher reads alt-vector).
    DB "launcher" panel."""
    return has_panel(etype, "launcher")


def spawns_lurkers(etype: str) -> bool:
    """Spawns child enemies (num-lurkers lump): the "spawner" panel."""
    return panel_exports(etype, "spawner")


def is_water(etype: str) -> bool:
    """Actor carries water attributes (water-height + attack-event). DB flag
    "water" panel (its standard fields are the water attributes)."""
    return panel_exports(etype, "water")


def needs_vol(etype: str) -> bool:
    """Actor gets its `vol` lump from a linked VOL_ mesh (convex, via
    _vol_planes) — the shared volume mechanism used by cameras/checkpoints.
    DB "volume" panel."""
    return panel_exports(etype, "volume")


def uses_navmesh(etype: str) -> bool:
    """Actor has the "nav-mesh" panel: on the nav-enemy parent, plus any actor
    that lists it itself (orbit-plat, square-platform, sunkenfisha)."""
    return panel_exports(etype, "nav-mesh")


def can_jump(etype: str) -> bool:
    """Nav-mesh panel "can-jump": true — a nav-enemy whose nav-enemy-info has
    a jump animation (jump-anim != -1), so it can follow cue-jump-to-point
    (battlecontroller spawn paths; nav-mesh jumps later). Read even when a
    pinned override stops the panel exporting."""
    p = actor_panels(etype).get("nav-mesh")
    return bool(p and p["options"].get("can-jump"))


def jumping_enemies() -> list[str]:
    """Every nav-enemy (child / sub-child of nav-enemy) tagged can-jump."""
    return [a["etype"] for a in actors()
            if can_jump(a["etype"]) and any(p.get("etype") == "nav-enemy" for p in parent_chain(a["etype"]))]


def battlecontroller_lurkers() -> list[str]:
    """Jumping enemies a battlecontroller can spawn: all but the ones marked
    "battlecontroller_lurker": false (no initialize-collision of their own,
    so nav-enemy-init-by-other crashes on them)."""
    return [et for et in jumping_enemies() if (find_actor(et) or {}).get("battlecontroller_lurker", True)]


def supports_aggro_trigger(etype: str) -> bool:
    """"aggro-trigger" panel: nav-enemies handle 'cue-chase / 'cue-patrol /
    'go-wait-for-cue (nav-enemy.gc). On the nav-enemy parent."""
    return has_panel(etype, "aggro-trigger")


def link_accepts(accepted, target_etype: str) -> bool:
    """True when `target_etype` fits a link slot's "accepts" list: "any"
    anywhere in the list, the etype itself, or any of its parent types
    (accepts ["basebutton"] also takes warp-gate-switch, a basebutton child)."""
    acc = list(accepted or [])
    if not acc or "any" in acc or target_etype in acc:
        return True
    return any(p.get("etype") in acc for p in parent_chain(target_etype))


def link_slot(etype: str, lump_key: str, slot: int) -> dict:
    """The slot dict ({} if none) — e.g. to read "allow-multiple"."""
    for s in link_slots(etype):
        if s.get("lump_key") == lump_key and s.get("slot", 0) == slot:
            return s
    return {}


def link_slots(etype: str) -> list[dict]:
    """Link slots (lump_key, slot, label, accepts, required): the "actor-link"
    panel's "slots", then those other panels bring (the path panel's
    path-actor), each lump once. None when actor-link doesn't export."""
    if not panel_exports(etype, "actor-link"):
        return []
    out = list(panel_option(etype, "actor-link", "slots", []) or [])
    for pid in actor_panels(etype):
        if pid != "actor-link":
            have = {s.get("lump_key") for s in out}
            out += [dict(s) for s in panel_option(etype, pid, "slots", []) or []
                    if s.get("lump_key") not in have]
    return out


def uses_waypoints(etype: str) -> bool:
    """True if this actor shows the "path" panel."""
    return has_panel(etype, "path")


# Membership sets (built once from the DB; mirror the legacy data.py constants).
def nav_unsafe_types() -> set[str]:
    return {a["etype"] for a in actors() if not is_nav_safe(a["etype"])}


def needs_path_types() -> set[str]:
    return {a["etype"] for a in actors() if needs_path(a["etype"])}


def needs_pathb_types() -> set[str]:
    return {a["etype"] for a in actors() if needs_pathb(a["etype"])}


def is_prop_types() -> set[str]:
    return {a["etype"] for a in actors() if a.get("is_prop")}


def launcher_types() -> set[str]:
    return {a["etype"] for a in actors() if is_launcher(a["etype"])}


def spawner_types() -> set[str]:
    return {a["etype"] for a in actors() if spawns_lurkers(a["etype"])}


# ── Trait fields (predicate-tagged field groups) ────────────────────────────
# Some fields belong to a *behaviour shared across many actors* rather than to
# one actor: every enemy reads idle-distance/vis-dist, every spawner reads
# num-lurkers, etc. There is no shared parent to hang these on, so the DB's
# "TraitFields" section maps a predicate name -> a fields[] list, and any actor
# for which that predicate is true inherits those fields. Set the flag/category
# on a new actor and it gets the behaviour (and its UI) with no duplication.
_TRAIT_PREDICATES = {
    "is_enemy":          is_enemy,
    "is_platform":       is_platform,
    "is_launcher":       is_launcher,
    "spawns_lurkers":    spawns_lurkers,
    "needs_notice_dist": needs_notice_dist,
    "is_water":          is_water,
    "needs_path":        needs_path,
    "needs_pathb":       needs_pathb,
    "is_prop":           is_prop,
}


# COMPAT: TraitFields is empty in the bundled DB (docs/backward-compat.md)
def trait_fields(etype: str) -> list[dict]:
    """Fields contributed by every behavioural predicate this actor matches
    (DB `TraitFields` section). Returns [] for actors matching nothing."""
    out = []
    for trait, flds in DB.get("TraitFields", {}).items():
        pred = _TRAIT_PREDICATES.get(trait)
        if pred and pred(etype):
            out.extend(flds)
    return out


def _field_is_output_only(f: dict) -> bool:
    """Const lumps have no editable prop — emit-only, never shown in the UI."""
    return f.get("type") == "const" or (f.get("lump") or {}).get("type") == "const"


def field_default(f: dict, etype: str = None):
    """Resolve a field's default value (honours default_per_etype)."""
    if etype and isinstance(f.get("default_per_etype"), dict):
        return f["default_per_etype"].get(etype, f.get("default"))
    return f.get("default")


def _resolve_choices(f: dict) -> list[dict]:
    """A field's choices as a list of dicts — resolving a named table string
    (e.g. "CrateTypes") through the DB, or returning an inline list."""
    ch = f.get("choices")
    if isinstance(ch, str):
        return DB.get(ch) or []
    return ch or []


def choices_table(name: str) -> list[dict] | None:
    """A top-level named choices table (e.g. "BridgeVariants") or None."""
    return DB.get(name)


def preview_offset(etype: str, prop_get) -> list:
    """Default preview-mesh offset in Blender metres [x, y, z]. A selected
    variant's `offset` overrides the actor's own `offset` (e.g. each bridge
    variant shifts its mesh back by half its length so the preview matches where
    the bridge spawns centred in-game). A per-object override is applied by the
    caller on top of this."""
    var = actor_variant(etype, prop_get)
    if var.get("offset"):
        return list(var["offset"])
    a = find_actor(etype) or {}
    return list(a.get("offset") or [0.0, 0.0, 0.0])


def actor_variant(etype: str, prop_get) -> dict:
    """The selected variant for an actor — the chosen entry of a field marked
    `"variant": true`, whose choices may carry `glb` / `art_group` / `code`
    overrides. Returns {} if the actor has no variant field. `prop_get(key,
    default)` reads the selected value off the object."""
    for f in inherited_fields(etype):
        if not f.get("variant"):
            continue
        sel = prop_get(f.get("key"), field_default(f, etype))
        for c in _resolve_choices(f):
            if sel in (c.get("id"), c.get("value")):
                return c
    return {}


def variant_field(etype: str) -> dict | None:
    """The field marked `"variant": true` for an actor, or None."""
    for f in inherited_fields(etype):
        if f.get("variant"):
            return f
    return None


def actor_has_variant(etype: str) -> bool:
    return variant_field(etype) is not None


def variant_choices(etype: str) -> list[dict]:
    """Resolved choices for an actor's variant field (or [])."""
    f = variant_field(etype)
    return _resolve_choices(f) if f else []


_SHARED_PANELS = ("custom-fields", "path", "sync", "actor-link", "nav-mesh",
                  "aggro-trigger", "volume", "water", "activation", "visibility",
                  "spawner", "notice-dist", "fact-options", "scale", "movie-pos", "game-task")


def generic_panels(etype: str) -> list[tuple[str, dict]]:
    """Shown panels whose PanelType says "draw": "generic" (no hand-written
    Blender panel): drawn as boxes in Actor Settings. [(pid, panel_type)]"""
    return [(pid, panel_type(pid)) for pid, p in actor_panels(etype).items()
            if p["show"] and panel_type(pid).get("draw") == "generic"]


def actor_panel(etype: str) -> str | None:
    """The first shown bespoke panel id of an actor (not the shared ones in
    _SHARED_PANELS), or None. Panels poll with has_panel()."""
    for pid, p in actor_panels(etype).items():
        if pid not in _SHARED_PANELS and p["show"]:
            return pid
    return None


def ui_fields(etype: str) -> list[dict]:
    """Fields to render in the generic actor panel: own/inherited fields plus
    trait fields, deduped by key (own wins), excluding output-only const lumps."""
    own = [f for f in custom_fields(etype) if not _field_is_output_only(f)]
    seen = {f.get("key") for f in own}
    return own + [f for f in trait_fields(etype)
                  if not _field_is_output_only(f) and f.get("key") not in seen]
