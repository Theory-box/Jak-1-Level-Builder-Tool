"""Import > From GOAL files: built-in cameras (a level .jsonc "cameras").

One CAMERA_ per camera: entries "<name>", "<name>-1" ... with the same
settings are one camera with several volumes (that's how the export writes
them). Mode from the lumps (align -> side-scroll, pivot -> orbit, campath ->
spline), the DB "Cameras" fields and flags, look-at / anchor / pivot empties,
the path as a curve, the volumes as VOL_ meshes by role.
"""
from __future__ import annotations

import re

import bpy
import mathutils

_ROLES = ("vol", "pvol", "cutoutvol")


def _group(entries):
    """[(name, [entries])]: "<name>-<n>" joins "<name>" when only the volume differs."""
    groups, done = [], set()
    for e in entries:
        if e["name"] in done:
            continue
        base = e["name"]
        members = [e]
        for o in entries:
            m = re.fullmatch(re.escape(base) + r"-(\d+)", o["name"])
            if m and o["name"] not in done and _same(o["data"], e["data"]):
                members.append(o)
        for x in members:
            done.add(x["name"])
        groups.append((base, members))
    return groups


def _same(a, b):
    la = {k: v for k, v in (a.get("lump") or {}).items() if k not in ("name", "vol")}
    lb = {k: v for k, v in (b.get("lump") or {}).items() if k not in ("name", "vol")}
    return la == lb and a.get("trans") == b.get("trans") and a.get("quat") == b.get("quat")


def _empty(ctx, name, loc, kind, size, color, col_path):
    from .collections import _link_object_to_sub_collection
    o = bpy.data.objects.new(name, None)
    o.empty_display_type = kind
    o.empty_display_size = size
    o.color = color
    o.show_name = True
    o.location = loc
    ctx.scene.collection.objects.link(o)
    _link_object_to_sub_collection(ctx.scene, o, *col_path)
    return o


def camera_matrix(q):
    """Blender camera rotation from a camera entity quat (the reverse of
    export/scene.py _camera_game_quat: rows right / up / look, conjugated)."""
    gq = mathutils.Quaternion((q[3], -q[0], -q[1], -q[2]))
    m = gq.to_matrix()
    r, u, l = m[0], m[1], m[2]
    bl = lambda v: mathutils.Vector((v[0], -v[2], v[1]))
    right, up, look = bl(r), bl(u), bl(l)
    # camera: -Z looks, +Y up; the game's up is "down" x look -> flip to keep a right-handed frame
    z = -look.normalized()
    y = z.cross(right.normalized())
    x = y.cross(z)
    return mathutils.Matrix((x, y, z)).transposed()


def import_cameras(ctx, entries):
    from . import db
    from .collections import _link_object_to_sub_collection, _COL_PATH_CAMERAS, free_object_name
    from .goal_import_actors import (apply_fields, game_to_blender, make_volume, _ltype, _scalars,
                                     _scalars_list, _make_path)
    from .operators.spawn import camera_fov_driver
    from .export import _vol_links, _rename_vol_for_links
    cam_db = db.cameras()
    made = []
    for base, members in _group(entries):
        d = members[0]["data"]
        lump = dict(d.get("lump") or {})
        name = re.sub(r"[^\w-]", "_", base)
        oname = name if name.startswith("CAMERA_") else "CAMERA_" + name
        if oname in bpy.data.objects:
            oname = free_object_name(oname + "-", 1)
        cd = bpy.data.cameras.new(oname)
        o = bpy.data.objects.new(oname, cd)
        o.show_name = True
        o.color = (0.0, 0.8, 0.9, 1.0)
        ctx.scene.collection.objects.link(o)
        _link_object_to_sub_collection(ctx.scene, o, *_COL_PATH_CAMERAS)
        t = d.get("trans") or [0, 0, 0]
        o.location = game_to_blender(t)
        q = d.get("quat")
        if q and len(q) == 4:
            o.rotation_euler = camera_matrix(q).to_euler()
        mode = "standoff" if "align" in lump else "orbit" if "pivot" in lump else \
            "spline" if "campath" in lump else "fixed"
        o["og_cam_mode"] = mode
        o["og_cam_look_at"] = ""
        for f in cam_db.get("fields", []):
            o[f["key"]] = f.get("default", 0.0)
        def _applies(f):
            modes = (f.get("visible_if") or {}).get("og_cam_mode")
            return modes is None or mode in (modes if isinstance(modes, list) else [modes])
        took = apply_fields(o, "", lump, [f for f in cam_db.get("fields", []) if _applies(f)])
        fl = lump.get("flags")
        if fl is not None:
            words = re.findall(r"[\w-]+", str(_scalars(fl)[0]))[1:] if _ltype(fl) else []
            ids = {f["id"] for f in cam_db.get("flags", [])}
            for w in words:
                if w in ids:
                    o["og_cam_flag_" + w] = True
            took.add("flags")
        for key, suf, kind, color in (("interesting", "_LOOKAT", "ARROWS", (1.0, 0.8, 0.0, 1.0)),
                                      ("align", "_ALIGN", "PLAIN_AXES", (1.0, 0.6, 0.0, 1.0)),
                                      ("pivot", "_PIVOT", "SPHERE", (1.0, 0.2, 0.8, 1.0))):
            v = lump.get(key)
            if v is None:
                continue
            p = _scalars(v)
            if len(p) >= 3:
                e = _empty(ctx, o.name + suf, game_to_blender(p), kind, 0.5, color, _COL_PATH_CAMERAS)
                if key == "interesting":
                    o["og_cam_look_at"] = e.name
                made.append(e)
                took.add(key)
        if "campath" in lump:
            c = _make_path(ctx, o, "path", lump["campath"], lump.get("campath-k"))
            if c is not None:
                made.append(c)
                took |= {"campath", "campath-k"}
        # volumes: each member's vol, the first one's pvol / cutoutvol
        for role in _ROLES:
            vols = [m["data"].get("lump", {}).get(role) for m in (members if role == "vol" else members[:1])]
            for i, vv in enumerate(v for v in vols if v is not None):
                if _ltype(vv) != "vector-vol":
                    continue
                vol = make_volume(ctx, _scalars_list(vv), f"VOL_{o.name[7:]}_{role}{i or ''}")
                if vol is None:
                    continue
                en = _vol_links(vol).add()
                en.target_name = o.name
                en.role = role
                _rename_vol_for_links(vol)
                made.append(vol)
            took.add(role)
        camera_fov_driver(o)
        rest = sorted(k for k in lump if k not in took and k != "name")
        if rest:
            from .export import log
            log(f"[import] {o.name}: lumps without a camera setting, left out: {', '.join(rest)}")
        made.insert(0, o)
    return made
