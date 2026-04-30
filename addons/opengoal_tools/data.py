# ---------------------------------------------------------------------------
# data.py — OpenGOAL Level Tools
# COMPATIBILITY LAYER. All legacy symbols (ENTITY_DEFS, LUMP_REFERENCE,
# LEVEL_BANKS, ALL_SFX_ITEMS, etc.) are now derived at import time from
# db.py, which reads jak1_game_database.jsonc.
#
# This keeps existing `from .data import X` statements working unchanged while
# the actual game data lives in the database file. Post-migration, callers
# should import from `.db` directly and this module gets deleted.
#
# No bpy imports here — safe to import anywhere.
# ---------------------------------------------------------------------------
from __future__ import annotations

from . import db as _db


# ═══════════════════════════════════════════════════════════════════════════
# PAT ENUMS
# ═══════════════════════════════════════════════════════════════════════════
_pat = _db.pat()
pat_surfaces = [(s["id"], s["label"], "", s["value"]) for s in _pat["surfaces"]]
pat_events   = [(e["id"], e["label"], "", e["value"]) for e in _pat["events"]]
pat_modes    = [(m["id"], m["label"], "", m["value"]) for m in _pat["modes"]]


# ═══════════════════════════════════════════════════════════════════════════
# ENTITY_DEFS — reconstructed from db.actors()
# ═══════════════════════════════════════════════════════════════════════════
def _entity_info_from_actor(a: dict) -> dict:
    """Reverse-build the legacy ENTITY_DEFS dict from one Actor record."""
    info: dict = {"label": a["label"], "cat": a["category"]}
    if a.get("art_group"):    info["ag"] = a["art_group"]
    if a.get("tpage_group"):  info["tpage_group"] = a["tpage_group"]
    if a.get("glb"):          info["glb"] = a["glb"]
    if "color" in a:          info["color"] = tuple(a["color"])
    if "shape" in a:          info["shape"] = a["shape"]
    if a.get("is_prop"):      info["is_prop"] = True
    info["nav_safe"] = a.get("nav_safe", True)
    parent = a.get("parent", "prop")
    info["ai_type"] = "prop" if parent == "eco-collectable" else parent
    # Runtime-required flags — read from top-level actor record, NOT from links
    # (links are UI-availability; top-level is the old-schema runtime flag).
    info["needs_path"]  = bool(a.get("needs_path"))
    info["needs_pathb"] = bool(a.get("needs_pathb"))
    info["needs_sync"]  = bool(a.get("needs_sync"))
    info["needs_notice_dist"] = bool(a.get("needs_notice_dist"))
    info["requires_navmesh"]  = bool(a.get("requires_navmesh"))
    return info


ENTITY_DEFS: dict[str, dict] = {
    a["etype"]: _entity_info_from_actor(a) for a in _db.actors()
}


# ═══════════════════════════════════════════════════════════════════════════
# CRATE_ITEMS + CRATE_PICKUP_ITEMS
# ═══════════════════════════════════════════════════════════════════════════
CRATE_ITEMS = [(t["id"], t["label"], "", 0, i) for i, t in enumerate(_db.crate_types())]
CRATE_PICKUP_ITEMS = [
    (p["id"], p["label"], p["engine_string"], p["icon"], p["supports_multi_amount"])
    for p in _db.crate_pickups()
]


# ═══════════════════════════════════════════════════════════════════════════
# ENTITY_WIKI — images were dropped per user decision; descriptions retained.
# Includes orphan wiki entries (etypes with wiki text but not in ENTITY_DEFS).
# ═══════════════════════════════════════════════════════════════════════════
ENTITY_WIKI: dict[str, dict] = {}
for _a in _db.actors():
    if _a.get("description"):
        ENTITY_WIKI[_a["etype"]] = {"img": None, "desc": _a["description"]}
for _a in _db.orphan_etypes():
    if _a.get("description"):
        ENTITY_WIKI[_a["etype"]] = {"img": None, "desc": _a["description"]}


# ═══════════════════════════════════════════════════════════════════════════
# ENUM BUILDERS (unchanged from the old data.py — read from ENTITY_DEFS above)
# ═══════════════════════════════════════════════════════════════════════════
def _build_entity_enum():
    TPAGE_GROUP_ORDER = ["Beach", "Jungle", "Swamp", "Snow", "Sunken", "Ogre",
                         "Misty", "Maincave", "Robocave", "Rolling", "Lavatube", "Firecanyon",
                         "Village1", "Village2", "Village3", "Training", "Final"]
    cats: dict = {}
    for etype, info in ENTITY_DEFS.items():
        cat = info["cat"]
        cats.setdefault(cat, []).append((etype, info))
    order = ["Enemies", "Bosses", "NPCs", "Pickups", "Platforms",
             "Interactive Objects", "Obstacles", "Buttons and Doors", "Visuals",
             # Legacy aliases — kept so actors that didn't receive a new
             # category yet (or future additions using old names) still show.
             "Props", "Objects", "Debug"]
    items, i = [], 0
    for cat in order:
        if cat not in cats:
            continue
        if cat == "Enemies":
            by_group: dict = {}
            for etype, info in cats[cat]:
                g = info.get("tpage_group", "Other")
                by_group.setdefault(g, []).append((etype, info))
            for group in TPAGE_GROUP_ORDER:
                if group not in by_group:
                    continue
                for etype, info in sorted(by_group[group], key=lambda x: x[1]["label"]):
                    nav_safe   = info.get("nav_safe", True)
                    needs_path = info.get("needs_path", False)
                    warn = "" if nav_safe else " [nav]"
                    if needs_path:
                        warn += " [path]"
                    tip = ENTITY_WIKI.get(etype, {}).get("desc", "") or etype
                    items.append((etype, f"[{group}] {info['label']}{warn}", tip, i))
                    i += 1
        else:
            for etype, info in sorted(cats[cat], key=lambda x: x[1]["label"]):
                nav_safe   = info.get("nav_safe", True)
                needs_path = info.get("needs_path", False)
                warn = "" if nav_safe else " [nav]"
                if needs_path:
                    warn += " [path]"
                tip = ENTITY_WIKI.get(etype, {}).get("desc", "") or etype
                items.append((etype, f"[{cat}] {info['label']}{warn}", tip, i))
                i += 1
    return items


ENTITY_ENUM_ITEMS = _build_entity_enum()


def _build_cat_enum(cats):
    """Return sorted enum items for the given category set."""
    items = []
    for i, (etype, info) in enumerate(
        sorted(
            [(e, inf) for e, inf in ENTITY_DEFS.items() if inf.get("cat") in cats],
            key=lambda x: (x[1].get("tpage_group", ""), x[1]["label"])
        )
    ):
        warn = ""
        if not info.get("nav_safe", True): warn += " [nav]"
        if info.get("needs_path"):         warn += " [path]"
        group = info.get("tpage_group", "")
        prefix = f"[{group}] " if group else f"[{info.get('cat','')}] "
        tip = ENTITY_WIKI.get(etype, {}).get("desc", "") or etype
        items.append((etype, f"{prefix}{info['label']}{warn}", tip, i))
    return items


ENEMY_ENUM_ITEMS        = _build_cat_enum({"Enemies", "Bosses"})
INTERACTIVE_ENUM_ITEMS  = _build_cat_enum({"Interactive Objects", "Debug"})
NPC_ENUM_ITEMS          = _build_cat_enum({"NPCs"})
PICKUP_ENUM_ITEMS       = _build_cat_enum({"Pickups"})
OBSTACLE_ENUM_ITEMS     = _build_cat_enum({"Obstacles"})
BUTTONDOOR_ENUM_ITEMS   = _build_cat_enum({"Buttons and Doors"})
VISUALS_ENUM_ITEMS      = _build_cat_enum({"Visuals"})
# Alias kept for backward compatibility
PROP_ENUM_ITEMS         = INTERACTIVE_ENUM_ITEMS


# ═══════════════════════════════════════════════════════════════════════════
# Tpage filter
# ═══════════════════════════════════════════════════════════════════════════
GLOBAL_TPAGE_GROUPS = set(_db.defaults().get("global_tpage_groups", []))


def _build_tpage_filter_items():
    seen = set()
    for info in ENTITY_DEFS.values():
        g = info.get("tpage_group")
        if g and g not in GLOBAL_TPAGE_GROUPS:
            seen.add(g)
    order = ["Beach", "Jungle", "Swamp", "Snow", "Sunken", "Ogre",
             "Misty", "Maincave", "Robocave", "Rolling", "Lavatube",
             "Firecanyon", "Final"]
    ordered = [g for g in order if g in seen]
    ordered += sorted(seen - set(ordered))
    items = [("NONE", "— None —", "No filter")]
    for i, g in enumerate(ordered, 1):
        items.append((g, g, f"Show only {g} tpage group", i))
    return items


TPAGE_FILTER_ITEMS = _build_tpage_filter_items()


def _tpage_filter_passes(etype, g1, g2, enabled):
    if not enabled:
        return True
    info  = ENTITY_DEFS.get(etype, {})
    grp   = info.get("tpage_group")
    if grp is None:
        return True
    if grp in GLOBAL_TPAGE_GROUPS:
        return True
    allowed = {g for g in (g1, g2) if g != "NONE"}
    if not allowed:
        return True
    return grp in allowed


def _make_filtered_enum(base_items, cats):
    def _callback(self, context):
        if context is None:
            return base_items
        try:
            props   = context.scene.og_props
            enabled = props.tpage_limit_enabled
            g1      = props.tpage_filter_1
            g2      = props.tpage_filter_2
        except Exception:
            return base_items
        if not enabled:
            return base_items
        allowed = {g for g in (g1, g2) if g != "NONE"}
        if not allowed:
            return base_items
        result = []
        for item in base_items:
            etype = item[0]
            info  = ENTITY_DEFS.get(etype, {})
            grp   = info.get("tpage_group")
            if grp is None or grp in GLOBAL_TPAGE_GROUPS:
                result.append(item)
            elif grp in allowed:
                result.append(item)
        return result if result else [("__none__", "— No matches —", "", 0)]
    return _callback


_enemy_enum_cb        = _make_filtered_enum(ENEMY_ENUM_ITEMS,        {"Enemies", "Bosses"})
_interactive_enum_cb  = _make_filtered_enum(INTERACTIVE_ENUM_ITEMS,  {"Interactive Objects", "Debug"})
_npc_enum_cb          = _make_filtered_enum(NPC_ENUM_ITEMS,          {"NPCs"})
_pickup_enum_cb       = _make_filtered_enum(PICKUP_ENUM_ITEMS,       {"Pickups"})
_obstacle_enum_cb     = _make_filtered_enum(OBSTACLE_ENUM_ITEMS,     {"Obstacles"})
_buttondoor_enum_cb   = _make_filtered_enum(BUTTONDOOR_ENUM_ITEMS,   {"Buttons and Doors"})
_visuals_enum_cb      = _make_filtered_enum(VISUALS_ENUM_ITEMS,      {"Visuals"})
# Alias
_prop_enum_cb         = _interactive_enum_cb


# ═══════════════════════════════════════════════════════════════════════════
# Search results enum
# ═══════════════════════════════════════════════════════════════════════════
_search_enum_cache: dict = {"key": None, "items": [("__empty__", "Type to search…", "", 0)]}


def _search_results_cb(self, context):
    if context is None:
        return _search_enum_cache["items"]
    try:
        props   = context.scene.og_props
        query   = props.entity_search.strip().lower()
        enabled = props.tpage_limit_enabled
        g1      = props.tpage_filter_1
        g2      = props.tpage_filter_2
    except Exception:
        return _search_enum_cache["items"]

    key = (query, enabled, g1, g2)
    if key == _search_enum_cache["key"]:
        return _search_enum_cache["items"]

    if not query:
        items = [("__empty__", "Type to search…", "", 0)]
    else:
        allowed = None
        if enabled:
            allowed = {g for g in (g1, g2) if g != "NONE"} or None

        matches = []
        for etype, info in ENTITY_DEFS.items():
            lbl = info["label"]
            if query not in lbl.lower() and query not in etype.lower():
                continue
            grp = info.get("tpage_group")
            if allowed is not None and grp is not None and grp not in GLOBAL_TPAGE_GROUPS:
                if grp not in allowed:
                    continue
            matches.append((etype, info))
        matches.sort(key=lambda x: x[1]["label"].lower())

        if matches:
            items = [
                (etype, f"{info['label']}  [{info.get('cat','')}]",
                 ENTITY_WIKI.get(etype, {}).get("desc", "") or etype, i)
                for i, (etype, info) in enumerate(matches)
            ]
        else:
            items = [("__empty__", "No results found", "", 0)]

    _search_enum_cache["key"]   = key
    _search_enum_cache["items"] = items
    return items


# ═══════════════════════════════════════════════════════════════════════════
# Vertex-export whitelist
# ═══════════════════════════════════════════════════════════════════════════
_VERTEX_EXPORT_EXCLUDE = set(_db.vertex_export_excluded_etypes())

VERTEX_EXPORT_TYPES = {
    etype: info
    for etype, info in ENTITY_DEFS.items()
    if (
        info.get("cat") in ("Pickups", "Props", "Objects")
        and etype not in _VERTEX_EXPORT_EXCLUDE
        and (info.get("is_prop", False) or info.get("cat") == "Pickups")
    )
}


# Platform-only enum for the Platforms panel spawn dropdown
PLATFORM_ENUM_ITEMS = [
    (etype, info["label"], info.get("label", etype), i)
    for i, (etype, info) in enumerate(
        sorted(
            [(e, inf) for e, inf in ENTITY_DEFS.items() if inf.get("cat") == "Platforms"],
            key=lambda x: x[1]["label"]
        )
    )
]
_platform_enum_cb = _make_filtered_enum(PLATFORM_ENUM_ITEMS, {"Platforms"})


# ═══════════════════════════════════════════════════════════════════════════
# Derived lookup sets
# ═══════════════════════════════════════════════════════════════════════════
NAV_UNSAFE_TYPES  = {e for e, info in ENTITY_DEFS.items() if not info.get("nav_safe", True)}
NEEDS_PATH_TYPES  = {e for e, info in ENTITY_DEFS.items() if info.get("needs_path", False)}
NEEDS_PATHB_TYPES = {e for e, info in ENTITY_DEFS.items() if info.get("needs_pathb", False)}
IS_PROP_TYPES     = {e for e, info in ENTITY_DEFS.items() if info.get("is_prop", False)}
ETYPE_AG          = {e: [info["ag"]] for e, info in ENTITY_DEFS.items() if info.get("ag")}


# ═══════════════════════════════════════════════════════════════════════════
# ETYPE_CODE + ETYPE_TPAGES (direct pass-through from Actors[].code / .tpages)
# ═══════════════════════════════════════════════════════════════════════════
ETYPE_CODE: dict[str, dict] = {
    a["etype"]: dict(a["code"]) for a in _db.actors() if a.get("code")
}

ETYPE_TPAGES: dict[str, list] = {
    a["etype"]: list(a["tpages"]) for a in _db.actors() if a.get("tpages")
}


# ═══════════════════════════════════════════════════════════════════════════
# Per-level tpage arrays (legacy: BEACH_TPAGES, JUNGLE_TPAGES, …)
# ═══════════════════════════════════════════════════════════════════════════
def _level_tpages(name: str) -> list:
    lvl = _db.level(name)
    return list(lvl["tpages"]) if lvl else []


BEACH_TPAGES     = _level_tpages("beach")
JUNGLE_TPAGES    = _level_tpages("jungle")
JUNGLEB_TPAGES   = _level_tpages("jungleb")
SWAMP_TPAGES     = _level_tpages("swamp")
SNOW_TPAGES      = _level_tpages("snow")
SUNKEN_TPAGES    = _level_tpages("sunken")
SUB_TPAGES       = _level_tpages("sub")
CAVE_TPAGES      = _level_tpages("maincave")
ROBOCAVE_TPAGES  = _level_tpages("robocave")
DARK_TPAGES      = _level_tpages("darkcave")
OGRE_TPAGES      = _level_tpages("ogre")
MISTY_TPAGES     = _level_tpages("misty")
LAVATUBE_TPAGES  = _level_tpages("lavatube")
FIRECANYON_TPAGES= _level_tpages("firecanyon")
ROLLING_TPAGES   = _level_tpages("rolling")
TRAINING_TPAGES  = _level_tpages("training")
FINALBOSS_TPAGES = _level_tpages("finalboss")
CITADEL_TPAGES   = _level_tpages("citadel")
VILLAGE1_TPAGES  = _level_tpages("village1")
VILLAGE2_TPAGES  = _level_tpages("village2")
VILLAGE3_TPAGES  = _level_tpages("village3")


# ═══════════════════════════════════════════════════════════════════════════
# Music + audio
# ═══════════════════════════════════════════════════════════════════════════
MUSIC_FLAVA_TABLE: dict[str, list] = _db.music_flava_table()


def _music_flava_items_cb(self, context):
    bank = getattr(self, "og_music_amb_bank", "none") if self else "none"
    flavas = MUSIC_FLAVA_TABLE.get(bank, ["default"])
    return [(f, f, "", i) for i, f in enumerate(flavas)]


def needed_tpages(actors):
    """Return de-duplicated ordered list of tpage .go files needed for placed entities."""
    seen, r = set(), []
    for a in actors:
        for tp in ETYPE_TPAGES.get(a["etype"], []):
            if tp not in seen:
                seen.add(tp)
                r.append(tp)
    return r


LEVEL_BANKS = [(b["id"], b["label"], "", i) for i, b in enumerate(_db.sound_banks())]

SBK_SOUNDS: dict[str, list] = _db.bank_sfx()


# ─── Mood / lighting ──────────────────────────────────────────────────────
# 21 stock mood-context globals available in jak-project. The selected ID
# is written to level-info.gc as `:mood '*ID-mood*` and `:mood-func
# 'update-mood-FUNC` (FUNC defaults to ID; see MOOD_FUNC_OVERRIDES below).
# Source: knowledge-base/research/opengoal/lighting-system.md "Per-Level Mood
# Callbacks" table.
MOOD_LEVELS = [
    ("training",   "Training",          "Training course mood",                              0),
    ("village1",   "Village 1 (Sandover)", "Sandover Village — bright, warm, daytime cycle",  1),
    ("beach",      "Beach (Sentinel)",  "Sentinel Beach — shares update-mood-village1 callback", 2),
    ("jungle",     "Jungle (Forbidden)", "Forbidden Jungle",                                 3),
    ("jungleb",    "Jungle B",          "Jungle B (alternate)",                              4),
    ("misty",      "Misty Island",      "Misty Island — overcast, low sun-fade",             5),
    ("firecanyon", "Fire Canyon",       "Fire Canyon — perpetual orange daytime",            6),
    ("village2",   "Village 2 (Rock)",  "Rock Village",                                      7),
    ("swamp",      "Swamp",             "Boggy Swamp — pitch-dependent fog override",        8),
    ("sunken",     "Sunken (Lost Precursor City)", "Lost Precursor City — underwater caustics", 9),
    ("rolling",    "Rolling Hills",     "Precursor Basin",                                  10),
    ("ogre",       "Ogre (Mountain Pass)", "Mountain Pass",                                 11),
    ("village3",   "Village 3 (Volcanic Crater)", "Volcanic Crater village",                12),
    ("snow",       "Snow (Mountain)",   "Snowy Mountain — toggles weather via *weather-off*", 13),
    ("maincave",   "Main Cave",         "Spider Cave — single-slot cave lighting",          14),
    ("darkcave",   "Dark Cave",         "Dark Cave — single-slot cave lighting",            15),
    ("robocave",   "Robo Cave",         "Robot Cave — single-slot cave lighting",           16),
    ("lavatube",   "Lava Tube",         "Lava Tube — animated lava glow effects",           17),
    ("citadel",    "Citadel",           "Gol & Maia's Citadel",                             18),
    ("finalboss",  "Final Boss",        "Final Boss arena",                                 19),
    ("default",    "Default (fallback)", "Generic fallback — uses village1 fog/light/sun tables", 20),
]

# Most levels' mood-func name matches their mood ID. Beach is the only stock
# exception: it uses *beach-mood* tables but update-mood-village1 as the
# callback. Source: jak-project engine/level/level-info.gc.
MOOD_FUNC_OVERRIDES: dict[str, str] = {
    "beach": "village1",
}


# ALL_SFX_ITEMS — preserved verbatim from DB.AllSFX (not derived — see audit v2
# addendum §C.Q3 + the rebuild notes: BankSFX is NOT a superset of the legacy
# flat list, so derivation would lose ~577 entries).
ALL_SFX_ITEMS = [
    (s["id"], s["label"], "", s["index"]) for s in _db.all_sfx()
]


# ═══════════════════════════════════════════════════════════════════════════
# LUMP_REFERENCE + UNIVERSAL_LUMPS
# ═══════════════════════════════════════════════════════════════════════════
def _tuples_from_lumps(lumps_list) -> list:
    return [(l["key"], l["type"], l.get("description", "")) for l in lumps_list]


LUMP_REFERENCE: dict[str, list] = {}
for _actor in _db.actors():
    _et = _actor["etype"]
    LUMP_REFERENCE[_et] = _tuples_from_lumps(_actor.get("lumps", []))

_nav_enemy_parent = _db.find_parent("nav-enemy")
LUMP_REFERENCE["_enemy"] = (
    _tuples_from_lumps(_nav_enemy_parent["lumps"]) if _nav_enemy_parent else []
)

_pd_parent = _db.find_parent("process-drawable")
UNIVERSAL_LUMPS: list = (
    _tuples_from_lumps(_pd_parent["lumps"]) if _pd_parent else []
)


def _lump_ref_for_etype(etype):
    """Return (universal_lumps, actor_lumps) for a given etype."""
    actor_entries = list(LUMP_REFERENCE.get(etype, []))
    einfo = ENTITY_DEFS.get(etype, {})
    if einfo.get("cat") in ("Enemies", "Bosses"):
        actor_entries = list(LUMP_REFERENCE.get("_enemy", [])) + actor_entries
    return UNIVERSAL_LUMPS, actor_entries


# ═══════════════════════════════════════════════════════════════════════════
# ACTOR_LINK_DEFS — reconstruct legacy shape from Actors[].link_slots
# ═══════════════════════════════════════════════════════════════════════════
ACTOR_LINK_DEFS: dict[str, list] = {}
for _actor in _db.all_actors_including_orphans():
    _slots = _actor.get("link_slots")
    if not _slots:
        continue
    ACTOR_LINK_DEFS[_actor["etype"]] = [
        (s["lump_key"], s["slot"], s["label"], s["accepts"], s["required"])
        for s in _slots
    ]


def _actor_link_slots(etype):
    return ACTOR_LINK_DEFS.get(etype, [])


def _actor_has_links(etype):
    return bool(_actor_link_slots(etype))


def _actor_links(obj):
    return getattr(obj, "og_actor_links", None)


def _actor_get_link(obj, lump_key, slot_index):
    links = _actor_links(obj)
    if not links:
        return None
    for entry in links:
        if entry.lump_key == lump_key and entry.slot_index == slot_index:
            return entry
    return None


def _actor_set_link(obj, lump_key, slot_index, target_name):
    links = _actor_links(obj)
    if links is None:
        return
    for entry in links:
        if entry.lump_key == lump_key and entry.slot_index == slot_index:
            entry.target_name = target_name
            return
    entry = links.add()
    entry.lump_key    = lump_key
    entry.slot_index  = slot_index
    entry.target_name = target_name


def _actor_remove_link(obj, lump_key, slot_index):
    links = _actor_links(obj)
    if links is None:
        return False
    for i, entry in enumerate(links):
        if entry.lump_key == lump_key and entry.slot_index == slot_index:
            links.remove(i)
            return True
    return False


def _build_actor_link_lumps(obj, etype):
    """Build dict of lump_key → ["string", name0, name1, ...] for all set links."""
    slots = _actor_link_slots(etype)
    if not slots:
        return {}

    from collections import defaultdict
    by_key = defaultdict(dict)
    for (lkey, sidx, _label, _accepted, _required) in slots:
        by_key[lkey]

    links = _actor_links(obj)
    if links:
        for entry in links:
            if entry.target_name and entry.lump_key in by_key:
                raw = entry.target_name
                if raw.startswith("ACTOR_"):
                    raw = raw[6:]
                    raw = raw.replace("_", "-", 1)
                by_key[entry.lump_key][entry.slot_index] = raw

    result = {}
    for lkey, slot_map in by_key.items():
        if not slot_map:
            continue
        max_idx = max(slot_map.keys())
        names = []
        for i in range(max_idx + 1):
            if i in slot_map:
                names.append(slot_map[i])
        if names:
            result[lkey] = ["string"] + names
    return result


# ═══════════════════════════════════════════════════════════════════════════
# LUMP ROW SYSTEM — type registry + parser
# ═══════════════════════════════════════════════════════════════════════════
LUMP_TYPE_ITEMS = [
    (t["id"], t["label"], t["description"]) for t in _db.lump_types()
]

_LUMP_HARDCODED_KEYS = frozenset(_db.hardcoded_lump_keys())


def _parse_lump_row(key, ltype, value_str):
    """Parse an OGLumpRow into a JSONC lump value, or return None on error."""
    s = value_str.strip()
    if not s:
        return None, "empty value"
    if not key.strip():
        return None, "empty key"

    try:
        if ltype in ("symbol", "string", "type", "enum-int32", "enum-uint32",
                     "cell-info"):
            return [ltype, s], None

        if ltype == "buzzer-info":
            parts = s.split()
            if len(parts) == 1:
                return ["buzzer-info", parts[0], 1], None
            return ["buzzer-info", parts[0], int(parts[1])], None

        if ltype == "eco-info":
            s_stripped = s.strip()
            if ")" in s_stripped:
                paren_end = s_stripped.index(")") + 1
                pickup_type = s_stripped[:paren_end].strip()
                remainder = s_stripped[paren_end:].strip()
                if not remainder:
                    return None, "eco-info needs '(pickup-type ...) amount'"
                return ["eco-info", pickup_type, int(remainder)], None
            else:
                parts = s_stripped.split()
                if len(parts) < 2:
                    return None, "eco-info needs 'pickup-type amount'"
                return ["eco-info", parts[0], int(parts[1])], None

        if ltype in ("meters", "degrees"):
            return [ltype, float(s)], None

        if ltype == "float":
            nums = [float(x) for x in s.split()]
            return ["float"] + nums, None

        if ltype == "int32":
            nums = [int(x) for x in s.split()]
            return ["int32"] + nums, None

        if ltype == "uint32":
            nums = [int(x) for x in s.split()]
            return ["uint32"] + nums, None

        if ltype == "vector3m":
            nums = [float(x) for x in s.split()]
            if len(nums) != 3:
                return None, f"vector3m needs 3 values, got {len(nums)}"
            return ["vector3m", nums], None

        if ltype in ("vector4m", "vector", "movie-pos", "vector-vol"):
            nums = [float(x) for x in s.split()]
            if len(nums) != 4:
                return None, f"{ltype} needs 4 values, got {len(nums)}"
            return [ltype, nums], None

        if ltype == "water-height":
            parts = s.split()
            if len(parts) < 4:
                return None, "water-height needs at least 4 values"
            return ["water-height"] + [float(p) if i != 3 else p
                                       for i, p in enumerate(parts)], None

    except (ValueError, IndexError) as e:
        return None, str(e)

    return None, f"unknown type '{ltype}'"


# ═══════════════════════════════════════════════════════════════════════════
# Aggro trigger events
# ═══════════════════════════════════════════════════════════════════════════
AGGRO_TRIGGER_EVENTS = [
    (e["id"], e["label"], e["description"]) for e in _db.aggro_events()
]

AGGRO_EVENT_ENUM_ITEMS = [(n, lbl, desc) for n, lbl, desc in AGGRO_TRIGGER_EVENTS]


def _aggro_event_id(name):
    for i, (n, _, _) in enumerate(AGGRO_TRIGGER_EVENTS):
        if n == name:
            return i
    return 0


def _is_custom_type(etype):
    """Return True if etype is not a known ENTITY_DEFS entry."""
    return etype not in ENTITY_DEFS
