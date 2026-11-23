"""Viewport-only previews drawn with the GPU (no objects): race-ring circles
(one per path point) and the wire ghosts of distributed platform copies.

They used to be real objects, rebuilt from a timer after every edit of the
actor or its path: objects made / deleted outside any undo step broke undo
(Ctrl+Z, Adjust Last Operation) and crashed Blender, and the constant object
churn slowed Blender down more and more. Drawn here, nothing is created.

Each actor's matrices are cached and only recomputed when the actor or its
path is edited (mark()), on file load / undo (invalidate()).
"""
from __future__ import annotations

import math

import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix

_CACHE: dict = {}        # actor name -> {"rings": [Matrix], "ghosts": [(mesh name | None, size, Matrix)]}
_DIRTY: set = set()      # actor names to recompute at the next draw
_ALL = [True]            # recompute every candidate at the next draw
_BATCHES: dict = {}      # mesh key -> wire batch
_HANDLE = [None]
_SEG = 32


def mark(names):
    """These actors (or their paths) changed: recompute them at the next draw."""
    if names:
        _DIRTY.update(names)
        _redraw()


@bpy.app.handlers.persistent
def invalidate(*_a):
    _CACHE.clear()
    _DIRTY.clear()
    _ALL[0] = True
    _redraw()


def _redraw():
    try:
        for w in bpy.context.window_manager.windows:
            for a in w.screen.areas:
                if a.type == "VIEW_3D":
                    a.tag_redraw()
    except Exception:
        pass


# ── what to draw ────────────────────────────────────────────────────────────

def _compute(o):
    from . import race_rings, distribute, model_preview as mp
    entry = {"rings": [], "ghosts": []}
    if not mp.special_on(o):
        return entry
    if race_rings.uses_rings(o):
        entry["rings"] = race_rings.wanted(o)
    if getattr(o, "og_place_on_path", False) and getattr(o, "og_distribute", False):
        want = distribute.start_positions(o)
        if len(want) > 1:
            src = next((c for c in o.children if c.type == "MESH" and mp._is_any_preview(c)), None)
            base = src.matrix_world if src is not None else o.matrix_world
            for w in want[1:]:                # the copies: the actor's look, moved to their start spot
                M = Matrix.Translation(w - o.matrix_world.translation) @ base
                entry["ghosts"].append((src.data.name if src is not None else None,
                                        o.empty_display_size, M))
    return entry


def _refresh():
    from .race_rings import candidates
    if _ALL[0]:
        rings, place = candidates()
        _DIRTY.update(rings)
        _DIRTY.update(place)
        _ALL[0] = False
    for n in list(_DIRTY):
        o = bpy.data.objects.get(n)
        if o is None:
            _CACHE.pop(n, None)
            continue
        try:
            e = _compute(o)
        except Exception:
            e = None
        if e and (e["rings"] or e["ghosts"]):
            _CACHE[n] = e
        else:
            _CACHE.pop(n, None)
    _DIRTY.clear()


# ── batches ────────────────────────────────────────────────────────────────

def _shader():
    return gpu.shader.from_builtin("UNIFORM_COLOR")


def _ring_batch(sh):
    b = _BATCHES.get("__ring__")
    if b is None:
        from .race_rings import RING_RADIUS
        r = RING_RADIUS
        pts = [(r * math.cos(2 * math.pi * i / _SEG), 0.0, r * math.sin(2 * math.pi * i / _SEG)) for i in range(_SEG)]
        lines = [p for i in range(_SEG) for p in (pts[i], pts[(i + 1) % _SEG])]
        b = _BATCHES["__ring__"] = batch_for_shader(sh, "LINES", {"pos": lines})
    return b


def _cube_batch(sh):
    b = _BATCHES.get("__cube__")
    if b is None:
        c = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
        edges = [(i, j) for i in range(8) for j in range(i + 1, 8)
                 if sum(a != b_ for a, b_ in zip(c[i], c[j])) == 1]
        b = _BATCHES["__cube__"] = batch_for_shader(sh, "LINES", {"pos": c}, indices=edges)
    return b


def _mesh_batch(sh, name):
    me = bpy.data.meshes.get(name) if name else None
    if me is None:
        return None
    key = (name, len(me.vertices), len(me.edges))
    b = _BATCHES.get(key)
    if b is None:
        for k in [k for k in _BATCHES if isinstance(k, tuple) and k[0] == name]:
            del _BATCHES[k]
        co = [v.co[:] for v in me.vertices]
        b = _BATCHES[key] = batch_for_shader(sh, "LINES", {"pos": co}, indices=[e.vertices[:] for e in me.edges])
    return b


# ── drawing ────────────────────────────────────────────────────────────────

def _draw():
    if not _CACHE and not _DIRTY and not _ALL[0]:
        return
    ctx = bpy.context
    space = getattr(ctx, "space_data", None)
    if space is None or not getattr(space.overlay, "show_overlays", True):
        return
    if _DIRTY or _ALL[0]:
        _refresh()
    if not _CACHE:
        return
    sh = _shader()
    th = ctx.preferences.themes[0].view_3d
    ring_col = (*th.empty, 1.0)
    ghost_col = (*th.wire, 0.9)
    vl = ctx.view_layer
    gpu.state.depth_test_set("LESS_EQUAL")
    gpu.state.blend_set("ALPHA")
    sh.bind()
    for name, e in _CACHE.items():
        o = bpy.data.objects.get(name)
        if o is None or o.name not in vl.objects or not o.visible_get():
            continue
        if e["rings"]:
            sh.uniform_float("color", ring_col)
            b = _ring_batch(sh)
            for M in e["rings"]:
                with gpu.matrix.push_pop():
                    gpu.matrix.multiply_matrix(M)
                    b.draw(sh)
        sh.uniform_float("color", ghost_col)
        for mesh, size, M in e["ghosts"]:
            b = _mesh_batch(sh, mesh)
            with gpu.matrix.push_pop():
                gpu.matrix.multiply_matrix(M)
                if b is None:
                    gpu.matrix.scale((size, size, size))
                    b = _cube_batch(sh)
                b.draw(sh)
    gpu.state.depth_test_set("NONE")
    gpu.state.blend_set("NONE")


# ── old files: the ring / ghost objects these previews used to be ──────────

def remove_old_objects():
    """Delete the race-ring circle empties and ghost objects older versions made."""
    n = 0
    for o in [o for o in bpy.data.objects if o.get("og_ring_preview") or o.get("og_dist_ghost")]:
        bpy.data.objects.remove(o, do_unlink=True); n += 1
    return n


@bpy.app.handlers.persistent
def _on_load(*_a):
    """File opened: drop the old preview objects, fix old cameras' lens driver."""
    try:
        remove_old_objects()
        from .operators.spawn import fix_camera_drivers
        fix_camera_drivers()
    except Exception:
        pass
    invalidate()


def register():
    if _HANDLE[0] is None:
        _HANDLE[0] = bpy.types.SpaceView3D.draw_handler_add(_draw, (), "WINDOW", "POST_VIEW")
    if _on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load)
    for h in (bpy.app.handlers.undo_post, bpy.app.handlers.redo_post):
        if invalidate not in h:
            h.append(invalidate)
    invalidate()


def unregister():
    if _HANDLE[0] is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_HANDLE[0], "WINDOW")
        _HANDLE[0] = None
    if _on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load)
    for h in (bpy.app.handlers.undo_post, bpy.app.handlers.redo_post):
        if invalidate in h:
            h.remove(invalidate)
    _CACHE.clear(); _BATCHES.clear()
