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
    # Active (the render colour layer) keeps vertex colour + alpha on every
    # object in every Blender version; "all vertex colours" off avoids a 5.2.2
    # bug (meshes whose render / active layers differ exported white).
    "export_vertex_color": "ACTIVE", "export_all_vertex_colors": False,
    "export_active_vertex_color_when_no_material": True, "export_normals": True,
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


def exported_meshes(level_col):
    """The meshes the level GLB is made of: Geometry and its folders, without
    skip_export folders, without meshes whose rendering is off."""
    geo = geometry_collection(level_col, create=False)
    if geo is None:
        return []
    out, seen = [], set()

    def walk(c):
        if _col_is_no_export(c) or c.hide_render:
            return
        for o in c.objects:
            if o.type == "MESH" and not o.hide_render and o.name not in seen:
                seen.add(o.name)
                out.append(o)
        for ch in c.children:
            walk(ch)
    walk(geo)
    return out


# collision / visibility properties the level builder reads from glTF extras
_COLLISION_PROPS = ("set_invisible", "set_collision", "ignore", "noedge", "noentity", "nolineofsight",
                    "nocamera", "collide_material", "collide_event", "collide_mode")


def _plain_collision_props(ids):
    """Blender 5.0 only: its glTF exporter leaves out properties registered by
    addons, so collision was lost. Copy them to plain custom properties (what
    the exporter writes) for the export; the caller removes them after."""
    added = []
    for idb in ids:
        rna = idb.bl_rna.properties
        for k in _COLLISION_PROPS:
            if k not in rna or k in idb.keys():
                continue
            v = getattr(idb, k)
            if rna[k].type == "ENUM":
                v = rna[k].enum_items[v].value if v in rna[k].enum_items else 0
            idb[k] = int(v)
            added.append((idb, k))
    return added


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
    plain = []
    if bpy.app.version[:2] == (5, 0):
        ids = set()
        for o in exported_meshes(level_col):
            ids.add(o)
            ids.update(s.material for s in o.material_slots if s.material)
        plain = _plain_collision_props(ids)
    try:
        idx = list(geo.exporters).index(ex)
        with bpy.context.temp_override(collection=geo):
            r = bpy.ops.collection.exporter_export(index=idx)
        if "FINISHED" not in r:
            raise RuntimeError(f"glTF export of {geo.name} failed")
    finally:
        for parent, ch in unlinked:
            parent.children.link(ch)
        for idb, k in plain:              # Blender 5.0 copies, only for the export
            if k in idb.keys():
                del idb[k]
