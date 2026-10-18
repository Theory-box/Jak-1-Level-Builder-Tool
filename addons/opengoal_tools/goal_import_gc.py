"""Import > From GOAL files: checkpoints (level-info.gc continue-points),
load boundaries (load-boundary-data.gc) and nav-meshes (entity.gc case
entries / custom-nav defines), read with goal_import.read_sexprs.

Numbers are game units: (meters x) = x * 4096, #x.. hex, plain numbers raw.
"""
from __future__ import annotations

import math
import re

import bpy
import mathutils

M = 4096.0


def num(f, default=0.0):
    """A GOAL number form -> float (game units)."""
    if isinstance(f, list):
        if len(f) == 2 and f[0] == "meters":
            return num(f[1]) * M
        if len(f) == 2 and f[0] == "degrees":
            return num(f[1]) * 65536.0 / 360.0
        return default
    if not isinstance(f, str):
        return default
    try:
        if f.lower().startswith("#x"):
            return float(int(f[2:], 16))
        if f.lower().startswith("#b"):
            return float(int(f[2:], 2))
        return float(f)
    except ValueError:
        return default


def _sym(f):
    """'x / x -> "x"; #f -> None."""
    if isinstance(f, list) and len(f) == 2 and f[0] == "quote":
        f = f[1]
    if f in (None, "#f", "'#f"):
        return None
    return str(f)


def _vec(form, keys=("x", "y", "z", "w")):
    from .goal_import import static_fields
    sf = static_fields(form) if isinstance(form, list) else {}
    return [num(sf.get(k), 0.0) for k in keys]


def _to_text(f):
    """A form back to GOAL text."""
    if isinstance(f, list):
        if len(f) == 2 and f[0] == "quote":
            return "'" + _to_text(f[1])
        return "(" + " ".join(_to_text(x) for x in f) + ")"
    return str(f)


def _bl(p):
    """Game (x, y, z) in meters -> Blender."""
    return mathutils.Vector((p[0], -p[2], p[1]))


_R = mathutils.Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0)))


def _cam_rot(rows):
    """Blender rotation (3x3) of a camera-rot matrix (rows right, up, look in
    game axes): -Z looks, Y up (the reverse of export/scene.py collect_spawns)."""
    r = mathutils.Vector(rows[0:3]); l = mathutils.Vector(rows[6:9])
    bl = lambda v: mathutils.Vector((v[0], -v[2], v[1]))
    z = -bl(l).normalized()
    x = bl(r).normalized()
    y = z.cross(x)
    return mathutils.Matrix((x, y, z)).transposed()


# ── Checkpoints ──────────────────────────────────────────────────────────────

def _level_choice(o, attr, custom_attr, lev, src_level, none_value):
    """Set a level picker: the file's own level -> "self", a project level ->
    itself, another level -> custom + its name, #f -> none_value."""
    if lev is None:
        setattr(o, attr, none_value)
        return
    if lev == src_level:
        try:
            setattr(o, attr, "self")
            return
        except TypeError:                       # no "self" in this picker (level 1)
            pass
    try:
        setattr(o, attr, lev)
    except TypeError:
        setattr(o, attr, "custom")
        setattr(o, custom_attr, lev)


LAST_CHECKPOINTS = {}    # continue-point name -> object name of the last checkpoint import


def import_checkpoints(ctx, entries):
    """Continue-points first, then the triggers (lt-checkpoint actors) onto them."""
    triggers = [e for e in entries if e.get("trigger_of") is not None]
    made = _import_continue_points(ctx, [e for e in entries if e.get("trigger_of") is None])
    skipped = []
    for e in triggers:
        o = _checkpoint_for(ctx, e["trigger_of"])
        if o is None:
            skipped.append(f"{e['name']} (no checkpoint {e['trigger_of']})")
            continue
        made += _add_trigger(ctx, o, e["data"])
    return made, skipped


def _checkpoint_for(ctx, cont_name):
    from .collections import spawn_uid, _level_objects, _get_level_prop
    n = LAST_CHECKPOINTS.get(cont_name)
    if n and n in bpy.data.objects:
        return bpy.data.objects[n]
    lv = str(_get_level_prop(ctx.scene, "og_level_name", "")).strip().lower().replace(" ", "-")
    return next((o for o in _level_objects(ctx.scene) if o.name.startswith("CHECKPOINT_") and not o.name.endswith("_CAM")
                 and f"{lv}-{spawn_uid(o)}" == cont_name), None)


def _add_trigger(ctx, o, d):
    """Trigger on, the sphere radius or the volume (a VOL_ linked to the checkpoint)."""
    from .goal_import_actors import make_volume, _ltype, _scalars, _scalars_list
    lump = d.get("lump") or {}
    o.og_cp_trigger = True
    r = lump.get("radius")
    if r is not None:
        v = _scalars(r)
        if v:
            o["og_checkpoint_radius"] = float(v[0]) if _ltype(r) else float(v[0]) / M
    vv = lump.get("vol")
    if vv is None:
        return []
    planes = _scalars_list(vv) if _ltype(vv) else [[a, b, c, w / M] for a, b, c, w in vv]
    vol = make_volume(ctx, planes, f"VOL_{o.name[11:]}")
    if vol is None:
        return []
    from .export import _vol_links, _rename_vol_for_links
    en = _vol_links(vol).add()
    en.target_name = o.name
    _rename_vol_for_links(vol)
    return [vol]


def _import_continue_points(ctx, entries):
    from .goal_import import static_fields
    from .collections import _link_object_to_sub_collection, _COL_PATH_SPAWNS, spawn_uid, _level_objects
    from .operators.spawn import _cp_clean, _cp_object_name
    from . import db
    made = []
    used = {spawn_uid(o) for o in _level_objects(ctx.scene) if o.name.startswith("CHECKPOINT_") and not o.name.endswith("_CAM")}
    for e in entries:
        sf = static_fields(e["data"])
        src_level = _sym(sf.get("level"))
        name = e["name"]
        if src_level and name.startswith(src_level + "-"):
            name = name[len(src_level) + 1:]
        uid = _cp_clean(name) or "start"
        base, n = uid, 1
        while uid in used or _cp_object_name(ctx.scene, uid) in bpy.data.objects:
            uid = f"{base}-{n}"
            n += 1
        used.add(uid)
        t = [v / M for v in _vec(sf.get("trans"))]
        o = bpy.data.objects.new(_cp_object_name(ctx.scene, uid), None)
        LAST_CHECKPOINTS[e["name"]] = o.name
        o.empty_display_type = "CONE"
        o.empty_display_size = 1.2
        o.color = (1.0, 0.85, 0.0, 1.0)
        o.show_name = True
        o.location = _bl(t)
        q = _vec(sf.get("quat"))
        g = mathutils.Quaternion((q[3], q[0], q[1], q[2]))
        if g.magnitude < 1e-6:
            g = mathutils.Quaternion()
        m3 = mathutils.Matrix.Rotation(math.pi, 3, "Z").inverted() @ (_R.transposed() @ g.normalized().to_matrix() @ _R)
        o.rotation_euler = m3.to_euler()
        o["og_checkpoint_radius"] = 3.0
        ctx.scene.collection.objects.link(o)
        _link_object_to_sub_collection(ctx.scene, o, *_COL_PATH_SPAWNS)
        bpy.context.view_layer.update()
        # resident levels
        _level_choice(o, "og_cp_lev0", "og_cp_lev0_custom", _sym(sf.get("lev0")), src_level, "self")
        _level_choice(o, "og_cp_lev1", "og_cp_lev1_custom", _sym(sf.get("lev1")), src_level, "none")
        for k in ("disp0", "disp1"):
            d = _sym(sf.get(k))
            setattr(o, "og_cp_" + k, d if d in ("display", "special") else "off")
        # vis-nick: the file level's own nick (the export's default) -> blank
        # (this level's nick), like :level -> "self"
        vn = _sym(sf.get("vis-nick"))
        from .collections import _active_level_col, _resolve_vis_nick
        from .export import _nick
        if vn and vn != _resolve_vis_nick(_active_level_col(ctx.scene)) and not (src_level and vn == _nick(src_level)):
            o.og_cp_vis_nick = vn
        fl = sf.get("flags")
        if isinstance(fl, list) and fl and fl[0] == "continue-flags":
            ids = {f["id"] for f in db.continue_flags()}
            o.og_cp_flags = {w for w in fl[1:] if w in ids}
        lc = sf.get("load-commands")
        if isinstance(lc, list) and lc and lc[0] == "quote" and isinstance(lc[1], list):
            for c in lc[1]:
                r = o.og_cp_load_cmds.add()
                r.cmd = _to_text(c)[1:-1] if isinstance(c, list) else str(c)
        # respawn camera (not the default: 4 m up, no rotation)
        ct = [v / M for v in _vec(sf.get("camera-trans"))]
        cr = sf.get("camera-rot")
        rows = [num(x) for x in cr[5:14]] if isinstance(cr, list) and len(cr) >= 14 else [1, 0, 0, 0, 1, 0, 0, 0, 1]
        default = (abs(ct[0] - t[0]) < 1e-3 and abs(ct[1] - t[1] - 4.0) < 1e-3 and abs(ct[2] - t[2]) < 1e-3
                   and all(abs(a - b) < 1e-4 for a, b in zip(rows, [1, 0, 0, 0, 1, 0, 0, 0, 1])))
        made.append(o)
        if not default:
            c = bpy.data.objects.new(o.name + "_CAM", None)
            c.empty_display_type = "ARROWS"
            c.empty_display_size = 0.8
            c.color = (0.2, 0.6, 1.0, 1.0)
            c.show_name = True
            ctx.scene.collection.objects.link(c)
            _link_object_to_sub_collection(ctx.scene, c, *_COL_PATH_SPAWNS)
            c.matrix_world = mathutils.Matrix.Translation(_bl(ct)) @ _cam_rot(rows).to_4x4()
            c.parent = o
            c.matrix_parent_inverse = o.matrix_world.inverted()
            made.append(c)
    return made


# ── Load boundaries ──────────────────────────────────────────────────────────

def _lb_dir(o, d, form, src_level):
    """og_lb_<d>_* from a (load a b) / (display a mode) / (vis nick #f) /
    (force-vis a #t) / (checkpt "name" #f) form."""
    if not isinstance(form, list) or not form:
        return
    cmd = form[0]
    args = form[1:]
    p = f"og_lb_{d}"
    def lev(i, attr):
        v = _sym(args[i]) if i < len(args) else None
        _level_choice(o, f"{p}_{attr}", f"{p}_{attr}_custom", v, src_level, "none")
    if cmd == "load":
        setattr(o, p + "_cmd", "load")
        lev(0, "lev0"); lev(1, "lev1")
    elif cmd == "display":
        setattr(o, p + "_cmd", "display")
        lev(0, "lev0")
        m = _sym(args[1]) if len(args) > 1 else None
        setattr(o, p + "_disp", m if m in ("display", "display-no-wait") else "off")
    elif cmd == "vis":
        setattr(o, p + "_cmd", "vis")
        setattr(o, p + "_name", _sym(args[0]) or "" if args else "")
    elif cmd == "force-vis":
        setattr(o, p + "_cmd", "force-vis")
        lev(0, "lev0")
    elif cmd == "checkpt":
        setattr(o, p + "_cmd", "checkpt")
        setattr(o, p + "_name", str(args[0]).strip('"') if args else "")


def import_boundaries(ctx, entries):
    from .goal_import import static_fields
    from .collections import _link_object_to_sub_collection, _COL_PATH_TRIGGERS, free_object_name
    from . import boundary_viz as bviz
    made = []
    for e in entries:
        f = e["data"]
        sf = static_fields([None, None, None] + f[1:])
        flags = sf.get("flags") if isinstance(sf.get("flags"), list) else []
        pts = [num(x) / M for x in (sf.get("points") or [])] if isinstance(sf.get("points"), list) else []
        xy = [(pts[i], -pts[i + 1]) for i in range(0, len(pts) - 1, 2)]
        if len(xy) < 2:
            continue
        top, bot = num(sf.get("top"), 524288.0) / M, num(sf.get("bot"), -524288.0) / M
        base = (top + bot) / 2.0
        closed = "closed" in flags
        verts = [(x, y, base) for x, y in xy]
        nm = free_object_name("LOADBND_", 0) if not e.get("level") else free_object_name(f"LOADBND_{e['level']}_", 1)
        me = bpy.data.meshes.new(nm)
        if closed:
            me.from_pydata(verts, [], [list(range(len(verts)))])
        else:
            me.from_pydata(verts, [(i, i + 1) for i in range(len(verts) - 1)], [])
        me.update()
        o = bpy.data.objects.new(nm, me)
        ctx.scene.collection.objects.link(o)
        o.show_name = True
        o.display_type = "SOLID"
        o.color = (1.0, 0.4, 0.0, 0.6)
        o.set_invisible = True
        o.ignore = True
        _link_object_to_sub_collection(ctx.scene, o, *_COL_PATH_TRIGGERS)
        o.og_lb_closed = closed
        o.og_lb_player = "player" in flags
        o.og_lb_custom_flags = " ".join(x for x in flags if x not in ("player", "closed"))
        o.og_lb_top = top - base
        o.og_lb_bot = bot - base
        _lb_dir(o, "fwd", sf.get("fwd"), e.get("level"))
        _lb_dir(o, "bwd", sf.get("bwd"), e.get("level"))
        try:
            bviz.add_modifier(o)
        except Exception:
            pass
        made.append(o)
    return made


# ── Nav-meshes ───────────────────────────────────────────────────────────────

def nav_mesh_data(form):
    """(vertices in Blender coords, [(v0, v1, v2, pat)]) of a (new 'static 'nav-mesh ...)."""
    from .goal_import import static_fields, is_new_static
    sf = static_fields(form)
    ox, oy, oz, _w = _vec(sf.get("origin"))
    def items(arr, typ):
        return [x for x in (arr or []) if is_new_static(x, typ)] if isinstance(arr, list) else []
    verts = []
    for v in items(sf.get("vertex"), "nav-vertex"):
        x, y, z, _w = _vec(v)
        verts.append(_bl(((ox + x) / M, (oy + y) / M, (oz + z) / M)))
    tris = []
    for p in items(sf.get("poly"), "nav-poly"):
        pf = static_fields(p)
        vv = pf.get("vertex")
        idx = [int(num(x)) for x in vv[5:8]] if isinstance(vv, list) and len(vv) >= 8 else []
        if len(idx) == 3 and all(0 <= i < len(verts) for i in idx):
            tris.append((idx[0], idx[1], idx[2], int(num(pf.get("pat"), 0))))
    return verts, tris


def import_navmeshes(ctx, entries):
    from .operators.links import _link_navmesh
    from .export.navmesh import NAV_MATERIALS
    from .goal_import import all_entries
    from .goal_import_actors import LAST_ACTORS
    from .collections import actor_lump_name
    made, skipped = [], []
    by_lump = {actor_lump_name(o.name): o for o in ctx.scene.objects if o.name.startswith("ACTOR_")}
    by_lump.update({k: bpy.data.objects[v] for k, v in LAST_ACTORS.items() if v in bpy.data.objects})
    aid_lump = {}
    for x in all_entries():
        a = x.get("aid", x["data"].get("aid") if isinstance(x.get("data"), dict) else None)
        if x["cat"] == "ACTORS" and a is not None:
            aid_lump[int(a)] = x["name"]
    for e in entries:
        verts, tris = nav_mesh_data(e["data"])
        if not tris:
            skipped.append(e["name"])
            continue
        owner = by_lump.get(aid_lump.get(int(num(e["aid"])))) if e.get("aid") is not None else None
        name = f"{owner.name[6:]}_nav" if owner is not None else re.sub(r"[^\w-]", "_", e["name"].replace("aid ", "aid"))
        me = bpy.data.meshes.new(name)
        faces = []
        for a, b, c, _p in tris:
            n = (verts[b] - verts[a]).cross(verts[c] - verts[a])
            faces.append((a, b, c) if n.z >= 0 else (a, c, b))     # facing up
        me.from_pydata([tuple(v) for v in verts], [], faces)
        me.update()
        nm = bpy.data.objects.new(name, me)
        ctx.scene.collection.objects.link(nm)
        actors = []
        if e.get("aid") is not None:
            if owner is not None:
                actors.append(owner)
        else:                                    # custom-nav: the actors naming it
            for o in by_lump.values():
                for i, r in enumerate(o.og_lump_rows):
                    if r.key == "custom-nav" and r.value.strip().strip("'") == e["name"]:
                        actors.append(o)
                        o.og_lump_rows.remove(i)
                        break
        _link_navmesh(ctx.scene, nm, actors)
        slots = {s.material.name: i for i, s in enumerate(nm.material_slots) if s.material}
        pat_slot = {p: slots.get(n, 0) for n, p, _c in NAV_MATERIALS}
        for poly, (_a, _b, _c, pat) in zip(me.polygons, tris):
            poly.material_index = pat_slot.get(pat, pat_slot.get(2 if pat & 2 else 1 if pat & 1 else 0, 0))
        # nav-mesh-sphere rows of its actors -> nav-sphere empties
        for o in actors:
            for i, r in enumerate(list(o.og_lump_rows)):
                if r.key != "nav-mesh-sphere":
                    continue
                import json
                try:
                    v = json.loads(r.value) if r.ltype == "plain-text" else None
                except ValueError:
                    v = None
                sph = [s for s in (v[1:] if isinstance(v, list) else []) if isinstance(s, list) and len(s) == 4]
                if not sph:
                    continue
                scale = 1.0 / M if v[0] == "vector" else 1.0
                for s in sph:
                    em = bpy.data.objects.new(f"NAVSPHERE_{nm.name[8:]}", None)
                    em.empty_display_type = "SPHERE"
                    em.empty_display_size = s[3] * scale
                    em.location = _bl((s[0] * scale, s[1] * scale, s[2] * scale))
                    for c in nm.users_collection:
                        c.objects.link(em)
                    nm.og_nav_spheres.add().obj = em
                    made.append(em)
                o.og_lump_rows.remove(list(o.og_lump_rows).index(r))
                break
        if not actors:
            skipped.append(f"{nm.name} (no actor found to link it to)")
        made.insert(0, nm)
    return made, skipped
