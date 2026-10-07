# level_bounds.py — OpenGOAL Level Tools
# Level extent (Blender world AABB) and the vanilla Jak 1 load boundaries.
#
# level_extent(scene) covers the level's geometry meshes plus actor / spawn /
# checkpoint / camera positions. It feeds the level-info bsphere and the
# "overlaps a vanilla load boundary" audit check.
#
# vanilla_load_boundaries.json is generated from OpenGOAL's
# goal_src/jak1/engine/level/load-boundary-data.gc (see the file's "source").
# Points are Blender metres [x, y] (y = -game z); top/bot are metres (Blender z).

import json
import os

from .collections import _level_objects

_LB_PATH = os.path.join(os.path.dirname(__file__), "vanilla_load_boundaries.json")
_LB_CACHE = None

# Objects that are helpers, not level content.
_SKIP_PREFIXES = ("VOL_", "LOADBND_")
_POINT_PREFIXES = ("ACTOR_", "SPAWN_", "CHECKPOINT_", "CAMERA_")


def vanilla_load_boundaries() -> list[dict]:
    global _LB_CACHE
    if _LB_CACHE is None:
        try:
            with open(_LB_PATH, encoding="utf-8") as f:
                _LB_CACHE = json.load(f).get("boundaries", [])
        except Exception:
            _LB_CACHE = []
    return _LB_CACHE


def level_extent(scene):
    """(min_xyz, max_xyz) of the level in Blender world space, or None when
    the level has nothing placed."""
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3

    def add(p):
        for i in range(3):
            lo[i] = min(lo[i], p[i]); hi[i] = max(hi[i], p[i])

    for o in _level_objects(scene):
        if o.name.startswith(_SKIP_PREFIXES):
            continue
        if o.type == "MESH":
            if o.get("og_preview_mesh") or o.get("og_waypoint_preview_mesh"):
                continue
            mw = o.matrix_world
            for c in o.bound_box:
                add(mw @ _vec(c))
        elif o.name.startswith(_POINT_PREFIXES):
            if "_wp_" in o.name or "_wpb_" in o.name:
                continue
            add(o.matrix_world.translation)
    if lo[0] == float("inf"):
        return None
    return tuple(lo), tuple(hi)


def _vec(c):
    from mathutils import Vector
    return Vector((c[0], c[1], c[2]))


# ── 2D geometry ─────────────────────────────────────────────────────────────

def _seg_hits_box(a, b, x0, y0, x1, y1):
    """Segment a-b intersects the axis-aligned box (Liang-Barsky)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
        if p == 0:
            if q < 0:
                return False
            continue
        t = q / p
        if p < 0:
            if t > t1: return False
            t0 = max(t0, t)
        else:
            if t < t0: return False
            t1 = min(t1, t)
    return True


def _point_in_poly(pt, poly):
    x, y = pt; inside = False
    for i in range(len(poly)):
        (ax, ay), (bx, by) = poly[i], poly[i - 1]
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            inside = not inside
    return inside


def boundary_hits_extent(bnd, extent, margin=10.0):
    """True when a vanilla boundary crosses the level's extent (grown by
    `margin` metres on every side, so a player/camera at the edge counts)."""
    (x0, y0, z0), (x1, y1, z1) = extent
    x0 -= margin; y0 -= margin; z0 -= margin
    x1 += margin; y1 += margin; z1 += margin
    if bnd["top"] < z0 or bnd["bot"] > z1:
        return False
    pts = bnd["points"]
    closed = "closed" in bnd.get("flags", [])
    segs = list(zip(pts, pts[1:])) + ([(pts[-1], pts[0])] if closed and len(pts) > 2 else [])
    if any(_seg_hits_box(a, b, x0, y0, x1, y1) for a, b in segs):
        return True
    if closed and len(pts) > 2:
        return _point_in_poly(((x0 + x1) / 2, (y0 + y1) / 2), pts)
    return False


def describe_boundary(bnd) -> str:
    who = "camera" if "player" not in bnd.get("flags", []) else "player"
    cmds = [c for c in (bnd.get("fwd"), bnd.get("bwd")) if c]
    return f"{who} boundary ({'; '.join(cmds) or 'no command'})"
