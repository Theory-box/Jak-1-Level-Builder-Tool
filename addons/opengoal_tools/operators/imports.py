# ───────────────────────────────────────────────────────────────────────
# operators/imports.py — OpenGOAL Level Tools
#
# Operators for the Import panel: scan decompiler_out/jak1/glb_out/ for
# available GLBs, import a chosen one into an Imports/<name>/ sub-collection
# at scene root.
#
# The Imports collection lives OUTSIDE every level collection, so the
# export pipeline (which walks <active_level>/Geometry/) never sees these
# meshes. No og_no_export flag needed.
#
# Module-level _GLB_CACHE holds the scan result so the live filter in the
# panel's draw() stays cheap. Populated on first access and on explicit
# rescan (OG_OT_RescanGlbs).
#
# _FIND_ATTEMPTED is set by OG_OT_FindModels so the Import panel knows
# whether to show the first-time "Find Models" prompt or the manual-path
# fallback. Resets on Blender restart, which is fine — once the cache
# populates the panel skips both prompts entirely.
# ───────────────────────────────────────────────────────────────────────

from __future__ import annotations

import bpy
from bpy.types import Operator
from bpy.props import StringProperty
from pathlib import Path

from .. import model_preview as _mp

# ── GLB cache (module-level) ─────────────────────────────────────────────
# Two parallel structures: a sorted list of basenames (without .glb) for
# the live filter to walk, and a dict mapping basename → full path so the
# import op doesn't have to re-resolve.
_GLB_CACHE: list[str] = []          # sorted basenames
_GLB_PATHS: dict[str, Path] = {}    # basename → full path
_SCAN_DONE: bool = False             # True once we've run a scan at least once
_FIND_ATTEMPTED: bool = False        # True once the user has clicked Find Models


def _glb_out_dir() -> Path:
    """Path to decompiler_out/jak1/glb_out/. Late-imported to avoid a
    circular import at module load time."""
    from ..build import _decompiler_path
    return _decompiler_path() / "glb_out"


def _scan_glbs() -> tuple[int, str]:
    """Rescan glb_out/ and refresh _GLB_CACHE + _GLB_PATHS.

    Returns (count, message). message is empty on success, otherwise a
    short reason string for the panel/operator report.
    """
    global _GLB_CACHE, _GLB_PATHS, _SCAN_DONE
    _GLB_CACHE = []
    _GLB_PATHS = {}
    _SCAN_DONE = True

    d = _glb_out_dir()
    if not d.exists():
        return 0, f"glb_out not found at {d}"
    try:
        files = sorted(d.glob("*.glb"), key=lambda p: p.name.lower())
    except OSError as e:
        return 0, f"scan failed: {e}"

    for p in files:
        stem = p.stem  # filename without extension
        _GLB_PATHS[stem] = p
        _GLB_CACHE.append(stem)
    return len(_GLB_CACHE), ""


def get_glb_cache() -> list[str]:
    """Lazy accessor — scans on first call, returns cached basenames after."""
    if not _SCAN_DONE:
        _scan_glbs()
    return _GLB_CACHE


def get_glb_path(basename: str) -> Path | None:
    """Map a cached basename back to its full Path. Returns None if the
    cache is empty or the basename was not in the last scan."""
    if not _SCAN_DONE:
        _scan_glbs()
    return _GLB_PATHS.get(basename)


def is_find_attempted() -> bool:
    """True once the user has clicked Find Models at least once in this
    Blender session. Used by the Import panel to choose between the
    first-time prompt and the manual-path fallback when the cache is
    empty. Resets to False on Blender restart."""
    return _FIND_ATTEMPTED


def _tag_view3d_redraw(ctx):
    """Force the 3D viewport sidebar to repaint so the Import panel
    transitions out of setup mode the moment the cache fills."""
    for area in ctx.screen.areas:
        if area.type == "VIEW_3D":
            area.tag_redraw()


# ── Operators ────────────────────────────────────────────────────────────

class OG_OT_RescanGlbs(Operator):
    """Re-scan the decompiler_out/jak1/glb_out/ folder for available GLB
    files. Use after running the OpenGOAL decompiler with new flags or
    after dropping new GLBs into the folder manually."""
    bl_idname  = "og.rescan_glbs"
    bl_label   = "Rescan GLBs"
    bl_options = {"INTERNAL"}

    def execute(self, ctx):
        n, msg = _scan_glbs()
        if msg:
            self.report({"WARNING"}, msg)
        else:
            self.report({"INFO"}, f"Found {n} GLB{'s' if n != 1 else ''} in glb_out/")
        _tag_view3d_redraw(ctx)
        return {"FINISHED"}


class OG_OT_FindModels(Operator):
    """First-time setup helper for the Import panel. Opens a directory
    picker for the OpenGOAL install root, runs the existing scan-paths
    auto-detect to populate exe/data folders, then refreshes the GLB
    cache. If GLBs are found the panel transitions to normal UI; if not,
    the panel falls back to manual decompiler-path entry."""
    bl_idname  = "og.find_models"
    bl_label   = "Find Models"
    bl_description = (
        "Pick your OpenGOAL install folder. The addon will auto-detect "
        "exe/data subfolders and scan decompiler_out for available GLBs."
    )
    bl_options = {"INTERNAL"}

    directory: StringProperty(subtype="DIR_PATH")

    def invoke(self, ctx, event):
        ctx.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, ctx):
        global _FIND_ATTEMPTED
        _FIND_ATTEMPTED = True

        picked = (self.directory or "").strip().rstrip("\\/")
        if not picked:
            self.report({"WARNING"}, "No folder selected — set paths manually below")
            _tag_view3d_redraw(ctx)
            return {"CANCELLED"}

        prefs = ctx.preferences.addons.get("opengoal_tools")
        if not prefs:
            self.report({"ERROR"}, "Addon preferences not found")
            _tag_view3d_redraw(ctx)
            return {"CANCELLED"}

        prefs.preferences.og_root_path = picked

        # Run the existing scan_paths op to auto-derive exe + data folders
        # from the root. If it fails we still try a GLB scan — the user
        # may have set a decompiler_path override that's enough on its own.
        try:
            bpy.ops.og.scan_paths()
        except Exception as e:
            self.report({"WARNING"}, f"Auto-detect failed: {e}. Trying GLB scan anyway.")

        n, msg = _scan_glbs()
        if n > 0:
            self.report({"INFO"}, f"Found {n} GLB{'s' if n != 1 else ''} — Import panel ready")
        else:
            self.report(
                {"WARNING"},
                msg or "No GLBs found under that folder. Set decompiler path manually below."
            )
        _tag_view3d_redraw(ctx)
        return {"FINISHED"}


def _ensure_imports_root(scene) -> bpy.types.Collection:
    """Find or create the top-level 'Imports' collection at scene root.
    Lives outside any level collection so the export pipeline ignores it."""
    col = bpy.data.collections.get("Imports")
    if col is None:
        col = bpy.data.collections.new("Imports")
        scene.collection.children.link(col)
    elif col.name not in {c.name for c in scene.collection.children}:
        # Collection exists in bpy.data but isn't linked to this scene yet
        scene.collection.children.link(col)
    return col


def _ensure_imports_subcollection(scene, name: str) -> bpy.types.Collection:
    """Find or create Imports/<name>/. Each imported GLB gets its own
    sub-collection so multiple imports are easy to inspect, hide, or delete."""
    root = _ensure_imports_root(scene)
    # Blender appends .001 etc. on name collision — look up by exact
    # parented-to-root match rather than bpy.data.collections.get which
    # may return one from elsewhere.
    for child in root.children:
        if child.name == name or child.name.startswith(f"{name}."):
            return child
    col = bpy.data.collections.new(name)
    root.children.link(col)
    return col


class OG_OT_ImportGlb(Operator):
    """Import a GLB from decompiler_out/jak1/glb_out/ into a sub-collection
    of the scene-root 'Imports' collection. Re-importing the same GLB
    creates additional copies in the same sub-collection (no deduplication
    by design — explicit user action each time)."""
    bl_idname  = "og.import_glb"
    bl_label   = "Import GLB"
    bl_options = {"REGISTER", "UNDO"}

    glb_name: StringProperty(
        name="GLB Name",
        description="Basename (without .glb) of the GLB to import",
    )

    def execute(self, ctx):
        name = (self.glb_name or "").strip()
        if not name:
            self.report({"ERROR"}, "No GLB name provided")
            return {"CANCELLED"}

        path = get_glb_path(name)
        if path is None or not path.exists():
            self.report({"ERROR"}, f"GLB not found: {name}.glb (try Rescan)")
            return {"CANCELLED"}

        # Import via the same helper model_preview.py uses for actor models —
        # handles the VIEW_3D context override Blender requires.
        new_objs = _mp._import_glb(ctx, path)
        if not new_objs:
            self.report({"WARNING"}, f"{name}: imported, but produced no objects")
            return {"CANCELLED"}

        target_col = _ensure_imports_subcollection(ctx.scene, name)

        # Move every newly created object into the target sub-collection.
        # The GLTF importer parents new objects under the scene root collection
        # by default; we unlink from there and re-link into target_col.
        scene_root = ctx.scene.collection
        for obj in new_objs:
            # Unlink from wherever the importer put it
            for col in list(obj.users_collection):
                col.objects.unlink(obj)
            target_col.objects.link(obj)

        self.report({"INFO"}, f"Imported {name}.glb ({len(new_objs)} object{'s' if len(new_objs) != 1 else ''}) into Imports/{target_col.name}/")
        return {"FINISHED"}


CLASSES = (
    OG_OT_RescanGlbs,
    OG_OT_FindModels,
    OG_OT_ImportGlb,
)
