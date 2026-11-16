# ---------------------------------------------------------------------------
# path_curves.py — OpenGOAL Level Tools
# Path additions (Path panel of actors / cameras):
#   - Add Curve: a new curve linked to the path, options in Adjust Last
#     Operation (type, shape, points, cyclic, endpoints, size, rotation).
#   - Edit: select a path source; a curve goes into Edit Mode.
#   - Path curves live in the level's "Paths" collection (new, linked, and
#     Sort & Clean for every curve a path uses). Tagged og_path_curve.
# The game reads NURBS paths as non-rational cubic B-splines (export
# path_modes), so circles are made of points that keep the curve round
# without weights: 8 points on a looped cubic are within 0.12 % of a circle.
# ---------------------------------------------------------------------------
from __future__ import annotations

import math
import numpy as np
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, StringProperty

TAG = "og_path_curve"

# default points per (type, shape); None = fixed by the shape (hidden)
_POINTS = {("NURBS", "CIRCLE"): None, ("NURBS", "LINE"): 4, ("NURBS", "POINT"): None, ("NURBS", "HALF"): None,
           ("POLY", "CIRCLE"): 8, ("POLY", "LINE"): 2, ("POLY", "POINT"): None, ("POLY", "HALF"): 4,
           ("BEZIER", "CIRCLE"): None, ("BEZIER", "LINE"): 2, ("BEZIER", "POINT"): None, ("BEZIER", "HALF"): None}
_MIN_POINTS = {("NURBS", "LINE"): 4, ("POLY", "CIRCLE"): 3, ("POLY", "LINE"): 2, ("POLY", "HALF"): 2,
               ("BEZIER", "LINE"): 2}
_CYCLIC = {"CIRCLE": True, "LINE": False, "POINT": False, "HALF": False}
_ENDPOINT = {"CIRCLE": False, "LINE": True, "POINT": True, "HALF": True}
_BEZIER_K = 4.0 / 3.0 * math.tan(math.pi / 8)       # circle handle length / radius (quarter arcs)


# ── shapes (local XY, centred on the object's origin; lines along +X) ───────

def nurbs_circle(r, n=8):
    """n control points of a looped uniform cubic B-spline whose curve has
    radius r on average (it's between the control-point and mid-segment
    radii, 0.12 % apart for 8 points)."""
    th = 2 * math.pi / n
    f_cp = (4 + 2 * math.cos(th)) / 6
    f_mid = (23 * math.cos(th / 2) + math.cos(3 * th / 2)) / 24
    R = r / ((f_cp + f_mid) / 2)
    return [(R * math.cos(i * th), R * math.sin(i * th), 0.0) for i in range(n)]


def _bspline_basis(knots, n, t, p=3):
    """Cubic B-spline basis values N_i(t), i < n (Cox-de Boor)."""
    N = np.array([1.0 if knots[i] <= t < knots[i + 1] else 0.0 for i in range(len(knots) - 1)])
    if t >= knots[-1]:
        N[:] = 0.0
        N[n - 1] = 1.0
        return N[:n]
    for d in range(1, p + 1):
        M = np.zeros(len(knots) - 1 - d)
        for i in range(len(M)):
            a = knots[i + d] - knots[i]
            b = knots[i + d + 1] - knots[i + 1]
            M[i] = ((t - knots[i]) / a * N[i] if a else 0.0) + ((knots[i + d + 1] - t) / b * N[i + 1] if b else 0.0)
        N = M
    return N[:n]


def nurbs_half_circle(r, tol=0.002):
    """Fewest control points (clamped cubic, ends on the arc) whose curve
    stays within tol x r of the half circle (0 to 180 degrees)."""
    for n in range(4, 17):
        knots = [0.0] * 4 + list(range(1, n - 3)) + [float(n - 3)] * 4
        ts = np.linspace(0, n - 3, 80)
        ang = np.linspace(0, math.pi, 80)          # parameter spread evenly over the arc
        A = np.array([_bspline_basis(knots, n, t) for t in ts])
        target = np.stack([r * np.cos(ang), r * np.sin(ang)], 1)
        # ends fixed on the arc, inner points by least squares
        fixed = A[:, [0, n - 1]] @ np.array([[r, 0.0], [-r, 0.0]])
        inner, *_ = np.linalg.lstsq(A[:, 1:n - 1], target - fixed, rcond=None)
        P = np.vstack([[r, 0.0], inner, [-r, 0.0]])
        dense = np.array([_bspline_basis(knots, n, t) for t in np.linspace(0, n - 3, 400)]) @ P
        err = np.abs(np.hypot(dense[:, 0], dense[:, 1]) - r).max()
        if err <= tol * r:
            break
    return [(x, y, 0.0) for x, y in P]


def poly_points(shape, r, length, n):
    if shape == "CIRCLE":
        return [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n), 0.0) for i in range(n)]
    if shape == "HALF":
        return [(r * math.cos(math.pi * i / (n - 1)), r * math.sin(math.pi * i / (n - 1)), 0.0) for i in range(n)]
    if shape == "LINE":
        return [(length * i / (n - 1), 0.0, 0.0) for i in range(n)]
    return [(0.0, 0.0, 0.0)]


def bezier_points(shape, r, length, n):
    """[(co, handle_left, handle_right)] (None handles = VECTOR)."""
    k = _BEZIER_K * r
    if shape in ("CIRCLE", "HALF"):
        count = 4 if shape == "CIRCLE" else 3
        out = []
        for i in range(count):
            a = math.pi / 2 * i
            c, s = math.cos(a), math.sin(a)
            co = (r * c, r * s, 0.0)
            tan = (-s * k, c * k, 0.0)
            out.append((co, (co[0] - tan[0], co[1] - tan[1], 0.0), (co[0] + tan[0], co[1] + tan[1], 0.0)))
        return out
    if shape == "LINE":
        return [((length * i / (n - 1), 0.0, 0.0), None, None) for i in range(n)]
    return [((0.0, 0.0, 0.0), None, None)]


# ── building / linking ──────────────────────────────────────────────────────

def build_curve(name, ctype, shape, n, cyclic, endpoint, size):
    """A new curve object (not linked to a scene)."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    r, length = size / 2.0, size
    sp = cu.splines.new("BEZIER" if ctype == "BEZIER" else ctype)
    if ctype == "BEZIER":
        pts = bezier_points(shape, r, length, n)
        sp.bezier_points.add(len(pts) - 1)
        for bp, (co, hl, hr) in zip(sp.bezier_points, pts):
            bp.co = co
            if hl is None:
                bp.handle_left_type = bp.handle_right_type = "VECTOR"
            else:
                bp.handle_left_type = bp.handle_right_type = "ALIGNED"
                bp.handle_left, bp.handle_right = hl, hr
    else:
        if ctype == "NURBS":
            pts = {"CIRCLE": lambda: nurbs_circle(r), "HALF": lambda: nurbs_half_circle(r),
                   "LINE": lambda: poly_points("LINE", r, length, n),
                   "POINT": lambda: [(0.0, 0.0, 0.0)]}[shape]()
        else:
            pts = poly_points(shape, r, length, n)
        sp.points.add(len(pts) - 1)
        for p, co in zip(sp.points, pts):
            p.co = (*co, 1.0)
        if ctype == "NURBS":
            sp.order_u = 4
            sp.use_endpoint_u = endpoint
    sp.use_cyclic_u = cyclic
    return bpy.data.objects.new(name, cu)


def to_paths_collection(scene, obj):
    """Tag a path curve and move it to the level's Paths collection."""
    from .collections import _link_object_to_sub_collection, _COL_PATH_PATHS
    obj[TAG] = True
    _link_object_to_sub_collection(scene, obj, *_COL_PATH_PATHS)


def path_curves_of(objs):
    """Every curve used by the paths (main + extra) of objs."""
    out = []
    for o in objs:
        lists = [getattr(o, "og_waypoint_sources", ())] + [x.sources for x in getattr(o, "og_extra_paths", ())]
        for lst in lists:
            for s in lst:
                if s.obj is not None and s.obj.type == "CURVE" and s.obj not in out:
                    out.append(s.obj)
    return out


def curve_name(owner, path_index):
    """PATH_<actor without ACTOR_>_<path lump> (Blender adds .001 ...)."""
    base = owner.name[len("ACTOR_"):] if owner.name.startswith("ACTOR_") else owner.name
    if path_index >= 0:
        lump = owner.og_extra_paths[path_index].name.strip() or "path"
    else:
        lump = (getattr(owner, "og_path_lump", "") or "path").strip()
    return f"PATH_{base}_{lump}"


# ── operators ───────────────────────────────────────────────────────────────

def _shape_update(self, ctx):
    self.cyclic = _CYCLIC[self.shape]
    self.endpoint = _ENDPOINT[self.shape]
    _points_update(self, ctx)


def _points_update(self, ctx):
    d = _POINTS.get((self.curve_type, self.shape))
    if d is not None:
        self.points = d


class OG_OT_AddPathCurve(bpy.types.Operator):
    """Add a new curve to this path (at the 3D cursor, or at the actor with At Actor Position on).
Its type, shape, points ... are in the Adjust Last Operation panel"""
    bl_idname = "og.add_path_curve"
    bl_label = "Add Path Curve"
    bl_options = {"REGISTER", "UNDO"}

    owner_name: StringProperty(options={"HIDDEN"})
    path_index: IntProperty(default=-1, options={"HIDDEN"})
    curve_type: EnumProperty(name="Curve Type", default="NURBS", update=_points_update,
                             items=[("NURBS", "NURBS", "Smooth curve (the game's smooth paths)"),
                                    ("POLY", "Poly", "Straight lines between the points"),
                                    ("BEZIER", "Bézier", "Bézier curve with handles")])
    shape: EnumProperty(name="Curve Shape", default="LINE", update=_shape_update,
                        items=[("CIRCLE", "Circle", ""), ("LINE", "Straight Line", ""),
                               ("POINT", "Single Point", ""), ("HALF", "Half Circle", "")])
    points: IntProperty(name="Number of Points", default=4, min=1, max=256)
    cyclic: BoolProperty(name="Cyclic", default=False)
    endpoint: BoolProperty(name="Endpoints", default=True,
                           description="NURBS: the curve starts and ends on its first / last point")
    size: FloatProperty(name="Size", default=2.0, min=0.01, unit="LENGTH",
                        description="Circle / half circle: diameter. Straight line: length")
    rotation: FloatVectorProperty(name="Rotation", subtype="EULER", size=3, default=(0.0, 0.0, 0.0),
                                  description="0, 0, 0: flat on the XY plane")

    def draw(self, ctx):
        l = self.layout
        l.use_property_split = True
        l.prop(self, "curve_type")
        l.prop(self, "shape")
        key = (self.curve_type, self.shape)
        if _POINTS.get(key) is not None:
            l.prop(self, "points")
        l.prop(self, "cyclic")
        if self.curve_type == "NURBS":
            l.prop(self, "endpoint")
        if self.shape != "POINT":
            l.prop(self, "size", text="Diameter" if self.shape in ("CIRCLE", "HALF") else "Length")
        l.prop(self, "rotation")

    def execute(self, ctx):
        from .operators.links import _path_list
        owner = bpy.data.objects.get(self.owner_name)
        if owner is None:
            self.report({"ERROR"}, "No actor"); return {"CANCELLED"}
        coll, holder, attr = _path_list(owner, self.path_index)
        if coll is None:
            self.report({"ERROR"}, "That path no longer exists"); return {"CANCELLED"}
        key = (self.curve_type, self.shape)
        n = max(self.points, _MIN_POINTS.get(key, 1))
        ob = build_curve(curve_name(owner, self.path_index), self.curve_type, self.shape, n,
                         self.cyclic, self.endpoint, self.size)
        at_actor = ctx.scene.og_props.waypoint_spawn_at_actor
        ob.location = owner.matrix_world.translation.copy() if at_actor else ctx.scene.cursor.location.copy()
        ob.rotation_euler = self.rotation
        ctx.scene.collection.objects.link(ob)
        to_paths_collection(ctx.scene, ob)
        src = coll.add()
        src.obj = ob
        setattr(holder, attr, len(coll) - 1)
        sp = ob.data.splines[0]
        if self.curve_type == "NURBS" and sp.order_u != 4:
            self.report({"WARNING"}, f"{ob.name}: Blender keeps Order U at {sp.order_u} with "
                                     f"{len(sp.points)} point(s); set it to 4 once the curve has 4+ points")
        else:
            self.report({"INFO"}, f"Added {ob.name} to {owner.name}")
        return {"FINISHED"}


class OG_OT_WaypointSourceEdit(bpy.types.Operator):
    """Edit the highlighted path source: a curve is selected and goes into Edit Mode, a waypoint empty is selected"""
    bl_idname = "og.waypoint_source_edit"
    bl_label = "Edit Path Source"
    bl_options = {"REGISTER", "UNDO"}
    path_index: IntProperty(default=-1)

    def execute(self, ctx):
        from .operators.links import _path_list, _get_actor_for_waypoint_ops
        owner = _get_actor_for_waypoint_ops(ctx)
        if owner is None:
            return {"CANCELLED"}
        coll, holder, attr = _path_list(owner, self.path_index)
        idx = getattr(holder, attr) if holder is not None else -1
        if coll is None or not (0 <= idx < len(coll)) or coll[idx].obj is None:
            return {"CANCELLED"}
        o = coll[idx].obj
        if o.name not in ctx.view_layer.objects:
            self.report({"WARNING"}, f"{o.name} isn't in this view layer"); return {"CANCELLED"}
        if ctx.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for x in ctx.selected_objects:
            x.select_set(False)
        o.hide_set(False)
        o.select_set(True)
        ctx.view_layer.objects.active = o
        if o.type == "CURVE":
            bpy.ops.object.mode_set(mode="EDIT")
        return {"FINISHED"}


CLASSES = (OG_OT_AddPathCurve, OG_OT_WaypointSourceEdit)
