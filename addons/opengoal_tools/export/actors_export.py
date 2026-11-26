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


def order_animations(js, names):
    """Keep only the named animations, in that order."""
    anims = js.get("animations") or []
    by = {a.get("name"): a for a in anims}
    js["animations"] = [by[n] for n in names if n in by]
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


def post_process(data, anim_names, fix):
    js, binb = _chunks(data)
    order_animations(js, anim_names)
    if fix:
        bone_fix(js, binb)
    js["buffers"][0]["byteLength"] = len(binb) + (-len(binb) % 4)
    return _pack(js, binb)


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
    fd, tmp = tempfile.mkstemp(suffix=".glb")
    os.close(fd)
    try:
        _export_glb(scene, objs, tmp)
        data = open(tmp, "rb").read()
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    data = post_process(data, anims, CA.bone_fix_on(scene))
    p = glb_path(name)
    if not (p.exists() and p.read_bytes() == data):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        log(f"[custom actor] wrote {p.name} ({len(data)} bytes, {len(anims)} animation(s))")
    register(name, gen_mesh=bool(CA.collision_objects(a)))
    return ""


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


def export_for_level(scene, objs):
    """Export the custom actors the level places. Returns error texts."""
    from .. import custom_actors as CA
    errs = []
    for n in level_models(scene, objs):
        a = CA.actor_by_name(scene, n)
        e = export_actor(scene, a) if a is not None else "not found"
        if e:
            errs.append(f"{n}: {e}")
    return errs
