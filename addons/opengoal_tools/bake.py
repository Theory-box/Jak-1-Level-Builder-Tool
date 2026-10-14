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
#     sharp edges, corners across the mesh's sharp edges (marked sharp,
#     flat-shaded faces; Auto sharp: also edges sharper than the angle) aren't
#     mixed, so face-corner bakes keep their clean edges.
#   - Curve presets: built-ins + your own (saved in the addon preferences).
#   - Time of day: one light pass per enabled time into _SUNRISE ... _GREENSUN
#     (the level builder's names), each with only its own light collection
#     rendering and its own world; emit / curve / blur apply to every time.
# Each pass is one Blender bake job (UI stays responsive); the modal Bake
# operator starts the next pass / the post-processing once that pass's
# object_bake_complete event came, the job is gone and data writes are allowed
# again; the emit pass only renders the emissive meshes. A status line under the Bake button shows each step / errors. Post-processing works
# on whole attribute arrays (numpy). Values are the stored (sRGB) bytes, the
# ones Blender shows / paints.
# ---------------------------------------------------------------------------
from __future__ import annotations

import math
import numpy as np
import bpy

BAKE_ATTR = "BakedLight"
_EMIT_ATTR = "_og_bake_emit"

_LIN = [(0.0, 0.0), (1.0, 1.0)]
_PRESETS = {
    # [R, G, B, combined] curve points (built-ins only shape the combined curve)
    "LINEAR":   [_LIN, _LIN, _LIN, _LIN],
    "JAK":      [_LIN, _LIN, _LIN, [(0.0, 0.25), (0.35, 0.4), (0.75, 0.72), (1.0, 0.9)]],
    "SOFT":     [_LIN, _LIN, _LIN, [(0.0, 0.1), (0.5, 0.5), (1.0, 0.9)]],
    "CONTRAST": [_LIN, _LIN, _LIN, [(0.0, 0.0), (0.25, 0.18), (0.75, 0.82), (1.0, 1.0)]],
}
_BUILTIN_ITEMS = [
    ("JAK", "Fit 0.25-0.75", "Lifts darks above 0.25 and eases highlights, keeping bright spots over 0.75"),
    ("SOFT", "Soft", "Slightly flatter"),
    ("CONTRAST", "Contrast", "Darker darks, brighter brights"),
    ("LINEAR", "Linear", "No change (edit the curve yourself)"),
]
_USER = "USER:"   # enum ids of saved presets


def user_presets() -> dict:
    """Saved curves {name: [R, G, B, C points]} (addon preferences: every file)."""
    import json
    a = bpy.context.preferences.addons.get("opengoal_tools")
    try:
        return json.loads(a.preferences.bake_curve_presets) if a else {}
    except Exception:
        return {}


def _save_user_presets(d):
    import json
    a = bpy.context.preferences.addons.get("opengoal_tools")
    if a:
        a.preferences.bake_curve_presets = json.dumps(d)
        bpy.context.preferences.is_dirty = True


_ITEMS: list = []


def _preset_items(self, ctx):
    items = list(_BUILTIN_ITEMS)
    items += [(_USER + n, n, "Saved curve") for n in sorted(user_presets())]
    items.append(("CUSTOM", "Custom", "Your own curve (choosing a preset overwrites it)"))
    _ITEMS[:] = [(a, b, c, i) for i, (a, b, c) in enumerate(items)]
    return _ITEMS


def preset_points(preset):
    if preset in _PRESETS:
        return _PRESETS[preset]
    if preset.startswith(_USER):
        return user_presets().get(preset[len(_USER):])
    return None


def mapping_points(m):
    return [[list(p.location) for p in m.curves[ci].points] for ci in range(4)]


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
    pts = preset_points(preset)
    if pts is None:
        return
    node = next(n for n in ng.nodes if n.bl_idname == "ShaderNodeRGBCurve")
    m = node.mapping
    for ci in range(4):
        c = m.curves[ci]
        want = pts[ci]
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


# Time of day: the 8 colour attributes the level builder reads (jak-project
# d04ac9d; a missing one uses the closest time, none at all COLOR_0).
# (key, attribute, label, default world colour, strength, sun elevation deg, sun colour, sun strength)
TIMES = (
    ("sunrise",   "_SUNRISE",   "Sunrise",   (1.0, 0.62, 0.42), 0.6,  8.0, (1.0, 0.62, 0.38), 2.5),
    ("morning",   "_MORNING",   "Morning",   (0.72, 0.82, 1.0), 0.9, 30.0, (1.0, 0.92, 0.8), 3.5),
    ("noon",      "_NOON",      "Noon",      (0.8, 0.9, 1.0),   1.0, 70.0, (1.0, 1.0, 0.95), 4.0),
    ("afternoon", "_AFTERNOON", "Afternoon", (0.9, 0.86, 0.8),  0.9, 40.0, (1.0, 0.9, 0.75), 3.5),
    ("sunset",    "_SUNSET",    "Sunset",    (1.0, 0.5, 0.32),  0.6,  8.0, (1.0, 0.5, 0.25), 2.5),
    ("twilight",  "_TWILIGHT",  "Twilight",  (0.42, 0.42, 0.72), 0.35, 4.0, (0.7, 0.55, 0.9), 1.0),
    ("evening",   "_EVENING",   "Evening",   (0.14, 0.18, 0.36), 0.2, 35.0, (0.55, 0.65, 1.0), 0.6),
    ("greensun",  "_GREENSUN",  "Green Sun", (0.42, 0.9, 0.55), 0.5, 45.0, (0.55, 1.0, 0.6), 3.0),
)
TOD_ATTRS = tuple(t[1] for t in TIMES)
# moods whose function picks a fixed time (update-mood-quick): time of day doesn't change in game
FIXED_TIME_MOODS = {"jungleb", "maincave", "darkcave", "robocave", "lavatube", "citadel"}
PARTLY_FIXED_MOODS = {"ogre", "finalboss"}


class OGTodTime(bpy.types.PropertyGroup):
    enabled: bpy.props.BoolProperty(name="Bake", default=True, description="Bake this time of day")
    lights: bpy.props.PointerProperty(type=bpy.types.Collection, name="Lights",
                                      description="Lights only used for this time (other times' collections are "
                                                  "off while it bakes; lights outside them light every time)")
    world: bpy.props.PointerProperty(type=bpy.types.World, name="World",
                                     description="World (environment) used while this time bakes")
    show: bpy.props.BoolProperty(name="Show", default=True)


def tod_times(settings):
    """[(key, attr, label, OGTodTime)] for the 8 times."""
    return [(k, a, l, getattr(settings, "tod_" + k)) for k, a, l, *_ in TIMES]


class OGBakeSettings(bpy.types.PropertyGroup):
    emit_strength: bpy.props.FloatProperty(
        name="Emit strength", default=1.0, min=0.0, soft_max=1.0,
        description="How much emissive materials brighten the bake (screen blend). 0 = no emit pass")
    use_curve: bpy.props.BoolProperty(
        name="Light curve", default=False,
        description="Remap the baked light with a curve (Jak 1: < 0.25 shows black, > 0.75 over-lit)")
    curve_preset: bpy.props.EnumProperty(name="Preset", items=_preset_items, update=_preset_update)
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
                                            description="Don't mix across the mesh's sharp edges (marked sharp, or flat-shaded faces)")
    blur_auto_sharp: bpy.props.BoolProperty(name="Auto sharp", default=False,
                                            description="Also treat edges sharper than the angle as sharp")
    blur_angle: bpy.props.FloatProperty(name="Angle", default=math.radians(30.0), min=0.0, max=math.pi,
                                        subtype="ANGLE")
    tod_enabled: bpy.props.BoolProperty(
        name="Time of day", default=False,
        description="Bake one colour layer per time of day (_SUNRISE ... _GREENSUN), each with its own lights / world. "
                    "Off: one BakedLight layer, as before")
    tod_sunrise: bpy.props.PointerProperty(type=OGTodTime)
    tod_morning: bpy.props.PointerProperty(type=OGTodTime)
    tod_noon: bpy.props.PointerProperty(type=OGTodTime)
    tod_afternoon: bpy.props.PointerProperty(type=OGTodTime)
    tod_sunset: bpy.props.PointerProperty(type=OGTodTime)
    tod_twilight: bpy.props.PointerProperty(type=OGTodTime)
    tod_evening: bpy.props.PointerProperty(type=OGTodTime)
    tod_greensun: bpy.props.PointerProperty(type=OGTodTime)



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


def _corner_groups(mesh, keep_sharp, angle=None):
    """Group id per face corner: corners at one vertex joined across smooth
    edges: not marked sharp, neither face flat-shaded, and (angle given)
    faces less than `angle` apart."""
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
    flat = np.zeros(npoly, dtype=bool)
    if "sharp_face" in mesh.attributes:
        mesh.attributes["sharp_face"].data.foreach_get("value", flat)
    parent = np.arange(nl)

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    order = np.argsort(le, kind="stable")
    se = le[order]
    cos_lim = math.cos(angle) if angle is not None else -2.0
    i = 0
    while i < nl:
        j = i
        while j + 1 < nl and se[j + 1] == se[i]:
            j += 1
        if j == i + 1 and not sharp[se[i]]:              # manifold edge shared by two faces
            a, b = order[i], order[j]
            if (not flat[poly_of[a]] and not flat[poly_of[b]]
                    and float(np.dot(pn[poly_of[a]], pn[poly_of[b]])) >= cos_lim):
                for x, y in ((a, nxt[b]), (b, nxt[a])):  # same vertex on both faces
                    rx, ry = find(x), find(y)
                    if rx != ry:
                        parent[rx] = ry
        i = j + 1
    roots = np.array([find(k) for k in range(nl)])
    _, gid = np.unique(roots, return_inverse=True)
    return gid, int(gid.max()) + 1 if nl else 0


def blur(mesh, cols, domain, strength, passes, keep_sharp=True, angle=None):
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


def post_process(obj, settings, mapping, emitted, attrs=(BAKE_ATTR,), luts=None):
    """Emit combine, curve, blur on each baked layer (BakedLight, or the time
    of day layers)."""
    mesh = obj.data
    em = None
    if emitted and _EMIT_ATTR in mesh.color_attributes:
        em, _ = _read(mesh.color_attributes[_EMIT_ATTR])
    for name in attrs:
        attr = mesh.color_attributes.get(name)
        if attr is None:
            continue
        cols, key = _read(attr)
        if em is not None:
            cols = screen(cols, em, settings.emit_strength)
        if settings.use_curve and mapping is not None and settings.curve_factor > 0:
            xs, lu = luts if luts is not None else curve_luts(mapping)
            cols = apply_curve(cols, xs, lu, settings.curve_factor)
        if settings.use_blur and settings.blur_strength > 0:
            cols = blur(mesh, cols, attr.domain, settings.blur_strength, settings.blur_passes,
                        settings.blur_keep_sharp, settings.blur_angle if settings.blur_auto_sharp else None)
        _write(attr, np.clip(cols, 0.0, 1.0), key)
    if _EMIT_ATTR in mesh.color_attributes:
        mesh.color_attributes.remove(mesh.color_attributes[_EMIT_ATTR])
    use_baked(mesh, "_NOON" if "_NOON" in attrs else attrs[0])   # shown in the viewport / COLOR_0
    mesh.update()


def use_baked(mesh, name=None):
    """The baked layer becomes the active and render colour layer: what the
    viewport shows and the GLB exports as COLOR_0. Default: BakedLight, else
    a time of day layer (noon first)."""
    cas = mesh.color_attributes
    if name is None:
        name = next((n for n in (BAKE_ATTR, "_NOON") + TOD_ATTRS if n in cas), None)
    a = cas.get(name) if name else None
    if a is None:
        return False
    cas.active_color = a
    idx = next(i for i, x in enumerate(cas) if x.name == name)
    cas.active_color_index = idx
    cas.render_color_index = idx
    return True


def _lit(sock, colour=False):
    """The socket carries something: linked (texture, nodes) or a non-zero value."""
    if sock is None:
        return False
    if sock.is_linked:
        return True
    v = sock.default_value
    return any(float(x) > 0 for x in list(v)[:3]) if colour else float(v) > 0


def _tree_emits(tree, seen) -> bool:
    if tree is None or tree.name in seen:
        return False
    seen.add(tree.name)
    for n in tree.nodes:
        if n.mute:
            continue
        if n.bl_idname == "ShaderNodeBsdfPrincipled":
            st = n.inputs.get("Emission Strength")
            co = n.inputs.get("Emission Color") or n.inputs.get("Emission")
            if _lit(st) and _lit(co, colour=True):
                return True
        elif n.bl_idname == "ShaderNodeEmission":
            if _lit(n.inputs.get("Strength")) and _lit(n.inputs.get("Color"), colour=True):
                return True
        elif n.bl_idname == "ShaderNodeGroup" and _tree_emits(n.node_tree, seen):
            return True
    return False


def has_emission(obj) -> bool:
    """A material of the object emits light (Principled emission or an Emission
    node, plain values or driven by textures / nodes, also inside groups)."""
    for slot in obj.material_slots:
        m = slot.material
        if m and m.use_nodes and m.node_tree and _tree_emits(m.node_tree, set()):
            return True
    return False


# ── the pass queue ──────────────────────────────────────────────────────────

_JOB: dict = {}


def _status(msg):
    try:
        bpy.context.window_manager.og_bake_status = msg
        for w in bpy.context.window_manager.windows:
            for a in w.screen.areas:
                if a.type == "VIEW_3D":
                    a.tag_redraw()
    except Exception:
        pass


def _prepare(objs, name, domain):
    for o in objs:
        cas = o.data.color_attributes
        if name in cas and (cas[name].domain != domain or cas[name].data_type != "BYTE_COLOR"):
            cas.remove(cas[name])
        if name not in cas:
            cas.new(name=name, type="BYTE_COLOR", domain=domain)
        cas.active_color = cas[name]


def _objs(names):
    return [o for o in (bpy.data.objects.get(n) for n in names) if o is not None]


def _select_only(objs):
    vl = bpy.context.view_layer
    keep = set(o.name for o in objs)
    for o in vl.objects:
        if o.select_get() != (o.name in keep):
            o.select_set(o.name in keep)
    if objs:
        vl.objects.active = objs[0]


def _run_pass():
    job = _JOB
    kind = job["passes"][job["i"]]
    if kind.startswith("light"):
        objs = _objs(job["objs"])
        attr = kind[6:] or BAKE_ATTR       # "light" or "light:_SUNRISE"
        if attr != BAKE_ATTR:
            _tod_setup(job, attr)
        _prepare(objs, attr, job["domain"])
        args = dict(type="DIFFUSE", pass_filter={"DIRECT", "INDIRECT"})
    else:   # only the meshes with an emissive material render the emit pass
        objs = _objs(job["emit_objs"])
        _prepare(objs, _EMIT_ATTR, job["domain"])
        args = dict(type="EMIT")
    _select_only(objs)
    import time
    job["evt"] = False                     # set by object_bake_complete for this pass
    job["pass_t"] = time.time()
    job["seen"] = False
    label = {a: l for _k, a, l, *_r in TIMES}.get(kind[6:], kind) if kind.startswith("light:") else kind
    _status(f"Baking: {label} pass ({len(objs)} mesh(es)) — {job['i'] + 1} of {len(job['passes'])}")
    if job["blocking"]:
        bpy.ops.object.bake("EXEC_DEFAULT", target="VERTEX_COLORS", save_mode="INTERNAL", **args)
        _next()
    else:
        # started from the modal Bake operator (operators/build.py), which
        # calls step() on its timer events
        bpy.ops.object.bake("INVOKE_DEFAULT", target="VERTEX_COLORS", save_mode="INTERNAL", **args)


def step() -> bool:
    """Called by the modal Bake operator on its timer: start the next pass /
    post-process once this pass's bake has really finished (its
    object_bake_complete event came, the job is gone and Blender accepts data
    writes again). False when the whole bake is over (or failed)."""
    import time
    if not _JOB:
        return False                      # finished / cancelled / error
    job_running = bpy.app.is_job_running("OBJECT_BAKE")
    refused = _still_rendering(_JOB["objs"])
    running = job_running or refused
    if running:
        _JOB["seen"] = True
    if running or not _JOB.get("evt"):
        waited = time.time() - _JOB.get("pass_t", 0)
        if not running and not _JOB["seen"] and waited > 120:
            _status("Bake error: the bake job never started (see the system console)")
            print("[OpenGOAL] bake: the bake job never started")
            _restore(_JOB)
            _JOB.clear()
            return False
        if waited > 60 and not _JOB.get("told"):
            _JOB["told"] = True           # one diagnostic line for long waits
            print(f"[OpenGOAL] bake: still waiting on the {_JOB['passes'][_JOB['i']]} pass after {waited:.0f}s "
                  f"(job running {job_running}, finished event {bool(_JOB.get('evt'))}, writes refused {refused})")
        return True
    _JOB["told"] = False
    _safe(_next)
    return bool(_JOB)


def _still_rendering(names) -> bool:
    """Blender refuses data writes while a bake is still rendering ("Writing to
    ID classes in this context is not allowed"). A no-op write tells us,
    whatever the job / event signals say."""
    for o in _objs(names[:1]):
        cas = o.data.color_attributes
        try:
            cas.active_color_index = cas.active_color_index
        except Exception as e:            # anything else (linked data ...) isn't "still rendering"
            return "not allowed" in str(e)
    return False


@bpy.app.handlers.persistent
def _on_complete(_scene, *args):
    if _JOB:
        _JOB["evt"] = True


def _level_settings(job):
    col = bpy.data.collections.get(job.get("level", "")) if job.get("level") else None
    return col, (col.og_bake if col is not None else None)


def _tod_setup(job, attr):
    """Only this time's light collection renders; its world is the scene's."""
    col, s = _level_settings(job)
    if s is None:
        return
    sc = bpy.context.scene
    if "restore" not in job:                 # put back after the bake
        job["restore"] = {"world": sc.world.name if sc.world else "",
                          "hide": {t.lights.name: t.lights.hide_render for _k, _a, _l, t in tod_times(s) if t.lights}}
    for _k, a, _l, t in tod_times(s):
        if t.lights:
            t.lights.hide_render = (a != attr)
    cur = next(t for _k, a, _l, t in tod_times(s) if a == attr)
    if cur.world:
        sc.world = cur.world


def _restore(job):
    r = job.get("restore")
    if not r:
        return
    for n, h in r["hide"].items():
        c = bpy.data.collections.get(n)
        if c is not None:
            c.hide_render = h
    bpy.context.scene.world = bpy.data.worlds.get(r["world"]) if r["world"] else None


def _finish():
    job = dict(_JOB)
    _JOB.clear()
    _restore(job)
    _status("Baking: post-processing…")
    _select_only(_objs(job["objs"]))       # the selection the bake started with
    col = bpy.data.collections.get(job.get("level", "")) if job.get("level") else None
    settings = col.og_bake if col is not None else None
    if settings is None:
        return
    mapping = curve_mapping(col) if settings.use_curve else None
    luts = curve_luts(mapping) if mapping is not None else None
    attrs = tuple(p[6:] or BAKE_ATTR for p in job["passes"] if p.startswith("light"))
    for n in job["objs"]:
        o = bpy.data.objects.get(n)
        if o is not None:
            post_process(o, settings, mapping, o.name in job["emit_objs"], attrs, luts)
    labels = {a: l for _k, a, l, *_r in TIMES}
    steps = [labels.get(p[6:], p) if p.startswith("light:") else p for p in job["passes"]] + \
            [x for x, on in (("curve", settings.use_curve), ("blur", settings.use_blur)) if on]
    _status(f"Baked {len(job['objs'])} mesh(es): {' + '.join(steps)}")


def _safe(fn):
    """Run a queue step; on error drop the job so later bakes aren't blocked."""
    try:
        fn()
    except Exception as e:
        _restore(_JOB)
        _JOB.clear()
        _status(f"Bake error: {e}")
        import traceback
        print("[OpenGOAL] bake:", traceback.format_exc())
        raise


def _next():
    import time
    _JOB["t"] = time.time()
    _JOB["i"] += 1
    if _JOB["i"] < len(_JOB["passes"]):
        _run_pass()
    else:
        _finish()


@bpy.app.handlers.persistent
def _on_cancel(_scene, *args):
    if _JOB:
        _status("Bake cancelled")
        _restore(_JOB)
    _JOB.clear()


def start(objs, level_col, blocking=False):
    """Bake the passes for objs (names kept), then post-process."""
    s = level_col.og_bake if level_col is not None else None
    passes = ["light"]
    if s is not None and s.tod_enabled:
        passes = [f"light:{a}" for _k, a, _l, t in tod_times(s) if t.enabled]
        if not passes:
            _status("Bake error: time of day is on but every time is off")
            return []
    emit_objs = [o.name for o in objs if has_emission(o)] if s is not None and s.emit_strength > 0 else []
    if emit_objs:
        passes.append("emit")
    _JOB.clear()
    import time
    _JOB.update({"t": time.time(), "objs": [o.name for o in objs], "emit_objs": emit_objs, "passes": passes, "i": 0,
                 "domain": s.domain if s is not None else "CORNER",
                 "level": level_col.name if level_col is not None else "", "blocking": blocking})
    _safe(_run_pass)
    return passes


def busy() -> bool:
    """A bake queue is running. A leftover queue (an error, a reload) with no
    Blender bake job behind it is dropped."""
    if _JOB and not _JOB.get("blocking") and not bpy.app.is_job_running("OBJECT_BAKE") and _JOB.get("evt"):
        import time
        if time.time() - _JOB.get("t", 0) > 5.0:
            _JOB.clear()
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
        row.operator("og.bake_curve_save", text="", icon="ADD")
        if s.curve_preset.startswith(_USER):
            row.operator("og.bake_curve_update", text="", icon="FILE_REFRESH")
            row.operator("og.bake_curve_remove", text="", icon="REMOVE")
        col.prop(s, "curve_factor")
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
            col.prop(s, "blur_keep_sharp")
            if s.blur_keep_sharp:
                row = col.row(align=True)
                row.prop(s, "blur_auto_sharp")
                sub = row.row(); sub.enabled = s.blur_auto_sharp
                sub.prop(s, "blur_angle")


def draw_tod(layout, level_col):
    s = level_col.og_bake
    box = layout.box()
    box.prop(s, "tod_enabled", icon="TIME")
    if not s.tod_enabled:
        return
    from .versions import draw_feature_note
    draw_feature_note(box, "time_of_day")
    mood = str(level_col.get("og_mood", "village1") or "village1")
    if mood in FIXED_TIME_MOODS or mood in PARTLY_FIXED_MOODS:
        r = box.row(); r.alert = True
        r.label(text=(f"Mood '{mood}' uses a fixed time: time of day won't change in game" if mood in FIXED_TIME_MOODS
                      else f"Mood '{mood}' switches to a fixed time in places"), icon="ERROR")
    row = box.row(align=True)
    row.operator("og.tod_default_worlds", icon="WORLD")
    row.operator("og.tod_default_suns", icon="LIGHT_SUN")
    for k, a, l, t in tod_times(s):
        col = box.column(align=True)
        row = col.row(align=True)
        row.prop(t, "show", text="", emboss=False, icon="TRIA_DOWN" if (t.show and t.enabled) else "TRIA_RIGHT")
        row.prop(t, "enabled", text=f"{l}  ({a})")
        if not (t.show and t.enabled):
            continue
        r = col.row(align=True)
        r.prop(t, "lights", text="Lights")
        op = r.operator("og.tod_new_lights", text="", icon="ADD"); op.time = k
        r = col.row(align=True)
        r.prop(t, "world", text="World")
        op = r.operator("og.tod_new_world", text="", icon="ADD"); op.time = k


def _tod_level(ctx):
    from .collections import _active_level_col
    return _active_level_col(ctx.scene)


def _time_row(key):
    return next(t for t in TIMES if t[0] == key)


def _new_lights(level_col, key):
    from .collections import _ensure_sub_collection
    label = _time_row(key)[2]
    c = _ensure_sub_collection(level_col, "Time of Day", label)
    c["skip_export"] = True                       # lights aren't level geometry
    getattr(level_col.og_bake, "tod_" + key).lights = c
    return c


def _new_world(level_col, key):
    _k, _a, label, colour, strength, *_r = _time_row(key)
    w = bpy.data.worlds.new(f"{level_col.name} {label}")
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    if bg is not None:
        bg.inputs["Color"].default_value = (*colour, 1.0)
        bg.inputs["Strength"].default_value = strength
    w.color = colour
    getattr(level_col.og_bake, "tod_" + key).world = w
    return w


def _new_sun(level_col, key):
    import math as _m
    _k, _a, label, _c, _s, elev, scol, sstr = _time_row(key)
    t = getattr(level_col.og_bake, "tod_" + key)
    col = t.lights or _new_lights(level_col, key)
    d = bpy.data.lights.new(f"{level_col.name} {label} Sun", "SUN")
    d.color = scol; d.energy = sstr; d.angle = _m.radians(2.0)
    o = bpy.data.objects.new(d.name, d)
    # elevation above the horizon; the sun turns through the day (east -> west)
    az = {"sunrise": 90, "morning": 120, "noon": 180, "afternoon": 240, "sunset": 270,
          "twilight": 280, "evening": 200, "greensun": 150}[key]
    o.rotation_euler = (_m.radians(90 - elev), 0.0, _m.radians(az))
    o.location = (0.0, 0.0, 20.0)
    col.objects.link(o)
    return o


class OG_OT_TodNewLights(bpy.types.Operator):
    """New light collection for this time of day (in <level>.Time of Day)"""
    bl_idname = "og.tod_new_lights"
    bl_label = "New Light Collection"
    bl_options = {"REGISTER", "UNDO"}
    time: bpy.props.StringProperty()

    def execute(self, ctx):
        lv = _tod_level(ctx)
        if lv is None:
            return {"CANCELLED"}
        _new_lights(lv, self.time)
        return {"FINISHED"}


class OG_OT_TodNewWorld(bpy.types.Operator):
    """New world for this time of day (outdoor-looking default colour)"""
    bl_idname = "og.tod_new_world"
    bl_label = "New World"
    bl_options = {"REGISTER", "UNDO"}
    time: bpy.props.StringProperty()

    def execute(self, ctx):
        lv = _tod_level(ctx)
        if lv is None:
            return {"CANCELLED"}
        _new_world(lv, self.time)
        return {"FINISHED"}


class OG_OT_TodDefaultWorlds(bpy.types.Operator):
    """Give every time of day without a world a default outdoor world"""
    bl_idname = "og.tod_default_worlds"
    bl_label = "Default Worlds"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        lv = _tod_level(ctx)
        if lv is None:
            return {"CANCELLED"}
        n = 0
        for k, *_r in TIMES:
            if getattr(lv.og_bake, "tod_" + k).world is None:
                _new_world(lv, k); n += 1
        self.report({"INFO"}, f"Created {n} world(s)")
        return {"FINISHED"}


class OG_OT_TodDefaultSuns(bpy.types.Operator):
    """Add a default sun to every time of day's light collection (angle and
    colour per time, for an outdoor look like Sandover's)"""
    bl_idname = "og.tod_default_suns"
    bl_label = "Default Suns"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        lv = _tod_level(ctx)
        if lv is None:
            return {"CANCELLED"}
        for k, *_r in TIMES:
            _new_sun(lv, k)
        self.report({"INFO"}, "Added 8 suns (one per time of day)")
        return {"FINISHED"}


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


def _level_curve(ctx):
    from .collections import _active_level_col
    col = _active_level_col(ctx.scene)
    return col, (curve_mapping(col) if col is not None else None)


class OG_OT_BakeCurveSave(bpy.types.Operator):
    """Save the current curve as a preset (kept in the addon preferences: every file)"""
    bl_idname = "og.bake_curve_save"
    bl_label = "Save Curve Preset"
    bl_options = {"REGISTER", "UNDO"}

    name: bpy.props.StringProperty(name="Name", default="My curve")

    def invoke(self, ctx, event):
        return ctx.window_manager.invoke_props_dialog(self)

    def execute(self, ctx):
        col, m = _level_curve(ctx)
        name = self.name.strip()
        if m is None or not name:
            return {"CANCELLED"}
        d = user_presets(); d[name] = mapping_points(m); _save_user_presets(d)
        col.og_bake.curve_preset = _USER + name
        self.report({"INFO"}, f"Saved curve preset '{name}'")
        return {"FINISHED"}


class OG_OT_BakeCurveUpdate(bpy.types.Operator):
    """Overwrite the selected saved preset with the current curve"""
    bl_idname = "og.bake_curve_update"
    bl_label = "Update Curve Preset"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        col, m = _level_curve(ctx)
        if m is None or not col.og_bake.curve_preset.startswith(_USER):
            return {"CANCELLED"}
        name = col.og_bake.curve_preset[len(_USER):]
        d = user_presets(); d[name] = mapping_points(m); _save_user_presets(d)
        self.report({"INFO"}, f"Updated curve preset '{name}'")
        return {"FINISHED"}


class OG_OT_BakeCurveRemove(bpy.types.Operator):
    """Delete the selected saved preset (the curve itself stays)"""
    bl_idname = "og.bake_curve_remove"
    bl_label = "Remove Curve Preset"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        col, m = _level_curve(ctx)
        p = col.og_bake.curve_preset if col is not None else ""
        if not p.startswith(_USER):
            return {"CANCELLED"}
        d = user_presets(); d.pop(p[len(_USER):], None); _save_user_presets(d)
        col.og_bake["curve_preset"] = len(_BUILTIN_ITEMS) + len(d)   # -> Custom (keeps the curve)
        self.report({"INFO"}, f"Removed curve preset '{p[len(_USER):]}'")
        return {"FINISHED"}


CLASSES = (OGTodTime, OGBakeSettings, OG_OT_TodNewLights, OG_OT_TodNewWorld, OG_OT_TodDefaultWorlds,
           OG_OT_TodDefaultSuns, OG_OT_BakeCurveInit, OG_OT_BakeCurveSave, OG_OT_BakeCurveUpdate, OG_OT_BakeCurveRemove)


def register_props():
    bpy.types.Collection.og_bake = bpy.props.PointerProperty(type=OGBakeSettings)
    # an addon reload can leave the previous module's handlers registered
    for hl in (bpy.app.handlers.object_bake_cancel, bpy.app.handlers.object_bake_complete):
        for f in [f for f in hl if getattr(f, "__module__", "").endswith(".bake")]:
            hl.remove(f)
    bpy.types.WindowManager.og_bake_status = bpy.props.StringProperty(default="")
    if _on_cancel not in bpy.app.handlers.object_bake_cancel:
        bpy.app.handlers.object_bake_cancel.append(_on_cancel)
    if _on_complete not in bpy.app.handlers.object_bake_complete:
        bpy.app.handlers.object_bake_complete.append(_on_complete)


def unregister_props():
    if _on_cancel in bpy.app.handlers.object_bake_cancel:
        bpy.app.handlers.object_bake_cancel.remove(_on_cancel)
    if _on_complete in bpy.app.handlers.object_bake_complete:
        bpy.app.handlers.object_bake_complete.remove(_on_complete)
    try: del bpy.types.WindowManager.og_bake_status
    except Exception: pass
    try: del bpy.types.Collection.og_bake
    except Exception: pass
