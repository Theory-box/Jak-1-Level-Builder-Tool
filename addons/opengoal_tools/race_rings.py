# ---------------------------------------------------------------------------
# race_rings.py — OpenGOAL Level Tools
# A race-ring with a path exports one ring per path point (DB path panel
# option "rings"): linked next / prev, alt-actor = the first ring, the actor's
# settings and task on every ring, timeout = the actor's time x the point's
# Radius, rotoffset = the point's Tilt (+ the actor's extra yaw), movie-pos on
# the last ring only.
#
# Ring facing (rolling-race-ring.gc init-from-entity!): yaw rot-y from the
# neighbours, flattened to the ground:
#   middle ring: s = norm(prev - here) + norm(next - here) (bisector);
#                rot-y = angle of s from +z (negative when s.x < 0)
#   end rings:   face = next - here (first) or here - prev (last);
#                rot-y = angle of face from +z + 90 deg
#   rot-y += rotoffset; the ring's axis is (cos rot-y, 0, -sin rot-y).
# Each point gets a circle empty preview (circle in its XZ plane: local Y =
# the ring's axis), 4.5 m like the ring particles.
# ---------------------------------------------------------------------------
from __future__ import annotations

import math
import bpy
import mathutils

RING_RADIUS = 4.5     # m, the particle ring (the pass-through cylinder is 6 m)
_PREVIEW_PROP = "og_preview_mesh"


def uses_rings(o) -> bool:
    from . import db
    p = o.name.split("_", 2)
    return (len(p) >= 3 and p[0] == "ACTOR"
            and db.panel_option(p[1], "path", "rings", False) is True)


def points(o) -> list:
    """[{co (Blender world), tilt (rad), weight}] — one per path point."""
    out = []
    for src in getattr(o, "og_waypoint_sources", []):
        s = src.obj
        if s is None or s.name not in bpy.data.objects:
            continue
        if s.type == "EMPTY":
            out.append({"co": s.matrix_world.translation.copy(), "tilt": 0.0, "weight": 1.0})
        elif s.type == "CURVE":
            M = s.matrix_world
            for sp in s.data.splines:
                for p in (sp.bezier_points if sp.type == "BEZIER" else sp.points):
                    co = mathutils.Vector(p.co[:3])
                    # the point's Radius (every curve type, default 1) multiplies the time
                    out.append({"co": M @ co, "tilt": float(p.tilt), "weight": max(0.0, float(p.radius))})
    return out


def _game(v):          # Blender -> game axes (x, z, -y)
    return mathutils.Vector((v.x, v.z, -v.y))


def _flat_norm(v):
    v = mathutils.Vector((v.x, 0.0, v.z))
    return v.normalized() if v.length > 1e-9 else v


def yaws(pts, extra=0.0) -> list:
    """Game rot-y (radians) per ring, without / with each point's tilt."""
    g = [_game(p["co"]) for p in pts]
    n = len(g)
    out = []
    for i in range(n):
        prv = g[i - 1] if i > 0 else None
        nxt = g[i + 1] if i < n - 1 else None
        if nxt is not None:
            face = _flat_norm(nxt - g[i])
        elif prv is not None:
            face = _flat_norm(g[i] - prv)
        else:
            face = mathutils.Vector((0, 0, 1))
        if prv is not None and nxt is not None:
            s = _flat_norm(_flat_norm(prv - g[i]) + face)
            r = math.acos(max(-1.0, min(1.0, s.z)))
            if s.x < 0:
                r = -r
        else:
            r = math.acos(max(-1.0, min(1.0, face.z)))
            if face.x < 0:
                r = -r
            r += math.pi / 2
        out.append(r + pts[i]["tilt"] + extra)
    return out


def straight_rings(pts) -> list:
    """Indices of middle rings whose neighbours are in a straight line through
    them: the game's bisector is then zero and it falls back to 90 deg (axis
    along game Z), so the ring is edge-on unless the line runs along Z."""
    g = [_game(p["co"]) for p in pts]
    bad = []
    for i in range(1, len(g) - 1):
        a, b = _flat_norm(g[i - 1] - g[i]), _flat_norm(g[i + 1] - g[i])
        if (a + b).length < 1e-3 and abs(b.z) < 0.999:
            bad.append(i)
    return bad


def _ring_matrix(co, yaw):
    """Circle empty: local Y on the ring's axis (game (cos, 0, -sin) ->
    Blender (cos, sin, 0))."""
    ax, ay = math.cos(yaw), math.sin(yaw)
    rot = mathutils.Matrix.Rotation(math.atan2(-ax, ay), 4, "Z")
    return mathutils.Matrix.Translation(co) @ rot


def _extra_yaw(o):
    return math.radians(float(o.get("og_ring_rot", 0.0)))


def wanted(o) -> list:
    pts = points(o)
    return [_ring_matrix(p["co"], y) for p, y in zip(pts, yaws(pts, _extra_yaw(o)))]


def _ring_objs(o):
    return sorted((c for c in o.children if c.get("og_ring_preview")), key=lambda c: c.name)


def build_preview(ctx, o):
    from . import model_preview as mp
    for c in _ring_objs(o):
        bpy.data.objects.remove(c, do_unlink=True)
    mats = wanted(o)
    if not mats:
        return
    col = mp._ensure_preview_collection(ctx.scene)
    for i, M in enumerate(mats):
        e = bpy.data.objects.new(f"{o.name}_ring_{i}", None)
        e.empty_display_type = "CIRCLE"
        e.empty_display_size = RING_RADIUS
        e[_PREVIEW_PROP] = True
        e["og_ring_preview"] = True
        col.objects.link(e)
        e.parent = o
        e.matrix_world = M
        e.hide_select = True
        e.show_in_front = True


def _differs(o):
    have = _ring_objs(o)
    want = wanted(o)
    if len(have) != len(want):
        return True
    for e, M in zip(have, want):
        a, b = e.matrix_world, M
        if any(abs(a[r][c] - b[r][c]) > 1e-4 for r in range(3) for c in range(4)):
            return True
    return False


_PENDING = set()


def update_preview(ctx, o):
    """Move the existing circles; rebuild only when the point count changed."""
    have = _ring_objs(o)
    want = wanted(o)
    if len(have) != len(want):
        build_preview(ctx, o)
        return
    for e, M in zip(have, want):
        e.matrix_world = M


def _rebuild_later(names):
    def _run():
        try:
            for n in names:
                o = bpy.data.objects.get(n)
                if o is not None:
                    try:
                        update_preview(bpy.context, o)
                    except Exception as e:   # never stop following this actor
                        print(f"[OpenGOAL] race-ring preview {n}: {e}")
        finally:
            _PENDING.difference_update(names)
        return None
    bpy.app.timers.register(_run, first_interval=0.0)


def changed(depsgraph):
    """(object names, curve data names) this update touched."""
    objs, curves = set(), set()
    for u in depsgraph.updates:
        n = u.id.__class__.__name__
        if n == "Object":
            objs.add(u.id.original.name)
        elif n == "Curve":
            curves.add(u.id.original.name)
    return objs, curves


def touched(o, objs, curves) -> bool:
    """The actor itself, one of its path empties / curves, or a curve's points."""
    if o.name in objs:
        return True
    for s in getattr(o, "og_waypoint_sources", []):
        p = s.obj
        if p is not None and (p.name in objs or (p.type == "CURVE" and p.data.name in curves)):
            return True
    return False


def on_depsgraph(scene, depsgraph, objs=None, curves=None):
    """Called from the preview depsgraph handler: only race-rings whose actor
    or path was edited are looked at (moving circles in place)."""
    if objs is None:
        objs, curves = changed(depsgraph)
    if not objs and not curves:
        return
    todo = [o.name for o in scene.objects
            if o.name.startswith("ACTOR_race-ring_") and not o.get(_PREVIEW_PROP) and o.name not in _PENDING
            and touched(o, objs, curves) and uses_rings(o) and _differs(o)]
    if todo:
        _PENDING.update(todo)
        _rebuild_later(todo)


def entities(o, base: dict) -> list:
    """The JSONC entries for a ring chain built from base (the actor's own
    entry). [] when the actor has no path."""
    import copy
    pts = points(o)
    if not pts:
        return []
    name = base["lump"]["name"]
    names = [f"{name}-{i}" for i in range(len(pts))]
    timeout = float(o.get("og_ring_timeout", 8.0))
    out = []
    for i, p in enumerate(pts):
        e = copy.deepcopy(base)
        g = _game(p["co"])
        t = [round(g.x, 4), round(g.y, 4), round(g.z, 4)]
        e["trans"] = t
        e["quat"] = [0.0, 0.0, 0.0, 1.0]
        e["bsphere"] = t + [base["bsphere"][3]]
        L = e["lump"]
        for k in ("next-actor", "prev-actor", "alt-actor", "movie-pos", "alt-task", "rotoffset"):
            L.pop(k, None)
        L["name"] = names[i]
        L["timeout"] = ["float", round(timeout * p["weight"], 4)]
        rot = math.degrees(p["tilt"] + _extra_yaw(o))
        if abs(rot) > 1e-6:
            L["rotoffset"] = ["degrees", round(rot, 4)]
        if i > 0:
            L["prev-actor"] = ["string", names[i - 1]]
            L["alt-actor"] = ["string", names[0]]
        if i < len(pts) - 1:
            L["next-actor"] = ["string", names[i + 1]]
        if i == 0 and "alt-task" in base["lump"]:
            L["alt-task"] = base["lump"]["alt-task"]
        if i == len(pts) - 1 and "movie-pos" in base["lump"]:
            L["movie-pos"] = base["lump"]["movie-pos"]
        out.append(e)
    return out
