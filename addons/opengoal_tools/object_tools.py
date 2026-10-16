"""Object Controls tools: Set to floor, Distribute along curve, Export
selected definitions."""
from __future__ import annotations

import bpy
from bpy.props import FloatProperty, BoolProperty, EnumProperty, PointerProperty, StringProperty
from mathutils import Vector, Matrix

_SKIP_PREFIXES = ("VOL_", "LOADBND_")       # not ground


class OGFloorSettings(bpy.types.PropertyGroup):
    offset: FloatProperty(name="Distance", default=0.0, unit="LENGTH",
                          description="Height above the ground (e.g. floating orbs)")
    align: BoolProperty(name="Align to floor", default=False,
                        description="Tilt the object so its up axis follows the ground's slope")
    point: EnumProperty(name="Mesh point", default="BOTTOM",
                        items=[("BOTTOM", "Lowest vertex", "Meshes: their lowest point touches the ground"),
                               ("ORIGIN", "Origin", "Meshes: their origin touches the ground (like empties)")],
                        description="Which point of a mesh is put on the ground")
    above: FloatProperty(name="Search from above", default=1.0, min=0.0, unit="LENGTH",
                         description="The ray starts this far above the object, so one slightly under the ground still finds it")


def _bottom_drop(o, point):
    """Distance from the origin down to the point that goes on the ground."""
    if o.type != "MESH" or point == "ORIGIN" or not o.data.vertices:
        return 0.0
    mw = o.matrix_world
    return o.matrix_world.translation.z - min((mw @ v.co).z for v in o.data.vertices)


def _ignored(scene):
    def ignore(hit):
        return bool(hit.name.startswith(_SKIP_PREFIXES) or hit.name.startswith("NAVMESH_") or hit.get("og_navmesh")
                    or hit.get("og_preview_mesh") or hit.get("og_waypoint_preview_mesh"))
    return ignore


def find_floor(scene, depsgraph, start, skip, max_hits=32):
    """(location, normal) of the first ground below `start`, skipping objects
    in `skip` and helpers (volumes, previews ...). None if nothing below."""
    ignore = _ignored(scene)
    origin = Vector(start)
    for _ in range(max_hits):
        ok, loc, normal, _i, hit, _m = scene.ray_cast(depsgraph, origin, Vector((0, 0, -1)))
        if not ok:
            return None
        if hit in skip or (hit.parent is not None and hit.parent in skip) or ignore(hit):
            origin = loc - Vector((0, 0, 1e-4))
            continue
        return loc, normal
    return None


class OG_OT_SetToFloor(bpy.types.Operator):
    """Put the selected objects on the ground below them (Object Controls > Set to Floor settings)"""
    bl_idname = "og.set_to_floor"
    bl_label = "Set to Floor"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, ctx):
        return bool(ctx.selected_objects) and ctx.mode == "OBJECT"

    def execute(self, ctx):
        s = ctx.scene.og_floor
        dg = ctx.evaluated_depsgraph_get()
        objs = [o for o in ctx.selected_objects
                if not (o.get("og_preview_mesh") or o.get("og_waypoint_preview_mesh"))]
        objs = [o for o in objs if o.parent not in objs]          # children move with their parent
        skip = set(ctx.selected_objects)
        moved, missed = 0, []
        for o in objs:
            drop = _bottom_drop(o, s.point)
            pos = o.matrix_world.translation.copy()
            start = Vector((pos.x, pos.y, pos.z - drop + s.above))
            hit = find_floor(ctx.scene, dg, start, skip)
            if hit is None:
                missed.append(o.name)
                continue
            loc, normal = hit
            mw = o.matrix_world.copy()
            if s.align:
                q = Vector((0, 0, 1)).rotation_difference(normal)
                # keep the current turn around Z, tilt to the slope
                yaw = Matrix.Rotation(mw.to_euler().z, 4, "Z")
                rot = q.to_matrix().to_4x4() @ yaw
                scale = Matrix.Diagonal(mw.to_scale().to_4d())
                mw = rot @ scale
            new = loc + (normal if s.align else Vector((0, 0, 1))) * (s.offset + drop)
            mw.translation = new
            o.matrix_world = mw
            moved += 1
        if missed:
            self.report({"WARNING"}, f"No ground below {len(missed)} object(s): {', '.join(missed[:5])}")
        else:
            self.report({"INFO"}, f"{moved} object(s) set to the floor")
        return {"FINISHED"}


# ── Distribute along curve ───────────────────────────────────────────────────

def _is_curve(self, ob):
    return ob.type == "CURVE"


AXES = [("NONE", "No Align", "Keep the objects' rotation"),
        ("X", "X", "The object's X axis follows the curve"), ("Y", "Y", "The object's Y axis follows the curve"),
        ("Z", "Z", "The object's Z axis follows the curve"), ("-X", "-X", "The object's -X axis follows the curve"),
        ("-Y", "-Y", "The object's -Y axis follows the curve"), ("-Z", "-Z", "The object's -Z axis follows the curve")]


class OGDistributeSettings(bpy.types.PropertyGroup):
    curve: PointerProperty(name="Curve", type=bpy.types.Object, poll=_is_curve,
                           description="The curve to put the objects on (set when a curve becomes the active object)")
    method: EnumProperty(name="Method", default="DISTANCE", items=[
        ("DISTANCE", "Distance", "The same distance along the curve between the objects, first to last end"),
        ("POINTS", "Per segment", "The same share of each segment between two curve points, whatever its length "
                                  "(how OpenGOAL moves along a path: the points joined by straight lines)"),
        ("SPACING", "Fixed spacing", "One object every N meters from the curve's start (stops at its end)")])
    spacing: FloatProperty(name="Spacing", default=2.0, min=0.01, unit="LENGTH",
                           description="Distance between two objects along the curve")
    align: EnumProperty(name="Align", items=AXES, default="NONE",
                        description="Turn the objects so this axis follows the curve (up stays up)")


def _polyline(points, cyclic):
    """(points, cumulative lengths) of a polyline (closed: back to the start)."""
    pts = list(points) + ([points[0]] if cyclic and len(points) > 1 else [])
    acc = [0.0]
    for a, b in zip(pts, pts[1:]):
        acc.append(acc[-1] + (b - a).length)
    return pts, acc


def _at_length(pts, acc, s):
    """(position, tangent) at arc length s of a polyline."""
    s = max(0.0, min(s, acc[-1]))
    for i in range(1, len(pts)):
        if acc[i] >= s or i == len(pts) - 1:
            seg = acc[i] - acc[i - 1]
            t = (s - acc[i - 1]) / seg if seg > 0 else 0.0
            d = pts[i] - pts[i - 1]
            return pts[i - 1] + d * t, (d.normalized() if d.length else Vector((1, 0, 0)))
    return pts[0], Vector((1, 0, 0))


def curve_samples(curve, depsgraph):
    """(smooth points, control points, cyclic) of a curve's first spline, world space."""
    mw = curve.matrix_world
    sp = curve.data.splines[0]
    if sp.type == "BEZIER":
        ctrl = [mw @ p.co for p in sp.bezier_points]
    else:
        ctrl = [mw @ Vector(p.co[:3]) for p in sp.points]
    ev = curve.evaluated_get(depsgraph)
    me = ev.to_mesh()
    smooth = [mw @ v.co for v in me.vertices] if me is not None else []
    ev.to_mesh_clear()
    return smooth or ctrl, ctrl, bool(sp.use_cyclic_u)


def distribute_positions(curve, depsgraph, n, method, spacing=2.0):
    """[(position, tangent)] for n objects; fewer with Fixed spacing past the end."""
    smooth, ctrl, cyclic = curve_samples(curve, depsgraph)
    if method == "POINTS":
        pts = list(ctrl) + ([ctrl[0]] if cyclic else [])
        segs = len(pts) - 1
        out = []
        for i in range(n):
            u = (i * segs / n) if cyclic else (i * segs / (n - 1) if n > 1 else 0.0)
            k = min(int(u), segs - 1)
            t = u - k
            d = pts[k + 1] - pts[k]
            out.append((pts[k] + d * t, d.normalized() if d.length else Vector((1, 0, 0))))
        return out
    pts, acc = _polyline(smooth, cyclic)
    total = acc[-1]
    if method == "SPACING":
        return [_at_length(pts, acc, i * spacing) for i in range(n) if i * spacing <= total + 1e-6]
    step = total / n if cyclic else (total / (n - 1) if n > 1 else 0.0)
    return [_at_length(pts, acc, i * step) for i in range(n)]


def _natural(name):
    import re
    return [(0, int(t), "") if t.isdigit() else (1, 0, t) for t in re.split(r"(\d+)", name)]


class OG_OT_DistributeAlongCurve(bpy.types.Operator):
    """Put the selected objects along the curve (Object Controls > Distribute Along Curve settings),
in name order"""
    bl_idname = "og.distribute_along_curve"
    bl_label = "Distribute Along Curve"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, ctx):
        return ctx.mode == "OBJECT" and ctx.scene.og_distribute.curve is not None

    def execute(self, ctx):
        s = ctx.scene.og_distribute
        curve = s.curve
        if curve is None or not curve.data.splines:
            self.report({"ERROR"}, "Pick a curve with points")
            return {"CANCELLED"}
        objs = distribute_targets(ctx, curve)
        if not objs:
            self.report({"WARNING"}, "Select the objects to distribute")
            return {"CANCELLED"}
        objs.sort(key=lambda o: _natural(o.name))
        dg = ctx.evaluated_depsgraph_get()
        placed = distribute_positions(curve, dg, len(objs), s.method, s.spacing)
        for o, (pos, tan) in zip(objs, placed):
            mw = o.matrix_world.copy()
            if s.align != "NONE":
                axis = s.align
                up = "Y" if axis.endswith("Z") else "Z"
                q = tan.to_track_quat(axis, up)
                mw = q.to_matrix().to_4x4() @ Matrix.Diagonal(mw.to_scale().to_4d())
            mw.translation = pos
            o.matrix_world = mw
        left = len(objs) - len(placed)
        if left:
            self.report({"WARNING"}, f"{left} object(s) didn't fit on the curve with this spacing")
        else:
            self.report({"INFO"}, f"{len(placed)} object(s) distributed")
        return {"FINISHED"}


def distribute_targets(ctx, curve=None):
    """The selected objects to distribute: not the curve, not previews,
    not children of other selected objects."""
    sel = [o for o in ctx.selected_objects if o is not curve and o.type != "CURVE"
           and not (o.get("og_preview_mesh") or o.get("og_waypoint_preview_mesh"))]
    return [o for o in sel if o.parent not in sel]


def _on_active_change():
    """A curve becoming the active object fills Distribute's curve."""
    ctx = bpy.context
    ob = getattr(ctx, "active_object", None)
    sc = getattr(ctx, "scene", None)
    if ob is not None and ob.type == "CURVE" and sc is not None and hasattr(sc, "og_distribute") \
            and sc.og_distribute.curve is not ob:
        sc.og_distribute.curve = ob


_MSGBUS_OWNER = object()


def subscribe():
    bpy.msgbus.clear_by_owner(_MSGBUS_OWNER)
    bpy.msgbus.subscribe_rna(key=(bpy.types.LayerObjects, "active"), owner=_MSGBUS_OWNER, args=(),
                             notify=_on_active_change)


@bpy.app.handlers.persistent
def _resubscribe(*_a):
    subscribe()


class OGExportDefsSettings(bpy.types.PropertyGroup):
    path: StringProperty(name="Write to", subtype="FILE_PATH", default="",
                         description="A text file (rewritten each export) or a folder (a new file each export). "
                                     "Empty: clipboard only")


def export_target(path, now=None):
    """The file to write: the path itself, or a new dated file in a folder."""
    import os
    import time
    p = bpy.path.abspath(path.strip())
    if not p:
        return None
    if os.path.isdir(p) or p.endswith(("/", "\\")):
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
        base = os.path.join(p, f"og-definitions-{stamp}")
        f, n = base + ".txt", 1
        while os.path.exists(f):
            f, n = f"{base}-{n}.txt", n + 1
        return f
    return p


class OG_OT_ExportSelectedDefs(bpy.types.Operator):
    """Export the selected actors, cameras, checkpoints and load boundaries as the level files write
them (with the art groups / code the actors need): to the clipboard and the file / folder set below"""
    bl_idname = "og.export_selected_defs"
    bl_label = "Export Selected Definitions"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, ctx):
        return bool(ctx.selected_objects)

    def execute(self, ctx):
        import os
        from .export.selected_defs import build
        text, counts = build(ctx.scene, ctx.evaluated_depsgraph_get(), list(ctx.selected_objects))
        if not counts:
            self.report({"WARNING"}, "Nothing to export: select actors, cameras, checkpoints or load boundaries")
            return {"CANCELLED"}
        ctx.window_manager.clipboard = text
        what = ", ".join(f"{n} {k}" for k, n in counts.items())
        f = export_target(ctx.scene.og_export_defs.path)
        if f:
            try:
                os.makedirs(os.path.dirname(f) or ".", exist_ok=True)
                with open(f, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(text)
            except OSError as e:
                self.report({"ERROR"}, f"Couldn't write {f}: {e}")
                return {"CANCELLED"}
            self.report({"INFO"}, f"Exported {what} to {f} (and the clipboard)")
        else:
            self.report({"INFO"}, f"Copied {what} to the clipboard")
        return {"FINISHED"}


CLASSES = (OGFloorSettings, OG_OT_SetToFloor, OGDistributeSettings, OG_OT_DistributeAlongCurve,
           OGExportDefsSettings, OG_OT_ExportSelectedDefs)


def register_props():
    bpy.types.Scene.og_floor = PointerProperty(type=OGFloorSettings)
    bpy.types.Scene.og_distribute = PointerProperty(type=OGDistributeSettings)
    bpy.types.Scene.og_export_defs = PointerProperty(type=OGExportDefsSettings)
    subscribe()
    if _resubscribe not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_resubscribe)       # msgbus subscriptions are cleared on file load


def unregister_props():
    bpy.msgbus.clear_by_owner(_MSGBUS_OWNER)
    if _resubscribe in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_resubscribe)
    for p in ("og_floor", "og_distribute", "og_export_defs"):
        if hasattr(bpy.types.Scene, p):
            delattr(bpy.types.Scene, p)
