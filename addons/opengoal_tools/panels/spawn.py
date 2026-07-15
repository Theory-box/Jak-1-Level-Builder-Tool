# ───────────────────────────────────────────────────────────────────────
# panels/spawn.py — OpenGOAL Level Tools
#
# Unified spawn picker panel. Renders one searchable, sortable, filterable
# list of every placeable thing in the level.
#
# This file replaces what used to be 15 separate sub-panels (one per
# category) with a single OG_PT_Spawn that builds the UI from the index
# in spawn_items.py and dispatches via og.spawn_selected.
# ───────────────────────────────────────────────────────────────────────

from __future__ import annotations

import bpy
from bpy.types import Panel
from .. import db as _db
from ..spawn_items import (
    get_spawn_index, get_active_categories, is_favorited,
    get_selected_spawn_item, count_filtered,
    CATEGORY_ICONS, CATEGORY_TO_PROP, TILE_CATEGORIES,
)


class OG_PT_Spawn(Panel):
    bl_label       = "➕  Spawn Objects"
    bl_idname      = "OG_PT_spawn"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_options     = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        layout = self.layout
        props  = ctx.scene.og_props

        # ── Sort row ─────────────────────────────────────────────────────
        row = layout.row(align=True)
        row.label(text="", icon="SORTALPHA")
        row.prop(props, "spawn_sort_mode", text="")

        # ── 15-tile category grid (multi-select) ────────────────────────
        # Click a tile to solo it (hide other categories), shift+click to
        # toggle it in/out of the multi-selection. Click an already-soloed
        # tile to clear the filter.
        flow = layout.grid_flow(
            row_major=True, columns=4,
            even_columns=True, even_rows=True, align=True,
        )
        for cat_name in TILE_CATEGORIES:
            prop_name = CATEGORY_TO_PROP[cat_name]
            op = flow.operator(
                "og.toggle_spawn_category",
                text=cat_name,
                icon=CATEGORY_ICONS[cat_name],
                depress=getattr(props, prop_name, False),
            )
            op.prop_name = prop_name

        # ── Status hint when any category filter is active ──────────────
        active_cats = get_active_categories(props)
        if active_cats:
            visible, total = count_filtered(ctx.scene)
            hint = layout.row()
            hint.scale_y = 0.85
            if visible == 0:
                if active_cats == {"Favorites"}:
                    hint.label(text="No favorites yet — tap the star on any row",
                               icon="SOLO_OFF")
                else:
                    hint.label(text="No items match selected categories",
                               icon="INFO")
            else:
                hint.label(text=f"Showing {visible} of {total}", icon="FILTER")

        # ── Scrollable picker list ───────────────────────────────────────
        layout.template_list(
            "OG_UL_SpawnableItems", "",
            props, "spawn_list_items",
            props, "spawn_list_index",
            rows=10,
        )

        # ── Dynamic settings (only when an item is selected) ─────────────
        selected = get_selected_spawn_item(ctx.scene)
        if selected is not None:
            _draw_dynamic_settings(layout, ctx, selected)

        # ── Spawn button (always rendered; poll disables when no selection) ─
        spawn_row = layout.row()
        spawn_row.scale_y = 1.6
        spawn_row.operator("og.spawn_selected", icon="ADD")


# ═══════════════════════════════════════════════════════════════════════════
# Field drawers + dynamic settings helper
# ───────────────────────────────────────────────────────────────────────────
# Each FIELD_DRAWER is a function (layout, ctx, item) → None that renders
# one pre-spawn field. SpawnItem.pre_spawn_fields lists which ones to draw
# for a given item; _draw_dynamic_settings iterates and dispatches.
# ═══════════════════════════════════════════════════════════════════════════


def _wrap_text(text: str, width: int = 40) -> list[str]:
    """Simple word-wrap for label-based prose rendering. Splits on
    whitespace; never breaks mid-word."""
    out: list[str] = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split():
            if not line:
                line = word
            elif len(line) + 1 + len(word) <= width:
                line += " " + word
            else:
                out.append(line)
                line = word
        if line:
            out.append(line)
        if not paragraph:
            out.append("")
    return out


def _draw_field_crate_type(layout, ctx, item):
    layout.prop(ctx.scene.og_props, "crate_type", text="Crate type")


def _draw_field_variant(layout, ctx, item):
    layout.prop(ctx.scene.og_props, "spawn_variant", text="Variant")


def _draw_field_nav_radius(layout, ctx, item):
    box = layout.box()
    box.label(text="Nav-enemy — needs navmesh", icon="ERROR")
    box.prop(ctx.scene.og_props, "nav_radius", text="Sphere radius (m)")


def _draw_field_sfx_sound(layout, ctx, item):
    props = ctx.scene.og_props
    snd_display = (
        props.sfx_sound.split("__")[0] if "__" in props.sfx_sound else props.sfx_sound
    )
    layout.operator("og.pick_sound", text=f"🔊  {snd_display}", icon="VIEWZOOM")


def _draw_field_ambient_radius(layout, ctx, item):
    layout.prop(ctx.scene.og_props, "ambient_default_radius", text="Default radius (m)")


def _draw_field_music_bank(layout, ctx, item):
    layout.prop(ctx.scene.og_props, "og_music_amb_bank", text="Bank")


def _draw_field_music_flava(layout, ctx, item):
    layout.prop(ctx.scene.og_props, "og_music_amb_flava", text="Flava")


def _draw_field_music_priority(layout, ctx, item):
    layout.prop(ctx.scene.og_props, "og_music_amb_priority", text="Priority")


def _draw_field_music_radius(layout, ctx, item):
    layout.prop(ctx.scene.og_props, "og_music_amb_radius", text="Radius (m)")


def _draw_field_custom_name(layout, ctx, item):
    layout.prop(ctx.scene.og_props, "custom_type_name", text="Deftype name")


def _draw_field_target_context(layout, ctx, item):
    """Read-only context indicator for the Camera anchor item.
    Mirrors OG_OT_SpawnSelected._validate so the user sees the same state."""
    sel = ctx.active_object
    is_ok = (sel is not None and sel.type == "EMPTY"
             and (sel.name.startswith("SPAWN_") or sel.name.startswith("CHECKPOINT_"))
             and not sel.name.endswith("_CAM"))
    box = layout.box()
    if is_ok:
        box.label(text=f"Will spawn: {sel.name}_CAM", icon="CHECKMARK")
    else:
        sub = box.row()
        sub.alert = True
        sub.label(text="Select a SPAWN_ or CHECKPOINT_ empty first", icon="ERROR")


FIELD_DRAWERS = {
    "crate_type":     _draw_field_crate_type,
    "variant":        _draw_field_variant,
    "nav_radius":     _draw_field_nav_radius,
    "sfx_sound":      _draw_field_sfx_sound,
    "ambient_radius": _draw_field_ambient_radius,
    "music_bank":     _draw_field_music_bank,
    "music_flava":    _draw_field_music_flava,
    "music_priority": _draw_field_music_priority,
    "music_radius":   _draw_field_music_radius,
    "custom_name":    _draw_field_custom_name,
    "target_context": _draw_field_target_context,
}


def _draw_dynamic_settings(layout, ctx, item):
    """Render the dynamic settings box for a selected SpawnItem.

    Shows:
      - The wiki/description text (word-wrapped at ~40 chars/line)
      - Entity-specific info messages (nav-mesh need, path requirements,
        prop-only notice) — derived from NEEDS_PATH / IS_PROP type sets
      - Any pre_spawn_fields, dispatched via FIELD_DRAWERS
    """
    box = layout.box()
    header = box.row(align=True)
    header.label(text=item.label, icon=item.icon)

    if item.description:
        col = box.column(align=True)
        col.scale_y = 0.85
        for line in _wrap_text(item.description, width=40):
            col.label(text=line if line else " ")

    # Entity-specific info messages.
    if item.etype is not None:
        if _db.needs_pathb(item.etype):
            box.label(text="Needs 2 path sets (wp + wpb)", icon="INFO")
        elif _db.needs_path(item.etype):
            box.label(text="Needs waypoints to patrol", icon="INFO")
        elif _db.is_prop(item.etype):
            box.label(text="Prop — idle animation only", icon="INFO")

    # Pre-spawn fields.
    for field_id in item.pre_spawn_fields:
        drawer = FIELD_DRAWERS.get(field_id)
        if drawer is not None:
            drawer(box, ctx, item)


# ═══════════════════════════════════════════════════════════════════════════
# Unified Spawn picker — UIList class
# ───────────────────────────────────────────────────────────────────────────
# OG_UL_SpawnableItems renders the scrollable list of every placeable thing.
# filter_items combines:
#   - self.filter_name        (Blender's built-in real-time text input)
#   - active category toggles (props.cat_*)
#   - sort mode               (props.spawn_sort_mode)
# Star icon at the start of each row toggles per-file favorites.
# ═══════════════════════════════════════════════════════════════════════════


class OG_UL_SpawnableItems(bpy.types.UIList):
    """Unified spawnable picker list. Read-only collection populated once at
    register from SPAWN_INDEX. Per-row data lookup goes through the dict so
    we don't duplicate metadata onto every PropertyGroup row."""

    # Show Blender's built-in filter/sort row by default — that's where the
    # real-time search input lives.
    use_filter_show: bpy.props.BoolProperty(default=True, options={'HIDDEN'})

    def draw_item(self, ctx, layout, data, item, icon, active_data,
                  active_propname, index):
        sp = get_spawn_index().get(item.spawn_id)
        if sp is None:
            layout.label(text=f"(missing: {item.spawn_id})", icon="ERROR")
            return

        row = layout.row(align=True)

        # Star (favorite toggle). emboss=False to render without button chrome.
        fav = is_favorited(ctx.scene, item.spawn_id)
        op = row.operator(
            "og.toggle_spawn_favorite",
            text="",
            icon="SOLO_ON" if fav else "SOLO_OFF",
            emboss=False,
        )
        op.spawn_id = item.spawn_id

        # Category icon + main label with tpage suffix in parens.
        cat_icon = CATEGORY_ICONS.get(sp.category, "EMPTY_DATA")
        row.label(text="", icon=cat_icon)
        display = f"{sp.label} ({sp.tpage_group})" if sp.tpage_group else sp.label
        row.label(text=display)

        # Category text, right-aligned. Dimmed via active=False so the main
        # label still reads as the primary content.
        sub = row.row(align=True)
        sub.alignment = 'RIGHT'
        sub.active = False
        sub.label(text=sp.category)

    def filter_items(self, ctx, data, propname):
        """Combine search text + category toggles + sort mode.

        Returns (flt_flags, flt_neworder):
          flt_flags[i]    — bitflag_filter_item if item i should be shown
          flt_neworder[i] — new display position for original index i
        Search text matches against label + tpage_group, so typing 'beach'
        finds all Beach-tpage items even though their labels don't contain it.
        """
        items = getattr(data, propname)
        props = ctx.scene.og_props
        scene = ctx.scene
        index = get_spawn_index()

        active_cats = get_active_categories(props)
        # Favorites tile is a virtual filter — handled separately from the
        # rest of the category filter so it can be combined or used solo.
        favorites_only = "Favorites" in active_cats
        regular_cats = active_cats - {"Favorites"}
        filter_text = (self.filter_name or "").lower()

        flt_flags = []
        for row in items:
            sp = index.get(row.spawn_id)
            if sp is None:
                flt_flags.append(0)
                continue

            if favorites_only and not is_favorited(scene, row.spawn_id):
                flt_flags.append(0)
                continue

            if regular_cats and sp.category not in regular_cats:
                flt_flags.append(0)
                continue

            if filter_text:
                searchable = sp.label.lower()
                if sp.tpage_group:
                    searchable += " " + sp.tpage_group.lower()
                if filter_text not in searchable:
                    flt_flags.append(0)
                    continue

            flt_flags.append(self.bitflag_filter_item)

        flt_neworder = self._compute_sort_order(items, props, scene, index)

        return flt_flags, flt_neworder

    def _compute_sort_order(self, items, props, scene, index):
        """Build flt_neworder mapping (original_index → new_display_pos)
        from the current sort mode. Only ALPHA and TPAGEGROUP are supported;
        anything else falls back to alphabetical."""
        mode = props.spawn_sort_mode
        n = len(items)
        if n == 0:
            return []

        def key_for(idx):
            row = items[idx]
            sp = index.get(row.spawn_id)
            if sp is None:
                return ("zzzz", "")
            label_key = sp.label.lower()
            if mode == "TPAGEGROUP":
                return ((sp.tpage_group or "zzzz"), label_key)
            # ALPHA (and any unknown future value) → label A-Z
            return (label_key,)

        ordered = sorted(range(n), key=key_for)

        # flt_neworder format: flt_neworder[i] = new display position for
        # the item that was originally at index i.
        flt_neworder = [0] * n
        for new_pos, orig_idx in enumerate(ordered):
            flt_neworder[orig_idx] = new_pos
        return flt_neworder



# ─── Classes to register ───────────────────────────────────────────────────
CLASSES = (
    OG_UL_SpawnableItems,
    OG_PT_Spawn,
)
