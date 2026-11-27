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


def _skin_ibms(js, binb):
    """({bone name: skin index}, [inverse bind matrices]) of the first skin."""
    from mathutils import Matrix
    skin = (js.get("skins") or [None])[0]
    ibm = []
    if skin and "inverseBindMatrices" in skin:
        acc = js["accessors"][skin["inverseBindMatrices"]]
        bv = js["bufferViews"][acc["bufferView"]]
        st = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
        for k in range(acc["count"]):
            f = struct.unpack_from("<16f", binb, st + 64 * k)
            ibm.append(Matrix([[f[c * 4 + r] for c in range(4)] for r in range(4)]))
    joint_of = {js["nodes"][j].get("name"): s for s, j in enumerate(skin["joints"])} if skin else {}
    return joint_of, ibm


def bone_collision(js, binb, coll_bones):
    """Collision meshes that follow a bone: moved into that bone's rest space (its inverse bind
    matrix), so the game can carry them on the joint. Returns [(mesh name, joint index)] (node-list:
    0 = the actor, a skin's bone s = s + 2), in build-actor's order (its mesh ids)."""
    nodes = js["nodes"]
    parent = {c: i for i, n in enumerate(nodes) for c in n.get("children", [])}

    def world(i):
        m = _mat(nodes[i])
        while i in parent:
            i = parent[i]
            m = _mat(nodes[i]) @ m
        return m
    joint_of, ibm = _skin_ibms(js, binb)
    out = []
    for i in _dfs(js):
        n = nodes[i]
        if "mesh" not in n or n.get("name") not in coll_bones:
            continue
        b = coll_bones[n["name"]]
        s = joint_of.get(b) if b else None
        if s is None or s >= len(ibm):
            out.append((n["name"], 0))
            continue
        new_world = ibm[s] @ world(i)
        local = (world(parent[i]).inverted() @ new_world) if i in parent else new_world
        for k in ("translation", "rotation", "scale"):
            n.pop(k, None)
        n["matrix"] = [local[r][c] for c in range(4) for r in range(4)]
        out.append((n["name"], s + 2))
    return out


def sphere_joints(js, binb, spheres):
    """[(bone, centre in glTF space)] -> [(joint index, centre in that joint's rest space)]."""
    from mathutils import Vector
    joint_of, ibm = _skin_ibms(js, binb)
    out = []
    for b, c in spheres:
        s = joint_of.get(b) if b else None
        if s is None or s >= len(ibm):
            out.append((0, tuple(c)))
        else:
            out.append((s + 2, tuple(ibm[s] @ Vector(c))))
    return out


def post_process(data, anim_names, fix, coll_bones=None, spheres=None):
    """Returns (glb bytes, [(collision mesh, joint)] in build-actor's order, [(sphere joint, centre)])."""
    js, binb = _chunks(data)
    order_animations(js, anim_names)
    joints = bone_collision(js, binb, coll_bones) if coll_bones else []
    sj = sphere_joints(js, binb, spheres) if spheres else []
    if fix:
        bone_fix(js, binb)
    js["buffers"][0]["byteLength"] = len(binb) + (-len(binb) % 4)
    return _pack(js, binb), joints, sj


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
                                  export_animation_mode="NLA_TRACKS", export_extras=True,
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
    objs = CA.model_objects(a) + CA.used_meshes(a)
    if a.armature is not None and a.armature not in objs:
        objs.append(a.armature)
    objs = [o for o in objs if o.type in ("MESH", "ARMATURE")]
    if not objs:
        return "nothing to export"
    CA.sync_anims(a)
    anims = [x.track for x in a.anims if x.include and x.track]
    ad = a.armature.animation_data if a.armature is not None else None
    if ad is not None and ad.use_tweak_mode:              # (the exporter wants the tracks as they are)
        ad.use_tweak_mode = False
    gen_mesh = uses_mesh_collision(a)
    marks = _collision_marks(a) if gen_mesh else []
    stub = _camera_stub(scene, a, objs)
    if stub is not None:
        objs.append(stub)
    # Export origin: the chosen point moved to the scene's origin for the export (then put back)
    p0 = CA.origin_point(a)
    sig = CA.collision_signature(a)
    # spheres: centre relative to the origin, in glTF axes (x, z, -y)
    sph = []
    for o in CA.used_spheres(a):
        c = o.matrix_world.translation - p0
        sph.append((o, CA.collision_bone(o), (c.x, c.z, -c.y), CA.sphere_radius(o)))
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
        if stub is not None:
            me = stub.data
            bpy.data.objects.remove(stub)
            bpy.data.meshes.remove(me)
        try:
            os.remove(tmp)
        except OSError:
            pass
    coll_bones = {o.name: CA.collision_bone(o) for o in CA.used_meshes(a)} if gen_mesh else None
    data, joints, sj = post_process(data, anims, CA.bone_fix_on(scene), coll_bones,
                                    [(b, c) for _o, b, c, _r in sph])
    prims = []
    for i, (mname, j) in enumerate(joints):
        o = bpy.data.objects.get(mname)
        prims.append(_prim("mesh", o, j, mesh=i))
    for (o, _b, _c, r), (j, c) in zip(sph, sj):
        prims.append(_prim("sphere", o, j, sphere=[round(v, 4) for v in c] + [round(r, 4)]))
    a.coll_data = json.dumps({"sig": sig, "prims": prims})
    p = glb_path(name)
    if not (p.exists() and p.read_bytes() == data):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        log(f"[custom actor] wrote {p.name} ({len(data)} bytes, {len(anims)} animation(s))")
    register(name, gen_mesh=gen_mesh)
    return ""


def _prim(kind, o, joint, **kw):
    d = {"kind": kind, "name": o.name if o else "", "joint": joint,
         "solid": getattr(o, "og_ca_solid", "SOLID"), "touch": getattr(o, "og_ca_touch", "NONE"),
         "attack": getattr(o, "og_ca_attack", "NONE")}
    d.update(kw)
    return d


def _camera_stub(scene, a, objs):
    """A camera with no skinned mesh: a 1 mm triangle on the camera bone, so the exporter writes the
    skin (the joints build-actor reads). It sits in the lens, inside the near clip: never seen."""
    from mathutils import Vector
    from .. import custom_actors as CA
    arm = a.armature
    if a.template != "camera" or arm is None or CA.CAM_BONE not in arm.data.bones:
        return None
    if any(o.type == "MESH" and any(m.type == "ARMATURE" and m.object == arm for m in o.modifiers) for o in objs):
        return None
    h = arm.data.bones[CA.CAM_BONE].head_local
    me = bpy.data.meshes.new("og-camera-stub")
    me.from_pydata([h, h + Vector((0.001, 0, 0)), h + Vector((0, 0.001, 0))], [], [(0, 1, 2)])
    ob = bpy.data.objects.new("og-camera-stub", me)
    scene.collection.objects.link(ob)
    ob.parent = arm
    ob.vertex_groups.new(name=CA.CAM_BONE).add([0, 1, 2], 1.0, "REPLACE")
    ob.modifiers.new("Armature", "ARMATURE").object = arm
    return ob


def uses_mesh_collision(a):
    from .. import custom_actors as CA
    return bool(CA.used_meshes(a))


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


def coll_prims(a):
    """The exported collision prims (custom_actors.coll_data, written by the export)."""
    if a.template != "basic":
        return []
    try:
        return list(json.loads(a.coll_data).get("prims") or [])
    except (ValueError, AttributeError):
        return []


_SOLID_ACT = {"SOLID": ("solid",), "RIDE": ("solid", "rider-plat-sticky"), "NONE": ()}


def _bits(p):
    from ..custom_actors import PRIM_BITS
    return PRIM_BITS.get(("touch", p["touch"]), 0) | PRIM_BITS.get(("attack", p["attack"]), 0)


def _prim_core(p):
    """(collide-as, action, offense) of a prim: attackable ones are enemies Jak's attacks reach."""
    hit = p["attack"] != "NONE"
    return ("enemy" if hit else "ground-object", _SOLID_ACT.get(p["solid"], ("solid",)),
            "touch" if hit else "indestructible")


def actor_gc(scene, a):
    """The Basic actor's GOAL (deftype <name>, def-actor, states, init) for a level's -obs.gc."""
    from .. import custom_actors as CA
    n = CA.clean(a.name)
    anims = [anim_name(x.track) for x in a.anims if x.include and x.track] if a.armature else []
    art = [f"{x}-ja" for x in anims] or ["idle-ja"]
    idle = f"{n}-{art[0]}"
    trig = None
    if a.armature and a.trigger_anim not in ("", "NONE"):
        tn = anim_name(a.trigger_anim)
        if tn in anims:
            trig = f"{n}-{tn}-ja"
    prims = coll_prims(a)
    bits = 0
    for p in prims:
        bits |= _bits(p)
    touch_hurt = bits & 3
    touch_trig = bool(bits & 4) and trig
    att_trig = bool(bits & 8) and trig
    breaks = bool(bits & 16)
    overlap = bool(bits & 7)                   # touch reactions: the actor looks for Jak itself
    b = CA.bounds(a)
    post = (f"{n}-post" if overlap else "transform-post") if prims else "ja-post"
    states = [f"{n}-idle"] + ([f"{n}-play"] if trig else []) + ([f"{n}-die"] if breaks else [])
    out = ["", f";; ---- custom actor {n} (OpenGOAL Actors tab: Basic actor) ----",
           f"(deftype {n} (process-drawable)",
           f"  ({'(root collide-shape-moving :override)' if prims else ''})",
           f"  (:states {' '.join(states)}))",
           f"(def-actor {n} :bounds (0 0 0 {_f(b)}) :art ({' '.join(art)}))"]
    if overlap:
        out += [f"(defbehavior {n}-post {n} ()",
                "  (transform-post)",
                "  (let ((o (new 'stack-no-clear 'overlaps-others-params)))",
                "    (set! (-> o options) (the uint 1))",
                "    (set! (-> o tlist) *touching-list*)",
                "    (find-overlapping-shapes (-> self root) o))",
                "  (none))"]
    event = bool(trig or touch_hurt or touch_trig or att_trig or breaks)
    if event:
        play = f"(if (not (= (-> self state) {n}-play)) (go {n}-play))"
        me = "(the-as collide-shape-moving (-> self root))"
        out += [f"(defbehavior {n}-event {n} ((proc process) (argc int) (message symbol) (block event-message-block))",
                "  (case message"]
        if trig:
            out += [f"    (('trigger) (go {n}-play))"]
        if touch_hurt or touch_trig:
            out += ["    (('touch)",
                    "     (let ((e (the-as touching-shapes-entry (-> block param 0))))",
                    "       (when (and e (= proc *target*))"]
            if touch_hurt:
                out += ["         (cond",
                        f"           ((prims-touching? e {me} (the uint 2))",
                        "            (send-event proc 'attack-invinc e (static-attack-info ((mode 'death)))))",   # (as lava pools)
                        f"           ((prims-touching? e {me} (the uint 1))",
                        "            (send-event proc 'attack e (new 'static 'attack-info))))"]
            if touch_trig:
                out += [f"         (if (prims-touching? e {me} (the uint 4)) {play})"]
            out[-1] += ")))"
        if att_trig or breaks:
            out += ["    (('attack)",
                    "     (let ((e (the-as touching-shapes-entry (-> block param 0))))",
                    "       (when e"]
            if breaks:
                out += [f"         (if (prims-touching? e {me} (the uint 16)) (go {n}-die))"]
            if att_trig:
                out += [f"         (if (prims-touching? e {me} (the uint 8)) {play})"]
            out[-1] += ")))"
        out[-1] += "))"
    out += [f"(defstate {n}-idle ({n})"]
    if event:
        out += [f"  :event {n}-event"]
    out += ["  :code",
            "    (behavior ()",
            "      (loop",
            f"        (ja-no-eval :group! {idle} :num! (seek!) :frame-num 0.0)",
            "        (until (ja-done? 0) (suspend) (ja :num! (seek!)))))",
            f"  :post {post})"]
    if trig:
        out += [f"(defstate {n}-play ({n})"]
        if event:
            out += [f"  :event {n}-event"]
        out += ["  :code",
                "    (behavior ()",
                f"      (ja-no-eval :group! {trig} :num! (seek!) :frame-num 0.0)",
                "      (until (ja-done? 0) (suspend) (ja :num! (seek!)))",
                f"      (go {n}-idle))",
                f"  :post {post})"]
    if breaks:
        out += [f"(defstate {n}-die ({n})",
                "  :code",
                "    (behavior ()",
                "      (clear-collide-with-as (-> self root))",
                "      (process-entity-status! self (entity-perm-status dead) #t)",
                "      (deactivate self)))"]
    out += [f"(defmethod init-from-entity! ((this {n}) (arg0 entity-actor))"]
    if not prims:
        out += ["  (set! (-> this root) (new 'process 'trsqv))"]
    else:
        kinds, acts = set(), set()
        for p in prims:
            k, ac, _o = _prim_core(p)
            kinds.add(k)
            acts.update(ac)
        out += ["  (let ((cshape (new 'process 'collide-shape-moving this (collide-list-enum hit-by-player))))",
                "    (set! (-> cshape dynam) (copy *standard-dynamics* 'process))",
                "    (set! (-> cshape reaction) default-collision-reaction)",
                "    (set! (-> cshape no-reaction) (the (function collide-shape-moving collide-shape-intersect vector vector none) nothing))",
                f"    (let ((group (new 'process 'collide-shape-prim-group cshape (the uint {len(prims)}) 0)))",
                f"      (set! (-> group prim-core collide-as) (collide-kind {' '.join(sorted(kinds))}))",
                "      (set! (-> group collide-with) (collide-kind target))",
                f"      (set! (-> group prim-core action) (collide-action {' '.join(sorted(acts))}))",
                "      (set! (-> group transform-index) 0)",
                f"      (set-vector! (-> group local-sphere) 0.0 0.0 0.0 (meters {_f(b)}))",
                "      (set-root-prim! cshape group)"]
        for p in prims:
            k, ac, off = _prim_core(p)
            pid = _bits(p)
            if p["kind"] == "mesh":
                out += [f"      (let ((prim (new 'process 'collide-shape-prim-mesh cshape (the uint {p['mesh']}) (the uint {pid}))))"]
                sphere = f"0.0 0.0 0.0 (meters {_f(b)})"
            else:
                x, y, z, r = p["sphere"]
                out += [f"      (let ((prim (new 'process 'collide-shape-prim-sphere cshape (the uint {pid}))))"]
                sphere = f"(meters {_f(x)}) (meters {_f(y)}) (meters {_f(z)}) (meters {_f(r)})"
            out += [f"        (set! (-> prim prim-core collide-as) (collide-kind {k}))",
                    "        (set! (-> prim collide-with) (collide-kind target))",
                    f"        (set! (-> prim prim-core action) (collide-action {' '.join(ac)}))",
                    f"        (set! (-> prim prim-core offense) (collide-offense {off}))",
                    f"        (set! (-> prim transform-index) {p['joint']})",
                    f"        (set-vector! (-> prim local-sphere) {sphere})",
                    "        (append-prim group prim))"]
        out[-1] += ")"
        out += ["    (set! (-> cshape nav-radius) (* 0.75 (-> cshape root-prim local-sphere w)))",
                "    (backup-collide-with-as cshape)",
                "    (set! (-> this root) cshape))"]
    out += ["  (process-drawable-from-entity! this arg0)",
            f"  (initialize-skeleton this *{n}-sg* '())"]
    if prims:
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
    return out                       # (Camera animations: pov.skel_lines defines their skeleton group)


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
    from .. import pov
    for g in pov.level_groups(objs):                 # Camera animations the level's actors play
        if g in names and g not in out:
            out.append(g)
    return out


def level_ags(scene, objs):
    return [f"{n}-ag.go" for n in level_models(scene, objs)]


def missing_for_level(scene, objs):
    """Custom actors the level places that were never exported (their model file is missing):
    they are only exported from the OpenGOAL Actors tab."""
    return [n for n in level_models(scene, objs) if not glb_path(n).exists()]
