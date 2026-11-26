"""Oceans panel: custom ocean maps (the game's ocean-map) for the levels' Ocean setting.

A map is a fixed grid of 48 x 48 cells of 96 m (6 x 6 squares of 768 m, 8 x 8 cells each),
drawn at y = 0, plus a ring of "far" ocean around it in one colour. Here it is a grid mesh
(one face per cell): faces with the "Ocean water" material have ocean, "No water" ones
don't; its OceanColor colour attribute (one per grid point) colours the water, blended
across each cell. Water and colour can also come from one of the game's maps. Exported by
export/oceans_export.py, always loaded (GAME.CGO) or with the levels that use it.
"""
from __future__ import annotations

import re

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatVectorProperty, IntProperty,
                       PointerProperty, StringProperty)

CELL = 96.0                      # m
CELLS = 48                       # per side
HALF = CELL * CELLS / 2          # 2304 m: the grid mesh's origin is its centre
COLOR_ATTR = "OceanColor"
MAT_WATER, MAT_NONE = "OG Ocean Water", "OG Ocean No Water"
DEFAULT_COLOR = (0x1F / 255, 0x32 / 255, 0x42 / 255)     # the most used vanilla ocean colour
VANILLA = ("village1", "village2", "sunken")
_FROM = [("own", "Own", "From the grid mesh")] + [(v, f"{v} (game)", f"The game's *ocean-map-{v}* data") for v in VANILLA]
_PLACE = [("game", "Always loaded", "In GAME.CGO (like moods): one copy for every level; a change means a full build"),
          ("level", "With its levels", "In the code of each level that uses it: level-only builds; one copy per level")]


def clean(s):
    return re.sub(r"[^a-z0-9-]+", "-", s.strip().lower()).strip("-")


class OGOcean(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="", description="The map is *<name>-ocean-map* in the game")
    export: BoolProperty(name="Export", default=True)
    expanded: BoolProperty(default=True)
    show_grid: BoolProperty(default=False)
    show_water: BoolProperty(default=False)
    show_color: BoolProperty(default=False)
    far_color: FloatVectorProperty(name="Far colour", subtype="COLOR_GAMMA", size=3, min=0.0, max=1.0,
                                   default=DEFAULT_COLOR,
                                   description="The ocean beyond the grid (the game's 0-255 values; 128 = full brightness)")
    grid: PointerProperty(type=bpy.types.Object, name="Grid mesh",
                          description="The grid mesh: one face per 96 m cell, its centre is the map's centre")
    water_from: EnumProperty(name="Water", items=_FROM, default="own",
                             description="Which cells have ocean: the grid mesh's materials, or a game map's")
    color_from: EnumProperty(name="Colour", items=_FROM, default="own",
                             description="The ocean colours: the grid mesh's OceanColor attribute, or a game map's")
    place: EnumProperty(name="Loaded", items=_PLACE, default="game")


def map_symbol(o):
    return f"*{clean(o.name)}-ocean-map*"


# ── the grid mesh ──────────────────────────────────────────────────────────

def _material(name, color):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.diffuse_color = color                      # viewport colour (Solid view)
    return m


def make_grid(ctx, o):
    """A 48 x 48 face mesh of 96 m at y = 0, centred on the 3D cursor (x / y), all water."""
    from .collections import _active_level_col, _ensure_sub_collection
    n = CELLS + 1
    verts = [(i * CELL - HALF, j * CELL - HALF, 0.0) for j in range(n) for i in range(n)]
    faces = [(j * n + i, j * n + i + 1, (j + 1) * n + i + 1, (j + 1) * n + i) for j in range(CELLS) for i in range(CELLS)]
    me = bpy.data.meshes.new(f"OCEAN_{clean(o.name)}")
    me.from_pydata(verts, [], faces)
    me.materials.append(_material(MAT_WATER, (0.1, 0.35, 0.8, 1.0)))
    me.materials.append(_material(MAT_NONE, (0.0, 0.0, 0.0, 0.25)))
    ca = me.color_attributes.new(COLOR_ATTR, "BYTE_COLOR", "POINT")
    c = (*o.far_color, 128 / 255)
    for d in ca.data:
        d.color_srgb = c
    me.update()
    ob = bpy.data.objects.new(me.name, me)
    cur = ctx.scene.cursor.location
    ob.location = (cur.x, cur.y, 0.0)
    ob.lock_location[2] = True
    ob.lock_rotation = (True, True, True)
    ob.lock_scale = (True, True, True)
    ob.display_type = "SOLID"
    ob.show_wire = True
    lv = _active_level_col(ctx.scene)
    if lv is not None:
        c = _ensure_sub_collection(lv, "Ocean")
        c["skip_export"] = True                       # not level geometry
    else:
        c = ctx.scene.collection
    c.objects.link(ob)
    o.grid = ob
    return ob


def set_faces(g, mi, selected=False):
    """Material mi (0 water, 1 no water) on the grid's faces (only the selected ones if asked).
    In Edit Mode through bmesh, so leaving Edit Mode keeps it. Returns how many changed."""
    import bmesh
    n = 0
    if g.mode == "EDIT":
        bm = bmesh.from_edit_mesh(g.data)
        for f in bm.faces:
            if (f.select or not selected) and f.material_index != mi:
                f.material_index = mi
                n += 1
        bmesh.update_edit_mesh(g.data)
    else:
        for f in g.data.polygons:
            if (f.select or not selected) and f.material_index != mi:
                f.material_index = mi
                n += 1
        g.data.update()
    return n


def cell_of(g, p):
    """(col, row) of a world point on the grid (game axes: row along game z = -Blender y)."""
    t = g.matrix_world.translation
    return int((p.x - t.x + HALF) // CELL), int((-(p.y - t.y) + HALF) // CELL)


def point_of(g, p):
    t = g.matrix_world.translation
    return int(round((p.x - t.x + HALF) / CELL)), int(round((-(p.y - t.y) + HALF) / CELL))


def load_template(ctx, o, name):
    """Water cells, colours and far colour of a game map onto the grid (made if missing)."""
    from . import db as _db
    v = _db.vanilla_oceans().get(name)
    if v is None:
        return False
    g = o.grid if o.grid is not None and o.grid.type == "MESH" else make_grid(ctx, o)
    if g.mode == "EDIT":
        bpy.ops.object.mode_set(mode="OBJECT")
    me = g.data
    mw = g.matrix_world
    for f in me.polygons:
        c, r = cell_of(g, mw @ f.center)
        if 0 <= c < CELLS and 0 <= r < CELLS:
            f.material_index = 0 if v["water"][r][c] == "1" else 1
    ca = me.color_attributes.get(COLOR_ATTR) or me.color_attributes.new(COLOR_ATTR, "BYTE_COLOR", "POINT")
    for vert, d in zip(me.vertices, ca.data):
        c, r = point_of(g, mw @ vert.co)
        if 0 <= c <= CELLS and 0 <= r <= CELLS:
            h = v["colors"][r][c * 6:c * 6 + 6]
            d.color_srgb = (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, 128 / 255)
    o.far_color = [min(1.0, x / 255) for x in v["far"]]
    o.water_from = o.color_from = "own"
    me.update()
    return True


def grid_problems(o):
    g = o.grid
    if o.water_from != "own" and o.color_from != "own":
        return []
    if g is None or g.type != "MESH":
        return ["no grid mesh (Make Grid Mesh)"]
    out = []
    if len(g.data.polygons) != CELLS * CELLS:
        out.append(f"the grid mesh needs {CELLS * CELLS} faces (it has {len(g.data.polygons)})")
    if any(abs(s - 1.0) > 1e-4 for s in g.scale) or any(abs(r) > 1e-4 for r in g.rotation_euler):
        out.append("the grid mesh is scaled or rotated (the game's grid can't be)")
    if abs(g.location.z) > 1e-3:
        out.append("grey: the sea is always at y = 0 in game")
    return out


# ── operators ──────────────────────────────────────────────────────────────

def _level_name(ctx):
    from .collections import _active_level_col, level_name
    col = _active_level_col(ctx.scene)
    return clean(level_name(col)) if col is not None else "my-level"


class OG_OT_OceanAdd(bpy.types.Operator):
    """Add a custom ocean map"""
    bl_idname = "og.ocean_add"
    bl_label = "Add Ocean Map"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        base = _level_name(ctx)                          # the map is *<level>-ocean-map*
        names = {o.name for o in ctx.scene.og_oceans}
        o = ctx.scene.og_oceans.add()
        o.name = base if base not in names else next(f"{base}-{k}" for k in range(2, 99) if f"{base}-{k}" not in names)
        return {"FINISHED"}


class OG_OT_OceanRemove(bpy.types.Operator):
    """Delete this ocean map (its grid mesh stays)"""
    bl_idname = "og.ocean_remove"
    bl_label = "Delete"
    bl_options = {"REGISTER", "UNDO"}
    index: IntProperty(options={"HIDDEN"})

    def execute(self, ctx):
        if 0 <= self.index < len(ctx.scene.og_oceans):
            ctx.scene.og_oceans.remove(self.index)
        return {"FINISHED"}


class OG_OT_OceanDuplicate(bpy.types.Operator):
    """Make a copy of it (with a copy of its grid mesh)"""
    bl_idname = "og.ocean_duplicate"
    bl_label = "Duplicate"
    bl_options = {"REGISTER", "UNDO"}
    index: IntProperty(options={"HIDDEN"})

    def execute(self, ctx):
        coll = ctx.scene.og_oceans
        if not (0 <= self.index < len(coll)):
            return {"CANCELLED"}
        src = coll[self.index]
        dst = coll.add()
        for k in ("export", "far_color", "water_from", "color_from", "place"):
            setattr(dst, k, getattr(src, k))
        names = {x.name for x in coll}
        dst.name = next(f"{src.name}-copy{'' if k == 1 else k}" for k in range(1, 99)
                        if f"{src.name}-copy{'' if k == 1 else k}" not in names)
        if src.grid is not None:
            g = src.grid.copy()
            g.data = src.grid.data.copy()
            g.name = g.data.name = f"OCEAN_{clean(dst.name)}"
            for c in src.grid.users_collection:
                c.objects.link(g)
            dst.grid = g
        coll.move(len(coll) - 1, self.index + 1)
        return {"FINISHED"}


class OG_OT_OceanMakeGrid(bpy.types.Operator):
    """Make the grid mesh: 48 x 48 faces of 96 m (one per cell) at y = 0, centred on the 3D cursor, all water"""
    bl_idname = "og.ocean_make_grid"
    bl_label = "Make Grid Mesh"
    bl_options = {"REGISTER", "UNDO"}
    index: IntProperty(options={"HIDDEN"})

    def execute(self, ctx):
        o = ctx.scene.og_oceans[self.index]
        make_grid(ctx, o)
        return {"FINISHED"}


class OG_OT_OceanFill(bpy.types.Operator):
    """Set every cell of the grid mesh (water / no water), or fill its colour"""
    bl_idname = "og.ocean_fill"
    bl_label = "Fill"
    bl_options = {"REGISTER", "UNDO"}
    index: IntProperty(options={"HIDDEN"})
    what: StringProperty(options={"HIDDEN"})          # water / none / color
    selected: BoolProperty(options={"HIDDEN"})         # only the selected faces (Edit Mode)

    def execute(self, ctx):
        o = ctx.scene.og_oceans[self.index]
        g = o.grid
        if g is None or g.type != "MESH":
            return {"CANCELLED"}
        me = g.data
        if self.what in ("water", "none"):
            n = set_faces(g, 0 if self.what == "water" else 1, self.selected)
            self.report({"INFO"}, f"{n} cell(s) changed")
            return {"FINISHED"}
        else:
            ca = me.color_attributes.get(COLOR_ATTR) or me.color_attributes.new(COLOR_ATTR, "BYTE_COLOR", "POINT")
            c = (*o.far_color, 128 / 255)
            for d in ca.data:
                d.color_srgb = c
        me.update()
        return {"FINISHED"}


class OG_OT_OceanCutOut(bpy.types.Operator):
    """Cells under the selected objects (seen from above, their bounding boxes) get No water: islands, the
    level's ground (Object Mode: select the objects, not the grid)"""
    bl_idname = "og.ocean_cut_out"
    bl_label = "Cut Out Under Selected Objects"
    bl_options = {"REGISTER", "UNDO"}
    index: IntProperty(options={"HIDDEN"})

    def execute(self, ctx):
        o = ctx.scene.og_oceans[self.index]
        g = o.grid
        if g is None or g.type != "MESH":
            return {"CANCELLED"}
        from mathutils import Vector
        boxes = []
        for ob in ctx.selected_objects:
            if ob == g:
                continue
            pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
            boxes.append((min(p.x for p in pts), max(p.x for p in pts), min(p.y for p in pts), max(p.y for p in pts)))
        if not boxes:
            self.report({"WARNING"}, "Select the objects to cut out (in Object Mode), not the grid")
            return {"CANCELLED"}
        if g.mode == "EDIT":
            bpy.ops.object.mode_set(mode="OBJECT")
        n = 0
        mw = g.matrix_world
        for f in g.data.polygons:
            c = mw @ f.center
            if f.material_index != 1 and any(x0 <= c.x <= x1 and y0 <= c.y <= y1 for x0, x1, y0, y1 in boxes):
                f.material_index = 1
                n += 1
        g.data.update()
        self.report({"INFO"}, f"{n} cell(s) cut out")
        return {"FINISHED"}


def _template_items(self, ctx):
    from . import db as _db
    out = [(k, f"{k} (game)", "") for k in _db.vanilla_oceans()]
    from .moods import _ITEMS
    _ITEMS.setdefault("otpl", [])[:] = [(a, b, c, i) for i, (a, b, c) in enumerate(out)]
    return _ITEMS["otpl"]


class OG_OT_OceanTemplate(bpy.types.Operator):
    """Fill the grid mesh from one of the game's oceans: its water / no water cells, colours and far colour
    (the grid stays where it is)"""
    bl_idname = "og.ocean_template"
    bl_label = "Template"
    bl_options = {"REGISTER", "UNDO"}
    bl_property = "pick"
    index: IntProperty(options={"HIDDEN"})
    pick: EnumProperty(name="Ocean", items=_template_items)

    def invoke(self, ctx, event):
        ctx.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, ctx):
        o = ctx.scene.og_oceans[self.index]
        if not load_template(ctx, o, self.pick):
            return {"CANCELLED"}
        self.report({"INFO"}, f"{map_symbol(o)}: from {self.pick}")
        return {"FINISHED"}


def _file_items(self, ctx):
    out = [(map_symbol(o), o.name, "") for o in ctx.scene.og_oceans if o.name]
    from .moods import _ITEMS
    _ITEMS.setdefault("oceans", [])[:] = [(a, b, c, i) for i, (a, b, c) in enumerate(out or [("", "(none in this file)", "")])]
    return _ITEMS["oceans"]


class OG_OT_LevelUseOcean(bpy.types.Operator):
    """Use one of this file's ocean maps for the active level"""
    bl_idname = "og.level_use_ocean"
    bl_label = "This File's Ocean"
    bl_options = {"REGISTER", "UNDO"}
    bl_property = "pick"
    pick: EnumProperty(name="Ocean", items=_file_items)

    def invoke(self, ctx, event):
        ctx.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, ctx):
        if not self.pick:
            return {"CANCELLED"}
        from .collections import _active_level_col
        col = _active_level_col(ctx.scene)
        if col is None:
            return {"CANCELLED"}
        col.og_level.ocean = "CUSTOM"
        col.og_level.ocean_custom = self.pick
        return {"FINISHED"}


def level_ocean(scene, col):
    """This file's ocean map a level uses (or None)."""
    if col is None or col.og_level.ocean != "CUSTOM":
        return None
    v = col.og_level.ocean_custom.strip().lstrip("'")
    return next((o for o in scene.og_oceans if map_symbol(o) == v), None)


def problems(scene):
    """[(index, text)] that stop the export (texts starting with 'grey:' don't)."""
    out, seen = [], set()
    for i, o in enumerate(scene.og_oceans):
        if not o.export:
            continue
        n = clean(o.name)
        if not n:
            out.append((i, "needs a name"))
        elif n in seen or n in VANILLA:
            out.append((i, f"name '{n}' is already used"))
        seen.add(n)
        out += [(i, t) for t in grid_problems(o)]
    return out


# ── drawing ────────────────────────────────────────────────────────────────

def _grey(layout, text, icon="NONE"):
    h = layout.row(); h.enabled = False; h.scale_y = 0.7
    h.label(text=text, icon=icon)


def _fold(box, o, prop, text):
    r = box.row()
    r.prop(o, prop, text=text, emboss=False, icon="TRIA_DOWN" if getattr(o, prop) else "TRIA_RIGHT")
    return getattr(o, prop)


def _draw_ocean(layout, o, i, issues):
    box = layout.box()
    row = box.row(align=True)
    row.prop(o, "expanded", text="", emboss=False, icon="TRIA_DOWN" if o.expanded else "TRIA_RIGHT")
    row.prop(o, "export", text="")
    row.label(text=map_symbol(o))
    mine = [t for j, t in issues if j == i]
    if any(not t.startswith("grey:") for t in mine):
        w = row.row(); w.alert = True
        w.label(text=f"{sum(not t.startswith('grey:') for t in mine)}⚠")
    row.operator("og.ocean_duplicate", text="", icon="DUPLICATE", emboss=False).index = i
    row.operator("og.ocean_remove", text="", icon="X", emboss=False).index = i
    if not o.expanded:
        return
    for t in mine:
        if t.startswith("grey:"):
            _grey(box, t[5:].strip(), "INFO")
        else:
            w = box.row(); w.alert = True
            w.label(text=t, icon="ERROR")
    box.prop(o, "name")
    box.operator("og.ocean_template", text="Template from a game ocean…", icon="PRESET").index = i
    box.prop(o, "far_color")
    box.prop(o, "place")
    if _fold(box, o, "show_grid", "Grid"):
        b = box.box()
        r = b.row(align=True)
        r.prop(o, "grid", text="")
        r.operator("og.ocean_make_grid", text="", icon="MESH_GRID").index = i
        _grey(b, "48 x 48 cells of 96 m, at y = 0; move the mesh to move the ocean", "INFO")
    if _fold(box, o, "show_water", "Water"):
        b = box.box()
        b.prop(o, "water_from")
        if o.water_from == "own":
            _grey(b, f"Faces with '{MAT_WATER}' have ocean, '{MAT_NONE}' don't", "INFO")
            editing = o.grid is not None and o.grid.mode == "EDIT"
            r = b.row(align=True)
            if editing:                                   # the selected faces
                op = r.operator("og.ocean_fill", text="Selected: Water", icon="FACESEL"); op.index, op.what, op.selected = i, "water", True
                op = r.operator("og.ocean_fill", text="Selected: No Water"); op.index, op.what, op.selected = i, "none", True
                r = b.row(align=True)
            op = r.operator("og.ocean_fill", text="All Water"); op.index, op.what = i, "water"
            op = r.operator("og.ocean_fill", text="Clear"); op.index, op.what = i, "none"
            if not editing:
                _grey(b, "Edit Mode on the grid: buttons for the selected faces", "INFO")
            b.operator("og.ocean_cut_out", icon="MOD_BOOLEAN").index = i
    if _fold(box, o, "show_color", "Colour"):
        b = box.box()
        b.prop(o, "color_from")
        if o.color_from == "own":
            _grey(b, f"The grid mesh's '{COLOR_ATTR}' attribute (Vertex Paint), 128 = full brightness", "INFO")
            op = b.operator("og.ocean_fill", text="Fill with the Far Colour", icon="BRUSH_DATA")
            op.index, op.what = i, "color"


def draw(layout, ctx):
    sc = ctx.scene
    issues = problems(sc)
    for line in ("The water drawn around a level (a picture: swimming needs",
                 "water volumes). Pick it in Level > Settings > Visuals > Ocean."):
        _grey(layout, line)
    for i, o in enumerate(sc.og_oceans):
        _draw_ocean(layout, o, i, issues)
    layout.operator("og.ocean_add", icon="ADD")


class OG_PT_Oceans(bpy.types.Panel):
    bl_label = "🌊  Oceans"
    bl_idname = "OG_PT_oceans"
    bl_order = 6                 # registered right after Moods: drawn under it
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "OpenGOAL"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        draw(self.layout, ctx)


CLASSES = (OGOcean, OG_OT_OceanAdd, OG_OT_OceanRemove, OG_OT_OceanDuplicate, OG_OT_OceanMakeGrid, OG_OT_OceanFill,
           OG_OT_OceanCutOut, OG_OT_OceanTemplate, OG_OT_LevelUseOcean, OG_PT_Oceans)


# ── the 768 m squares outlined in the viewport (one batch, drawn at each grid) ──

_DRAW = {"handle": None, "batch": None}


def _squares_batch(sh):
    if _DRAW["batch"] is None:
        from gpu_extras.batch import batch_for_shader
        z = 0.2                                          # just above the faces
        pts = []
        for k in range(7):
            a = -HALF + k * 768.0
            pts += [(a, -HALF, z), (a, HALF, z), (-HALF, a, z), (HALF, a, z)]
        _DRAW["batch"] = batch_for_shader(sh, "LINES", {"pos": pts})
    return _DRAW["batch"]


def _draw_squares():
    sc = bpy.context.scene
    grids = [o.grid for o in getattr(sc, "og_oceans", ()) if o.grid is not None]
    if not grids:
        return
    import gpu
    vl = bpy.context.view_layer
    sh = gpu.shader.from_builtin("UNIFORM_COLOR")
    b = _squares_batch(sh)
    gpu.state.depth_test_set("LESS_EQUAL")
    gpu.state.line_width_set(2.0)
    sh.bind()
    sh.uniform_float("color", (0.2, 0.9, 1.0, 1.0))
    for g in grids:
        if g.name in vl.objects and g.visible_get():
            with gpu.matrix.push_pop():
                gpu.matrix.multiply_matrix(g.matrix_world)
                b.draw(sh)
    gpu.state.line_width_set(1.0)
    gpu.state.depth_test_set("NONE")


def register_props():
    bpy.types.Scene.og_oceans = CollectionProperty(type=OGOcean)
    if _DRAW["handle"] is None and not bpy.app.background:
        _DRAW["handle"] = bpy.types.SpaceView3D.draw_handler_add(_draw_squares, (), "WINDOW", "POST_VIEW")


def unregister_props():
    if _DRAW["handle"] is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_DRAW["handle"], "WINDOW")
        _DRAW["handle"] = None
    _DRAW["batch"] = None
    if hasattr(bpy.types.Scene, "og_oceans"):
        del bpy.types.Scene.og_oceans
