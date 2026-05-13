# ───────────────────────────────────────────────────────────────────────
# panels/imports.py — OpenGOAL Level Tools
#
# Import panel: bring GLBs from decompiler_out/jak1/glb_out/ into the scene
# as reference geometry. Imports land in a top-level "Imports/<name>/"
# collection at scene root, outside any level — so the export pipeline
# never touches them.
#
# Structure:
#   OG_PT_Import           — parent panel (header only)
#     ├ OG_PT_ImportSearch — generic name search + filtered list
#     └ OG_PT_ImportLevels — alphabetical list of every GLB in glb_out/
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

from ..operators.imports import get_glb_cache, is_find_attempted

# How many matching rows to draw at most. The panel is in the sidebar,
# anything bigger than this makes the UI unusable.
_MAX_VISIBLE_ROWS = 25


def _draw_setup(layout, ctx):
    """Render the first-time setup UI when no GLBs have been found yet.

    Two-stage flow:
      A. Initial — single 'Find Models' button (a DIR picker for the OG root).
      B. Auto-detect attempted but cache still empty — manual fallback with
         DIR pickers for og_root_path and decompiler_path, plus Rescan.
    Once the cache populates, neither stage shows again until the scan
    is cleared (which doesn't happen during normal use).
    """
    box = layout.box()
    box.label(text="Setup needed", icon="ERROR")

    if not is_find_attempted():
        # Stage A — first time, single big button
        box.label(text="Point me at your OpenGOAL install to scan for GLBs:")
        box.operator("og.find_models", text="📂  Find Models", icon="FILEBROWSER")
        return

    # Stage B — auto-detect ran but came up empty. Show manual pickers.
    box.label(text="Auto-detect found no GLBs. Set paths manually:", icon="INFO")
    prefs = ctx.preferences.addons.get("opengoal_tools")
    if prefs:
        p = prefs.preferences
        col = box.column(align=True)
        col.prop(p, "og_root_path",      text="OpenGOAL Root")
        col.prop(p, "decompiler_path",   text="Decompiler override")
    row = box.row(align=True)
    row.operator("og.find_models",  text="📂  Re-pick install",   icon="FILEBROWSER")
    row.operator("og.rescan_glbs",  text="Rescan",                icon="FILE_REFRESH")


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
        row.operator("og.rescan_glbs", icon="FILE_REFRESH", text="Rescan glb_out/")


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

        # Filter: case-insensitive substring match.
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
        for name in shown:
            op = col.operator("og.import_glb", text=name, icon="IMPORT")
            op.glb_name = name


class OG_PT_ImportLevels(Panel):
    """Alphabetical list of every GLB in glb_out/. For v1 this is the
    same content as the unfiltered Search panel — once we add other
    sources (actor models, props), Search broadens but Levels stays
    scoped to glb_out/."""
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
        layout = self.layout
        cache  = get_glb_cache()

        layout.label(text=f"{len(cache)} GLB{'s' if len(cache) != 1 else ''} available", icon="OUTLINER")
        col = layout.column(align=True)
        for name in cache:
            op = col.operator("og.import_glb", text=name, icon="IMPORT")
            op.glb_name = name


CLASSES = (
    OG_PT_Import,
    OG_PT_ImportSearch,
    OG_PT_ImportLevels,
)
