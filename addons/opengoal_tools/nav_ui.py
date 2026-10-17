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
    h = box.row(); h.enabled = False; h.scale_y = 0.7
    h.label(text="Edit Mode: faces on NAV Jump = gaps enemies jump (NAV Special: sharkey / yakow)")
    draw_nav_spheres(layout, nm)


CLASSES = (OGNavSphere, OG_OT_NavMaterials, OG_OT_NavWire, OG_OT_NavSphereAdd, OG_OT_NavSpherePick, OG_OT_NavSphereRemove)


def register_props():
    bpy.types.Object.og_nav_spheres = CollectionProperty(type=OGNavSphere)


def unregister_props():
    if hasattr(bpy.types.Object, "og_nav_spheres"):
        del bpy.types.Object.og_nav_spheres
