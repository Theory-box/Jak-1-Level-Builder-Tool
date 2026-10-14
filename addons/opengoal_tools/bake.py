# ---------------------------------------------------------------------------
# bake.py — OpenGOAL Level Tools
# Light baking into vertex colours, with the level's bake options
# (Collection.og_bake on the level collection):
#   - Emit: emissive materials get a second (Emit) pass, screen-blended on top
#     (1 - (1 - light) * (1 - strength * emit)), so it can only brighten.
#   - Light curve: an RGB Curves mapping (kept in a hidden node group per
#     level, drawn with Blender's curve widget) + factor. Jak 1 shows < 0.25 as
#     black and > 0.75 as over-lit; the presets help fit the bake to that.
#   - Vertex / Face corner: which domain the next bake writes.
#   - Auto blur: averages neighbouring colours (Strength, Passes); with Keep
#     sharp edges, corners across a marked-sharp edge or an edge sharper than
#     the angle aren't mixed (face-corner bakes keep their clean edges).
# Each pass is one Blender bake job (UI stays responsive); the next pass and
# the post-processing start from object_bake_complete. Post-processing works
# on whole attribute arrays (numpy). Values are the stored (sRGB) bytes, the
# ones Blender shows / paints.
# ---------------------------------------------------------------------------
from __future__ import annotations

import math
import numpy as np
import bpy

BAKE_ATTR = "BakedLight"
_EMIT_ATTR = "_og_bake_emit"

_PRESETS = {
    # combined-curve points; channel curves stay linear
    "LINEAR":   [(0.0, 0.0), (1.0, 1.0)],
    "JAK":      [(0.0, 0.25), (0.35, 0.4), (0.75, 0.72), (1.0, 0.9)],
    "SOFT":     [(0.0, 0.1), (0.5, 0.5), (1.0, 0.9)],
    "CONTRAST": [(0.0, 0.0), (0.25, 0.18), (0.75, 0.82), (1.0, 1.0)],
}
_PRESET_ITEMS = (
    ("JAK", "Fit 0.25-0.75", "Lifts darks above 0.25 and eases highlights, keeping bright spots over 0.75"),
    ("SOFT", "Soft", "Slightly flatter"),
    ("CONTRAST", "Contrast", "Darker darks, brighter brights"),
    ("LINEAR", "Linear", "No change (edit the curve yourself)"),
    ("CUSTOM", "Custom", "Your own curve (choosing a preset overwrites it)"),
)


# ── settings ────────────────────────────────────────────────────────────────

def curve_group(level_col, create=False):
    name = f"OG Bake Curve {level_col.name}"
    ng = bpy.data.node_groups.get(name)
    if ng is None and create:
        ng = bpy.data.node_groups.new(name, "ShaderNodeTree")
        ng.use_fake_user = True
        ng.nodes.new("ShaderNodeRGBCurve")
        _apply_preset(ng, level_col.og_bake.curve_preset)
    return ng


def curve_mapping(level_col, create=False):
    ng = curve_group(level_col, create)
    if ng is None:
        return None
    node = next((n for n in ng.nodes if n.bl_idname == "ShaderNodeRGBCurve"), None)
    return node.mapping if node else None


def _apply_preset(ng, preset):
    pts = _PRESETS.get(preset)
    if pts is None:
        return
    node = next(n for n in ng.nodes if n.bl_idname == "ShaderNodeRGBCurve")
    m = node.mapping
    for ci in range(4):
        c = m.curves[ci]
        want = pts if ci == 3 else _PRESETS["LINEAR"]
        while len(c.points) > len(want):
            c.points.remove(c.points[-1])
        while len(c.points) < len(want):
            c.points.new(0.5, 0.5)
        for p, (x, y) in zip(c.points, want):
            p.location = (x, y)
    m.update()


def _preset_update(self, ctx):
    col = self.id_data
    ng = curve_group(col)
    if ng is not None:
        _apply_preset(ng, self.curve_preset)


class OGBakeSettings(bpy.types.PropertyGroup):
    emit_strength: bpy.props.FloatProperty(
        name="Emit strength", default=0.5, min=0.0, soft_max=1.0,
        description="How much emissive materials brighten the bake (screen blend). 0 = no emit pass")
    use_curve: bpy.props.BoolProperty(
        name="Light curve", default=False,
        description="Remap the baked light with a curve (Jak 1: < 0.25 shows black, > 0.75 over-lit)")
    curve_preset: bpy.props.EnumProperty(name="Preset", items=_PRESET_ITEMS, default="JAK", update=_preset_update)
    curve_factor: bpy.props.FloatProperty(name="Factor", default=1.0, min=0.0, max=1.0, subtype="FACTOR",
                                          description="How much the curve affects the result")
    domain: bpy.props.EnumProperty(
        name="Bake to", default="CORNER",
        items=(("CORNER", "Face Corner", "Clean edges where the model is sharp"),
               ("POINT", "Vertex", "Smoother, no hard edges")),
        description="Domain of the next bake (existing bakes aren't changed)")
    use_blur: bpy.props.BoolProperty(name="Auto blur", default=False,
                                     description="Smooth the bake by averaging neighbouring colours")
    blur_strength: bpy.props.FloatProperty(name="Strength", default=0.5, min=0.0, max=1.0, subtype="FACTOR")
    blur_passes: bpy.props.IntProperty(name="Passes", default=2, min=1, max=50)
    blur_keep_sharp: bpy.props.BoolProperty(name="Keep sharp edges", default=True,
                                            description="Don't mix across edges marked sharp or sharper than the angle")
    blur_angle: bpy.props.FloatProperty(name="Angle", default=math.radians(30.0), min=0.0, max=math.pi,
                                        subtype="ANGLE")


# ── post-processing (numpy) ─────────────────────────────────────────────────

def _read(attr):
    n = len(attr.data)
    arr = np.empty(n * 4, dtype=np.float32)
    key = "color_srgb" if attr.data_type == "BYTE_COLOR" else "color"
    attr.data.foreach_get(key, arr)
    return arr.reshape(n, 4), key


def _write(attr, arr, key):
    attr.data.foreach_set(key, np.ascontiguousarray(arr, dtype=np.float32).ravel())


def screen(light, emit, strength):
    out = light.copy()
    out[:, :3] = 1.0 - (1.0 - light[:, :3]) * (1.0 - np.clip(strength * emit[:, :3], 0.0, 1.0))
    return out


def curve_luts(mapping, n=1024):
    """RGB lookup tables of the curve (combined curve, then channel curve)."""
    mapping.initialize()
    xs = np.linspace(0.0, 1.0, n)
    luts = []
    for ci in range(3):
        luts.append(np.array([mapping.evaluate(mapping.curves[ci], mapping.evaluate(mapping.curves[3], float(x)))
                              for x in xs], dtype=np.float32))
    return xs, luts


def apply_curve(cols, xs, luts, factor):
    out = cols.copy()
    for ci in range(3):
        mapped = np.interp(np.clip(cols[:, ci], 0.0, 1.0), xs, luts[ci])
        out[:, ci] = cols[:, ci] + (mapped - cols[:, ci]) * factor
    return out


def _corner_groups(mesh, keep_sharp, angle):
    """Group id per face corner: corners at one vertex joined across smooth
    edges (not marked sharp, face angle under `angle`)."""
    nl = len(mesh.loops)
    lv = np.empty(nl, dtype=np.int64); mesh.loops.foreach_get("vertex_index", lv)
    le = np.empty(nl, dtype=np.int64); mesh.loops.foreach_get("edge_index", le)
    if not keep_sharp:
        return lv, int(lv.max()) + 1 if nl else 0
    npoly = len(mesh.polygons)
    ls = np.empty(npoly, dtype=np.int64); mesh.polygons.foreach_get("loop_start", ls)
    lt = np.empty(npoly, dtype=np.int64); mesh.polygons.foreach_get("loop_total", lt)
    poly_of = np.repeat(np.arange(npoly), lt)
    nxt = np.arange(nl) + 1
    ends = ls + lt
    nxt[ends - 1] = ls                                   # wrap inside each face
    pn = np.empty(npoly * 3, dtype=np.float32); mesh.polygons.foreach_get("normal", pn); pn = pn.reshape(-1, 3)
    sharp = np.zeros(len(mesh.edges), dtype=bool)
    if "sharp_edge" in mesh.attributes:
        mesh.attributes["sharp_edge"].data.foreach_get("value", sharp)
    parent = np.arange(nl)

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    order = np.argsort(le, kind="stable")
    se = le[order]
    cos_lim = math.cos(angle)
    i = 0
    while i < nl:
        j = i
        while j + 1 < nl and se[j + 1] == se[i]:
            j += 1
        if j == i + 1 and not sharp[se[i]]:              # manifold edge shared by two faces
            a, b = order[i], order[j]
            if float(np.dot(pn[poly_of[a]], pn[poly_of[b]])) >= cos_lim:
                for x, y in ((a, nxt[b]), (b, nxt[a])):  # same vertex on both faces
                    rx, ry = find(x), find(y)
                    if rx != ry:
                        parent[rx] = ry
        i = j + 1
    roots = np.array([find(k) for k in range(nl)])
    _, gid = np.unique(roots, return_inverse=True)
    return gid, int(gid.max()) + 1 if nl else 0


def blur(mesh, cols, domain, strength, passes, keep_sharp=True, angle=math.radians(30.0)):
    """Average neighbouring colours `passes` times."""
    if domain == "POINT":
        ne = len(mesh.edges)
        ev = np.empty(ne * 2, dtype=np.int64); mesh.edges.foreach_get("vertices", ev); ev = ev.reshape(-1, 2)
        gid, ng = np.arange(len(cols)), len(cols)
        a, b = ev[:, 0], ev[:, 1]
        vals = cols.copy()
    else:
        gid, ng = _corner_groups(mesh, keep_sharp, angle)
        nl = len(mesh.loops)
        npoly = len(mesh.polygons)
        ls = np.empty(npoly, dtype=np.int64); mesh.polygons.foreach_get("loop_start", ls)
        lt = np.empty(npoly, dtype=np.int64); mesh.polygons.foreach_get("loop_total", lt)
        nxt = np.arange(nl) + 1
        nxt[ls + lt - 1] = ls
        a, b = gid, gid[nxt]                             # neighbours along each face edge
        cnt = np.bincount(gid, minlength=ng).astype(np.float32)[:, None]
        vals = np.zeros((ng, 4), dtype=np.float32)
        np.add.at(vals, gid, cols)
        vals /= np.maximum(cnt, 1)
    for _ in range(passes):
        acc = np.zeros_like(vals)
        n = np.zeros((len(vals), 1), dtype=np.float32)
        np.add.at(acc, a, vals[b]); np.add.at(acc, b, vals[a])
        np.add.at(n, a, 1.0); np.add.at(n, b, 1.0)
        mean = np.where(n > 0, acc / np.maximum(n, 1), vals)
        vals = vals + (mean - vals) * strength
    return vals[gid] if domain != "POINT" else vals


def post_process(obj, settings, mapping, emitted):
    """Emit combine, curve, blur on the object's BakedLight layer."""
    mesh = obj.data
    attr = mesh.color_attributes.get(BAKE_ATTR)
    if attr is None:
        return
    cols, key = _read(attr)
    if emitted and _EMIT_ATTR in mesh.color_attributes:
        em, _ = _read(mesh.color_attributes[_EMIT_ATTR])
        cols = screen(cols, em, settings.emit_strength)
    if settings.use_curve and mapping is not None and settings.curve_factor > 0:
        xs, luts = curve_luts(mapping)
        cols = apply_curve(cols, xs, luts, settings.curve_factor)
    if settings.use_blur and settings.blur_strength > 0:
        cols = blur(mesh, cols, attr.domain, settings.blur_strength, settings.blur_passes,
                    settings.blur_keep_sharp, settings.blur_angle)
    _write(attr, np.clip(cols, 0.0, 1.0), key)
    if _EMIT_ATTR in mesh.color_attributes:
        mesh.color_attributes.remove(mesh.color_attributes[_EMIT_ATTR])
    mesh.color_attributes.active_color = mesh.color_attributes[BAKE_ATTR]
    mesh.update()


def has_emission(obj) -> bool:
    for slot in obj.material_slots:
        m = slot.material
        if not (m and m.use_nodes and m.node_tree):
            continue
        for n in m.node_tree.nodes:
            if n.bl_idname == "ShaderNodeBsdfPrincipled":
                s = n.inputs.get("Emission Strength")
                c = n.inputs.get("Emission Color")
                if s is not None and s.default_value > 0 and (c is None or any(c.default_value[:3]) or c.is_linked):
                    return True
            elif n.bl_idname == "ShaderNodeEmission":
                s = n.inputs.get("Strength")
                if s is not None and s.default_value > 0:
                    return True
    return False


# ── the pass queue ──────────────────────────────────────────────────────────

_JOB: dict = {}


def _prepare(objs, name, domain):
    for o in objs:
        cas = o.data.color_attributes
        if name in cas and (cas[name].domain != domain or cas[name].data_type != "BYTE_COLOR"):
            cas.remove(cas[name])
        if name not in cas:
            cas.new(name=name, type="BYTE_COLOR", domain=domain)
        cas.active_color = cas[name]


def _run_pass():
    job = _JOB
    kind = job["passes"][job["i"]]
    objs = [bpy.data.objects.get(n) for n in job["objs"]]
    objs = [o for o in objs if o is not None]
    if kind == "light":
        _prepare(objs, BAKE_ATTR, job["domain"])
        args = dict(type="DIFFUSE", pass_filter={"DIRECT", "INDIRECT"})
    else:
        _prepare(objs, _EMIT_ATTR, job["domain"])
        args = dict(type="EMIT")
    if job["blocking"]:
        bpy.ops.object.bake("EXEC_DEFAULT", target="VERTEX_COLORS", save_mode="INTERNAL", **args)
        _on_complete(None)
    else:
        # later passes start from a timer: give the bake job a window
        win = bpy.context.window or (bpy.context.window_manager.windows[0] if bpy.context.window_manager.windows else None)
        act = bpy.context.view_layer.objects.active
        if act is None or act.name not in job["objs"]:
            bpy.context.view_layer.objects.active = objs[0]
        with bpy.context.temp_override(window=win):
            bpy.ops.object.bake("INVOKE_DEFAULT", target="VERTEX_COLORS", save_mode="INTERNAL", **args)


def _finish():
    job = dict(_JOB)
    _JOB.clear()
    col = bpy.data.collections.get(job.get("level", "")) if job.get("level") else None
    settings = col.og_bake if col is not None else None
    if settings is None:
        return
    mapping = curve_mapping(col) if settings.use_curve else None
    for n in job["objs"]:
        o = bpy.data.objects.get(n)
        if o is not None:
            post_process(o, settings, mapping, "emit" in job["passes"])


def _safe(fn):
    """Run a queue step; on error drop the job so later bakes aren't blocked."""
    try:
        fn()
    except Exception as e:
        _JOB.clear()
        print(f"[OpenGOAL] bake: {e}")
        raise


@bpy.app.handlers.persistent
def _on_complete(_scene, *args):
    if not _JOB or (_JOB["blocking"] and _scene is not None):   # blocking passes advance themselves
        return
    _JOB["i"] += 1
    if _JOB["i"] < len(_JOB["passes"]):
        if _JOB["blocking"]:
            _run_pass()
        else:
            bpy.app.timers.register(lambda: (_safe(_run_pass), None)[1], first_interval=0.0)
    else:
        if _JOB["blocking"]:
            _finish()
        else:
            bpy.app.timers.register(lambda: (_safe(_finish), None)[1], first_interval=0.0)


@bpy.app.handlers.persistent
def _on_cancel(_scene, *args):
    _JOB.clear()


def start(objs, level_col, blocking=False):
    """Bake the passes for objs (names kept), then post-process."""
    s = level_col.og_bake if level_col is not None else None
    passes = ["light"]
    if s is not None and s.emit_strength > 0 and any(has_emission(o) for o in objs):
        passes.append("emit")
    _JOB.clear()
    _JOB.update({"objs": [o.name for o in objs], "passes": passes, "i": 0,
                 "domain": s.domain if s is not None else "CORNER",
                 "level": level_col.name if level_col is not None else "", "blocking": blocking})
    _safe(_run_pass)
    return passes


def busy() -> bool:
    return bool(_JOB)


# ── UI ──────────────────────────────────────────────────────────────────────

def draw_options(layout, level_col):
    s = level_col.og_bake
    box = layout.box()
    box.label(text="Bake options", icon="PREFERENCES")
    box.row().prop(s, "domain", expand=True)
    box.prop(s, "emit_strength")
    col = box.column()
    col.prop(s, "use_curve")
    if s.use_curve:
        m = curve_mapping(level_col)
        row = col.row(align=True)
        row.prop(s, "curve_preset", text="")
        row.prop(s, "curve_factor")
        if m is None:
            col.operator("og.bake_curve_init", icon="FCURVE")
        else:
            node = next(n for n in curve_group(level_col).nodes if n.bl_idname == "ShaderNodeRGBCurve")
            col.template_curve_mapping(node, "mapping", type="COLOR")
    col = box.column()
    col.prop(s, "use_blur")
    if s.use_blur:
        row = col.row(align=True)
        row.prop(s, "blur_strength")
        row.prop(s, "blur_passes")
        if s.domain == "CORNER":
            row = col.row(align=True)
            row.prop(s, "blur_keep_sharp")
            sub = row.row(); sub.enabled = s.blur_keep_sharp
            sub.prop(s, "blur_angle")


class OG_OT_BakeCurveInit(bpy.types.Operator):
    """Create the level's light curve (kept in a hidden node group)"""
    bl_idname = "og.bake_curve_init"
    bl_label = "Set Up Curve"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        from .collections import _active_level_col
        col = _active_level_col(ctx.scene)
        if col is None:
            return {"CANCELLED"}
        curve_group(col, create=True)
        return {"FINISHED"}


CLASSES = (OGBakeSettings, OG_OT_BakeCurveInit)


def register_props():
    bpy.types.Collection.og_bake = bpy.props.PointerProperty(type=OGBakeSettings)
    for h, f in ((bpy.app.handlers.object_bake_complete, _on_complete),
                 (bpy.app.handlers.object_bake_cancel, _on_cancel)):
        if f not in h:
            h.append(f)


def unregister_props():
    for h, f in ((bpy.app.handlers.object_bake_complete, _on_complete),
                 (bpy.app.handlers.object_bake_cancel, _on_cancel)):
        if f in h:
            h.remove(f)
    try: del bpy.types.Collection.og_bake
    except Exception: pass
