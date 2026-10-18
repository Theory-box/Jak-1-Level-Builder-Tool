"""Import > From GOAL files: actors.

Two inputs:
- a custom level .jsonc: typed lumps (["meters", 4.0], ["vector4m", [...]],
  "'symbol" ...), game_task "(game-task x)", names for actor links
- the game's decompiler_out/jak1/entities .json: raw lumps (game units, 4096
  per meter, 65536 per turn), int enums (pickup-type, game-task, fact-options)
  and actor ids (aid) for actor links

Both are first brought to the typed form (normalize), then each lump goes to
the actor's DB fields (the reverse of export/schema_emit.py), its path /
volume / links / scale, and what's left becomes custom lump rows, so a
re-export writes the same lumps.
"""
from __future__ import annotations

import json
import math
import re

import bpy
import mathutils

M = 4096.0                    # game units per meter
DEG = 65536.0 / 360.0         # game units per degree

# typed lump forms of a custom level .jsonc
_TYPES = {"float", "meters", "degrees", "int32", "uint32", "enum-int32", "enum-uint32", "vector", "vector4m",
          "vector3m", "vector-vol", "movie-pos", "water-height", "eco-info", "cell-info", "buzzer-info",
          "symbol", "string", "type"}
_VECTOR = {"vector", "vector4m", "vector3m", "vector-vol", "movie-pos"}

# raw floats the game shows in meters / degrees (pc/debug/entity-debug.gc)
_METERS = {"spring-height", "vis-dist", "height-info", "distance", "cam-notice-dist", "cam-vert", "cam-horz",
           "idle-distance", "nearest-y-threshold", "center-radius", "notice-dist", "trigger-height", "notice-top"}
_DEGREES = {"rotoffset", "fov", "rotmin", "rotmax", "tiltmin", "tiltmax", "rotspeed"}

PICKUPS = ("none", "eco-yellow", "eco-red", "eco-blue", "eco-green", "money", "fuel-cell", "eco-pill",
           "buzzer", "eco-pill-random")

# lumps the export makes itself or the game doesn't need from a custom level
_DROP = {"name", "visvol"}

# Blender (x, y, z) -> game (x, z, -y)
_R = mathutils.Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0)))


def _ltype(v):
    """The type of a typed lump value ("meters", "vector4m@0" -> "vector4m"), or None."""
    if isinstance(v, list) and v and isinstance(v[0], str):
        t = v[0].split("@")[0]
        return t if t in _TYPES else None
    return None


def _task_name(n):
    from . import db
    for t in db.game_tasks():
        if t.get("value") == n:
            return t["id"]
    return str(n)


def _task_expr(v):
    """game_task of an entry -> task id ("none" for none)."""
    if isinstance(v, int):
        return _task_name(v)
    s = str(v or "").strip()
    m = re.match(r"\(game-task\s+([^)\s]+)\)", s)
    return m.group(1) if m else (s or "none")


def _is_link_key(k):
    return k.endswith("-actor")


# ── Game entities .json -> typed ──────────────────────────────────────────────

def _field_types(etype):
    """{lump key: lump type} from the actor's DB fields (for raw values)."""
    from . import db
    out = {}
    for f in db.inherited_fields(etype) + db.trait_fields(etype):
        lp = f.get("lump")
        if isinstance(lp, dict) and lp.get("key"):
            out.setdefault(lp["key"], lp.get("type") or f.get("type"))
    return out


def _raw_to_typed(key, v, hint, aid_names):
    """One raw lump of a game entities .json -> its typed form (or a
    ("links", [names]) tuple for actor links)."""
    if _is_link_key(key) and isinstance(v, (int, list)):
        ids = v if isinstance(v, list) else [v]
        return ("links", [aid_names.get(i, str(i)) for i in ids])
    if isinstance(v, str):
        return "'" + v[1:] if v.startswith("'") else ["string", v]
    if key == "eco-info" and isinstance(v, list) and len(v) == 2 and all(isinstance(x, int) for x in v):
        p = PICKUPS[v[0]] if 0 <= v[0] < len(PICKUPS) else str(v[0])
        if p == "fuel-cell":
            return ["cell-info", f"(game-task {_task_name(v[1])})"]
        if p == "buzzer":
            return ["buzzer-info", f"(game-task {_task_name(v[1] & 0xffff)})", v[1] >> 16]
        return ["eco-info", f"(pickup-type {p})", v[1]]
    if key == "water-height" and isinstance(v, list) and len(v) in (4, 5):
        flags = int(v[3])
        names = " ".join(f"wt{i:02d}" for i in range(32) if flags >> i & 1)
        return ["water-height", v[0] / M, v[1] / M, v[2] / M, f"(water-flags {names})"] + \
            ([v[4] / M] if len(v) == 5 else [])
    vecs = v if isinstance(v, list) and v and isinstance(v[0], list) else None
    flat4 = isinstance(v, list) and len(v) == 4 and all(isinstance(x, (int, float)) for x in v)
    if vecs is None and flat4 and (key in ("movie-pos", "nav-mesh-sphere", "vol") or hint in _VECTOR):
        vecs = [v]                              # one vector, not wrapped in a list
    if vecs is not None:
        if key == "vol" or hint == "vector-vol":
            return ["vector-vol"] + [[a, b, c, d / M] for a, b, c, d in vecs]
        if key == "movie-pos" or hint == "movie-pos":
            return ["movie-pos"] + [[a / M, b / M, c / M, d / DEG] for a, b, c, d in vecs]
        if hint == "vector3m":
            return ["vector3m"] + [[x / M for x in p[:3]] for p in vecs]
        if hint == "vector4m" or key.startswith("path") or key == "campath":
            return ["vector4m"] + [[p[0] / M, p[1] / M, p[2] / M, p[3]] for p in vecs]
        return ["vector"] + [list(p) for p in vecs]
    vals = v if isinstance(v, list) else [v]
    if not all(isinstance(x, (int, float)) for x in vals):
        return None
    if hint == "meters" or (hint is None and key in _METERS and len(vals) == 1):
        return ["meters", vals[0] / M]
    if hint == "degrees" or (hint is None and key in _DEGREES and len(vals) == 1):
        return ["degrees", vals[0] / DEG]
    if all(isinstance(x, int) for x in vals) and hint not in ("float",):
        if hint in ("uint32", "enum-uint32") or any(x > 0x7fffffff for x in vals):
            return ["uint32"] + vals
        return ["int32"] + vals
    return ["float"] + [float(x) for x in vals]


def normalize(entry, aid_names):
    """(etype, task id, {key: typed value}, {key: [link names]}) of an actor entry."""
    etype = resolve_etype(entry)
    raw = entry.get("lump") or {}
    custom = isinstance(entry.get("game_task"), str) or "vis_id" in entry or \
        any(_ltype(v) for v in raw.values())
    lumps, links = {}, {}
    hints = None if custom else _field_types(etype)
    for k, v in raw.items():
        if k in _DROP:
            continue
        if custom:
            if _is_link_key(k) and _ltype(v) == "string":
                links[k] = list(v[1:])
            else:
                lumps[k] = v
            continue
        t = _raw_to_typed(k, v, hints.get(k), aid_names)
        if isinstance(t, tuple):
            links[k] = t[1]
        elif t is not None:
            lumps[k] = t
    return etype, _task_expr(entry.get("game_task", 0)), lumps, links


_VARIANT_ETYPES = None


def variant_etypes():
    """{exported etype: (DB etype, variant field key, choice id)} for variants
    that export as another etype (citb-arm -> citb-arm-a ...)."""
    global _VARIANT_ETYPES
    if _VARIANT_ETYPES is None:
        from . import db
        from .data import ENTITY_DEFS
        out = {}
        for et in ENTITY_DEFS:
            f = db.variant_field(et)
            if not f:
                continue
            for c in db._resolve_choices(f):
                v = c.get("etype")
                if v and v != et and not db.find_actor(v):
                    out.setdefault(v, (et, f["key"], c.get("id", c.get("value"))))
        _VARIANT_ETYPES = out
    return _VARIANT_ETYPES


def resolve_etype(entry):
    """The DB etype of an entry: the game's generic "eco" becomes the eco
    pickup its eco-info holds; variant / level subtype etypes their actor."""
    et = str(entry.get("etype", ""))
    if et in variant_etypes():
        return variant_etypes()[et][0]
    from . import db
    if et and not db.find_actor(et) and "-" in et and db.find_actor(et.split("-", 1)[1]):
        return et.split("-", 1)[1]
    if et == "eco":
        ei = (entry.get("lump") or {}).get("eco-info")
        if isinstance(ei, list) and ei and isinstance(ei[0], int) and 0 <= ei[0] < len(PICKUPS):
            return PICKUPS[ei[0]]
        if isinstance(ei, list) and len(ei) > 1 and isinstance(ei[1], str):
            m = re.match(r"\(pickup-type\s+([^)\s]+)\)", ei[1])
            if m:
                return m.group(1)
    return et


# ── Typed lumps -> DB fields ──────────────────────────────────────────────────

def _scalars(tv):
    """The values of a typed lump: [t, a, b] -> [a, b]; [t, [x, y, z]] -> [x, y, z]."""
    if isinstance(tv, list) and len(tv) >= 2 and isinstance(tv[1], list):
        return list(tv[1])
    return list(tv[1:]) if isinstance(tv, list) else [tv]


def _unformat(fmt, s):
    """'(foo {value})' + '(foo bar)' -> 'bar' (None when it doesn't match)."""
    if not isinstance(s, str):
        return None
    a, _, b = fmt.partition("{value}")
    if s.startswith(a) and s.endswith(b):
        return s[len(a):len(s) - len(b)] if b else s[len(a):]
    return None


def _enum_from(f, v):
    """The enum field's choice for a lump value (lump_value int or the value)."""
    ch = f.get("choices")
    if isinstance(ch, list):
        for c in ch:
            if "lump_value" in c and isinstance(v, (int, float)) and int(v) == c["lump_value"]:
                return c.get("value")
        for c in ch:
            if c.get("value") == v:
                return v
        return None
    return v


def _set(o, f, value):
    k = f["key"]
    t = f.get("type")
    if t == "bool":
        value = bool(value)
    elif t in ("int", "int32", "uint32", "mode") and isinstance(value, (int, float)):
        value = int(round(value))
    elif t in ("float", "meters", "degrees") and isinstance(value, (int, float)):
        value = float(value)
    o[k] = value


def _task_into(o, key, task):
    """A task field: a known task id, else "custom" + <key>_custom."""
    from . import db
    if task in {t["id"] for t in db.game_tasks()}:
        o[key] = task
    else:
        o[key] = "custom"
        o[key + "_custom"] = task


def apply_fields(o, etype, lumps, fields=None):
    """Set the actor's DB fields (or these fields) from its typed lumps;
    returns the lump keys they took (the rest goes to links / paths / custom
    rows)."""
    from . import db
    if fields is None:
        fields = db.inherited_fields(etype) + db.trait_fields(etype)
    took = set()
    by_key = {}
    for f in fields:
        lp = f.get("lump") if isinstance(f.get("lump"), dict) else None
        lb = f.get("lump_bit") if isinstance(f.get("lump_bit"), dict) else None
        if lp and lp.get("key"):
            by_key.setdefault(lp["key"], []).append(f)
        if lb and lb.get("key") and not lb.get("set_if_link"):
            by_key.setdefault(lb["key"], []).append(f)
    for key, fs in by_key.items():
        if key not in lumps:
            continue
        tv = lumps[key]
        ok = True
        for f in fs:
            if f.get("type") == "object_ref":
                ok = False
                continue
            lp = f.get("lump") if isinstance(f.get("lump"), dict) else None
            lb = f.get("lump_bit") if isinstance(f.get("lump_bit"), dict) else None
            if lb:
                n = _bits(key, tv)
                if n is None:
                    ok = False
                    continue
                _set(o, f, bool(n & int(lb.get("bit_value", 0))))
                continue
            lt = lp.get("type")
            if lt == "const":
                continue
            if lt == "water-height":
                vals = _scalars(tv)
                for ck, v in zip(lp.get("components", []), vals[:3]):
                    o[ck] = float(v)
                flags = next((x for x in vals if isinstance(x, str)), "")
                if lp.get("liquid_key"):
                    have = set(re.findall(r"wt\d\d", flags))
                    best = max(((n, set(d.get("flags", []))) for n, d in lp.get("liquids", {}).items()
                                if set(d.get("flags", [])) <= have), key=lambda x: len(x[1]), default=None)
                    if best:
                        o[lp["liquid_key"]] = best[0]
                    if lp.get("ripple_key"):
                        o[lp["ripple_key"]] = "wt20" in have
                continue
            if f.get("type") == "task":
                v = _scalars(tv)
                _task_into(o, f["key"], _task_expr(v[0] if v else ""))
                continue
            if f.get("type") == "color":
                v = _scalars(tv)
                if len(v) >= 3:
                    o[f["key"]] = [float(x) for x in v[:3]]
                continue
            if lt == "eco-info-picker":
                if not _eco_into(o, f, lp, tv):
                    ok = False
                continue
            if lt == "symbol_literal":
                v = tv[1:] if isinstance(tv, str) and tv.startswith("'") else (_scalars(tv)[0] if _ltype(tv) == "symbol" else None)
                if v is None:
                    ok = False
                    continue
                v = _enum_from(f, v) if f.get("type") == "enum" else v
                if v is None:
                    ok = False
                    continue
                _set(o, f, v)
                continue
            if lp.get("bare"):
                _set(o, f, tv)
                continue
            vals = _scalars(tv)
            slot = lp.get("slot")
            if slot is not None:
                if slot >= len(vals):
                    ok = False
                    continue
                v = vals[slot]
            elif len(vals) == 1:
                v = vals[0]
            else:
                ok = False
                continue
            if lp.get("format") and isinstance(v, str):
                u = _unformat(lp["format"], v)
                if u is None:
                    ok = False
                    continue
                v = u
            if lp.get("scale") and isinstance(v, (int, float)):
                v = v / lp["scale"]
            if f.get("type") == "enum":
                v = _enum_from(f, v)
                if v is None:
                    ok = False
                    continue
            elif "value_if_true" in f:
                v = v == f["value_if_true"]
            _set(o, f, v)
        if ok:
            took.add(key)
    return took


_OFF = {"if_not_none": "none", "if_true": False, "if_nonzero": 0, "if_positive": 0, "if_nonneg": -1,
        "if_non_empty": "", "if_any_nonzero": 0}


def _norm(v):
    """A lump value for comparing: numbers rounded, int / uint / enum types alike."""
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return round(float(v), 3)
    if isinstance(v, str):
        return {"uint32": "int32", "enum-uint32": "enum-int32"}.get(v, v)
    if isinstance(v, list):
        return [_norm(x) for x in v]
    return v


def settle(o, etype, lumps, took):
    """Make the fields export what the file had: a lump the fields write but
    the file didn't have is switched off (the field's "off" value: none / 0 /
    false / its default), a lump they write differently is returned to become
    a custom row (which wins at export). Returns {key: typed value}."""
    from . import db
    from .export.schema_emit import emit_schema_lumps
    fields = db.inherited_fields(etype)
    traits = db.trait_fields(etype)
    def emitted():
        get = db.prop_getter(o)
        em = emit_schema_lumps(get, fields, etype=etype, choice_tables={"CratePickups": db.crate_pickups()})
        em.update(emit_schema_lumps(get, traits, etype=etype))
        if "options" in em:
            em["options"] = db.options_enum_lump(em["options"])
        return em
    em = emitted()
    for k in [k for k in em if k not in lumps]:
        for f in fields + traits:
            lp = f.get("lump") if isinstance(f.get("lump"), dict) else {}
            lb = f.get("lump_bit") if isinstance(f.get("lump_bit"), dict) else {}
            if lb.get("key") == k and not lb.get("set_if_link"):
                o[f["key"]] = False
            elif lp.get("key") == k:
                rule = f.get("write_if") or ("if_not_none" if lp.get("type") == "eco-info-picker" else None)
                if rule == "if_not_default":
                    d = db.field_default(f, etype)
                    if d is not None:
                        o[f["key"]] = d
                elif rule in _OFF:
                    o[f["key"]] = _OFF[rule]
    em = emitted()
    src = dict(lumps)
    if "options" in src:
        src["options"] = db.options_enum_lump(src["options"])
    return {k: lumps[k] for k in took
            if (k in em and _norm(em[k]) != _norm(src[k])) or (k not in em and _writes(fields + traits, k))}


def _writes(fields, key):
    """True if a schema field writes this lump (const / computed ones don't count)."""
    for f in fields:
        lp = f.get("lump") if isinstance(f.get("lump"), dict) else {}
        if lp.get("key") == key and lp.get("type") != "const" and f.get("type") != "object_ref":
            return True
    return False


def _bits(key, tv):
    """Int value of a bit-field lump (["uint32", n] or "(fact-options a b)")."""
    from . import db
    v = _scalars(tv)
    if not v:
        return None
    if isinstance(v[0], (int, float)):
        return int(v[0])
    m = re.match(r"\(([\w-]+)\s*(.*)\)", str(v[0]))
    if not m:
        return None
    if key == "options":
        names = {n: b for b, n in db.fact_option_names().items()}
        n = 0
        for w in m.group(2).split():
            if w not in names:
                return None
            n |= names[w]
        return n
    return None


def _eco_into(o, f, lp, tv):
    """eco-info picker (crate contents): pickup + amount; a cell / scout fly
    also sets the game task (and fly number)."""
    from . import db
    t = _ltype(tv)
    v = _scalars(tv)
    table = db.crate_pickups() if f.get("choices") == "CratePickups" else f.get("choices") or []
    def pick(pid):
        c = next((c for c in table if pid in (c.get("id"), c.get("value"))), None)
        if c:
            o[f["key"]] = c.get("id", c.get("value"))
        return c is not None
    if t == "eco-info" and len(v) >= 2:
        m = re.match(r"\(pickup-type\s+([^)\s]+)\)", str(v[0]))
        if not m or not pick(m.group(1)):
            return False
        if lp.get("pairs_with"):
            o[lp["pairs_with"]] = int(v[1])
        return True
    if t in ("cell-info", "buzzer-info") and v:
        if not pick("fuel-cell" if t == "cell-info" else "buzzer"):
            return False
        _task_into(o, "og_game_task", _task_expr(v[0]))
        if t == "buzzer-info" and len(v) > 1:
            o["og_buzzer_index"] = int(v[1]) + 1
        return True
    return False


# ── Paths, volumes, links, custom rows ────────────────────────────────────────

def game_to_blender(p):
    return mathutils.Vector((p[0], -p[2], p[1]))


def _make_path(ctx, o, name, tv, knots):
    """A poly curve through the path points, linked as the actor's path (main
    "path") or an extra path; path-k knots -> smooth mode + its knots."""
    from .collections import _link_object_to_sub_collection, _COL_PATH_WAYPOINTS
    from .export import path_modes as pm
    pts = [game_to_blender(p) for p in _scalars_list(tv)]
    if not pts:
        return None
    cu = bpy.data.curves.new(f"{o.name}_{name}", "CURVE")
    cu.dimensions = "3D"
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for p, co in zip(sp.points, pts):
        p.co = (co.x, co.y, co.z, 1.0)
    c = bpy.data.objects.new(f"{o.name}_{name}", cu)
    ctx.scene.collection.objects.link(c)
    _link_object_to_sub_collection(ctx.scene, c, *_COL_PATH_WAYPOINTS)
    kv = _scalars(knots) if knots is not None else None
    mode = "LINEAR"
    if kv:
        mode = "SMOOTH_CLAMPED"
    manual = bool(kv) and [round(k, 5) for k in kv] != [round(k, 5) for k in pm.knots_clamped(len(pts))]
    if name == "path":
        o.og_waypoint_sources.add().obj = c
        o.og_path_mode = mode
        if manual:
            o.og_path_knots_manual = True
            o.og_path_knots.clear()
            for k in kv:
                o.og_path_knots.add().value = float(k)
    else:
        xp = o.og_extra_paths.add()
        xp.name = name
        xp.mode = mode
        xp.sources.add().obj = c
        if manual:
            xp.knots_manual = True
            for k in kv:
                xp.knots.add().value = float(k)
    return c


def _scalars_list(tv):
    """Vector list of a typed vector lump: ["vector4m", [..], [..]] -> [[..], [..]]."""
    return [p for p in tv[1:] if isinstance(p, list)] if isinstance(tv, list) else []


def make_volume(ctx, planes, name):
    """A VOL_ mesh from convex planes [nx, ny, nz, d] (game axes, d in meters):
    the corners where three planes meet inside all of them, convex hull."""
    import bmesh
    from itertools import combinations
    from .collections import _link_object_to_sub_collection, _COL_PATH_TRIGGERS
    P = [(mathutils.Vector((n[0], n[1], n[2])), n[3]) for n in planes]
    pts = []
    for (n1, d1), (n2, d2), (n3, d3) in combinations(P, 3):
        den = n1.dot(n2.cross(n3))
        if abs(den) < 1e-9:
            continue
        x = (d1 * n2.cross(n3) + d2 * n3.cross(n1) + d3 * n1.cross(n2)) / den
        if all(n.dot(x) - d <= 1e-4 for n, d in P):
            pts.append(x)
    if len(pts) < 4:
        return None
    bm = bmesh.new()
    for p in pts:
        bm.verts.new(game_to_blender(p))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bmesh.ops.convex_hull(bm, input=bm.verts)
    bmesh.ops.dissolve_limit(bm, angle_limit=0.001, verts=bm.verts, edges=bm.edges)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    # origin at the centre
    c = sum((v.co for v in me.vertices), mathutils.Vector()) / max(1, len(me.vertices))
    me.transform(mathutils.Matrix.Translation(-c))
    vol = bpy.data.objects.new(name, me)
    vol.location = c
    vol["og_vol_id"] = 0
    vol.show_name = True
    vol.display_type = "WIRE"
    vol.color = (0.0, 0.9, 0.3, 0.4)
    vol.set_invisible = True
    vol.set_collision = True
    vol.ignore = True
    ctx.scene.collection.objects.link(vol)
    _link_object_to_sub_collection(ctx.scene, vol, *_COL_PATH_TRIGGERS)
    return vol


def _row_for(key, tv):
    """(ltype, value text) of a custom lump row for a typed value."""
    t = _ltype(tv)
    if t in ("float", "int32", "uint32") and all(isinstance(x, (int, float)) for x in tv[1:]):
        return t, " ".join(repr(float(x)) if t == "float" else str(int(x)) for x in tv[1:])
    if t in ("meters", "degrees") and len(tv) == 2 and isinstance(tv[1], (int, float)):
        return t, repr(float(tv[1]))
    if t in ("symbol", "type", "enum-int32", "enum-uint32", "cell-info") and len(tv) == 2 and isinstance(tv[1], str):
        return t, tv[1]
    if t == "string" and all(isinstance(x, str) and x and " " not in x for x in tv[1:]):
        return t, " ".join(tv[1:])
    return "plain-text", json.dumps(tv)


def add_custom_row(o, key, tv):
    r = o.og_lump_rows.add()
    r.key = key
    r.ltype, r.value = _row_for(key, tv)


# ── The importer ─────────────────────────────────────────────────────────────

def actor_uid(name, etype):
    """The <n> of ACTOR_<etype>_<n> from an entry's lump name."""
    # "<etype>-<n>" (game) or "<level nick>-<etype>-<n>" (a custom level)
    m = re.match(r"(?:[\w]+-)?" + re.escape(etype) + r"-(.+)$", name)
    if m:
        name = m.group(1)
    return re.sub(r"[^\w.-]", "_", name) or "0"


def import_actors(ctx, entries):
    from . import db
    from .data import _actor_set_link
    from .operators.spawn import make_actor
    from .goal_import import all_entries
    # actor ids (game files) and lump names -> lump names (all loaded entries)
    aid_names = {}
    for e in all_entries():
        d = e["data"]
        if isinstance(d, dict) and "aid" in d:
            aid_names[d["aid"]] = e["name"]
    made, pending = [], []
    by_lump = {}
    for e in entries:
        d = e["data"]
        etype, task, lumps, links = normalize(d, aid_names)
        t = d.get("trans") or [0, 0, 0]
        variant = variant_etypes().get(str(d.get("etype", "")), (None, None, None))[2]
        o = make_actor(ctx, etype, game_to_blender(t), variant=variant)
        uid = actor_uid(e["name"], etype)
        want = f"ACTOR_{etype}_{uid}"
        if o.name != want:
            from .collections import free_object_name
            o.name = want if want not in bpy.data.objects else free_object_name(want + "-", 1)
        q = d.get("quat")
        if q and len(q) == 4:
            g = mathutils.Quaternion((q[3], q[0], q[1], q[2])).to_matrix()
            o.rotation_euler = (_R.transposed() @ g @ _R).to_euler()
        by_lump[e["name"]] = o
        if task and task != "none" and any(f.get("key") == "og_game_task" for f in db.inherited_fields(etype)):
            _task_into(o, "og_game_task", task)
        took = apply_fields(o, etype, lumps)
        rest = {k: v for k, v in lumps.items() if k not in took}
        rest.update(settle(o, etype, lumps, took))
        # cells / flies keep their task in eco-info (game-task panel)
        ei = rest.get("eco-info")
        if _ltype(ei) in ("cell-info", "buzzer-info") and db.panel_exports(etype, "game-task"):
            v = _scalars(ei)
            _task_into(o, "og_game_task", _task_expr(v[0]))
            if _ltype(ei) == "buzzer-info" and len(v) > 1:
                o["og_buzzer_index"] = int(v[1]) + 1
            rest.pop("eco-info")
        elif _ltype(ei) == "eco-info" and db.find_actor(etype) and \
                re.search(r"\(pickup-type " + re.escape(etype) + r"\)", str(ei[1])):
            rest.pop("eco-info")                     # an eco / orb pickup: its own etype
        # scale: game (x, y, z) -> Blender (x, z, y)
        sc = rest.get("scale")
        if sc is not None and db.panel_exports(etype, "scale"):
            v = _scalars(sc)
            if len(v) >= 3:
                o.scale = (float(v[0]), float(v[2]), float(v[1]))
                rest.pop("scale")
        # paths
        for k in [k for k in rest if re.fullmatch(r"path[a-z]?|pathspawn", k) and _ltype(rest[k]) in ("vector4m", "vector")]:
            if db.uses_waypoints(etype):
                if _make_path(ctx, o, k, rest[k], rest.get(k + "-k")):
                    rest.pop(k)
                    rest.pop(k + "-k", None)
        # a volume
        vv = rest.get("vol")
        if _ltype(vv) == "vector-vol" and db.needs_vol(etype):
            vol = make_volume(ctx, _scalars_list(vv), f"VOL_{o.name[6:]}")
            if vol is not None:
                from .export import _vol_links, _rename_vol_for_links
                en = _vol_links(vol).add()
                en.target_name = o.name
                en.behaviour = "cue-chase"
                _rename_vol_for_links(vol)
                made.append(vol)
                rest.pop("vol")
        for k, v in rest.items():
            add_custom_row(o, k, v)
        pending.append((o, etype, links))
        made.append(o)
    # links, now that every imported actor exists
    from .collections import actor_lump_name
    by_export = {actor_lump_name(o.name): o for o in bpy.context.scene.objects if o.name.startswith("ACTOR_")}
    for o, etype, links in pending:
        for k, names in links.items():
            tgts = [by_lump.get(n) or by_export.get(n) for n in names]
            multi = bool(db.link_slot(etype, k, 0).get("allow-multiple"))
            if all(tgts) and all(db.link_slot(etype, k, i) or (multi and i) for i in range(len(names))):
                for i, tgt in enumerate(tgts):
                    _actor_set_link(o, k, i, tgt.name)
            else:                                    # no link slot / target not in the scene
                add_custom_row(o, k, ["string"] + names)
    return made
