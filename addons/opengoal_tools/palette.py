# ---------------------------------------------------------------------------
# palette.py — OpenGOAL Level Tools
# Colour quantisation preview (Light Baking > Color Quantisation).
# The level builder (jak-project goalc/build_level/common/color_quantization.cpp,
# gltf_mesh_extract.cpp) gives every vertex a 32-byte colour (8 times of day x
# RGBA), and the whole level's colours share one palette: a k-d tree 13 levels
# deep (8192 colours at most), split round-robin on byte 0, 1, 2 ... (skipping
# one that's constant in the node) at the mean of the unique values, then
# empty buckets filled by splitting on the widest byte; each palette colour is
# its bucket's average (alpha halved). Bytes are what the GLB carries: linear
# 16-bit colours, top 8 bits. Times a mesh doesn't have use the closest time
# (earlier first); a level without time of day uses COLOR_0 for all 8.
# Before time of day (jak-project #4111) colours were 4 bytes (COLOR_0), same
# tree: the preview follows the install (versions "time_of_day").
# Preview runs the same steps on the level's exported meshes and shows one
# time in a preview colour layer; Restore removes it.
# ---------------------------------------------------------------------------
from __future__ import annotations

import numpy as np
import bpy

PREVIEW = "OG Palette Preview"
_PREV_KEY = "og_palette_prev"       # the layer shown before the preview (mesh custom prop)
_DEPTH = 13                         # kColorTreeDepth
_CACHE: dict = {}                   # mesh name -> quantised (corners, 32) uint8, last preview
_STATS: dict = {}


def _bytes(arr):
    """Linear float colours -> the level builder's bytes (16-bit, top 8 bits)."""
    return (np.clip(np.round(arr * 65535.0), 0, 65535).astype(np.uint32) >> 8).astype(np.uint8)


def _corner_colours(mesh, attr):
    """(corners, 4) linear colours of a colour layer, on face corners."""
    a = np.empty(len(attr.data) * 4, np.float32)
    attr.data.foreach_get("color", a)
    a = a.reshape(-1, 4)
    if attr.domain == "POINT":
        lv = np.empty(len(mesh.loops), np.int32)
        mesh.loops.foreach_get("vertex_index", lv)
        a = a[lv]
    return a


def mesh_vectors(mesh, tod, wide=True):
    """(corners, 32) uint8 (4 for a build without time of day): what the
    level builder reads for this mesh."""
    from .bake import TOD_ATTRS, BAKE_ATTR
    cas = mesh.color_attributes
    n = len(mesh.loops)
    have = [a in cas for a in TOD_ATTRS] if (tod and wide) else [False] * 8
    slots = [None] * 8
    if any(have):
        for i in range(8):
            for d in range(8):                      # closest time, earlier first
                if have[(i - d) % 8]:
                    slots[i] = TOD_ATTRS[(i - d) % 8]; break
                if have[(i + d) % 8]:
                    slots[i] = TOD_ATTRS[(i + d) % 8]; break
        cols = {a: _bytes(_corner_colours(mesh, cas[a])) for a in set(slots)}
        return np.concatenate([cols[a] for a in slots], axis=1)
    # COLOR_0: the layer the export makes active (bake.use_baked), else white
    name = next((x for x in (BAKE_ATTR, "_NOON") + TOD_ATTRS if x in cas), None)
    if name is None:
        rgba = np.tile(np.array([0x80, 0x80, 0x80, 0xFF], np.uint8), (n, 1))
    else:
        rgba = _bytes(_corner_colours(mesh, cas[name]))
    return np.tile(rgba, (1, 8)) if wide else rgba


def _split(U, idx, dim, depth):
    """split_kd for one node: (left, right) index arrays."""
    nc = U.shape[1]
    for _ in range(nc):                             # skip bytes that are constant here
        col = U[idx, dim]
        if (col == col[0]).all():
            dim = (dim + 1) % nc
        else:
            break
    order = idx[np.argsort(U[idx, dim], kind="stable")]
    vals = U[order, dim].astype(np.int32)
    k = len(vals)
    mean = np.unique(vals).mean()
    ge = np.nonzero(vals >= mean)[0]
    mid = int(ge[0]) if len(ge) else k - 1
    if depth & 1:
        if mid > 1:
            mid = max(int(np.searchsorted(vals, vals[mid], "left")), 1)
    elif mid + 2 < k:
        mid = min(int(np.searchsorted(vals, vals[mid], "right")) - 1, k - 2)
    return order[:mid], order[mid:], dim


def quantize(U, depth=_DEPTH):
    """quantize_colors_kd_tree on unique colours U (n, 32 or 4) uint8.
    Returns (bucket of each row, palette (buckets, 32) uint8)."""
    leaves = []
    stack = [(np.arange(len(U)), depth, 0)]
    while stack:
        idx, d, dim = stack.pop()
        if len(idx) == 0:
            continue
        if d == 0:
            leaves.append(idx); continue
        left, right, dim = _split(U, idx, dim, d)
        nd = (dim + 1) % U.shape[1]
        stack.append((right, d - 1, nd))           # left first (popped first)
        stack.append((left, d - 1, nd))
    target = 1 << depth
    while len(leaves) < target:
        splittable = [i for i, l in enumerate(leaves) if len(l) > 1 and (U[l[0]] != U[l[-1]]).any()]
        if not splittable:
            break
        count = len(leaves)
        new = list(leaves); shift = 0
        for i in splittable:
            if count >= target:
                break
            l = leaves[i]
            rng = U[l].max(0).astype(np.int32) - U[l].min(0)
            dim = int(np.argmax(rng)) if rng.max() > 0 else 0
            a, b, _d = _split(U, l, dim, 1)
            parts = [x for x in (a, b) if len(x)]
            new[i + shift:i + shift + 1] = parts
            shift += len(parts) - 1
            count += 1
        if len(new) == len(leaves):
            break
        leaves = new
    bucket = np.empty(len(U), np.int64)
    pal = np.empty((len(leaves), U.shape[1]), np.uint8)
    for j, l in enumerate(leaves):
        bucket[l] = j
        tot = U[l].astype(np.uint64).sum(0)
        avg = tot // len(l)
        avg[3::4] = tot[3::4] // (2 * len(l))
        pal[j] = np.minimum(avg, 255).astype(np.uint8)
    return bucket, pal


def _meshes(level_col):
    from .export.glb import exported_meshes
    seen, out = set(), []
    for o in exported_meshes(level_col):
        if o.data.name not in seen and not o.data.library:
            seen.add(o.data.name); out.append(o.data)
    return out


def show_time(meshes, slot):
    """Write the cached quantised colours of time `slot` (0-7) into the
    preview layers."""
    for me in meshes:
        q = _CACHE.get(me.name)
        if q is None or len(q) != len(me.loops):
            continue
        cas = me.color_attributes
        if PREVIEW not in cas:
            act = cas.active_color
            me[_PREV_KEY] = act.name if act else ""
            cas.new(PREVIEW, "FLOAT_COLOR", "CORNER")
        rgba = np.ones((len(q), 4), np.float32)
        slot = slot if q.shape[1] > 4 else 0
        rgba[:, :3] = q[:, slot * 4:slot * 4 + 3] / 255.0
        cas[PREVIEW].data.foreach_set("color", rgba.ravel())
        cas.active_color = cas[PREVIEW]
        cas.render_color_index = next(i for i, x in enumerate(cas) if x.name == PREVIEW)
        me.update()


def preview(level_col, slot):
    """Quantise the level's colours like the level builder; show time `slot`.
    Returns the stats dict."""
    from .versions import feature_available
    wide = bool(feature_available("time_of_day"))
    tod = bool(level_col.og_bake.tod_enabled) and wide
    meshes = _meshes(level_col)
    vecs = [mesh_vectors(me, tod, wide) for me in meshes]
    allv = np.concatenate(vecs) if vecs else np.zeros((0, 32), np.uint8)
    if not len(allv):
        return {}
    U, inv = np.unique(allv, axis=0, return_inverse=True)
    inv = inv.ravel()
    bucket, pal = quantize(U)
    q = pal[bucket[inv]]
    ref = allv.astype(np.int32); ref[:, 3::4] //= 2
    err = np.abs(q.astype(np.int32) - ref)
    nt = allv.shape[1] // 4
    per_time = [float(err[:, t * 4:t * 4 + 3].mean()) for t in range(nt)]
    worst = [int(err[:, t * 4:t * 4 + 3].max()) for t in range(nt)]
    _CACHE.clear()
    o = 0
    for me, v in zip(meshes, vecs):
        _CACHE[me.name] = q[o:o + len(v)]; o += len(v)
    show_time(meshes, slot)
    _STATS.clear()
    _STATS.update({"level": level_col.name, "unique": len(U), "palette": len(pal), "meshes": len(meshes),
                   "tod": tod, "mean": per_time, "worst": worst})
    return _STATS


def restore(meshes=None):
    """Remove the preview layers; the layer shown before comes back."""
    from .bake import use_baked
    n = 0
    for me in meshes if meshes is not None else list(bpy.data.meshes):
        cas = me.color_attributes
        if PREVIEW not in cas:
            continue
        cas.remove(cas[PREVIEW])
        prev = me.get(_PREV_KEY, "")
        if _PREV_KEY in me:
            del me[_PREV_KEY]
        if not (prev and use_baked(me, prev)):
            use_baked(me)
        me.update(); n += 1
    _CACHE.clear()
    return n


# ── UI ──────────────────────────────────────────────────────────────────────

HELP = (
    "The game keeps a level's vertex colours in one palette of at most 8192 colours,",
    "shared by all its meshes and all 8 times of day. When the level is built, similar",
    "colours are grouped and each group becomes its average, so rare colours (dark,",
    "tinted shadows especially) can come out quite different from the bake.",
    "Only sunrise, morning, noon and part of afternoon decide the groups; the other",
    "times are just averaged inside them.",
    "Preview Palette runs the same steps on this level's colours and shows the result;",
    "Restore shows your bake again (the bake itself is never changed).",
)


def time_update(self, ctx):
    if _CACHE and _STATS.get("level") == self.id_data.name:
        show_time(_meshes(self.id_data), int(self.palette_time))


def draw(layout, level_col):
    s = level_col.og_bake
    box = layout.box()
    row = box.row(align=True)
    row.prop(s, "show_palette", text="", emboss=False, icon="TRIA_DOWN" if s.show_palette else "TRIA_RIGHT")
    row.label(text="Color Quantisation", icon="COLOR")
    row.operator("og.palette_help", text="", icon="QUESTION", emboss=False)
    if not s.show_palette:
        return
    if s.tod_enabled:
        box.prop(s, "palette_time", text="Show")
    row = box.row(align=True)
    row.operator("og.palette_preview", icon="HIDE_OFF")
    row.operator("og.palette_restore", icon="LOOP_BACK")
    st = _STATS if _STATS.get("level") == level_col.name else None
    if st:
        col = box.column(align=True); col.scale_y = 0.8
        col.label(text=f"{st['unique']} colours on {st['meshes']} mesh(es) -> {st['palette']} in the palette")
        if st["tod"]:
            from .bake import TIMES
            for i, (_k, _a, l, *_r) in enumerate(TIMES):
                r = col.row(); r.alert = st["mean"][i] > 4.0
                r.label(text=f"{l}: off by {st['mean'][i]:.1f} on average, {st['worst'][i]} at most (of 255)")
        else:
            col.label(text=f"Off by {st['mean'][0]:.1f} on average, {st['worst'][0]} at most (of 255)")


class OG_OT_PaletteHelp(bpy.types.Operator):
    """What Color Quantisation is about"""
    bl_idname = "og.palette_help"
    bl_label = "Color Quantisation"

    def execute(self, ctx):
        return {"FINISHED"}

    def invoke(self, ctx, event):
        return ctx.window_manager.invoke_popup(self, width=480)

    def draw(self, ctx):
        col = self.layout.column(align=True)
        col.label(text="Color Quantisation", icon="COLOR")
        for line in HELP:
            col.label(text=line)


class OG_OT_PalettePreview(bpy.types.Operator):
    """Group this level's vertex colours into a palette like the level builder does and show the result
(a preview colour layer; Restore removes it)"""
    bl_idname = "og.palette_preview"
    bl_label = "Preview Palette"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        from .collections import _active_level_col
        lv = _active_level_col(ctx.scene)
        if lv is None:
            self.report({"ERROR"}, "No active level"); return {"CANCELLED"}
        import time
        t = time.time()
        st = preview(lv, int(lv.og_bake.palette_time) if lv.og_bake.tod_enabled else 0)
        if not st:
            self.report({"WARNING"}, "No level meshes"); return {"CANCELLED"}
        self.report({"INFO"}, f"Palette: {st['unique']} colours -> {st['palette']} ({time.time() - t:.1f}s)")
        return {"FINISHED"}


class OG_OT_PaletteRestore(bpy.types.Operator):
    """Remove the palette preview: the meshes show their bake again"""
    bl_idname = "og.palette_restore"
    bl_label = "Restore"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        n = restore()
        _STATS.clear()
        self.report({"INFO"}, f"Restored {n} mesh(es)")
        return {"FINISHED"}


CLASSES = (OG_OT_PaletteHelp, OG_OT_PalettePreview, OG_OT_PaletteRestore)
