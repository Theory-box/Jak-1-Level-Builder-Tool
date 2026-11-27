"""Custom actors (OpenGOAL Actors tab) -> the files OpenGOAL's build-actor reads.

export_actor: the actor's Model + Collision objects as custom_assets/jak1/models/custom_levels/
<name>.glb (glTF: +Y up, metres, skin, one animation per included action in the list's order,
custom properties for the collision settings, the active colour attribute), then a
(build-actor "<name>" [:gen-mesh #t]) line in game.gp. Only written when it changed.
On OpenGOAL 0.3.6+ (custom_actors.bone_fix_on) the glb gets the bone shift counter-fix:
an end joint under the skin's last joint (still channels in every animation) and +1 on
every vertex's bone indices (checked in game: without the end joint the last bone breaks).
A level that places an actor (ACTOR_<name>_ ...) lists it in custom_models and bundles
<name>-ag.go (level_models / level_ags).
"""
from __future__ import annotations

import json
import os
import struct
import tempfile

import bpy

from .paths import _data, _game_gp, log
from .fileio import patch, rewrite

MODEL_DIR = ("custom_assets", "jak1", "models", "custom_levels")
_TAG = "; og-level-tools custom-actor"


# ── glb (binary glTF) editing ──────────────────────────────────────────────

def _chunks(data):
    jlen = struct.unpack_from("<I", data, 12)[0]
    js = json.loads(data[20:20 + jlen])
    boff = 20 + jlen
    blen = struct.unpack_from("<I", data, boff)[0]
    return js, bytearray(data[boff + 8:boff + 8 + blen])


def _pack(js, binb):
    j = json.dumps(js, separators=(",", ":")).encode()
    j += b" " * (-len(j) % 4)
    binb = bytes(binb) + b"\0" * (-len(binb) % 4)
    js_total = 12 + 8 + len(j) + 8 + len(binb)
    return (struct.pack("<III", 0x46546C67, 2, js_total) + struct.pack("<II", len(j), 0x4E4F534A) + j
            + struct.pack("<II", len(binb), 0x004E4942) + binb)


def anim_name(action_name):
    """An action's animation name in the art group (<actor>-<this>-ja)."""
    from ..custom_actors import clean
    return clean(action_name) or "anim"


def order_animations(js, names):
    """Keep only the named animations, in that order, named like the art group's elements."""
    anims = js.get("animations") or []
    by = {a.get("name"): a for a in anims}
    js["animations"] = [by[n] for n in names if n in by]
    for a in js["animations"]:
        a["name"] = anim_name(a["name"])
    if not js["animations"]:
        js.pop("animations", None)


def bone_fix(js, binb):
    """The 0.3.6+ counter-fix (see the module notes)."""
    skins = js.get("skins") or []
    if not skins:
        return
    skin = skins[0]
    last = skin["joints"][-1]
    js["nodes"].append({"name": "og-end-joint"})
    end = len(js["nodes"]) - 1
    js["nodes"][last].setdefault("children", []).append(end)
    skin["joints"].append(end)
    if "inverseBindMatrices" in skin:
        acc = js["accessors"][skin["inverseBindMatrices"]]
        bv = js["bufferViews"][acc["bufferView"]]
        start = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
        old = bytes(binb[start:start + 64 * acc["count"]])
        binb += b"\0" * (-len(binb) % 4)
        off = len(binb)
        binb += old + struct.pack("<16f", 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
        js["bufferViews"].append({"buffer": 0, "byteOffset": off, "byteLength": len(old) + 64})
        acc["bufferView"] = len(js["bufferViews"]) - 1
        acc.pop("byteOffset", None)
        acc["count"] += 1
    for anim in js.get("animations", []):
        if not anim.get("samplers"):
            continue
        inp = anim["samplers"][0]["input"]
        n = js["accessors"][inp]["count"]
        for path, vals, typ in (("translation", (0.0, 0.0, 0.0), "VEC3"), ("rotation", (0.0, 0.0, 0.0, 1.0), "VEC4"),
                                ("scale", (1.0, 1.0, 1.0), "VEC3")):
            binb += b"\0" * (-len(binb) % 4)
            off = len(binb)
            binb += struct.pack(f"<{len(vals) * n}f", *(vals * n))
            js["bufferViews"].append({"buffer": 0, "byteOffset": off, "byteLength": 4 * len(vals) * n})
            js["accessors"].append({"bufferView": len(js["bufferViews"]) - 1, "componentType": 5126, "count": n,
                                    "type": typ})
            anim["samplers"].append({"input": inp, "output": len(js["accessors"]) - 1, "interpolation": "LINEAR"})
            anim["channels"].append({"sampler": len(anim["samplers"]) - 1, "target": {"node": end, "path": path}})
    done = set()
    for mesh in js.get("meshes", []):
        for p in mesh["primitives"]:
            ai = p["attributes"].get("JOINTS_0")
            if ai is None or ai in done:
                continue
            done.add(ai)
            acc = js["accessors"][ai]
            bv = js["bufferViews"][acc["bufferView"]]
            size, fmt = {5121: (1, "B"), 5123: (2, "H")}[acc["componentType"]]
            start = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
            stride = bv.get("byteStride", 4 * size)
            for k in range(acc["count"]):
                for c in range(4):
                    o = start + k * stride + c * size
                    struct.pack_into("<" + fmt, binb, o, struct.unpack_from("<" + fmt, binb, o)[0] + 1)


def _mat(node):
    from mathutils import Matrix, Quaternion
    if "matrix" in node:
        m = node["matrix"]
        return Matrix([[m[c * 4 + r] for c in range(4)] for r in range(4)])    # glTF: column-major
    t = node.get("translation", (0, 0, 0))
    q = node.get("rotation", (0, 0, 0, 1))
    s = node.get("scale", (1, 1, 1))
    return (Matrix.Translation(t) @ Quaternion((q[3], q[0], q[1], q[2])).to_matrix().to_4x4()
            @ Matrix.Diagonal((s[0], s[1], s[2], 1.0)))


def _dfs(js):
    """Node indices in build-actor's order (depth first from the scene's roots)."""
    out = []

    def walk(i):
        out.append(i)
        for c in js["nodes"][i].get("children", []):
            walk(c)
    for sc_ in js.get("scenes", []):
        for i in sc_.get("nodes", []):
            walk(i)
    return out


def bone_collision(js, binb, coll_bones):
    """Collision meshes that follow a bone: moved into that bone's rest space (its inverse bind
    matrix), so the game can carry them on the joint. Returns the joint index (node-list: 0 = the
    actor, a skin's bone s = s + 2) of each collision mesh, in build-actor's order."""
    from mathutils import Matrix
    nodes = js["nodes"]
    parent = {c: i for i, n in enumerate(nodes) for c in n.get("children", [])}

    def world(i):
        m = _mat(nodes[i])
        while i in parent:
            i = parent[i]
            m = _mat(nodes[i]) @ m
        return m
    skin = (js.get("skins") or [None])[0]
    ibm = []
    if skin and "inverseBindMatrices" in skin:
        acc = js["accessors"][skin["inverseBindMatrices"]]
        bv = js["bufferViews"][acc["bufferView"]]
        st = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
        for k in range(acc["count"]):
            f = struct.unpack_from("<16f", binb, st + 64 * k)
            ibm.append(Matrix([[f[c * 4 + r] for c in range(4)] for r in range(4)]))
    joint_of = {nodes[j].get("name"): s for s, j in enumerate(skin["joints"])} if skin else {}
    out = []
    for i in _dfs(js):
        n = nodes[i]
        if "mesh" not in n or n.get("name") not in coll_bones:
            continue
        b = coll_bones[n["name"]]
        s = joint_of.get(b) if b else None
        if s is None or s >= len(ibm):
            out.append(0)
            continue
        new_world = ibm[s] @ world(i)
        local = (world(parent[i]).inverted() @ new_world) if i in parent else new_world
        for k in ("translation", "rotation", "scale"):
            n.pop(k, None)
        n["matrix"] = [local[r][c] for c in range(4) for r in range(4)]
        out.append(s + 2)
    return out


def post_process(data, anim_names, fix, coll_bones=None):
    """Returns (glb bytes, collision joints in build-actor's order)."""
    js, binb = _chunks(data)
    order_animations(js, anim_names)
    joints = bone_collision(js, binb, coll_bones) if coll_bones else []
    if fix:
        bone_fix(js, binb)
    js["buffers"][0]["byteLength"] = len(binb) + (-len(binb) % 4)
    return _pack(js, binb), joints


# ── export ─────────────────────────────────────────────────────────────────

def glb_path(name):
    return _data().joinpath(*MODEL_DIR) / f"{name}.glb"


def _export_glb(scene, objs, path):
    """Blender's glTF exporter on just these objects (selection restored after)."""
    vl = bpy.context.view_layer
    sel = [o for o in bpy.context.selected_objects]
    act = vl.objects.active
    mode = act.mode if act is not None else "OBJECT"
    if mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")             # (edits in Edit Mode reach the mesh)
    try:
        for o in sel:
            o.select_set(False)
        for o in objs:
            o.hide_set(False)
            o.select_set(True)
        vl.objects.active = objs[0]
        bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_yup=True,
                                  export_apply=False, export_skins=True, export_animations=True,
                                  export_animation_mode="ACTIONS", export_extras=True,
                                  export_vertex_color="ACTIVE", export_cameras=False, export_lights=False)
    finally:
        for o in objs:
            o.select_set(False)
        for o in sel:
            if o.name in vl.objects:
                o.select_set(True)
        vl.objects.active = act
        if mode != "OBJECT" and act is not None:
            bpy.ops.object.mode_set(mode=mode)


def export_actor(scene, a):
    """Write the actor's glb + build line. Returns an error text, or ''."""
    from .. import custom_actors as CA
    name = CA.clean(a.name)
    red = [t for t, r in CA.checks(scene, a) if r]
    if red:
        return red[0]
    objs = CA.model_objects(a) + CA.collision_objects(a)
    if a.armature is not None and a.armature not in objs:
        objs.append(a.armature)
    objs = [o for o in objs if o.type in ("MESH", "ARMATURE")]
    if not objs:
        return "nothing to export"
    CA.sync_anims(a)
    anims = [x.action.name for x in a.anims if x.include and x.action]
    gen_mesh = uses_mesh_collision(a)
    marks = _collision_marks(a) if gen_mesh else []
    # Export origin: the chosen point moved to the scene's origin for the export (then put back)
    p0 = CA.origin_point(a)
    tops = [o for o in objs if o.parent is None or o.parent not in objs]
    for o in tops:
        o.matrix_world.translation -= p0
    bpy.context.view_layer.update()
    fd, tmp = tempfile.mkstemp(suffix=".glb")
    os.close(fd)
    try:
        _export_glb(scene, objs, tmp)
        data = open(tmp, "rb").read()
    finally:
        for o in tops:
            o.matrix_world.translation += p0
        bpy.context.view_layer.update()
        _unmark(marks)                                    # the user's own settings back
        try:
            os.remove(tmp)
        except OSError:
            pass
    coll_bones = {o.name: CA.collision_bone(o) for o in CA.collision_objects(a)} if gen_mesh else None
    data, joints = post_process(data, anims, CA.bone_fix_on(scene), coll_bones)
    a.coll_joints = ",".join(str(j) for j in joints)
    p = glb_path(name)
    if not (p.exists() and p.read_bytes() == data):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        log(f"[custom actor] wrote {p.name} ({len(data)} bytes, {len(anims)} animation(s))")
    register(name, gen_mesh=gen_mesh)
    return ""


def uses_mesh_collision(a):
    from .. import custom_actors as CA
    return a.template == "basic" and a.collision == "mesh" and bool(CA.collision_objects(a))


def _collision_marks(a):
    """For :gen-mesh (every mesh becomes collision unless told): the model's meshes no collision,
    the Collision meshes invisible + collision. Returns [(object, prop, old value)] to put back."""
    from .. import custom_actors as CA
    marks = []

    def put(ob, k, v):
        # a plain custom property (also the storage of the add-on's registered one): Blender 5's
        # glTF exporter leaves registered properties out, this one goes in
        marks.append((ob, k, k in ob.keys(), ob.get(k)))
        ob[k] = int(v)
    for ob in CA.model_objects(a):
        if ob.type == "MESH":
            put(ob, "set_collision", True)
            put(ob, "ignore", True)
    for ob in CA.collision_objects(a):
        put(ob, "set_invisible", True)
        put(ob, "set_collision", True)
        put(ob, "ignore", False)
    return marks


def _unmark(marks):
    for ob, k, had, old in reversed(marks):
        if had:
            ob[k] = old
        elif k in ob.keys():
            del ob[k]


def register(name, gen_mesh=False):
    """Its (build-actor ...) line in game.gp (replaced if the options changed)."""
    line = f'(build-actor "{name}"{" :gen-mesh #t" if gen_mesh else ""}) {_TAG}'
    gp = _game_gp()
    rewrite(gp, lambda t: "".join(l for l in t.splitlines(True)
                                  if not (_TAG in l and f'(build-actor "{name}"' in l and line not in l)))
    patch(gp, [line], '(group-list "all-code"', f"{name} build-actor")


def unregister_missing(scene):
    """Drop the build lines of custom actors this file no longer has."""
    from .. import custom_actors as CA
    keep = {CA.clean(a.name) for a in scene.og_custom_actors}

    def fn(t):
        out = []
        for l in t.splitlines(True):
            if _TAG in l:
                n = l.split('"')[1] if '"' in l else ""
                if n not in keep:
                    continue
            out.append(l)
        return "".join(out)
    rewrite(_game_gp(), fn)


# ── GOAL code (Basic actor) ────────────────────────────────────────────────

def _f(x):
    s = f"{float(x):.4f}".rstrip("0")
    return s + "0" if s.endswith(".") else s


def actor_gc(scene, a):
    """The Basic actor's GOAL (deftype <name>, def-actor, states, init) for a level's -obs.gc."""
    from .. import custom_actors as CA
    n = CA.clean(a.name)
    anims = [anim_name(x.action.name) for x in a.anims if x.include and x.action] if a.armature else []
    art = [f"{x}-ja" for x in anims] or ["idle-ja"]
    idle = f"{n}-{art[0]}"
    trig = None
    if a.armature and a.trigger_anim not in ("", "NONE"):
        tn = anim_name(a.trigger_anim)
        if tn in anims:
            trig = f"{n}-{tn}-ja"
    coll = a.collision if a.template == "basic" else "none"
    meshes = len(CA.collision_objects(a)) if coll == "mesh" else 0
    if coll == "mesh" and not meshes:
        coll = "none"
    b = CA.bounds(a)
    post = "transform-post" if coll != "none" else "ja-post"
    act = "(collide-action solid rider-plat-sticky)" if a.rideable else "(collide-action solid)"
    out = ["", f";; ---- custom actor {n} (OpenGOAL Actors tab: Basic actor) ----",
           f"(deftype {n} (process-drawable)",
           f"  ({'(root collide-shape-moving :override)' if coll != 'none' else ''})",
           f"  (:states {n}-idle{f' {n}-play' if trig else ''}))",
           f"(def-actor {n} :bounds (0 0 0 {_f(b)}) :art ({' '.join(art)}))",
           f"(defstate {n}-idle ({n})"]
    if trig:
        out += ["  :event",
                "    (behavior ((proc process) (argc int) (message symbol) (block event-message-block))",
                f"      (case message (('trigger) (go {n}-play))))"]
    out += ["  :code",
            "    (behavior ()",
            "      (loop",
            f"        (ja-no-eval :group! {idle} :num! (seek!) :frame-num 0.0)",
            "        (until (ja-done? 0) (suspend) (ja :num! (seek!)))))",
            f"  :post {post})"]
    if trig:
        out += [f"(defstate {n}-play ({n})",
                "  :code",
                "    (behavior ()",
                f"      (ja-no-eval :group! {trig} :num! (seek!) :frame-num 0.0)",
                "      (until (ja-done? 0) (suspend) (ja :num! (seek!)))",
                f"      (go {n}-idle))",
                f"  :post {post})"]
    out += [f"(defmethod init-from-entity! ((this {n}) (arg0 entity-actor))"]
    if coll == "none":
        out += ["  (set! (-> this root) (new 'process 'trsqv))"]
    else:
        out += ["  (let ((cshape (new 'process 'collide-shape-moving this (collide-list-enum hit-by-player))))",
                "    (set! (-> cshape dynam) (copy *standard-dynamics* 'process))",
                "    (set! (-> cshape reaction) default-collision-reaction)",
                "    (set! (-> cshape no-reaction) (the (function collide-shape-moving collide-shape-intersect vector vector none) nothing))"]
        if coll == "sphere":
            out += ["    (let ((s (new 'process 'collide-shape-prim-sphere cshape (the uint 0))))",
                    "      (set! (-> s prim-core collide-as) (collide-kind ground-object))",
                    "      (set! (-> s collide-with) (collide-kind target))",
                    f"      (set! (-> s prim-core action) {act})",
                    "      (set! (-> s prim-core offense) (collide-offense indestructible))",
                    "      (set! (-> s transform-index) 0)",
                    f"      (set-vector! (-> s local-sphere) 0.0 (meters {_f(a.sphere_height)}) 0.0 (meters {_f(a.sphere_radius)}))",
                    "      (set-root-prim! cshape s))"]
        else:
            out += [f"    (let ((group (new 'process 'collide-shape-prim-group cshape (the uint {meshes}) 0)))",
                    "      (set! (-> group prim-core collide-as) (collide-kind ground-object))",
                    "      (set! (-> group collide-with) (collide-kind target))",
                    f"      (set! (-> group prim-core action) {act})",
                    "      (set! (-> group transform-index) 0)",
                    f"      (set-vector! (-> group local-sphere) 0.0 0.0 0.0 (meters {_f(b)}))",
                    "      (set-root-prim! cshape group)"]
            joints = [int(x) for x in a.coll_joints.split(",") if x.strip().isdigit()]
            for i in range(meshes):
                j = joints[i] if i < len(joints) else 0
                out += [f"      (let ((mesh (new 'process 'collide-shape-prim-mesh cshape (the uint {i}) (the uint 0))))",
                        "        (set! (-> mesh prim-core collide-as) (collide-kind ground-object))",
                        "        (set! (-> mesh collide-with) (collide-kind target))",
                        f"        (set! (-> mesh prim-core action) {act})",
                        "        (set! (-> mesh prim-core offense) (collide-offense indestructible))",
                        f"        (set! (-> mesh transform-index) {j})",
                        f"        (set-vector! (-> mesh local-sphere) 0.0 0.0 0.0 (meters {_f(b)}))",
                        "        (append-prim group mesh))"]
            out[-1] += ")"
        out += ["    (set! (-> cshape nav-radius) (* 0.75 (-> cshape root-prim local-sphere w)))",
                "    (backup-collide-with-as cshape)",
                "    (set! (-> this root) cshape))"]
    out += ["  (process-drawable-from-entity! this arg0)",
            f"  (initialize-skeleton this *{n}-sg* '())"]
    if coll != "none":
        out += ["  (transform-post)"]
    out += [f"  (go {n}-idle)", "  (none))"]
    return out


def level_code(scene, objs):
    """GOAL of the Basic actors the level places (for its -obs.gc)."""
    from .. import custom_actors as CA
    out = []
    for n in level_models(scene, objs):
        a = CA.actor_by_name(scene, n)
        if a is not None and a.template == "basic":
            out += actor_gc(scene, a)
    return out


# ── levels ────────────────────────────────────────────────────────────────

def level_models(scene, objs):
    """Names of this file's custom actors placed in the level (ACTOR_<name>_ empties)."""
    from .. import custom_actors as CA
    from ..collections import actor_etype
    names = {CA.clean(a.name) for a in scene.og_custom_actors}
    out = []
    for o in objs:
        et = actor_etype(o)
        if et in names and et not in out:
            out.append(et)
    return out


def level_ags(scene, objs):
    return [f"{n}-ag.go" for n in level_models(scene, objs)]


def missing_for_level(scene, objs):
    """Custom actors the level places that were never exported (their model file is missing):
    they are only exported from the OpenGOAL Actors tab."""
    return [n for n in level_models(scene, objs) if not glb_path(n).exists()]
