# ---------------------------------------------------------------------------
# boundary_viz.py — OpenGOAL Level Tools
# Viewport-only visualization for LOADBND_ load-boundary objects.
#
# A Geometry Nodes modifier ("OG Boundary Viz") turns a boundary's flat
# polyline/face into a 3D wall (open) or filled area (closed) so the crossing
# surface is easy to see and edit in the viewport.
#
# The five controls the modifier reads are NOT modifier inputs — they are
# uniform mesh attributes written onto the object by the addon whenever the
# boundary's settings change:
#
#     top        FLOAT    wall extent up   (Blender metres)
#     bot        FLOAT    wall extent down (Blender metres, usually negative)
#     closed     BOOLEAN  mirrors og_lb_closed (open wall vs filled area)
#     flip       BOOLEAN  cosmetic — flip the wall's facing / arrows
#     wireframe  BOOLEAN  cosmetic — show as wireframe (delete faces)
#
# `top`/`bot` are the same values exported to :top/:bot in load-boundary-data.gc
# (export multiplies metres by 4096); `closed` mirrors the existing export flag.
# `flip` and `wireframe` are viewport-only and never touch export.
#
# Each control is read inside the node group via Named Attribute -> Sample Index
# (index 0 on the original input mesh). Sampling index 0 collapses the uniform
# attribute to a single value, which (a) is robust to attribute propagation
# through the Mesh->Curve->Mesh conversions and (b) is required because a
# Switch's condition socket takes a single value, not a per-element field.
#
# The modifier is stripped from all boundaries during geometry export and
# restored afterwards (see strip_viz_modifiers / restore_viz_modifiers).
# ---------------------------------------------------------------------------

import bpy
from bpy.app.handlers import persistent

NODE_GROUP_NAME = "OG_LoadBoundaryViz"
MODIFIER_NAME   = "OG Boundary Viz"

ATTR_TOP       = "top"
ATTR_BOT       = "bot"
ATTR_CLOSED    = "closed"
ATTR_FLIP      = "flip"
ATTR_WIREFRAME = "wireframe"

_BND_PREFIX = "LOADBND_"

# Defaults mirror the old geometry-derived flat-wall behaviour (WALL_UP /
# WALL_DN in collect_load_boundaries): up 30 m, down 128 m.
DEFAULT_TOP =  30.0
DEFAULT_BOT = -128.0


# ---------------------------------------------------------------------------
# Attribute writing (the addon stores; the modifier reads)
# ---------------------------------------------------------------------------

def _set_uniform_attr(me, name, data_type, value):
    """Create/replace a uniform POINT attribute and fill every vertex."""
    a = me.attributes.get(name)
    if a is not None and (a.domain != 'POINT' or a.data_type != data_type):
        me.attributes.remove(a)
        a = None
    if a is None:
        a = me.attributes.new(name=name, type=data_type, domain='POINT')
    n = len(me.vertices)
    if n == 0:
        return
    a.data.foreach_set("value", [value] * n)


def write_boundary_attrs(obj):
    """Write top/bot/closed/flip/wireframe as uniform attributes from og_lb_*.

    Safe to call any time; no-ops in Edit Mode or on empty/non-mesh data.
    """
    if obj is None or obj.type != 'MESH':
        return
    me = obj.data
    if me is None or obj.mode == 'EDIT' or len(me.vertices) == 0:
        return
    top  = float(getattr(obj, "og_lb_top",  DEFAULT_TOP))
    bot  = float(getattr(obj, "og_lb_bot",  DEFAULT_BOT))
    clsd = bool(getattr(obj, "og_lb_closed", False))
    flip = bool(getattr(obj, "og_lb_flip", False))
    wire = bool(getattr(obj, "og_lb_wireframe", False))
    _set_uniform_attr(me, ATTR_TOP,       'FLOAT',   top)
    _set_uniform_attr(me, ATTR_BOT,       'FLOAT',   bot)
    _set_uniform_attr(me, ATTR_CLOSED,    'BOOLEAN', clsd)
    _set_uniform_attr(me, ATTR_FLIP,      'BOOLEAN', flip)
    _set_uniform_attr(me, ATTR_WIREFRAME, 'BOOLEAN', wire)
    # Flag the mesh dirty so the Geometry Nodes modifier re-evaluates and the
    # viewport updates live when a setting changes.
    me.update_tag()


def _attrs_stale(obj):
    """True if the object is a boundary whose attrs are missing or wrong-length
    (e.g. verts added/removed in Edit Mode)."""
    if obj is None or obj.type != 'MESH' or not obj.name.startswith(_BND_PREFIX):
        return False
    me = obj.data
    if me is None or len(me.vertices) == 0:
        return False
    n = len(me.vertices)
    for name in (ATTR_TOP, ATTR_BOT, ATTR_CLOSED, ATTR_FLIP, ATTR_WIREFRAME):
        a = me.attributes.get(name)
        if a is None or a.domain != 'POINT' or len(a.data) != n:
            return True
    return False


# ---------------------------------------------------------------------------
# Property update callback (bound to og_lb_* in __init__.py)
# ---------------------------------------------------------------------------

def lb_setting_update(self, context):
    """Update callback for og_lb_top/bot/closed/flip/wireframe."""
    try:
        if self.type == 'MESH' and self.name.startswith(_BND_PREFIX):
            write_boundary_attrs(self)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Edit-mode-exit refresh handler
# ---------------------------------------------------------------------------

@persistent
def _refresh_on_edit(scene, depsgraph=None):
    """When a boundary's vertex count changes (Edit Mode edits), refill its
    uniform attributes so newly added verts carry the value."""
    obj = bpy.context.active_object
    if obj is None or obj.mode != 'OBJECT':
        return
    if _attrs_stale(obj):
        write_boundary_attrs(obj)


def register_handler():
    if _refresh_on_edit not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_refresh_on_edit)


def unregister_handler():
    if _refresh_on_edit in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_refresh_on_edit)


# ---------------------------------------------------------------------------
# Modifier management
# ---------------------------------------------------------------------------

def _find_viz_modifier(obj):
    for m in obj.modifiers:
        if m.type == 'NODES' and m.node_group is not None \
                and m.node_group.name == NODE_GROUP_NAME:
            return m
    return None


def add_modifier(obj):
    """Add the boundary-viz Geometry Nodes modifier (idempotent) and write the
    current settings as attributes so it has data to read."""
    if obj is None or obj.type != 'MESH':
        return None
    write_boundary_attrs(obj)
    mod = _find_viz_modifier(obj)
    if mod is None:
        ng = ensure_node_group()
        mod = obj.modifiers.new(name=MODIFIER_NAME, type='NODES')
        mod.node_group = ng
    return mod


def remove_modifier(obj):
    mod = _find_viz_modifier(obj)
    if mod is not None:
        obj.modifiers.remove(mod)


# ---------------------------------------------------------------------------
# Export strip / restore (call on the MAIN thread, around geometry export)
# ---------------------------------------------------------------------------

def strip_viz_modifiers(scene):
    """Remove the viz modifier from every LOADBND_ object. Returns the list of
    objects that had it, so they can be restored afterwards."""
    had = []
    for o in scene.objects:
        if o.type == 'MESH' and o.name.startswith(_BND_PREFIX):
            if _find_viz_modifier(o) is not None:
                remove_modifier(o)
                had.append(o)
    return had


def restore_viz_modifiers(objs):
    for o in objs:
        try:
            add_modifier(o)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Node group
# ---------------------------------------------------------------------------

def ensure_node_group():
    ng = bpy.data.node_groups.get(NODE_GROUP_NAME)
    if ng is None:
        ng = _build_node_group()
    return ng


def _build_node_group():
    ng = bpy.data.node_groups.new(type='GeometryNodeTree', name=NODE_GROUP_NAME)
    ng.is_modifier = True

    # Interface: Geometry in / Geometry out only. All controls are attributes.
    ng.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket(name="Geometry", in_out='INPUT',  socket_type='NodeSocketGeometry')

    nodes = ng.nodes
    links = ng.links

    def add(idname, name):
        n = nodes.new(idname)
        n.name = name
        return n

    # --- I/O ---
    group_input  = add("NodeGroupInput",  "Group Input")
    group_output = add("NodeGroupOutput", "Group Output")
    group_output.is_active_output = True

    # --- attribute reads: Named Attribute -> Sample Index (index 0) ---
    def read_attr(attr_name, data_type, tag):
        na = add("GeometryNodeInputNamedAttribute", f"Named Attribute {tag}")
        na.data_type = data_type
        na.inputs[0].default_value = attr_name
        si = add("GeometryNodeSampleIndex", f"Sample {tag}")
        si.data_type = data_type
        si.domain = 'POINT'
        # inputs: [0] Geometry, [1] Value, [2] Index
        links.new(group_input.outputs[0], si.inputs[0])
        links.new(na.outputs[0],          si.inputs[1])
        si.inputs[2].default_value = 0
        return si

    samp_top   = read_attr(ATTR_TOP,       'FLOAT',   "Top")
    samp_bot   = read_attr(ATTR_BOT,       'FLOAT',   "Bot")
    samp_clsd  = read_attr(ATTR_CLOSED,    'BOOLEAN', "Closed")
    samp_flip  = read_attr(ATTR_FLIP,      'BOOLEAN', "Flip")
    samp_wire  = read_attr(ATTR_WIREFRAME, 'BOOLEAN', "Wire")

    # --- open path: polyline -> wire mesh -> extrude into a wall ---
    mesh_to_curve = add("GeometryNodeMeshToCurve", "Mesh to Curve")
    mesh_to_curve.inputs[1].default_value = True
    links.new(group_input.outputs[0], mesh_to_curve.inputs[0])

    curve_to_mesh = add("GeometryNodeCurveToMesh", "Curve to Mesh")
    curve_to_mesh.inputs[2].default_value = False  # Fill Caps
    links.new(mesh_to_curve.outputs[0], curve_to_mesh.inputs[0])

    # height maths: extrude scale = top - bot ;  base offset Z = bot
    math_neg = add("ShaderNodeMath", "Math.001")
    math_neg.operation = 'MULTIPLY'
    math_neg.inputs[1].default_value = -1.0
    links.new(samp_bot.outputs[0], math_neg.inputs[0])

    math_add = add("ShaderNodeMath", "Math")
    math_add.operation = 'ADD'
    links.new(samp_top.outputs[0], math_add.inputs[0])
    links.new(math_neg.outputs[0], math_add.inputs[1])

    combine_xyz = add("ShaderNodeCombineXYZ", "Combine XYZ")
    combine_xyz.inputs[0].default_value = 0.0
    combine_xyz.inputs[1].default_value = 0.0
    links.new(samp_bot.outputs[0], combine_xyz.inputs[2])

    vector = add("FunctionNodeInputVector", "Vector")
    vector.vector = (0.0, 0.0, 1.0)

    extrude_mesh = add("GeometryNodeExtrudeMesh", "Extrude Mesh")
    extrude_mesh.mode = 'EDGES'
    extrude_mesh.inputs[1].default_value = True            # Selection
    links.new(curve_to_mesh.outputs[0], extrude_mesh.inputs[0])  # Mesh
    links.new(vector.outputs[0],        extrude_mesh.inputs[2])  # Offset
    links.new(math_add.outputs[0],      extrude_mesh.inputs[3])  # Offset Scale

    flip_faces = add("GeometryNodeFlipFaces", "Flip Faces")
    flip_faces.inputs[1].default_value = True
    links.new(extrude_mesh.outputs[0], flip_faces.inputs[0])

    switch = add("GeometryNodeSwitch", "Switch")
    switch.input_type = 'GEOMETRY'
    links.new(samp_flip.outputs[0],    switch.inputs[0])   # condition = flip
    links.new(extrude_mesh.outputs[0], switch.inputs[1])   # False
    links.new(flip_faces.outputs[0],   switch.inputs[2])   # True

    set_position = add("GeometryNodeSetPosition", "Set Position")
    set_position.inputs[1].default_value = True
    set_position.inputs[2].default_value = (0.0, 0.0, 0.0)
    links.new(switch.outputs[0],      set_position.inputs[0])
    links.new(combine_xyz.outputs[0], set_position.inputs[3])  # Offset

    join_geometry_001 = add("GeometryNodeJoinGeometry", "Join Geometry.001")
    links.new(set_position.outputs[0], join_geometry_001.inputs[0])

    # debug/legacy vector store, kept faithful to source graph
    store_norm = add("GeometryNodeStoreNamedAttribute", "Store Named Attribute")
    store_norm.data_type = 'FLOAT_VECTOR'
    store_norm.domain = 'FACE'
    store_norm.inputs[1].default_value = True
    store_norm.inputs[2].default_value = "myNorm"
    store_norm.inputs[3].default_value = (83.69999694824219, 95.99999237060547, 58.89999771118164)
    links.new(join_geometry_001.outputs[0], store_norm.inputs[0])

    reroute = add("NodeReroute", "Reroute")
    reroute.socket_idname = "NodeSocketGeometry"
    links.new(store_norm.outputs[0], reroute.inputs[0])

    # --- per-element pass: orient an arrow cone to the surface normal ---
    fe_in  = add("GeometryNodeForeachGeometryElementInput",  "For Each Geometry Element Input")
    fe_out = add("GeometryNodeForeachGeometryElementOutput", "For Each Geometry Element Output")
    fe_out.domain = 'FACE'
    fe_out.generation_items.clear()
    fe_out.generation_items.new('GEOMETRY', "Geometry")
    fe_out.generation_items[0].domain = 'POINT'
    fe_out.input_items.clear()
    fe_out.main_items.clear()
    fe_in.pair_with_output(fe_out)
    fe_in.inputs[1].default_value = True
    links.new(reroute.outputs[0], fe_in.inputs[0])

    bounding_box = add("GeometryNodeBoundBox", "Bounding Box")
    links.new(fe_in.outputs[1], bounding_box.inputs[0])

    mix = add("ShaderNodeMix", "Mix")
    mix.data_type = 'VECTOR'
    mix.inputs[0].default_value = 0.5
    links.new(bounding_box.outputs[1], mix.inputs[4])  # Min -> A
    links.new(bounding_box.outputs[2], mix.inputs[5])  # Max -> B

    points = add("GeometryNodePoints", "Points")
    points.inputs[0].default_value = 1
    points.inputs[1].default_value = (0.0, 0.0, 0.0)
    points.inputs[2].default_value = 0.10000000149011612

    set_position_001 = add("GeometryNodeSetPosition", "Set Position.001")
    set_position_001.inputs[1].default_value = True
    set_position_001.inputs[3].default_value = (0.0, 0.0, 0.0)
    links.new(points.outputs[0], set_position_001.inputs[0])
    links.new(mix.outputs[1],    set_position_001.inputs[2])  # Position

    cone = add("GeometryNodeMeshCone", "Cone")
    cone.fill_type = 'NGON'
    cone.inputs[0].default_value = 4
    cone.inputs[1].default_value = 1
    cone.inputs[2].default_value = 1
    cone.inputs[3].default_value = 0.0
    cone.inputs[4].default_value = 1.0
    cone.inputs[5].default_value = 2.0

    instance_on_points = add("GeometryNodeInstanceOnPoints", "Instance on Points")
    instance_on_points.inputs[1].default_value = True
    instance_on_points.inputs[3].default_value = False
    instance_on_points.inputs[4].default_value = 0
    instance_on_points.inputs[5].default_value = (0.0, 0.0, 0.0)
    instance_on_points.inputs[6].default_value = (1.0, 1.0, 1.0)
    links.new(set_position_001.outputs[0], instance_on_points.inputs[0])
    links.new(cone.outputs[0],             instance_on_points.inputs[2])

    normal_001 = add("GeometryNodeInputNormal", "Normal.001")

    sample_nearest_surface = add("GeometryNodeSampleNearestSurface", "Sample Nearest Surface")
    sample_nearest_surface.data_type = 'FLOAT_VECTOR'
    sample_nearest_surface.inputs[2].default_value = 0
    sample_nearest_surface.inputs[3].default_value = (0.0, 0.0, 0.0)
    sample_nearest_surface.inputs[4].default_value = 0
    links.new(fe_in.outputs[1],     sample_nearest_surface.inputs[0])  # Mesh
    links.new(normal_001.outputs[0], sample_nearest_surface.inputs[1]) # Value

    align = add("FunctionNodeAlignRotationToVector", "Align Rotation to Vector")
    align.axis = 'Z'
    align.pivot_axis = 'AUTO'
    align.inputs[0].default_value = (0.0, 0.0, 0.0)
    align.inputs[1].default_value = 1.0
    links.new(sample_nearest_surface.outputs[0], align.inputs[2])

    rotate_instances = add("GeometryNodeRotateInstances", "Rotate Instances")
    rotate_instances.inputs[1].default_value = True
    rotate_instances.inputs[3].default_value = (0.0, 0.0, 0.0)
    rotate_instances.inputs[4].default_value = True
    links.new(instance_on_points.outputs[0], rotate_instances.inputs[0])
    links.new(align.outputs[0],              rotate_instances.inputs[2])

    join_geometry = add("GeometryNodeJoinGeometry", "Join Geometry")
    links.new(rotate_instances.outputs[0], join_geometry.inputs[0])
    links.new(fe_in.outputs[1],            join_geometry.inputs[0])
    links.new(join_geometry.outputs[0],    fe_out.inputs[1])

    # --- closed path: fill the polygon flat ---
    set_spline_cyclic = add("GeometryNodeSetSplineCyclic", "Set Spline Cyclic.001")
    set_spline_cyclic.inputs[1].default_value = True
    set_spline_cyclic.inputs[2].default_value = True
    links.new(mesh_to_curve.outputs[0], set_spline_cyclic.inputs[0])

    fill_curve = add("GeometryNodeFillCurve", "Fill Curve")
    fill_curve.mode = 'NGONS'
    fill_curve.inputs[1].default_value = 0
    links.new(set_spline_cyclic.outputs[0], fill_curve.inputs[0])

    curve_to_mesh_001 = add("GeometryNodeCurveToMesh", "Curve to Mesh.001")
    curve_to_mesh_001.inputs[2].default_value = False
    links.new(fill_curve.outputs[0], curve_to_mesh_001.inputs[0])

    # --- open vs closed switch ---
    switch_002 = add("GeometryNodeSwitch", "Switch.002")
    switch_002.input_type = 'GEOMETRY'
    links.new(samp_clsd.outputs[0],        switch_002.inputs[0])  # condition = closed
    links.new(fe_out.outputs[2],           switch_002.inputs[1])  # False = open wall
    links.new(curve_to_mesh_001.outputs[0],switch_002.inputs[2])  # True  = filled area

    reroute_001 = add("NodeReroute", "Reroute.001")
    reroute_001.socket_idname = "NodeSocketGeometry"
    links.new(switch_002.outputs[0], reroute_001.inputs[0])

    delete_geometry = add("GeometryNodeDeleteGeometry", "Delete Geometry")
    delete_geometry.domain = 'FACE'
    delete_geometry.mode = 'ONLY_FACE'
    delete_geometry.inputs[1].default_value = True
    links.new(reroute_001.outputs[0], delete_geometry.inputs[0])

    # --- wireframe switch ---
    switch_001 = add("GeometryNodeSwitch", "Switch.001")
    switch_001.input_type = 'GEOMETRY'
    links.new(samp_wire.outputs[0],       switch_001.inputs[0])  # condition = wireframe
    links.new(reroute_001.outputs[0],     switch_001.inputs[1])  # False = solid
    links.new(delete_geometry.outputs[0], switch_001.inputs[2])  # True  = faces deleted
    links.new(switch_001.outputs[0],      group_output.inputs[0])

    return ng
