# ---------------------------------------------------------------------------
# distribute.py — OpenGOAL Level Tools
# Sync panel option "distribute" (DB, on plat and so its children):
#   - Distribute along the path: export this platform N times, evenly spread
#     in time. Copy i (1..N-1) is the same actor with phase (A + i / N)
#     wrapped to 0-1, A = its own phase.
#   - Place platform on path: the actor sits where the game first puts it
#     (time 0 of its sync), and with Distribute on, ghost copies show where
#     the others start.
# Start position (plat.gc / sync-info.gc): the path position is the sync
# phase, mirrored (0 -> 1 -> 0 per period) and eased, or the plain phase with
# Wrap phase; a linear path takes point index pos * (n - 1), a smooth one
# (path-k) the cubic B-spline at pos * last knot.
# ---------------------------------------------------------------------------
from __future__ import annotations

import copy
import bpy
import mathutils

from . import db as _db

_GHOST = "og_dist_ghost"


def allowed(etype) -> bool:
    return bool(_db.panel_option(etype, "sync", "distribute", False))


def enabled(o, etype) -> bool:
    return allowed(etype) and bool(getattr(o, "og_distribute", False))


def phases(a: float, n: int) -> list:
    return [round((a + i / n) % 1.0, 6) for i in range(n)]


def _etype(o):
    p = o.name.split("_", 2)
    return p[1] if len(p) >= 3 and p[0] == "ACTOR" else None


# ── where the game first puts the platform ─────────────────────────────────

def _eased(v, ease_out, ease_in):
    """sync-info-eased: setup-params! + the eased part of get-current-phase-with-mirror."""
    o = min(max(ease_out, 0.0), 1.0)
    i = min(max(ease_in, 0.001), 1.0)
    if o + i > 1.0:
        o = 1.0 - i
    tlo, thi = o, 1.0 - i
    ylo = o * o
    m2 = o / (1.0 - thi)
    yend = (1.0 - thi) ** 2 * m2 + 2.0 * o * (thi - o) + ylo
    if v < tlo:
        y = v * v
    elif v < thi:
        y = 2.0 * tlo * (v - tlo) + ylo
    else:
        y = yend - (1.0 - v) ** 2 * m2
    return y / yend


def path_pos(phase, ease_out=0.15, ease_in=0.15, wrap=False):
    """0-1 position along the path at time 0 for this phase."""
    if wrap:
        return phase % 1.0
    v = 2.0 * (phase % 1.0)
    mirror = v >= 1.0
    if mirror:
        v -= 1.0
    e = _eased(v, ease_out, ease_in)
    return 1.0 - e if mirror else e


def _de_boor(u, pts, knots):
    k = 3
    n = len(pts)
    s = k
    for j in range(k, n):
        if knots[j] <= u < knots[j + 1]:
            s = j
            break
    else:
        s = n - 1
    d = [mathutils.Vector(pts[j + s - k]) for j in range(k + 1)]
    for r in range(1, k + 1):
        for j in range(k, r - 1, -1):
            a_den = knots[j + 1 + s - r] - knots[j + s - k]
            a = 0.0 if a_den == 0 else (u - knots[j + s - k]) / a_den
            d[j] = (1.0 - a) * d[j - 1] + a * d[j]
    return d[k]


def point_at(pts, knots, pos):
    """Blender position at 0-1 along the exported path."""
    if not pts:
        return None
    if knots:
        u = min(max(pos * knots[-1], knots[0]), knots[-1])
        return _de_boor(u, pts, knots)
    if len(pts) == 1:
        return mathutils.Vector(pts[0])
    f = pos * (len(pts) - 1)
    i = min(int(f), len(pts) - 2)
    return mathutils.Vector(pts[i]).lerp(mathutils.Vector(pts[i + 1]), f - i)


def start_positions(o) -> list:
    """Where this platform (and its distributed copies) first sit."""
    from .export import path_modes as _pm
    et = _etype(o)
    if not et:
        return []
    pts, knots, _m, _w = _pm.build(_pm.gather_sources(o), getattr(o, "og_path_mode", "AUTO"),
                                   linear_only=_db.path_linear_only(et))
    if getattr(o, "og_path_knots_manual", False) and knots:
        knots, _ = _pm.manual_knots(knots, [k.value for k in o.og_path_knots])
    if not pts:
        return []
    a = float(o.get("og_sync_phase", 0.0))
    ph = phases(a, int(o.og_distribute_count)) if o.og_distribute else [a]
    eo, ei = float(o.get("og_sync_ease_out", 0.15)), float(o.get("og_sync_ease_in", 0.15))
    wrap = bool(o.get("og_fop_wrap_phase", False))
    return [point_at(pts, knots, path_pos(p, eo, ei, wrap)) for p in ph]


# ── keeping the actor / ghosts on the path ──────────────────────────────────

def _ghosts(o):
    return sorted((c for c in o.children if c.get(_GHOST)), key=lambda c: c.name)


def _differs(o):
    want = start_positions(o) if o.og_place_on_path else []
    if not want:
        return bool(_ghosts(o))
    if (o.matrix_world.translation - want[0]).length > 1e-4:
        return True
    gw = want[1:]
    have = _ghosts(o)
    if len(have) != len(gw):
        return True
    return any((g.matrix_world.translation - w).length > 1e-4 for g, w in zip(have, gw))


def apply(ctx, o):
    """Move the actor to its start spot and rebuild the ghost copies."""
    for g in _ghosts(o):
        bpy.data.objects.remove(g, do_unlink=True)
    if not o.og_place_on_path:
        return
    want = start_positions(o)
    if not want:
        return
    o.location = want[0] if o.parent is None else o.parent.matrix_world.inverted() @ want[0]
    if len(want) < 2:
        return
    from . import model_preview as mp
    col = mp._ensure_preview_collection(ctx.scene)
    src = next((c for c in o.children if c.type == "MESH" and mp._is_any_preview(c) and not c.get(_GHOST)), None)
    bpy.context.view_layer.update()
    for i, w in enumerate(want[1:], start=1):
        g = bpy.data.objects.new(f"{o.name}_ghost_{i}", src.data if src else None)
        if src is None:
            g.empty_display_type = "CUBE"
            g.empty_display_size = o.empty_display_size
        g[mp._PREVIEW_PROP] = True
        g[_GHOST] = True
        col.objects.link(g)
        g.parent = o
        # same as the actor (or its preview), moved to this copy's start spot
        g.matrix_world = (mathutils.Matrix.Translation(w - o.matrix_world.translation)
                          @ (src.matrix_world if src is not None else o.matrix_world))
        g.display_type = "WIRE"
        g.hide_select = True


_PENDING = set()


def on_depsgraph(scene, depsgraph, objs=None, curves=None):
    """Only platforms whose own settings or path were edited are looked at."""
    from .race_rings import changed, touched
    if objs is None:
        objs, curves = changed(depsgraph)
    if not objs and not curves:
        return
    todo = [o.name for o in scene.objects
            if o.type == "EMPTY" and o.name.startswith("ACTOR_") and not o.get("og_preview_mesh") and o.name not in _PENDING
            and getattr(o, "og_place_on_path", False) and touched(o, objs, curves)
            and allowed(_etype(o) or "") and _differs(o)]
    if not todo:
        return
    _PENDING.update(todo)

    def _run():
        for n in todo:
            ob = bpy.data.objects.get(n)
            if ob is not None:
                apply(bpy.context, ob)
        _PENDING.difference_update(todo)
        return None
    bpy.app.timers.register(_run, first_interval=0.0)


def _upd(self, ctx):
    if _etype(self):
        apply(ctx, self)


# ── UI / export ────────────────────────────────────────────────────────────

def draw(layout, o):
    box = layout.box()
    box.prop(o, "og_place_on_path")
    box.prop(o, "og_distribute")
    if not o.og_distribute:
        return
    box.prop(o, "og_distribute_count")
    a = float(o.get("og_sync_phase", 0.0))
    col = box.column(); col.scale_y = 0.8
    col.label(text="Phases: " + ", ".join(f"{p:.2f}" for p in phases(a, o.og_distribute_count)), icon="TIME")
    col.label(text="Copies share every other setting and the path")
    if o.og_place_on_path:
        col.label(text="Wire ghosts: where the copies start")


def entities(o, base: dict) -> list:
    """The extra platforms (the original stays as it is)."""
    n = int(o.og_distribute_count)
    sync = base["lump"].get("sync")
    if n < 2 or not sync or len(sync) < 3:
        return []
    out = []
    for i, ph in enumerate(phases(float(sync[2]), n)[1:], start=1):
        e = copy.deepcopy(base)
        e["lump"]["name"] = f"{base['lump']['name']}-{i}"
        e["lump"]["sync"][2] = ph
        out.append(e)
    return out


def register_props():
    T = bpy.types.Object
    T.og_distribute = bpy.props.BoolProperty(
        name="Distribute along the path", default=False, update=_upd,
        description="Export this platform several times on its path, evenly spread in time (phase)")
    T.og_distribute_count = bpy.props.IntProperty(
        name="Platforms", default=2, min=2, max=32, update=_upd,
        description="How many platforms in total (this one included)")
    T.og_place_on_path = bpy.props.BoolProperty(
        name="Place platform on path", default=False, update=_upd,
        description="Keep the platform where it first appears on its path (from its phase); "
                    "with Distribute, wire ghosts show where the copies start")


def unregister_props():
    for a in ("og_distribute", "og_distribute_count", "og_place_on_path"):
        try: delattr(bpy.types.Object, a)
        except Exception: pass
