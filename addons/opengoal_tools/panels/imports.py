# ───────────────────────────────────────────────────────────────────────
# panels/imports.py — OpenGOAL Level Tools
#
# Import panel: bring GLBs from decompiler_out/jak1/ into the scene as
# reference geometry. Imports land in a top-level "Imports/<name>/"
# collection at scene root, outside any level — so the export pipeline
# never touches them.
#
# Structure:
#   OG_PT_Import           — parent panel (setup flow or Rescan header)
#     ├ OG_PT_ImportSearch — generic name search + filtered list
#     └ OG_PT_ImportLevels — one row per vanilla level (background GLB)
#
# Live filter: the search box is a StringProperty on og_props
# (glb_search_filter). Blender re-runs draw() when it changes, so the
# filter is essentially free.
#
# GLB list caching lives in operators/imports.py — module-level dict
# populated on first access and on explicit Rescan.
# ───────────────────────────────────────────────────────────────────────

from __future__ import annotations

import bpy
from bpy.types import Panel
from pathlib import PurePosixPath

from ..operators.imports import get_glb_cache, is_find_attempted

# How many matching rows to draw at most. The panel is in the sidebar,
# anything bigger than this makes the UI unusable.
_MAX_VISIBLE_ROWS = 25


def _draw_setup(layout, ctx):
    """Render the first-time setup UI when no GLBs have been found yet.

    Two-stage flow:
      A. Initial — single 'Find Models' button (a DIR picker for the
         decompiler_out/jak1/ folder).
      B. Auto-detect attempted but cache still empty — manual fallback:
         the decompiler_path picker + Rescan + Re-pick.
    Once the cache populates, neither stage shows again. og_root_path is
    deliberately not exposed here — it belongs in Preferences and the
    Import panel only needs the decompiler folder.
    """
    box = layout.box()
    box.label(text="Setup needed", icon="ERROR")

    if not is_find_attempted():
        # Stage A — first time, single big button
        box.label(text="Point me at decompiler_out/jak1/:")
        box.operator("og.find_models", text="📂  Find Models", icon="FILEBROWSER")
        box.label(text="Typically <opengoal>/active/jak1/data/decompiler_out/jak1/", icon="DOT")
        return

    # Stage B — first attempt found nothing. Show the manual picker.
    box.label(text="No GLBs found. Set the path manually:", icon="INFO")
    prefs = ctx.preferences.addons.get("opengoal_tools")
    if prefs:
        box.prop(prefs.preferences, "decompiler_path", text="Decompiler path")
    row = box.row(align=True)
    row.operator("og.find_models",  text="📂  Re-pick",  icon="FILEBROWSER")
    row.operator("og.rescan_glbs",  text="Rescan",      icon="FILE_REFRESH")


class OG_PT_Import(Panel):
    """Parent panel.

    When GLBs are available: shows the Rescan button and lets the subpanels
    do the work.
    When no GLBs are available: shows the first-time setup flow inline; the
    subpanels are hidden via their own poll() so the UI stays clean.
    """
    bl_label       = "📥  Import"
    bl_idname      = "OG_PT_import"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_options     = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        layout = self.layout
        cache  = get_glb_cache()
        if not cache:
            _draw_setup(layout, ctx)
            return
        # Normal mode — children handle the listings, header just has Rescan.
        row = layout.row(align=True)
        row.operator("og.rescan_glbs", icon="FILE_REFRESH", text="Rescan")


class OG_PT_ImportSearch(Panel):
    """Generic search: type a substring, see matching GLBs, click to import."""
    bl_label       = "🔍  Search GLBs"
    bl_idname      = "OG_PT_import_search"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_import"
    bl_order       = 0

    @classmethod
    def poll(cls, ctx):
        # Hide while the parent panel is in setup mode; show once GLBs
        # are available. get_glb_cache() is cheap after the first call —
        # _SCAN_DONE short-circuits the file walk.
        return bool(get_glb_cache())

    def draw(self, ctx):
        layout = self.layout
        props  = ctx.scene.og_props

        # Search field — Blender redraws automatically on text change
        row = layout.row(align=True)
        row.prop(props, "glb_search_filter", text="", icon="VIEWZOOM")

        cache = get_glb_cache()

        # Filter: case-insensitive substring match against the relpath
        # (e.g. "levels/village1/babak-lod0" matches "babak" or "village").
        query = props.glb_search_filter.strip().lower()
        if query:
            matches = [name for name in cache if query in name.lower()]
        else:
            matches = cache  # Empty query → show everything (capped below)

        if not matches:
            layout.label(text=f"No matches for '{query}'", icon="INFO")
            return

        # Header line: match count + truncation notice if applicable
        if len(matches) > _MAX_VISIBLE_ROWS:
            layout.label(
                text=f"{_MAX_VISIBLE_ROWS} of {len(matches)} matches (refine search)",
                icon="OUTLINER",
            )
            shown = matches[:_MAX_VISIBLE_ROWS]
        else:
            layout.label(text=f"{len(matches)} match{'es' if len(matches) != 1 else ''}", icon="OUTLINER")
            shown = matches

        col = layout.column(align=True)
        for key in shown:
            # Display the basename on the button — the directory prefix is
            # clutter when the search query already implies context. The
            # full key still goes to the op so import resolves correctly.
            display = PurePosixPath(key).name
            op = col.operator("og.import_glb", text=display, icon="IMPORT")
            op.glb_name = key


def _level_background_entries(cache: list[str]) -> list[tuple[str, str]]:
    """Pick out one entry per level: the file at levels/<lvl>/<lvl>-background.
    Returns a list of (level_name, full_key) tuples sorted by level name.
    Anything not matching that exact shape is ignored — the Search subpanel
    is the place for arbitrary GLBs."""
    out = []
    for key in cache:
        parts = key.split("/")
        # Expected shape: ["levels", "<lvl>", "<lvl>-background"]
        if len(parts) != 3 or parts[0] != "levels":
            continue
        lvl, leaf = parts[1], parts[2]
        if leaf == f"{lvl}-background":
            out.append((lvl, key))
    return sorted(out, key=lambda t: t[0].lower())


class OG_PT_ImportLevels(Panel):
    """One row per vanilla level — imports the per-level background GLB
    (levels/<lvl>/<lvl>-background.glb). Use the Search subpanel for any
    other GLB (per-actor models, props, etc.)."""
    bl_label       = "🗺  Levels"
    bl_idname      = "OG_PT_import_levels"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_import"
    bl_order       = 1
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        return bool(get_glb_cache())

    def draw(self, ctx):
        layout  = self.layout
        cache   = get_glb_cache()
        entries = _level_background_entries(cache)

        if not entries:
            layout.label(text="No level backgrounds found.", icon="INFO")
            layout.label(text="Run the decompiler with rip_levels: true.", icon="DOT")
            return

        layout.label(text=f"{len(entries)} level{'s' if len(entries) != 1 else ''} available", icon="OUTLINER")
        col = layout.column(align=True)
        for lvl_name, key in entries:
            op = col.operator("og.import_glb", text=lvl_name, icon="IMPORT")
            op.glb_name = key


CLASSES = (
    OG_PT_Import,
    OG_PT_ImportSearch,
    OG_PT_ImportLevels,
)
