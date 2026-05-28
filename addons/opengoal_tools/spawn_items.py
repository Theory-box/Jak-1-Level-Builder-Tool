# ---------------------------------------------------------------------------
# spawn_items.py — OpenGOAL Level Tools
#
# Unified spawnable index — single source of truth for what can be placed
# via the Spawn panel.
#
# Items come from two sources:
#   - ENTITY_DEFS (entities defined in jak1_game_database.jsonc)
#   - Hard-coded synthetic items (player spawn, checkpoint, camera, etc.)
#
# The index (dict keyed by spawn_id) is built once at addon register and
# cached at module level. The Spawn panel's UIList reads from a per-scene
# CollectionProperty (OGSpawnListRow) whose spawn_id values reference this
# dict, allowing draw_item / filter_items to look up full SpawnItem metadata
# without storing it on every row.
# ---------------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import bpy
from bpy.app.handlers import persistent

from .data import ENTITY_DEFS, ENTITY_WIKI, NAV_UNSAFE_TYPES


# ---------------------------------------------------------------------------
# Tile categories — the 15 tiles shown in the picker grid (order matters)
# ---------------------------------------------------------------------------
TILE_CATEGORIES = (
    "Enemies",
    "Platforms",
    "Interactive Objects",
    "Obstacles",
    "Buttons and Doors",
    "Visuals",
    "NPCs",
    "Pickups",
    "Audio",
    "Volumes",
    "Triggers",
    "Level Flow",
    "Cameras",
    "Custom Types",
    "Favorites",
)

# DB category (ENTITY_DEFS info["cat"]) → tile category
DB_CAT_TO_TILE = {
    "Enemies":             "Enemies",
    "Bosses":              "Enemies",
    "Platforms":           "Platforms",
    "Interactive Objects": "Interactive Objects",
    "Debug":               "Interactive Objects",
    "Obstacles":           "Obstacles",
    "Buttons and Doors":   "Buttons and Doors",
    "Visuals":             "Visuals",
    "NPCs":                "NPCs",
    "Pickups":             "Pickups",
}

# Tile category → BoolProperty attribute name on OGProperties
CATEGORY_TO_PROP = {
    "Enemies":             "cat_enemies",
    "Platforms":           "cat_platforms",
    "Interactive Objects": "cat_interactive",
    "Obstacles":           "cat_obstacles",
    "Buttons and Doors":   "cat_buttons_doors",
    "Visuals":             "cat_visuals",
    "NPCs":                "cat_npcs",
    "Pickups":             "cat_pickups",
    "Audio":               "cat_audio",
    "Volumes":             "cat_volumes",
    "Triggers":            "cat_triggers",
    "Level Flow":          "cat_flow",
    "Cameras":             "cat_cameras",
    "Custom Types":        "cat_custom",
    "Favorites":           "cat_favorites",
}

# Tile category → Blender icon shown on the tile button
CATEGORY_ICONS = {
    "Enemies":             "MOD_ARMATURE",
    "Platforms":           "MESH_PLANE",
    "Interactive Objects": "PACKAGE",
    "Obstacles":           "MOD_TRIANGULATE",
    "Buttons and Doors":   "EVENT_RETURN",
    "Visuals":             "BRUSH_DATA",
    "NPCs":                "USER",
    "Pickups":             "OUTLINER_OB_LIGHT",
    "Audio":               "OUTLINER_OB_SPEAKER",
    "Volumes":             "MOD_FLUIDSIM",
    "Triggers":            "MESH_CUBE",
    "Level Flow":          "PLAY",
    "Cameras":             "CAMERA_DATA",
    "Custom Types":        "SCRIPT",
    "Favorites":           "SOLO_ON",
}


# ---------------------------------------------------------------------------
# SpawnItem — one placeable thing
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SpawnItem:
    """A single placeable item in the unified picker.

    For entity items (sourced from ENTITY_DEFS) the etype is set; for
    synthetic items (player spawn, checkpoint, etc.) it's None.

    pre_spawn_fields is a tuple of field IDs the dynamic settings area
    should render between the list and the spawn button. Each field ID
    maps to a draw function in panels/spawn.py.

    op_kwargs is a tuple of (key, value) pairs passed to the underlying
    operator. Used to pass e.g. source_prop="entity_type" to og.spawn_entity.
    """
    spawn_id: str
    label: str
    category: str
    art_group: Optional[str] = None
    tpage_group: Optional[str] = None
    description: str = ""
    operator: str = "og.spawn_entity"
    op_kwargs: tuple = ()
    pre_spawn_fields: tuple = ()
    needs_target_sel: bool = False
    icon: str = "EMPTY_DATA"
    etype: Optional[str] = None


# ---------------------------------------------------------------------------
# Synthetic items — not derived from ENTITY_DEFS
# ---------------------------------------------------------------------------
_SYNTHETIC_ITEMS: tuple[SpawnItem, ...] = (
    SpawnItem(
        spawn_id="special:player_spawn",
        label="Player spawn",
        category="Level Flow",
        description="Spawn point where the player appears when the level loads "
                    "or after death.",
        operator="og.spawn_player",
        icon="EMPTY_ARROWS",
    ),
    SpawnItem(
        spawn_id="special:checkpoint",
        label="Checkpoint",
        category="Level Flow",
        description="Mid-level continue point. Player respawns here after "
                    "death until the next checkpoint is reached.",
        operator="og.spawn_checkpoint",
        icon="EMPTY_SINGLE_ARROW",
    ),
    SpawnItem(
        spawn_id="special:load_boundary",
        label="Load Boundary",
        category="Level Flow",
        description="A plane the player/camera crosses to load, display, or vis "
                    "levels (or set a checkpoint). Draw an edge/polyline for a "
                    "vertical wall, or a flat face with the Closed flag for an "
                    "area. Configure forward/backward commands in Object Settings.",
        operator="og.spawn_load_boundary",
        icon="MOD_EDGESPLIT",
    ),
    SpawnItem(
        spawn_id="special:camera",
        label="Camera",
        category="Cameras",
        description="A standalone camera placed at the 3D cursor. After "
                    "spawn, configure mode / FOV / look-at and link to a "
                    "trigger volume via the Object Settings panel.\n"
                    "\n"
                    "Tip: to add a camera tied to a SPAWN_/CHECKPOINT_ "
                    "respawn point, select that empty first and use the "
                    "'Add Camera' button under Object Settings.",
        operator="og.spawn_camera",
        icon="CAMERA_DATA",
    ),
    SpawnItem(
        spawn_id="special:trigger_volume",
        label="Trigger volume",
        category="Triggers",
        description="A box mesh that fires when the player enters its "
                    "bounds. After spawn, scale it to cover the area you "
                    "want, then link it to a target (camera, checkpoint, "
                    "enemy) via the Object Settings panel.",
        operator="og.spawn_volume",
        icon="MESH_CUBE",
    ),
    SpawnItem(
        spawn_id="special:water_volume",
        label="Water volume",
        category="Volumes",
        description="Mesh volume that flags areas as water — affects swim/wade "
                    "behaviour. Scale to cover the water area; surface height "
                    "is set per-object after spawn.",
        operator="og.add_water_volume",
        icon="MOD_FLUIDSIM",
    ),
    SpawnItem(
        spawn_id="special:music_zone",
        label="Music zone",
        category="Audio",
        description="Ambient music trigger. Uses the bank / flava / priority / "
                    "radius fields as defaults.",
        operator="og.add_music_zone",
        pre_spawn_fields=("music_bank", "music_flava", "music_priority",
                          "music_radius"),
        icon="PLAY_SOUND",
    ),
    SpawnItem(
        spawn_id="special:sound_emitter",
        label="Sound emitter",
        category="Audio",
        description="Point sound source. Pick a sound + default radius below; "
                    "an emitter is added at the 3D cursor.",
        operator="og.add_sound_emitter",
        pre_spawn_fields=("sfx_sound", "ambient_radius"),
        icon="OUTLINER_OB_SPEAKER",
    ),
    SpawnItem(
        spawn_id="special:custom_type",
        label="Custom type",
        category="Custom Types",
        description="Custom GOAL deftype. Enter the deftype name (must match "
                    "obs.gc exactly). After spawn, write the type + states in "
                    "a GOAL code block via the Object Settings panel.",
        operator="og.spawn_custom_type",
        pre_spawn_fields=("custom_name",),
        icon="SCRIPT",
    ),
)


# ---------------------------------------------------------------------------
# Index construction
# ---------------------------------------------------------------------------
def _icon_for_shape(shape: str) -> str:
    """Map ENTITY_DEFS info["shape"] to a Blender icon name."""
    return {
        "CUBE":       "MESH_CUBE",
        "SPHERE":     "MESH_UVSPHERE",
        "CONE":       "MESH_CONE",
        "PLAIN_AXES": "EMPTY_AXIS",
    }.get(shape, "EMPTY_DATA")


def build_spawn_index() -> dict[str, SpawnItem]:
    """Build the full spawn index. Called once at addon register.

    Returns a dict keyed by spawn_id. Insertion order: entity items first
    (ENTITY_DEFS iteration order), then synthetic items.
    """
    idx: dict[str, SpawnItem] = {}

    for etype, info in ENTITY_DEFS.items():
        db_cat = info.get("cat")
        if not db_cat:
            continue
        tile = DB_CAT_TO_TILE.get(db_cat)
        if not tile:
            continue

        pre_fields: list[str] = []
        if etype == "crate":
            pre_fields.append("crate_type")
        if etype in NAV_UNSAFE_TYPES:
            pre_fields.append("nav_radius")

        idx[f"entity:{etype}"] = SpawnItem(
            spawn_id=f"entity:{etype}",
            label=info.get("label", etype),
            category=tile,
            art_group=info.get("ag"),
            tpage_group=info.get("tpage_group"),
            description=ENTITY_WIKI.get(etype, {}).get("desc", "") or "",
            operator="og.spawn_entity",
            op_kwargs=(("source_prop", "entity_type"),),
            pre_spawn_fields=tuple(pre_fields),
            icon=_icon_for_shape(info.get("shape", "")),
            etype=etype,
        )

    for item in _SYNTHETIC_ITEMS:
        idx[item.spawn_id] = item

    return idx


# Module-level cache — built lazily on first access.
SPAWN_INDEX: dict[str, SpawnItem] = {}


def get_spawn_index() -> dict[str, SpawnItem]:
    """Return the (lazily-built) spawn index."""
    global SPAWN_INDEX
    if not SPAWN_INDEX:
        SPAWN_INDEX = build_spawn_index()
    return SPAWN_INDEX


# ---------------------------------------------------------------------------
# Convenience helpers used by the panel and operators
# ---------------------------------------------------------------------------
def get_active_categories(props) -> set[str]:
    """Return the set of currently-active tile category names.

    Empty set means "no filter" → show everything. Full set is functionally
    identical: filter_items treats both as pass-through.
    """
    return {
        cat for cat, prop_name in CATEGORY_TO_PROP.items()
        if getattr(props, prop_name, False)
    }


def is_favorited(scene, spawn_id: str) -> bool:
    """True if spawn_id is in this scene's favorites collection."""
    props = getattr(scene, "og_props", None)
    if props is None:
        return False
    favs = getattr(props, "spawn_favorites", None)
    if favs is None:
        return False
    return any(f.spawn_id == spawn_id for f in favs)


def toggle_favorite(scene, spawn_id: str) -> bool:
    """Add or remove spawn_id from the favorites collection.

    Returns True if the item is now favorited, False if it was un-favorited.
    """
    favs = scene.og_props.spawn_favorites
    for i, f in enumerate(favs):
        if f.spawn_id == spawn_id:
            favs.remove(i)
            return False
    new = favs.add()
    new.spawn_id = spawn_id
    return True


def get_selected_spawn_item(scene) -> Optional[SpawnItem]:
    """Return the currently-highlighted SpawnItem from the UIList, or None.

    Reads scene.og_props.spawn_list_index → spawn_list_items[idx].spawn_id →
    SPAWN_INDEX[spawn_id]. Returns None if no valid selection.
    """
    props = scene.og_props
    idx = props.spawn_list_index
    rows = props.spawn_list_items
    if idx < 0 or idx >= len(rows):
        return None
    return get_spawn_index().get(rows[idx].spawn_id)


def count_filtered(scene) -> tuple[int, int]:
    """Return (visible_count, total_count) accounting for category and
    favorites filters. Does NOT include the UIList's native search-text
    filter — that's per-UIList-instance state not visible from a panel
    draw() context. Used by the panel header to show an "X of N" hint."""
    props = scene.og_props
    total = len(props.spawn_list_items)
    active_cats = get_active_categories(props)
    if not active_cats:
        return total, total
    favorites_only = "Favorites" in active_cats
    regular_cats = active_cats - {"Favorites"}
    index = get_spawn_index()
    visible = 0
    for row in props.spawn_list_items:
        sp = index.get(row.spawn_id)
        if sp is None:
            continue
        if favorites_only and not is_favorited(scene, row.spawn_id):
            continue
        if regular_cats and sp.category not in regular_cats:
            continue
        visible += 1
    return visible, total


# ---------------------------------------------------------------------------
# Scene population — handler + helpers
# ---------------------------------------------------------------------------
def populate_spawn_list(scene) -> None:
    """Fill scene.og_props.spawn_list_items from SPAWN_INDEX. Idempotent —
    skips work if the collection already matches the index size.

    Called:
      - At addon register for the current scene
      - From the load_post handler for every loaded scene
    """
    props = getattr(scene, "og_props", None)
    if props is None:
        return
    index = get_spawn_index()
    if len(props.spawn_list_items) == len(index):
        # Already populated and current — skip
        return
    props.spawn_list_items.clear()
    for spawn_id in index.keys():
        row = props.spawn_list_items.add()
        row.spawn_id = spawn_id


@persistent
def _on_load_post(_dummy):
    """Handler: re-populate every scene's spawn list after blend file load."""
    for scene in bpy.data.scenes:
        populate_spawn_list(scene)


def register_handlers() -> None:
    """Register load_post handler. Idempotent — won't double-register."""
    if _on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load_post)


def unregister_handlers() -> None:
    """Remove load_post handler. Safe to call if not registered."""
    if _on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load_post)
