"""Level GLB export through Blender's collection exporter.

Each level's Geometry collection (<level>.Geometry) carries a glTF 2.0
collection exporter. The addon creates it and sets what the level build needs
(file path, GLB, custom properties, Y up ...); everything else (Draco
compression, vertex colours, ...) is the user's to change in Properties >
Collection > Exporters. Every object in Geometry and its sub-collections is
exported, whether or not it can be selected; sub-collections marked "Disable
Export" (the collection's "skip_export" custom property) are skipped.
"""
from __future__ import annotations

import bpy
from ..collections import (
    _ensure_sub_collection, _recursive_col_objects, _col_is_no_export,
    _classify_object, _COL_PATH_GEO_SOLID, _COL_PATH_EXPORT_AS,
)

GLTF_HANDLER = "IO_FH_gltf2"

# set when the exporter is created; the user can change these afterwards
_DEFAULTS = {
    "export_vertex_color": "ACTIVE", "export_normals": True,
    "export_materials": "EXPORT", "export_texcoords": True,
    "export_skins": False, "export_animations": False,
    "export_cameras": False, "export_lights": False,
}
# what the level build needs: written before every export
_REQUIRED = {
    "export_format": "GLB", "export_extras": True, "export_yup": True,
    "export_apply": True, "use_selection": False, "use_visible": False,
    "use_renderable": False,  # render-off meshes (invisible walls / floors) are still level geometry
}

# meshes that are helpers, not level geometry
_HELPER_PREFIXES = ("VOL_", "WATER_", "CPVOL_", "NAVMESH_", "LOADBND_")


def geometry_collection(level_col, create=True):
    """<level>.Geometry (created if missing, else None when create=False)."""
    return _ensure_sub_collection(level_col, "Geometry") if create else find_sub_collection(level_col, "Geometry")


def find_sub_collection(level_col, *path):
    """_ensure_sub_collection without creating anything (safe in draw)."""
    name = str(level_col.get("og_level_name", level_col.name))
    cur = level_col
    for seg in path:
        name = f"{name}.{seg}"
        cur = next((c for c in cur.children if c.name == name), None)
        if cur is None:
            return None
    return cur


def glb_exporter(geo, create=True):
    """The glTF collection exporter of a Geometry collection."""
    for ex in geo.exporters:
        if type(ex.export_properties).__name__ == "EXPORT_SCENE_OT_gltf":
            return ex
    if not create:
        return None
    with bpy.context.temp_override(collection=geo):
        bpy.ops.collection.exporter_add(name=GLTF_HANDLER)
    ex = glb_exporter(geo, create=False)
    for k, v in _DEFAULTS.items():
        setattr(ex.export_properties, k, v)
    return ex


def stray_meshes(level_col):
    """Level meshes outside Geometry that look like level geometry: they are
    not exported until moved into Geometry."""
    if level_col is None:
        return []
    geo = geometry_collection(level_col, create=False)
    inside = set(geo.all_objects) if geo else set()
    export_as = find_sub_collection(level_col, *_COL_PATH_EXPORT_AS)
    out = []
    for o in _recursive_col_objects(level_col, exclude_no_export=True):
        if (o.type != "MESH" or o in inside or o.name.startswith(_HELPER_PREFIXES)
                or o.get("og_vertex_export_etype") or (export_as and o.name in export_as.all_objects)
                or (o.parent is not None and o.parent.name.startswith("ACTOR_"))):
            continue
        if _classify_object(o) == _COL_PATH_GEO_SOLID:
            out.append(o)
    return out


def export_level_glb(level_col, filepath):
    """Run the level's Geometry exporter to filepath."""
    geo = geometry_collection(level_col)
    ex = glb_exporter(geo)
    p = ex.export_properties
    p.filepath = str(filepath)
    for k, v in _REQUIRED.items():
        setattr(p, k, v)
    # time of day: _SUNRISE ... _GREENSUN go out as custom attributes
    p.export_attributes = bool(getattr(level_col, "og_bake", None) and level_col.og_bake.tod_enabled)
    if _col_is_no_export(geo):
        raise RuntimeError(f"{geo.name} has skip_export on: nothing to export")
    # meshes with a bake export it, whatever colour layer was picked since
    from ..bake import use_baked
    for o in geo.all_objects:
        if o.type == "MESH":
            use_baked(o.data)
    # skip_export sub-collections are unlinked while the exporter runs
    unlinked = []
    def _walk(c):
        for ch in list(c.children):
            if _col_is_no_export(ch):
                c.children.unlink(ch); unlinked.append((c, ch))
            else:
                _walk(ch)
    _walk(geo)
    try:
        idx = list(geo.exporters).index(ex)
        with bpy.context.temp_override(collection=geo):
            r = bpy.ops.collection.exporter_export(index=idx)
        if "FINISHED" not in r:
            raise RuntimeError(f"glTF export of {geo.name} failed")
    finally:
        for parent, ch in unlinked:
            parent.children.link(ch)
