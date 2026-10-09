# ───────────────────────────────────────────────────────────────────────
# export/actors.py — OpenGOAL Level Tools
#
# collect_actors — the main per-actor pipeline that walks the scene, reads each ACTOR_* object's og_* custom props, and emits the actor entries into actor_list.jsonc.
# Contains the per-actor branches for actors whose export needs bespoke logic (crate, launcher, water-vol, etc.).
# ───────────────────────────────────────────────────────────────────────

from __future__ import annotations

import bpy, os, re, json, math, mathutils
from pathlib import Path
from ..data import (
    ENTITY_DEFS, ETYPE_CODE, ETYPE_TPAGES, ETYPE_AG, VERTEX_EXPORT_TYPES,
    needed_tpages, ACTOR_LINK_DEFS,
    _lump_ref_for_etype, _actor_link_slots, _actor_has_links,
    _actor_links, _actor_get_link, _actor_set_link,
    _actor_remove_link, _build_actor_link_lumps,
    _parse_lump_row, _aggro_event_id, AGGRO_TRIGGER_EVENTS,
    _LUMP_HARDCODED_KEYS, _is_custom_type,
)
from .. import db as _schema_db
from .schema_emit import emit_schema_lumps
from ..collections import (
    _get_level_prop, _level_objects,
    _active_level_col, _classify_object, _col_path_for_entity,
    _ensure_sub_collection, _recursive_col_objects,
    _COL_PATH_WAYPOINTS, _COL_PATH_NAVMESHES,
)
from ..collections import (
    _COL_PATH_SPAWNABLE_ENEMIES, _COL_PATH_SPAWNABLE_PLATFORMS,
    _COL_PATH_SPAWNABLE_PROPS, _COL_PATH_SPAWNABLE_NPCS,
    _COL_PATH_SPAWNABLE_PICKUPS, _COL_PATH_TRIGGERS, _COL_PATH_CAMERAS,
    _COL_PATH_SPAWNS, _COL_PATH_SOUND_EMITTERS, _COL_PATH_GEO_SOLID,
    _COL_PATH_GEO_COLLISION, _COL_PATH_GEO_VISUAL, _COL_PATH_GEO_REFERENCE,
    _COL_PATH_WAYPOINTS, _COL_PATH_NAVMESHES,
    _ENTITY_CAT_TO_COL_PATH, _LEVEL_COL_DEFAULTS,
    _all_level_collections, _active_level_col, _col_is_no_export,
    _recursive_col_objects, _level_objects, _ensure_sub_collection,
    _link_object_to_sub_collection, _col_path_for_entity, _classify_object,
    _get_level_prop, _set_level_prop, _active_level_items,
    _set_blender_active_collection, _get_death_plane, _set_death_plane,
    _on_active_level_changed,
)

# Cross-module imports (siblings in the export package)
from .paths import (
    log,
)
from .predicates import (
    _canonical_actor_objects,
    _classify_target,
)
from .volumes import (
    _vol_aabb,
    _vol_planes,
    _vol_links,
    _vol_link_targets,
)


# Cross-module imports (siblings in the export package)


# ═══════════════════════════════════════════════════════════════════════════
# Waypoint collection
# ───────────────────────────────────────────────────────────────────────────
# An actor's path comes from its og_waypoint_sources collection — an ordered
# list of object pointers. Each entry is either:
#   - An EMPTY (single waypoint at the empty's world position)
#   - A CURVE (one waypoint per spline control point, in spline order;
#     bezier handles are ignored, only the main control points are used)
#
# If the collection is empty, fall back to the legacy `<actor>_wp_NN` empty
# name-grep so pre-existing levels still export correctly.
# ═══════════════════════════════════════════════════════════════════════════


def _to_game_coords(world_vec):
    """Blender world-space → Jak game coords (Y-up, axes swapped).
    Returns a 4-element list ready for the path lump's vector4m format."""
    return [round(world_vec.x, 4), round(world_vec.z, 4),
            round(-world_vec.y, 4), 1.0]


def _make_path_knots(n):
    """Clamped uniform cubic B-spline knot vector for `n` control points.

    Layout (verified by porting OpenGOAL's curve-evaluate! /
    calculate-basis-functions-vector! and checking in-bounds access,
    partition-of-unity, and endpoint interpolation):
        four leading 0.0, the interior sequence 1..n-4, then four copies
        of (n-3). Total = n + 4 values, i.e. num-knots = num-cverts + 4
        for a degree-3 (cubic) curve.

    The engine interpolates the first and last control point exactly;
    interior points are approached but not touched (the curve cuts corners).
    NOTE: this is N+4, NOT the N+8 figure in older research notes — N+8
    drives the control-vertex index out of bounds in curve-evaluate!.
    Requires n >= 4 (a cubic needs degree+1 control points).
    """
    lead = [0.0, 0.0, 0.0, 0.0]
    interior = [float(i) for i in range(1, n - 3)]  # empty when n == 4
    trail = [float(n - 3)] * 4
    return lead + interior + trail


def _curve_points_world(curve_obj):
    """Yield each spline control point of a curve object in world space.
    Handles bezier, poly, and NURBS splines. Bezier handles are ignored."""
    M = curve_obj.matrix_world
    for spline in curve_obj.data.splines:
        if spline.bezier_points:
            for bp in spline.bezier_points:
                yield M @ bp.co
        else:
            # Poly / NURBS: points are 4D (xyzw); use xyz only.
            for pt in spline.points:
                local = mathutils.Vector(pt.co[:3])
                yield M @ local


def _collect_waypoint_points(actor_obj):
    """Return the actor's path as a list of game-space [x,y,z,w] vectors.

    Reads og_waypoint_sources if populated; otherwise falls back to the
    legacy name-grep so older levels with manually-placed _wp_NN empties
    continue to export without migration.
    """
    points = []
    sources = getattr(actor_obj, "og_waypoint_sources", None)
    if sources and len(sources) > 0:
        # New collection-driven path
        for src in sources:
            src_obj = src.obj
            if src_obj is None or src_obj.name not in bpy.data.objects:
                continue
            if src_obj.type == "EMPTY":
                points.append(_to_game_coords(src_obj.matrix_world.translation))
            elif src_obj.type == "CURVE":
                for world_co in _curve_points_world(src_obj):
                    points.append(_to_game_coords(world_co))
    else:
        # Legacy fallback — name-based discovery of <actor>_wp_NN empties.
        wp_prefix = actor_obj.name + "_wp_"
        wp_objects = sorted(
            [o for o in bpy.data.objects
             if o.name.startswith(wp_prefix) and o.type == "EMPTY"],
            key=lambda o: o.name
        )
        for wp in wp_objects:
            points.append(_to_game_coords(wp.matrix_world.translation))

    return points


def movie_pos_vector(e):
    """[x, y, z, angle_deg] for a movie-pos empty: game-space position in
    meters and the empty's Z rotation as the facing angle."""
    import math
    t = e.matrix_world.translation
    yaw = math.degrees(e.matrix_world.to_euler("XYZ").z)
    return [round(t.x, 4), round(t.z, 4), round(-t.y, 4), round(yaw, 3)]


def _computed_lumps(o, etype):
    """Lumps computed from Blender object/scene/link state that the pure schema
    emitter can't produce. Declared in the DB, so any actor can opt in by adding
    the field — no per-actor code.

    Supported:
      - object_ref field + vector lump -> "target-vector": xyz = the linked
        object's game-space location (Blender x,z,-y, x4096), w = the paired time
        field in seconds (default 0.5s). Used by launcher's alt-vector.
      - lump_bit fields with key "flags" -> a uint32 bitfield OR-accumulated from
        bool props and link presence (lump_bit.set_if_link). Emitted only when
        nonzero. Used by the eco-door family. perm-status value_if_true handled.
    (Volume lumps for need_vol actors are handled in collect_actors from linked
    VOL_ meshes — the shared volume system — not here.)
    """
    out = {}
    fields = _schema_db.inherited_fields(etype)
    flags = 0
    have_flags = False
    for f in fields:
        lp = f.get("lump")
        lb = f.get("lump_bit")
        # target-vector from a linked object
        if f.get("type") == "object_ref" and isinstance(lp, dict) and lp.get("type") == "vector":
            dest_name = o.get(f["key"], "")
            dest_obj  = bpy.data.objects.get(dest_name) if dest_name else None
            if dest_obj:
                dl = dest_obj.matrix_world.translation   # world position (it may be parented)
                dx = round(dl.x * 4096, 2)
                dy = round(dl.z * 4096, 2)
                dz = round(-dl.y * 4096, 2)
                tkey = lp.get("pairs_with")
                t    = float(o.get(tkey, -1.0)) if tkey else -1.0
                fw   = t if t >= 0 else 0.5   # fly time in seconds (engine reads W as seconds)
                out[lp["key"]] = ["vector", [dx, dy, dz, fw]]
        # flags bitfield: prop bits + link-derived bits
        elif isinstance(lb, dict) and lb.get("key") == "flags":
            have_flags = True
            bit = int(lb.get("bit_value", 0))
            link = lb.get("set_if_link")
            if link:
                if _actor_get_link(o, link, 0):
                    flags |= bit
            elif bool(o.get(f.get("key"), False)):
                flags |= bit
        # perm-status: value_if_true bool -> fixed uint (starts-open door)
        elif (isinstance(lp, dict) and lp.get("key") == "perm-status"
              and f.get("value_if_true") is not None):
            if bool(o.get(f.get("key"), False)):
                out["perm-status"] = [lp.get("type", "uint32"), int(f["value_if_true"])]
    if have_flags and flags:
        out["flags"] = ["uint32", flags]
    return out


def collect_actors(scene, depsgraph=None):
    """Build actor list from ACTOR_ empties.

    Nav-unsafe enemies (move-to-ground=True, hover-if-no-ground=False) will
    crash the game when they try to resolve a navmesh and find a null pointer.
    Workaround: inject a 'nav-mesh-sphere' res-lump tag on each such actor.
    This tells the nav-control initialiser to use *default-nav-mesh* (a tiny
    stub mesh in navigate.gc) instead of dereferencing null.  The enemy will
    stand, idle, and notice Jak but won't properly pathfind — that requires a
    real navmesh (future work).
    """
    out = []
    _extra_actors = []   # entities generated for an actor (citadel BC camera position)
    level_objs = _level_objects(scene)
    # Shared volume system: VOL_ meshes link to target actors; any need_vol actor
    # gets its convex `vol` (via _vol_planes) from the VOL_ linked to it — same
    # mechanism cameras/checkpoints use.
    vol_by_target = {}
    for _v in level_objs:
        if _v.type == "MESH" and _v.name.startswith("VOL_"):
            for _tn in _vol_link_targets(_v):
                vol_by_target.setdefault(_tn, _v)
    for o in _canonical_actor_objects(scene, objects=level_objs):
        p = o.name.split("_", 2)
        etype, uid = p[1], p[2]

        # Abstract actors export as a concrete subclass (DB `export_as`), e.g.
        # eco-door → jng-iris-door (a real skeleton + art group).
        _rec0 = _schema_db.find_actor(etype)
        if _rec0 and _rec0.get("export_as"):
            etype = _rec0["export_as"]
        l = o.location
        gx, gy, gz = round(l.x, 4), round(l.z, 4), round(-l.y, 4)

        # ── Facing quaternion ────────────────────────────────────────────────
        # Remap Blender rotation into game space: game_rot = R @ bl_rot @ R^T
        # where R maps Blender(x,y,z) → game(x,z,-y).
        # No conjugate — the similarity transform R @ bl_rot @ R^T already
        # produces the correct game-space orientation. The previous negate-xyz
        # was erroneously borrowed from the camera system and inverted facing for
        # all non-0/180 angles (same fix already applied to the spawn path).
        _R  = mathutils.Matrix(((1,0,0),(0,0,1),(0,-1,0)))
        _m3 = o.matrix_world.to_3x3()
        _gq = (_R @ _m3 @ _R.transposed()).to_quaternion()
        aqx = round(_gq.x, 6)
        aqy = round(_gq.y, 6)
        aqz = round(_gq.z, 6)
        aqw = round(_gq.w, 6)

        lump = {"name": f"{etype}-{uid}"}

        einfo = ENTITY_DEFS.get(etype, {})

        # Collect waypoints. Reads from the actor's og_waypoint_sources
        # collection (Phase 4 of waypoint-link-source) — each source is an
        # empty (single point) or a curve (one point per spline control
        # point). Falls back to legacy <actor>_wp_NN name-grep for older
        # levels with no collection populated.
        # Path mode (AUTO / LINEAR / SMOOTH / BEZIER ... — export/path_modes.py)
        # decides the control points and, for curve-control actors, path-k.
        # Actors flagged path_linear_only in the DB (path-control readers that
        # ignore path-k) always get the straight-line reading.
        from . import path_modes as _pm
        _arec_p = _schema_db.find_actor(etype) or {}
        _ppts, path_knots, _pmode, _pwarn = _pm.build(
            _pm.gather_sources(o), getattr(o, "og_path_mode", "AUTO"),
            linear_only=_schema_db.path_linear_only(etype))
        path_pts = [_to_game_coords(mathutils.Vector(p)) for p in _ppts]
        if _pwarn and path_pts:
            log(f"  [path] {o.name}: {_pwarn}")
        if path_knots and getattr(o, "og_path_knots_manual", False):
            path_knots, _kn = _pm.manual_knots(path_knots, [k.value for k in o.og_path_knots])
            log(f"  [path-k] {o.name}: manual knots" + (f" — {_kn}" if _kn else ""))

        # ── Nav-enemy workaround (nav_safe=False) ────────────────────────────
        # These extend nav-enemy. Without a real navmesh they idle forever.
        # Inject nav-mesh-sphere so the engine doesn't dereference null.
        # entity.gc is also patched separately with a real navmesh if linked.
        if _schema_db.nav_unsafe(etype):
            nav_r = float(o.get("og_nav_radius", 6.0))
            if path_pts:
                first = path_pts[0]
                lump["nav-mesh-sphere"] = ["vector4m", [first[0], first[1], first[2], nav_r]]
                log(f"  [nav+path] {o.name}  {len(path_pts)} waypoints  sphere r={nav_r}m")
            else:
                lump["nav-mesh-sphere"] = ["vector4m", [gx, gy, gz, nav_r]]
                log(f"  [nav-workaround] {o.name}  sphere r={nav_r}m  (no waypoints - will idle)")

        # ── Path lump (DB "path" panel) ───────────────────────────────────────
        # Any actor with the path panel exports its waypoints/curves as 'path'
        # (patrolling nav-enemies, process-drawable enemies, sync platforms,
        # plat-button ...). "required" actors error at runtime without one.
        # "export": false on the panel turns the lump off.
        if _schema_db.panel_exports(etype, "path"):
            if path_pts:
                lump["path"] = ["vector4m"] + path_pts
                log(f"  [path] {o.name}  {len(path_pts)} points")
            elif _actor_get_link(o, "path-actor", 0):
                log(f"  [path] {o.name}  uses the path of {_actor_get_link(o, 'path-actor', 0).target_name}")
            elif einfo.get("needs_path"):
                log(f"  [WARNING] {o.name} needs a path but has no waypoints — will crash/error at runtime!")

        # swamp-bat's second route ('pathb') is an extra path (og_extra_paths).
        if einfo.get("needs_pathb") and not _actor_get_link(o, "path-actor", 0) and not any(
                p.name.strip() == "pathb" and len(p.sources) for p in getattr(o, "og_extra_paths", [])):
            log(f"  [WARNING] {o.name} needs a 'pathb' path (Path panel > Add Path) — will error at runtime!")

        # ── Sync ──────────────────────────────────────────────────────────────
        # The 'sync' lump comes from the sync panel's fields (schema block
        # below): [period, phase, ease out, ease in]. Both eases have a 0.001
        # minimum: an ease out of 0 makes sync-info-eased divide by zero
        # (y-end 0, sync-info.gc setup-params!); the game clamps ease in itself.
        # Leaving them out makes the game use the actor's default eases (0.15).
        if einfo.get("needs_sync") and not path_pts and _schema_db.has_panel(etype, "path"):
            log(f"  [sync-platform] {o.name}  no waypoints — will spawn idle (add ≥2 waypoints to make it move)")


        # ── Smooth-curve knots (path-k) ──────────────────────────────────────
        # When Path Mode = SMOOTH and a 'path' lump was emitted, also emit the
        # matching 'path-k' knot vector. curve-control actors (plat, plat-eco,
        # plat-button, and curve-control enemies) then load as a cubic B-spline
        # and glide along the path. Without path-k they silently downgrade to a
        # linear path-control (path-h.gc: "downgrade us to a path-control, we
        # got cverts but no knots"). Emitting it for a plain path-control actor
        # is harmless — only curve-control reads path-k.
        # A cubic needs >= 4 control points; fewer falls back to linear.
        if path_knots and "path" in lump:
            lump["path-k"] = ["float"] + path_knots
            log(f"  [path-k] {o.name}  {_pm.MODE_LABELS.get(_pmode, _pmode)}  "
                f"{len(path_pts)} cverts  {len(path_knots)} knots")

        # ── Trait fields ──────────────────────────────────────────────────────
        # Behaviours shared across many actors by predicate: idle-distance +
        # vis-dist (enemies), num-lurkers (spawners), notice-dist
        # (needs_notice_dist). Driven by the DB's TraitFields section and applied
        # to every matching actor.
        for _tk, _tv in emit_schema_lumps(
                _schema_db.prop_getter(o),
                _schema_db.trait_fields(etype),
                etype=etype).items():
            lump[_tk] = _tv

        # Bsphere radius controls vis-culling distance.  nav-enemy run-logic?
        # only processes AI/collision events when draw-status was-drawn is set,
        # which requires the bsphere to pass the renderer's cull test.
        # Custom levels lack a proper BSP vis system.
        bsph_r = 10.0  # Rockpool uses 10m for all entities; 120m caused merc renderer crashes

        # need_vol actors: bsphere must enclose the linked volume so the process
        # isn't culled before it can run point-in-vol checks each frame. Size it
        # from the linked VOL_ mesh's AABB (same as the checkpoint/WATER path).
        if _schema_db.needs_vol(etype):
            _volm = vol_by_target.get(o.name)
            if _volm:
                _xn, _xx, _yn, _yx, _zn, _zx, _cx, _cy, _cz, _rad = _vol_aabb(_volm)
                bsph_r = round((((_xx-_xn)/2)**2 + ((_yx-_yn)/2)**2 + ((_zx-_zn)/2)**2) ** 0.5 + 5.0, 2)

        # ── Movie Position panel: 'movie-pos' (one vector per position, in order) ─
        if _schema_db.panel_exports(etype, "movie-pos"):
            _mp_list = [s.obj for s in getattr(o, "og_movie_pos", []) if s.obj and s.obj.name in bpy.data.objects]
            if _mp_list:
                lump["movie-pos"] = ["movie-pos"] + [movie_pos_vector(e) for e in _mp_list]
                log(f"  [movie-pos] {o.name}  {len(_mp_list)} position(s)")

        # ── Oracle / pontoon: alt-task ────────────────────────────────────────
        if etype == "pontoon":  # oracle is schema-driven; pontoon not yet migrated
            task = _schema_db.task_expression(_schema_db.prop_getter(o), "og_alt_task")
            if task:
                lump["alt-task"] = ["enum-uint32", task]
                log(f"  [{etype}] {o.name}  alt-task={task}")

        # ── Entity links (alt-actor, water-actor, state-actor, etc.) ─────────
        # Build string-array lumps from og_actor_links CollectionProperty.
        # These are merged before custom lump rows so rows can override them.
        link_lumps = _build_actor_link_lumps(o, etype)
        # Keys that must outrank the schema: computed entity links and (below)
        # user custom lump rows. The schema overrides only legacy hardcoded values.
        _protected_keys = set(link_lumps.keys())
        for lkey, lval in link_lumps.items():
            lump[lkey] = lval
            names = lval[1:]  # strip "string" prefix
            log(f"  [entity-link] {o.name}  '{lkey}' → {names}")

        # Warn about required slots that are unset
        for (lkey, sidx, label, _accepted, required) in _actor_link_slots(etype):
            if required and not _actor_get_link(o, lkey, sidx):
                log(f"  [WARNING] {o.name} required link '{lkey}[{sidx}]' ({label}) is not set — may crash at runtime!")

        # ── Custom lump rows (assisted panel) ────────────────────────────────
        # Merge OGLumpRow entries into the lump dict. Rows take priority over
        # hardcoded values above — any conflict logs a warning but the row wins.
        for row in getattr(o, "og_lump_rows", []):
            value, err = _parse_lump_row(row.key, row.ltype, row.value)
            if err:
                log(f"  [WARNING] {o.name} lump row '{row.key}': {err} — skipped")
                continue
            key = row.key.strip()
            if key in _LUMP_HARDCODED_KEYS and key in lump:
                log(f"  [WARNING] {o.name} lump row '{key}' overrides addon default")
            lump[key] = value
            _protected_keys.add(key)
            log(f"  [lump-row] {o.name}  '{key}' = {value}")

        # ── Schema-driven lumps (every actor) ────────────────────────────────
        # The fields of all the actor's panels (its own + its parents') drive
        # its value lumps directly. Authoritative over the legacy hardcoded
        # branches above, but yields to computed entity links and to explicit
        # user custom lump rows (both in _protected_keys).
        _arec = _schema_db.find_actor(etype)
        for _lk, _lv in emit_schema_lumps(
                _schema_db.prop_getter(o),
                _schema_db.inherited_fields(etype),
                etype=etype,
                choice_tables={"CratePickups": _schema_db.crate_pickups()}).items():
            if _lk not in _protected_keys:
                lump[_lk] = _lv
                log(f"  [schema] {o.name}  '{_lk}' = {_lv}")

        # Computed lumps needing object/scene/link context (skipped by emitter).
        for _lk, _lv in _computed_lumps(o, etype).items():
            if _lk not in _protected_keys:
                lump[_lk] = _lv
                log(f"  [computed] {o.name}  '{_lk}' = {_lv}")

        # Game Task panel: cells / scout flies (and crates holding one) carry
        # the task in their eco-info (panel option "eco-info").
        _gt_task = None
        if _schema_db.panel_exports(etype, "game-task"):
            _get = _schema_db.prop_getter(o)
            _gt_task = _schema_db.task_expression(_get, "og_game_task")
            _eco = _schema_db.panel_option(etype, "game-task", "eco-info")
            if _eco == "pickup":       # crate / pickup-spawner: by its contents
                _eco = {"fuel-cell": "cell-info", "buzzer": "buzzer-info"}.get(str(_get("og_crate_pickup", "")))
            if _eco and "eco-info" not in _protected_keys:
                _t = _gt_task or "(game-task none)"
                if _eco == "cell-info":
                    lump["eco-info"] = ["cell-info", _t]
                elif _eco == "buzzer-info":
                    # fly 1-7 in the UI; the game counts them 0-6
                    _n = max(1, min(7, int(_get("og_buzzer_index", 1) or 1)))
                    lump["eco-info"] = ["buzzer-info", _t, _n - 1]
                log(f"  [game-task] {o.name}  {_t}  eco-info={lump['eco-info']}")

        # need_vol: convex `vol` from the VOL_ mesh linked to this actor.
        if _schema_db.needs_vol(etype) and "vol" not in _protected_keys:
            _volm = vol_by_target.get(o.name)
            if _volm:
                _planes, _cr = _vol_planes(_volm)
                if _planes:
                    lump["vol"] = ["vector-vol"] + _planes
                    log(f"  [need_vol] {o.name} <- {_volm.name} ({len(_planes)} planes)")

        # Main path under another lump name (some actors start at 'patha') and
        # optional keyframe ("vector4m@<kf>"; blank = default res time).
        _main_name = (getattr(o, "og_path_lump", "path") or "path").strip()
        if _main_name and _main_name != "path" and "path" in lump and _main_name not in _protected_keys:
            lump[_main_name] = lump.pop("path")
            if "path-k" in lump:
                lump[_main_name + "-k"] = lump.pop("path-k")
            log(f"  [path] {o.name} main path exported as '{_main_name}'")
        _main_kf = _pm.keyframe_suffix(getattr(o, "og_path_keyframe", ""))
        if _main_kf and _main_name in lump:
            lump[_main_name][0] += _main_kf
            if _main_name + "-k" in lump:
                lump[_main_name + "-k"][0] += _main_kf

        # ── Extra paths (og_extra_paths: pathb, patha..pathh, pathspawn ...) ──
        # Same sources + modes as the main path; each exports to <name> and,
        # for curve modes, <name>-k (path-h.gc reads knots as "<name>-k").
        # A .jsonc lump holds one entry per name, so two paths can't share a
        # name (even with different keyframes) — the first one wins.
        for _xp in getattr(o, "og_extra_paths", []):
            _xn = _xp.name.strip()
            if not _xn or _xn in _protected_keys:
                continue
            if _xn in lump:
                log(f"  [WARNING] {o.name}: path name '{_xn}' used twice — only the first is exported")
                continue
            _xkf = _pm.keyframe_suffix(getattr(_xp, "keyframe", ""))
            _xpts, _xk, _xmode, _xwarn = _pm.build(
                _pm.gather_from(_xp.sources), _xp.mode,
                linear_only=_schema_db.path_linear_only(etype))
            if _xwarn and _xpts:
                log(f"  [path] {o.name} '{_xn}': {_xwarn}")
            if _xk and getattr(_xp, "knots_manual", False):
                _xk, _kn = _pm.manual_knots(_xk, [k.value for k in _xp.knots])
                log(f"  [{_xn}-k] {o.name}: manual knots" + (f" — {_kn}" if _kn else ""))
            if _xpts:
                lump[_xn] = ["vector4m" + _xkf] + [_to_game_coords(mathutils.Vector(p)) for p in _xpts]
                lump.pop(_xn + "-k", None)
                if _xk:
                    lump[_xn + "-k"] = ["float" + _xkf] + _xk
                log(f"  [{_xn}] {o.name}  {_pm.MODE_LABELS.get(_xmode, _xmode)}  {len(_xpts)} points"
                    + (f"  {len(_xk)} knots" if _xk else ""))
            else:
                log(f"  [WARNING] {o.name} path '{_xn}' has no waypoints — not exported")

        # Variant art-group/code override (e.g. per-bridge art group). Falls back
        # to the actor's own art group/code when the variant doesn't specify one.
        _variant = _schema_db.actor_variant(etype, _schema_db.prop_getter(o))

        # A variant may also switch the exported etype (e.g. OgreStepVariants:
        # ogre-step -> ogre-step-a). The DB lookups (code, tpages, art groups)
        # keep using the DB actor's etype via _db_etype.
        if "options" in lump and "options" not in _protected_keys:
            lump["options"] = _schema_db.options_enum_lump(lump["options"])
        # Scale panel: the empty's Blender scale -> 'scale' lump.
        if "scale" not in _protected_keys:
            _sc = _schema_db.scale_lump(etype, o.matrix_world.to_scale())
            if _sc:
                lump["scale"] = _sc
                log(f"  [scale] {o.name}  {_sc[1:4]}")
        # Battlecontroller camera variants (export/battlecontroller.py)
        _out_etype = _variant.get("etype") or etype
        _out_ag = _variant.get("art_group")
        _bc_campos = None
        _extra = {}
        if etype == "battlecontroller":
            from . import battlecontroller as _bc
            for _lk, _lv in _bc.lumps(o).items():
                if _lk not in _protected_keys:
                    lump[_lk] = _lv
            for _w in _bc.percent_problems(o):
                log(f"  [WARNING] {o.name}: {_w}")
            _cag, _canim = _bc.camera(o)
            _gen = _bc.type_base(o, level_objs)
            if _gen:
                _out_etype = _gen                           # write_jsonc adds the level prefix
                _out_ag = f"{_cag}-ag.go"
            elif _bc.is_custom(o):
                log(f"  [WARNING] {o.name}: custom camera needs a camera art group and animation")
            if _variant.get("needs_citadel_camera"):
                _cam = _bc.citadel_camera_object(o)
                if _cam is None:
                    log(f"  [WARNING] {o.name}: the citadel camera variant needs a camera position "
                        f"('{_bc.CITADEL_CAM_NAME}') — the game crashes without it")
                else:
                    _ct = _cam.matrix_world.translation
                    _cx, _cy, _cz = round(_ct.x, 4), round(_ct.z, 4), round(-_ct.y, 4)
                    _bc_campos = {"trans": [_cx, _cy, _cz], "etype": "process-hidden",
                                  "game_task": "(game-task none)", "quat": [0.0, 0.0, 0.0, 1.0], "vis_id": 0,
                                  "bsphere": [_cx, _cy, _cz, 10.0], "lump": {"name": _bc.CITADEL_CAM_NAME},
                                  "_db_etype": "process-hidden"}
            # the lurkers it spawns need their code / art / textures in the level
            _lc, _lag, _ltp = _bc.lurker_assets(o)
            _out_ag = ([_out_ag] if _out_ag else []) + [g for g in _lag if g != _out_ag] or None
            _extra = {"extra_code": _lc, "extra_tpages": _ltp}
        out.append({
            "trans":     [gx, gy, gz],
            "etype":     _out_etype,
            "game_task": _gt_task or "(game-task none)",
            "quat":      [aqx, aqy, aqz, aqw],
            "vis_id":    0,
            "bsphere":   [gx, gy, gz, bsph_r],
            "lump":      lump,
            # Internal build bookkeeping below — stripped by write_jsonc.
            "_db_etype": etype,
            "art_group": _out_ag,   # None -> fall back to ETYPE_AG
            "code":      _variant.get("code"),   # variant's extra .o files (db.code_files)
            "extra_art_groups": _variant.get("extra_art_groups") or [],
            **_extra,
        })
        if _bc_campos is not None and not any(x["lump"]["name"] == _bc_campos["lump"]["name"] for x in _extra_actors):
            _extra_actors.append(_bc_campos)   # after all actors (AIDs follow the canonical order); one per name

    out += _extra_actors

    # ── Checkpoint trigger actors ─────────────────────────────────────────────
    # CHECKPOINT_ empties export as two things:
    #   1. A continue-point record in level-info.gc (via collect_spawns) — the
    #      spawn data the engine uses on respawn.
    #   2. A checkpoint-trigger actor in the JSONC (here) — an invisible entity
    #      that calls set-continue! when Jak enters it.
    # Both are needed: the actor does the triggering, the continue-point holds
    # the spawn position. The actor's continue-name lump must match the
    # continue-point name exactly: "{level_name}-{uid}".
    #
    # Volume mode: if a CPVOL_ mesh is linked (og_cp_link = checkpoint name),
    # the actor uses AABB bounds instead of sphere radius. The GOAL code reads
    # a 'has-volume' lump (uint32 1) to choose AABB vs sphere.
    level_name_for_cp = str(_get_level_prop(scene, "og_level_name", "")).strip().lower().replace(" ", "-")

    # Build cp_name → first linked vol_obj from og_vol_links collections.
    # Checkpoint links are soft-enforced 1:1 at link time (block duplicates),
    # so first() is the same as only() in well-formed scenes.
    vol_by_cp = {}
    for o in level_objs:
        if o.type == "MESH" and o.name.startswith("VOL_"):
            for entry in _vol_links(o):
                if _classify_target(entry.target_name) == "checkpoint":
                    vol_by_cp.setdefault(entry.target_name, o)

    for o in sorted(level_objs, key=lambda o: o.name):
        if not (o.name.startswith("CHECKPOINT_") and o.type == "EMPTY"):
            continue
        if o.name.endswith("_CAM"):
            continue
        uid = o.name[11:] or "cp0"
        l   = o.location
        gx  = round(l.x,  4)
        gy  = round(l.z,  4)
        gz  = round(-l.y, 4)
        r   = float(o.get("og_checkpoint_radius", 3.0))
        cp_name = f"{level_name_for_cp}-{uid}"
        lump = {
            "name":          f"checkpoint-trigger-{uid}",
            "continue-name": cp_name,
        }

        vol_obj = vol_by_cp.get(o.name)
        if vol_obj:
            # Volume mode — convex half-space planes from the linked mesh.
            xmin, xmax, ymin, ymax, zmin, zmax, cx, cy, cz, rad = _vol_aabb(vol_obj)
            planes, cull_r = _vol_planes(vol_obj)
        if vol_obj and planes:
            lump["has-volume"]  = ["uint32", 1]
            lump["cull-radius"] = ["meters", cull_r]
            lump["vol"]         = ["vector-vol"] + planes
            out.append({
                "trans":     [cx, cy, cz],
                "etype":     "checkpoint-trigger",
                "game_task": "(game-task none)",
                "quat":      [0, 0, 0, 1],
                "vis_id":    0,
                "bsphere":   [cx, cy, cz, rad],
                "lump":      lump,
            })
            log(f"  [checkpoint] {o.name} → '{cp_name}'  vol={vol_obj.name} ({len(planes)} planes)")
        else:
            # Sphere mode — use og_checkpoint_radius
            lump["radius"] = ["meters", r]
            out.append({
                "trans":     [gx, gy, gz],
                "etype":     "checkpoint-trigger",
                "game_task": "(game-task none)",
                "quat":      [0, 0, 0, 1],
                "vis_id":    0,
                "bsphere":   [gx, gy, gz, max(r, 3.0)],
                "lump":      lump,
            })
            log(f"  [checkpoint] {o.name} → '{cp_name}'  sphere r={r}m")

    # ── Vertex-export meshes ─────────────────────────────────────────────────
    # Plain MESH objects tagged with og_vertex_export_etype emit one actor per
    # vertex at world-space position. Modifiers are evaluated via the dependency
    # graph so the final post-modifier mesh is used — the original is untouched.
    # This lets you use Subdivision Surface / Array / Curve modifiers to control
    # point density non-destructively.
    #
    # depsgraph must be fetched on the main thread and passed in — calling
    # bpy.context from a background thread is unsafe and causes intermittent
    # Blender crashes (~25% of compile runs). Falls back to bpy.context only
    # when called directly from a panel (i.e. on the main thread).
    if depsgraph is None:
        depsgraph = bpy.context.evaluated_depsgraph_get()
    ve_counter = 0
    for o in _level_objects(scene):
        if o.type != "MESH":
            continue
        etype = str(o.get("og_vertex_export_etype", "")).strip()
        if not etype or etype not in VERTEX_EXPORT_TYPES:
            continue
        # Evaluate with modifiers applied — safe, does not modify the original
        o_eval = o.evaluated_get(depsgraph)
        mesh_eval = o_eval.to_mesh()
        mat  = o.matrix_world
        verts = mesh_eval.vertices
        for v in verts:
            wco  = mat @ v.co
            gx_v = round(wco.x, 4)
            gy_v = round(wco.z, 4)
            gz_v = round(-wco.y, 4)
            uid  = f"ve{ve_counter}"
            ve_counter += 1
            lump_v = {"name": f"{etype}-{uid}"}
            for _lk, _lv in emit_schema_lumps(
                    _schema_db.prop_getter(o),
                    _schema_db.inherited_fields(etype),
                    etype=etype,
                    choice_tables={"CratePickups": _schema_db.crate_pickups()}).items():
                lump_v[_lk] = _lv
            if "options" in lump_v:
                lump_v["options"] = _schema_db.options_enum_lump(lump_v["options"])
            out.append({
                "trans":     [gx_v, gy_v, gz_v],
                "etype":     etype,
                "game_task": "(game-task none)",
                "quat":      [0, 0, 0, 1],
                "vis_id":    0,
                "bsphere":   [gx_v, gy_v, gz_v, 3.0],
                "lump":      lump_v,
            })
        log(f"  [vertex-export] {o.name} → {len(verts)} × {etype} (modifiers applied)")
        o_eval.to_mesh_clear()  # free the temporary evaluated mesh

    return out
