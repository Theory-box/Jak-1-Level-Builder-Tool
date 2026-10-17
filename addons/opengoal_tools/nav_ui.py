"""Nav-mesh panel extras: nav materials (jump faces -> :pat) and nav-spheres.

Nav materials: a nav-mesh gets "NAV Walk", "NAV Jump" and "NAV Special"
material slots; in Edit Mode assign faces to them. NAV Jump faces export as gap
triangles (:pat 1, nav-enemies jump across), NAV Special as :pat 2 (sharkey
water area, yakow pen). See export/navmesh.py NAV_MATERIALS.

Nav-spheres: empties listed on the nav-mesh (Object.og_nav_spheres). Each one
is an area the mesh's enemies steer around: its position, radius = display
size x scale. None by default.
"""
from __future__ import annotations

import bpy
from bpy.props import PointerProperty, CollectionProperty, IntProperty, StringProperty


def _is_empty(self, ob):
    return ob.type == "EMPTY"


class OGNavSphere(bpy.types.PropertyGroup):
    obj: PointerProperty(name="Sphere", type=bpy.types.Object, poll=_is_empty,
                         description="An empty: its position and display size x scale make the sphere")


NAV_ALPHA = 0.6        # see-through, so the level under the nav-mesh shows


def _linear(hexcol):
    """sRGB hex -> linear RGB (Blender colours are linear)."""
    def ch(v):
        v /= 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    h = hexcol.lstrip("#")
    return tuple(ch(int(h[i:i + 2], 16)) for i in (0, 2, 4))


def nav_material(name):
    """The nav material, its colour in the viewport colour (Solid mode) and in
    the Principled BSDF base colour (Material Preview / Rendered), see-through."""
    from .export.navmesh import NAV_MATERIALS
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    rgb = _linear(next(c for n, _p, c in NAV_MATERIALS if n == name))
    m.diffuse_color = (*rgb, NAV_ALPHA)
    m.use_nodes = True
    bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
        bsdf.inputs["Alpha"].default_value = NAV_ALPHA
    if hasattr(m, "surface_render_method"):
        m.surface_render_method = "BLENDED"
    elif hasattr(m, "blend_method"):
        m.blend_method = "BLEND"
    return m


def nav_display(obj):
    """A nav-mesh shows its faces in the nav colours, see-through, with its
    edges drawn on top (the wire it had before)."""
    obj.display_type = "SOLID"
    obj.show_wire = True


def ensure_nav_materials(obj):
    """The three nav materials as slots of a nav-mesh (existing faces keep theirs;
    a mesh without materials gets NAV Walk first, so its faces are walkable)."""
    from .export.navmesh import NAV_MATERIALS
    have = {s.material.name for s in obj.material_slots if s.material}
    for name, _p, _c in NAV_MATERIALS:
        m = nav_material(name)                  # (also refreshes the colours)
        if name not in have:
            obj.data.materials.append(m)
    nav_display(obj)


class OG_OT_NavMaterials(bpy.types.Operator):
    """Add the nav materials (NAV Walk / NAV Jump / NAV Special) to this nav-mesh:
in Edit Mode, assign faces to NAV Jump for gaps enemies jump across"""
    bl_idname = "og.nav_materials"
    bl_label = "Add Nav Materials"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        n = 0
        for o in ctx.selected_objects or [ctx.active_object]:
            if o is not None and o.type == "MESH":
                ensure_nav_materials(o)
                n += 1
        self.report({"INFO"}, f"Nav materials on {n} mesh(es)")
        return {"FINISHED"}


class OG_OT_NavSphereAdd(bpy.types.Operator):
    """Add a new nav-sphere empty at the 3D cursor to this nav-mesh"""
    bl_idname = "og.nav_sphere_add"
    bl_label = "New Nav-Sphere"
    bl_options = {"REGISTER", "UNDO"}
    mesh: StringProperty()

    def execute(self, ctx):
        nm = bpy.data.objects.get(self.mesh)
        if nm is None:
            return {"CANCELLED"}
        e = bpy.data.objects.new(f"NAVSPHERE_{nm.name[8:] if nm.name.startswith('NAVMESH_') else nm.name}", None)
        e.empty_display_type = "SPHERE"
        e.empty_display_size = 2.0
        e.location = ctx.scene.cursor.location
        for c in nm.users_collection:
            c.objects.link(e)
        nm.og_nav_spheres.add().obj = e
        return {"FINISHED"}


_EMPTY_ITEMS: list = []


class OG_OT_NavSpherePick(bpy.types.Operator):
    """Add an existing empty as a nav-sphere of this nav-mesh (search)"""
    bl_idname = "og.nav_sphere_pick"
    bl_label = "Add Empty as Nav-Sphere"
    bl_options = {"REGISTER", "UNDO"}
    bl_property = "empty"
    mesh: StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    def _items(self, context):
        items = [(o.name, o.name, "") for o in context.scene.objects if o.type == "EMPTY"]
        items = [(a, b, c, i) for i, (a, b, c) in enumerate(items)] or [("", "(no empties)", "", 0)]
        if items != _EMPTY_ITEMS:
            _EMPTY_ITEMS[:] = items
        return _EMPTY_ITEMS

    empty: bpy.props.EnumProperty(name="Empty", items=_items)

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        nm = bpy.data.objects.get(self.mesh)
        e = bpy.data.objects.get(self.empty)
        if nm is None or e is None:
            return {"CANCELLED"}
        if any(s.obj is e for s in nm.og_nav_spheres):
            return {"CANCELLED"}
        nm.og_nav_spheres.add().obj = e
        return {"FINISHED"}


class OG_OT_NavSphereRemove(bpy.types.Operator):
    """Remove this nav-sphere from the nav-mesh (the empty stays)"""
    bl_idname = "og.nav_sphere_remove"
    bl_label = "Remove Nav-Sphere"
    bl_options = {"REGISTER", "UNDO"}
    mesh: StringProperty()
    index: IntProperty()

    def execute(self, ctx):
        nm = bpy.data.objects.get(self.mesh)
        if nm is None or not 0 <= self.index < len(nm.og_nav_spheres):
            return {"CANCELLED"}
        nm.og_nav_spheres.remove(self.index)
        return {"FINISHED"}


class OG_OT_NavWire(bpy.types.Operator):
    """Show this nav-mesh as a plain wire, or as coloured faces (walk / jump / special) with its wire on top"""
    bl_idname = "og.nav_wire"
    bl_label = "Nav-Mesh Display"
    bl_options = {"REGISTER", "UNDO"}
    mesh: StringProperty()

    def execute(self, ctx):
        nm = bpy.data.objects.get(self.mesh)
        if nm is None:
            return {"CANCELLED"}
        if nm.display_type == "WIRE":
            nav_display(nm)
        else:
            nm.display_type = "WIRE"
        return {"FINISHED"}


def draw_nav_spheres(layout, nm):
    """Nav-spheres of a nav-mesh: a sub-menu, collapsed by default."""
    head, body = layout.panel(f"og_nav_spheres_{nm.name}", default_closed=True)
    head.label(text=f"Nav-Spheres ({len(nm.og_nav_spheres)})", icon="SPHERE")
    if body is None:
        return
    for i, s in enumerate(nm.og_nav_spheres):
        r = body.row(align=True)
        r.prop(s, "obj", text="")
        if s.obj is not None:
            r.label(text=f"r {s.obj.empty_display_size * max(s.obj.scale):.2f} m")
        op = r.operator("og.nav_sphere_remove", text="", icon="X"); op.mesh = nm.name; op.index = i
    r = body.row(align=True)
    r.operator("og.nav_sphere_add", text="New", icon="ADD").mesh = nm.name
    r.operator("og.nav_sphere_pick", text="Add Empty", icon="VIEWZOOM").mesh = nm.name
    h = body.row(); h.enabled = False; h.scale_y = 0.7
    h.label(text="Areas this mesh's enemies steer around (radius = size x scale)")


def draw_nav_extras(layout, nm):
    """Nav-mesh panel: jump faces + nav-spheres (collapsed sub-menu)."""
    from .export.navmesh import NAV_MATERIALS
    names = {s.material.name.split(".")[0] for s in nm.material_slots if s.material}
    box = layout.box()
    r = box.row(align=True)
    r.label(text="Jump faces", icon="MOD_DISPLACE")
    if not all(n in names for n, _p, _c in NAV_MATERIALS):
        r.operator("og.nav_materials", text="Add Nav Materials", icon="MATERIAL")
    r.operator("og.nav_wire", text="", icon="SHADING_WIRE" if nm.display_type != "WIRE" else "SHADING_SOLID").mesh = nm.name
    if nav_tri_count(nm) > 255:
        w = box.row(); w.alert = True
        w.operator("og.nav_reduce", text="Reduce to 255 Triangles", icon="MOD_DECIM").mesh = nm.name
    h = box.row(); h.enabled = False; h.scale_y = 0.7
    h.label(text="Edit Mode: faces on NAV Jump = gaps enemies jump (NAV Special: sharkey / yakow)")
    draw_nav_spheres(layout, nm)


# ── make a nav-mesh from faces / reduce one ──────────────────────────────────

class OGNavGenSettings(bpy.types.PropertyGroup):
    slope: bpy.props.FloatProperty(name="Max slope", default=0.785398, min=0.0, max=1.5708, subtype="ANGLE",
                                   description="Faces steeper than this are left out (walls)")
    lift: bpy.props.FloatProperty(name="Height", default=0.03, min=0.0, max=0.5, unit="LENGTH",
                                  description="Raised this much above the faces so they don't overlap")
    reduce: bpy.props.BoolProperty(name="Reduce to the limit", default=True,
                                   description="Simplify the result to the game's 255 triangles if it has more")


NAV_TARGET = 250       # under the game's 255, room for the triangulation


def nav_tri_count(obj):
    obj.data.calc_loop_triangles()
    return len(obj.data.loop_triangles)


def _apply_decimate(obj, ratio):
    """One collapse-decimate pass applied to the mesh (materials kept). It runs
    on a temporary object in the scene's own collection (a nav-mesh in a
    hidden / excluded collection evaluates to nothing); an empty result never
    replaces the mesh."""
    import bpy as _b
    sc = _b.context.scene
    tmp = _b.data.objects.new("og_nav_decimate_tmp", obj.data)
    sc.collection.objects.link(tmp)
    mod = tmp.modifiers.new("og_nav_decimate", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = max(0.01, min(1.0, ratio))
    try:
        _b.context.view_layer.update()
        dg = _b.context.evaluated_depsgraph_get()
        new = _b.data.meshes.new_from_object(tmp.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    finally:
        _b.data.objects.remove(tmp, do_unlink=True)
    if not len(new.polygons):
        _b.data.meshes.remove(new)
        return nav_tri_count(obj)
    old = obj.data
    obj.data = new
    if old.users == 0:
        _b.data.meshes.remove(old)
    return nav_tri_count(obj)


def decimate_nav_mesh(obj, ratio):
    """One collapse-decimate pass (materials kept)."""
    return _apply_decimate(obj, ratio)


def reduce_nav_mesh(obj, target=NAV_TARGET):
    """Collapse-decimate a mesh until it has <= target triangles (materials kept)."""
    for _ in range(8):
        n = nav_tri_count(obj)
        if n <= target:
            return n
        if _apply_decimate(obj, target / n * 0.98) >= n:
            break                        # nothing changed: stop
    return nav_tri_count(obj)


def _gen_faces(obj):
    """(bmesh, faces) to build from: the selected faces in Edit Mode, else all."""
    import bmesh
    if obj.mode == "EDIT":
        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.index_update()
        return bm, [f for f in bm.faces if f.select]
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    return bm, list(bm.faces)


class OG_OT_NavFromFaces(bpy.types.Operator):
    """Make a nav-mesh from this mesh's floor faces (the selected faces in Edit Mode): steep faces
are left out, the result is merged, raised a little and reduced to the game's limit"""
    bl_idname = "og.nav_from_faces"
    bl_label = "Make Nav-Mesh"
    bl_options = {"REGISTER", "UNDO"}

    # the Adjust Last Operation panel (bottom left): change and see the result
    slope: bpy.props.FloatProperty(name="Max slope", default=0.785398, min=0.0, max=1.5708, subtype="ANGLE",
                                   description="Faces steeper than this are left out (walls)")
    lift: bpy.props.FloatProperty(name="Height", default=0.03, min=0.0, max=0.5, unit="LENGTH",
                                  description="Raised this much above the faces so they don't overlap")
    reduce: bpy.props.BoolProperty(name="Reduce to the limit", default=True,
                                   description="Simplify the result to the game's 255 triangles if it has more")
    decimate: bpy.props.FloatProperty(name="Decimate", default=1.0, min=0.01, max=1.0, subtype="FACTOR",
                                      description="Simplify the result (1 = keep every triangle), also under the limit")
    result: bpy.props.IntProperty(options={"HIDDEN", "SKIP_SAVE"})

    def invoke(self, ctx, event):
        s = ctx.scene.og_navgen                  # start from the panel's settings
        self.slope, self.lift, self.reduce = s.slope, s.lift, s.reduce
        return self.execute(ctx)

    def draw(self, ctx):
        col = self.layout.column()
        col.prop(self, "slope")
        col.prop(self, "lift")
        col.prop(self, "decimate", slider=True)
        col.prop(self, "reduce")
        r = col.row(); r.alert = self.result > 255
        r.label(text=f"Result: {self.result} triangles" + (" (the game allows 255)" if self.result > 255 else ""),
                icon="MESH_DATA")

    @classmethod
    def poll(cls, ctx):
        o = ctx.active_object
        if o is None or o.type != "MESH":
            return False
        if o.mode == "EDIT":
            return o.data.total_face_sel > 0
        return len(o.data.polygons) > 0

    def execute(self, ctx):
        import bmesh, math
        from mathutils import Vector
        s = self
        sc_s = ctx.scene.og_navgen               # the panel keeps the last settings
        sc_s.slope, sc_s.lift, sc_s.reduce = self.slope, self.lift, self.reduce
        src = ctx.active_object
        mw = src.matrix_world
        rot = mw.to_3x3()
        bm, faces = _gen_faces(src)
        up = math.cos(s.slope)
        out = bmesh.new()
        vmap = {}
        kept = 0
        for f in faces:
            n = (rot @ f.normal).normalized()
            if n.z < up:
                continue
            vs = []
            for v in f.verts:
                if v.index not in vmap:
                    vmap[v.index] = out.verts.new((mw @ v.co) + Vector((0, 0, s.lift)))
                vs.append(vmap[v.index])
            try:
                out.faces.new(vs)
                kept += 1
            except ValueError:
                pass
        if src.mode != "EDIT":
            bm.free()
        if not kept:
            out.free()
            self.report({"WARNING"}, "No floor faces (all steeper than the max slope)")
            return {"CANCELLED"}
        bmesh.ops.remove_doubles(out, verts=out.verts, dist=0.01)
        bmesh.ops.triangulate(out, faces=out.faces)
        me = bpy.data.meshes.new(f"{src.name}_nav")
        out.to_mesh(me)
        out.free()
        if src.mode == "EDIT":
            bpy.ops.object.mode_set(mode="OBJECT")
        nm = bpy.data.objects.new(f"{src.name}_nav", me)
        ctx.scene.collection.objects.link(nm)
        from .operators.links import _link_navmesh
        _link_navmesh(ctx.scene, nm, [])
        if self.decimate < 1.0:
            decimate_nav_mesh(nm, self.decimate)
        n = reduce_nav_mesh(nm) if s.reduce else nav_tri_count(nm)
        self.result = n
        for o in ctx.selected_objects:
            o.select_set(False)
        nm.select_set(True)
        ctx.view_layer.objects.active = nm
        self.report({"WARNING"} if n > 255 else {"INFO"},
                    f"{nm.name}: {n} triangles from {kept} face(s)" + (" (over the game's 255: Reduce it)" if n > 255 else ""))
        return {"FINISHED"}


class OG_OT_NavReduce(bpy.types.Operator):
    """Simplify this nav-mesh to the game's limit (255 triangles); jump / special faces keep their material"""
    bl_idname = "og.nav_reduce"
    bl_label = "Reduce Nav-Mesh"
    bl_options = {"REGISTER", "UNDO"}
    mesh: StringProperty()

    def execute(self, ctx):
        nm = bpy.data.objects.get(self.mesh)
        if nm is None:
            return {"CANCELLED"}
        if nm.mode == "EDIT":
            bpy.ops.object.mode_set(mode="OBJECT")
        n = reduce_nav_mesh(nm)
        self.report({"INFO"}, f"{nm.name}: {n} triangles")
        return {"FINISHED"}


def draw_nav_generate(layout, obj):
    """Object Settings > NavMesh, for a mesh: make a nav-mesh from its faces."""
    s = bpy.context.scene.og_navgen
    box = layout.box()
    box.label(text="Make a nav-mesh from faces", icon="MOD_MESHDEFORM")
    col = box.column(align=True)
    col.prop(s, "slope")
    col.prop(s, "lift")
    box.prop(s, "reduce")
    edit = obj.mode == "EDIT"
    box.operator("og.nav_from_faces", text="From Selected Faces" if edit else "From All Faces", icon="ADD")
    if edit and obj.data.total_face_sel == 0:
        h = box.row(); h.enabled = False; h.scale_y = 0.7
        h.label(text="Select faces first")


CLASSES = (OGNavSphere, OGNavGenSettings, OG_OT_NavFromFaces, OG_OT_NavReduce, OG_OT_NavMaterials, OG_OT_NavWire, OG_OT_NavSphereAdd, OG_OT_NavSpherePick, OG_OT_NavSphereRemove)


def register_props():
    bpy.types.Object.og_nav_spheres = CollectionProperty(type=OGNavSphere)
    bpy.types.Scene.og_navgen = PointerProperty(type=OGNavGenSettings)


def unregister_props():
    if hasattr(bpy.types.Object, "og_nav_spheres"):
        del bpy.types.Object.og_nav_spheres
    if hasattr(bpy.types.Scene, "og_navgen"):
        del bpy.types.Scene.og_navgen
