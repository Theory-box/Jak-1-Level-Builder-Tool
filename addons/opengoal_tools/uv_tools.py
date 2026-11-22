"""UV Tools (Object Controls > UV Tools): Fit Faces on UV and Cube Project.

Both work on the selected meshes' active UV map: every face in Object Mode, the
selected faces in Edit Mode. Faces are oriented in world space: walls stand
upright (bottom edge along U), floors / ceilings follow world X / Y."""
from __future__ import annotations

import math
from collections import deque

import bpy
import bmesh
from bpy.props import BoolProperty, EnumProperty, FloatProperty
from mathutils import Vector

_Z = Vector((0, 0, 1))
_Y = Vector((0, 1, 0))
_FLOOR = 0.7            # |normal.z| above this: floor / ceiling


# ── Targets ───────────────────────────────────────────────────────────────────

def targets(ctx):
    """Meshes to work on: the objects in Edit Mode, else the selected meshes (no previews)."""
    if ctx.mode == "EDIT_MESH":
        return [o for o in ctx.objects_in_mode if o.type == "MESH"]
    return [o for o in ctx.selected_objects
            if o.type == "MESH" and not o.get("og_preview_mesh") and not o.get("og_waypoint_preview_mesh")]


def _edit(ctx, fn):
    """Run fn(obj, bm, faces, uv_layer) on every target; returns (meshes, faces) changed."""
    edit = ctx.mode == "EDIT_MESH"
    n_obj = n_face = 0
    for o in targets(ctx):
        me = o.data
        if edit:
            bm = bmesh.from_edit_mesh(me)
        else:
            bm = bmesh.new(); bm.from_mesh(me)
        faces = [f for f in bm.faces if f.select] if edit else list(bm.faces)
        if faces:
            uv = bm.loops.layers.uv.active or bm.loops.layers.uv.new("UVMap")
            n_face += fn(o, bm, faces, uv)
            n_obj += 1
        if edit:
            bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)
        else:
            bm.to_mesh(me); me.update(); bm.free()
    return n_obj, n_face


# ── Orientation ───────────────────────────────────────────────────────────────

def frame(n):
    """(u, v) axes for a world normal: walls upright, floors / ceilings along world X / Y."""
    up = _Y if abs(n.z) > _FLOOR else _Z
    u = up.cross(n)
    if u.length < 1e-6:
        u = Vector((1, 0, 0))
    u.normalize()
    return u, n.cross(u).normalized()


def axis_normal(n):
    """The closest of the 6 world axes to n (cube projection side)."""
    i = max(range(3), key=lambda k: abs(n[k]))
    a = Vector((0, 0, 0)); a[i] = 1.0 if n[i] >= 0 else -1.0
    return a


# ── Units: quads, triangle pairs, triangles ───────────────────────────────────

class Unit:
    """One cell of the UV grid: a quad, two triangles used as a quad, or a triangle.
    verts = the corners in counter-clockwise order, normal = world normal."""
    __slots__ = ("faces", "verts", "normal")

    def __init__(self, faces, verts, normal):
        self.faces, self.verts, self.normal = faces, verts, normal


def _tri_pairs(faces, mw3):
    """Pair triangles across their longest edge when both sides choose it."""
    tris = {f for f in faces if len(f.verts) == 3}
    longest = {f: max(f.edges, key=lambda e: e.calc_length()) for f in tris}
    pairs, used = [], set()
    for f in tris:
        if f in used:
            continue
        e = longest[f]
        g = next((x for x in e.link_faces if x is not f and x in tris and x not in used and longest[x] is e), None)
        if g is None:
            continue
        a = next(v for v in f.verts if v not in e.verts)
        d = next(v for v in g.verts if v not in e.verts)
        # f's loop order a -> b -> c (counter-clockwise); the quad is a, b, d, c
        la = next(l for l in f.loops if l.vert is a)
        b, c = la.link_loop_next.vert, la.link_loop_next.link_loop_next.vert
        pairs.append((f, g, [a, b, d, c]))
        used.update((f, g))
    return pairs, used


def units(faces, mw3, pair_tris):
    """Split faces into units (n-gons are skipped)."""
    out = []
    used = set()
    if pair_tris:
        pairs, used = _tri_pairs(faces, mw3)
        for f, g, vs in pairs:
            out.append(Unit((f, g), vs, (mw3 @ (f.normal + g.normal)).normalized()))
    for f in faces:
        if f in used or len(f.verts) > 4:
            continue
        out.append(Unit((f,), [l.vert for l in f.loops], (mw3 @ f.normal).normalized()))
    return out


def _set(unit, uv, coords):
    """Write coords[i] for unit.verts[i] into every loop of the unit's faces."""
    m = {v: c for v, c in zip(unit.verts, coords)}
    for f in unit.faces:
        for l in f.loops:
            c = m.get(l.vert)
            if c is not None:
                l[uv].uv = c


def _start(unit, mw, u):
    """Corner index whose outgoing edge points most along +U (the bottom edge, left to right)."""
    ws = [mw @ v.co for v in unit.verts]
    k = len(ws)

    def score(i):
        d = ws[(i + 1) % k] - ws[i]
        return d.normalized().dot(u) if d.length > 1e-9 else -2.0
    return max(range(k), key=score)


def _tri_start(unit, mw):
    """Triangle corner with the largest angle (it goes on (0,0))."""
    ws = [mw @ v.co for v in unit.verts]

    def ang(i):
        a, b = ws[(i + 1) % 3] - ws[i], ws[(i + 2) % 3] - ws[i]
        return a.angle(b, 0.0) if a.length > 1e-9 and b.length > 1e-9 else 0.0
    return max(range(3), key=ang)


_QUAD = (Vector((0, 0)), Vector((1, 0)), Vector((1, 1)), Vector((0, 1)))
_TRI = (Vector((0, 0)), Vector((1, 0)), Vector((0, 1)))


def _square(unit, mw, normal):
    """Coords for one unit on the 0-1 square, oriented by the world frame of `normal`."""
    k = len(unit.verts)
    if k == 4:
        s = _start(unit, mw, frame(normal)[0]); grid = _QUAD
    else:
        s = _tri_start(unit, mw); grid = _TRI
    coords = [None] * k
    for i in range(k):
        coords[(s + i) % k] = grid[i].copy()
    return coords


# ── Fit Faces on UV ───────────────────────────────────────────────────────────

def _transform(coords_list, s):
    """Scale and rotate every coord around the pivot."""
    piv = Vector((0.5, 0.5)) if s.pivot == "CENTER" else Vector((0, 0))
    c, n = math.cos(s.rotation), math.sin(s.rotation)
    for coords in coords_list:
        for i, p in enumerate(coords):
            d = (p - piv) * s.scale
            coords[i] = piv + Vector((d.x * c - d.y * n, d.x * n + d.y * c))


def _spread(us, mw):
    """Islands of connected units, laid out on a unit grid; one row, one empty tile between islands."""
    by_vertpair = {}
    for un in us:
        k = len(un.verts)
        for i in range(k):
            by_vertpair.setdefault(frozenset((un.verts[i], un.verts[(i + 1) % k])), []).append(un)
    side = {un: tuple(axis_normal(un.normal)) for un in us}
    placed = {}                                  # unit -> coords
    islands = []
    for seed in us:
        if seed in placed:
            continue
        placed[seed] = _square(seed, mw, Vector(side[seed]))
        island = [seed]
        q = deque([seed])
        while q:
            un = q.popleft()
            k = len(un.verts)
            cu = placed[un]
            for i in range(k):
                p, r = un.verts[i], un.verts[(i + 1) % k]
                for nb in by_vertpair.get(frozenset((p, r)), ()):
                    if nb is un or nb in placed or side[nb] != side[un]:
                        continue
                    # in nb the shared edge runs r -> p; its interior is left of that edge (counter-clockwise)
                    kk = len(nb.verts)
                    j = nb.verts.index(r)
                    if nb.verts[(j + 1) % kk] is not p:
                        continue                 # flipped normals: leave it for its own island
                    uq, upp = cu[(i + 1) % k], cu[i]
                    e = upp - uq
                    if e.length < 1e-9:
                        continue
                    perp = Vector((-e.y, e.x)).normalized()
                    coords = [None] * kk
                    coords[j], coords[(j + 1) % kk] = uq.copy(), upp.copy()
                    if kk == 4:
                        coords[(j + 2) % kk] = upp + perp
                        coords[(j + 3) % kk] = uq + perp
                    else:
                        coords[(j + 2) % kk] = uq + perp
                    placed[nb] = coords
                    island.append(nb); q.append(nb)
        islands.append(island)
    x = 0.0
    for isl in islands:
        pts = [c for un in isl for c in placed[un]]
        lo_x = math.floor(min(p.x for p in pts) + 1e-6); lo_y = math.floor(min(p.y for p in pts) + 1e-6)
        hi_x = math.ceil(max(p.x for p in pts) - 1e-6)
        off = Vector((x - lo_x, -lo_y))
        for un in isl:
            placed[un] = [c + off for c in placed[un]]
        x += (hi_x - lo_x) + 1                   # one empty tile between islands
    return placed


def fit_faces(ctx, s):
    def run(o, bm, faces, uv):
        mw = o.matrix_world
        mw3 = mw.to_3x3().inverted_safe().transposed()     # normals to world
        us = units(faces, mw3, s.pair_triangles)
        if s.placement == "SPREAD":
            placed = _spread(us, mw)
        else:
            placed = {un: _square(un, mw, un.normal) for un in us}
        coords = [placed[un] for un in us]
        _transform(coords, s)
        for un, c in zip(us, coords):
            _set(un, uv, c)
        return sum(len(un.faces) for un in us)
    return _edit(ctx, run)


# ── Cube Project ──────────────────────────────────────────────────────────────

def cube_project(ctx, s):
    size = max(s.size, 1e-4)

    def run(o, bm, faces, uv):
        mw = o.matrix_world
        mw3 = mw.to_3x3().inverted_safe().transposed()
        for f in faces:
            u, v = frame(axis_normal((mw3 @ f.normal).normalized()))
            for l in f.loops:
                p = mw @ l.vert.co
                l[uv].uv = (p.dot(u) / size, p.dot(v) / size)
        return len(faces)
    return _edit(ctx, run)


# ── Settings + operators ──────────────────────────────────────────────────────

class OGUVSettings(bpy.types.PropertyGroup):
    placement: EnumProperty(name="Placement", default="OVERLAP", items=(
        ("OVERLAP", "Overlap", "Every face on the same 0-1 square"),
        ("SPREAD", "Spread", "Connected faces stay connected, one square each; islands (grouped by cube "
                             "projection side) in a row with one empty tile between them"),
    ))
    pair_triangles: BoolProperty(name="Triangles as Quads", default=False,
        description="Two triangles sharing their longest edge take the 4 corners like a quad. "
                    "Off: a triangle takes 3 corners, its largest angle on (0,0)")
    scale: FloatProperty(name="Scale", default=1.0, min=0.0001, soft_max=16.0,
        description="Scale of the whole result (around the pivot)")
    rotation: FloatProperty(name="Rotation", default=0.0, subtype="ANGLE",
        description="Rotation of the whole result (around the pivot)")
    pivot: EnumProperty(name="Pivot", default="CORNER", items=(
        ("CORNER", "Corner", "The 0,0 corner of the UV space"),
        ("CENTER", "Center", "The 0.5,0.5 center of the UV space"),
    ))
    size: FloatProperty(name="Texture Size", default=4.0, min=0.001, soft_max=64.0, unit="LENGTH",
        description="The texture repeats every this many metres")


class _UVOp:
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, ctx):
        return ctx.mode in ("OBJECT", "EDIT_MESH") and bool(targets(ctx))

    def done(self, n_obj, n_face):
        if not n_face:
            self.report({"WARNING"}, "No faces (in Edit Mode, select faces)"); return {"CANCELLED"}
        self.report({"INFO"}, f"{n_face} face(s) on {n_obj} mesh(es)")
        return {"FINISHED"}


class OG_OT_UVFitFaces(_UVOp, bpy.types.Operator):
    """Put every quad on the four corners of the UV square (triangles on three; n-gons are left alone).
    Whole mesh, or the selected faces in Edit Mode"""
    bl_idname = "og.uv_fit_faces"
    bl_label = "Fit Faces on UV"

    def execute(self, ctx):
        return self.done(*fit_faces(ctx, ctx.scene.og_uv))


class OG_OT_UVCubeProject(_UVOp, bpy.types.Operator):
    """Project each face along its closest world axis; the texture repeats every Texture Size metres.
    Whole mesh, or the selected faces in Edit Mode"""
    bl_idname = "og.uv_cube_project"
    bl_label = "Cube Project"

    def execute(self, ctx):
        return self.done(*cube_project(ctx, ctx.scene.og_uv))


CLASSES = (OGUVSettings, OG_OT_UVFitFaces, OG_OT_UVCubeProject)


def register_props():
    bpy.types.Scene.og_uv = bpy.props.PointerProperty(type=OGUVSettings)


def unregister_props():
    if hasattr(bpy.types.Scene, "og_uv"):
        del bpy.types.Scene.og_uv
