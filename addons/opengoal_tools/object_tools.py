"""Object Controls tools: Set to floor."""
from __future__ import annotations

import bpy
from bpy.props import FloatProperty, BoolProperty, EnumProperty, PointerProperty
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


CLASSES = (OGFloorSettings, OG_OT_SetToFloor)


def register_props():
    bpy.types.Scene.og_floor = PointerProperty(type=OGFloorSettings)


def unregister_props():
    if hasattr(bpy.types.Scene, "og_floor"):
        del bpy.types.Scene.og_floor
