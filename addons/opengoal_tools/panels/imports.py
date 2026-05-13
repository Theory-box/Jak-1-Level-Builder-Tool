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

        # Search field + collapse toggle. Blender redraws automatically
        # when the StringProperty changes, so the filter is live as you
        # type. The eye-icon toggle hides the result list without losing
        # the search query — useful once you have a stack of 25 rows
        # pushing other panels off-screen.
        row = layout.row(align=True)
        row.prop(props, "glb_search_filter", text="", icon="VIEWZOOM")
        eye = "HIDE_OFF" if props.glb_results_show else "HIDE_ON"
        row.prop(props, "glb_results_show", text="", icon=eye, toggle=True)

        cache = get_glb_cache()

        # Filter: case-insensitive substring match against the *basename*
        # only (the last path component, no extension). Matching the full
        # relpath confused users — searching "beach" would surface
        # "babak-lod0" because the babak file lives in levels/beach/.
        # Basename-only match means what you type is what you see.
        query = props.glb_search_filter.strip().lower()
        if query:
            matches = [
                k for k in cache
                if query in PurePosixPath(k).name.lower()
            ]
        else:
            matches = cache  # Empty query → show everything (capped below)

        # Header: match count + truncation notice if applicable. Always
        # shown so the user knows how many hits there are even when the
        # result list is collapsed.
        if not matches:
            layout.label(text=f"No matches for '{query}'", icon="INFO")
            return
        if len(matches) > _MAX_VISIBLE_ROWS:
            layout.label(
                text=f"{_MAX_VISIBLE_ROWS} of {len(matches)} matches (refine search)",
                icon="OUTLINER",
            )
            shown = matches[:_MAX_VISIBLE_ROWS]
        else:
            layout.label(text=f"{len(matches)} match{'es' if len(matches) != 1 else ''}", icon="OUTLINER")
            shown = matches

        if not props.glb_results_show:
            return  # collapsed — header above is enough feedback

        col = layout.column(align=True)
        for key in shown:
            # Display the basename on the button — the directory prefix is
            # clutter when the search query already implies context. The
            # full key still goes to the op so import resolves correctly.
            display = PurePosixPath(key).name
            op = col.operator("og.import_glb", text=display, icon="IMPORT")
            op.glb_name = key


def _level_entries(cache: list[str]) -> list[tuple[str, str]]:
    """For each unique folder under `levels/`, pick the best-matching GLB
    to represent that level. Returns (level_name, full_key) tuples sorted
    by level name.

    The decompiler doesn't always name the level visual `<lvl>-background`;
    some configs emit `<lvl>.glb` or `<lvl>-something.glb`. We try a few
    common patterns in priority order:
      1. stem == `<folder>-background`
      2. stem == `<folder>`
      3. stem starts with `<folder>-`
      4. any GLB containing the folder name as a substring
      5. (last resort) the alphabetically first GLB in the folder

    Folders containing zero GLBs are skipped. Folders containing only
    per-actor models (no level visual) end up importing the first GLB —
    user may want to rescan with `rip_levels: true` if they want the
    proper level background, but this at least gives them something.
    """
    by_folder: dict[str, list[str]] = {}
    for key in cache:
        parts = key.split("/")
        if len(parts) < 3 or parts[0] != "levels":
            continue
        folder = parts[1]
        by_folder.setdefault(folder, []).append(key)

    out: list[tuple[str, str]] = []
    for folder, keys in by_folder.items():
        # Pre-compute stems for fast comparisons
        stems = [(k, PurePosixPath(k).name) for k in keys]

        candidate: str | None = None
        # 1. <folder>-background
        for k, stem in stems:
            if stem == f"{folder}-background":
                candidate = k; break
        # 2. <folder> exactly
        if candidate is None:
            for k, stem in stems:
                if stem == folder:
                    candidate = k; break
        # 3. <folder>-anything
        if candidate is None:
            for k, stem in stems:
                if stem.startswith(f"{folder}-"):
                    candidate = k; break
        # 4. anything containing the folder name (loose match)
        if candidate is None:
            for k, stem in stems:
                if folder in stem:
                    candidate = k; break
        # 5. just take the first one
        if candidate is None and keys:
            candidate = sorted(keys)[0]

        if candidate:
            out.append((folder, candidate))

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
        entries = _level_entries(cache)

        if not entries:
            layout.label(text="No level folders found under levels/", icon="INFO")
            return

        layout.label(text=f"{len(entries)} level{'s' if len(entries) != 1 else ''}", icon="OUTLINER")
        col = layout.column(align=True)
        for lvl_name, key in entries:
            op = col.operator("og.import_glb", text=lvl_name, icon="IMPORT")
            op.glb_name = key


CLASSES = (
    OG_PT_Import,
    OG_PT_ImportSearch,
    OG_PT_ImportLevels,
)
