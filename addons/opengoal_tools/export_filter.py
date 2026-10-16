"""Export filter (Developer Tools > Build): leave parts of the export out.
For testing / special setups; skipping parts can break the compile or crash
the game. Only active when "Filter exports" is on."""
from __future__ import annotations

import bpy
from bpy.props import BoolProperty, PointerProperty

# (key, label, description); every key is a BoolProperty, True = exported
PARTS = (
    ("glb", "Geometry (GLB)", "The level's .glb (geometry + collision)"),
    ("jsonc", "Entities (.jsonc)", "Actors, ambients, cameras, art groups"),
    ("gd", "Load (.gd)", "The level's DGO file list"),
    ("obs", "Actor code (-obs.gc)", "The level's generated GOAL code"),
    ("gamegp", "game.gp definition", "The level's build / code entries in game.gp"),
    ("navmesh", "Nav-mesh (entity.gc)", "The level's nav-mesh entries in entity.gc"),
    ("tasks", "Task & Menu", "Custom tasks: task enum, task file, texts"),
    ("level_settings", "Level settings", "level-info.gc: everything but the checkpoints"),
    ("checkpoints", "Checkpoints", "level-info.gc: the continue-points"),
    ("load_boundaries", "Load Boundaries", "load-boundary-data.gc"),
)
GROUPS = (("Level folder", ("glb", "jsonc", "gd", "obs")), (None, ("gamegp", "navmesh", "tasks")),
          ("Level-info", ("level_settings", "checkpoints")), (None, ("load_boundaries",)))


def _settings_class():
    ann = {"enabled": BoolProperty(name="Filter exports", default=False,
                                   description="Leave the unticked parts out of the export (advanced; can break the "
                                               "compile or crash the game)")}
    for k, label, desc in PARTS:
        ann[k] = BoolProperty(name=label, default=True, description=f"Export: {desc}")
    return type("OGExportFilter", (bpy.types.PropertyGroup,), {"__annotations__": ann})


OGExportFilter = _settings_class()


def allowed(key, scene=None):
    """False when the filter is on and this part is unticked (logged)."""
    scene = scene or bpy.context.scene
    f = getattr(scene, "og_export_filter", None)
    if f is None or not f.enabled or getattr(f, key, True):
        return True
    from .export.paths import log
    log(f"[export filter] skipped: {dict((k, l) for k, l, _d in PARTS)[key]}")
    return False


def draw(layout, scene):
    f = scene.og_export_filter
    head, body = layout.panel("og_export_filter", default_closed=True)
    head.label(text="Export Filter" + ("  (on)" if f.enabled else ""), icon="FILTER")
    if body is None:
        return
    w = body.row(); w.alert = True
    w.label(text="Skipping parts can break the compile and crash the game", icon="ERROR")
    body.prop(f, "enabled")
    col = body.column(align=True)
    col.enabled = f.enabled
    for title, keys in GROUPS:
        if title:
            col.label(text=title)
        for k in keys:
            r = col.row()
            if title:
                r.separator(factor=2.0)
            r.prop(f, k)


CLASSES = (OGExportFilter,)


def register_props():
    bpy.types.Scene.og_export_filter = PointerProperty(type=OGExportFilter)


def unregister_props():
    if hasattr(bpy.types.Scene, "og_export_filter"):
        del bpy.types.Scene.og_export_filter
