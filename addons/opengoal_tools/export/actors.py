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
    needed_tpages, LUMP_REFERENCE, ACTOR_LINK_DEFS,
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
#
# Ping-pong toggle: when set, the forward path is followed by the reverse
# minus endpoints — a 4-point path [A,B,C,D] becomes [A,B,C,D,C,B], which
# the engine's modulo walk renders as A→B→C→D→C→B→A→B→... with no point
# duplicated at the turn.
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
    continue to export without migration. Applies the ping-pong toggle
    at the end if set.
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

    # Ping-pong: append the reverse path minus endpoints so the loop is
    # seamless (no duplicated point at A or at the turn).
    if getattr(actor_obj, "og_waypoint_pingpong", False) and len(points) > 2:
        points = points + list(reversed(points))[1:-1]

    return points


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
      - object_ref field + vol-mesh lump -> "vol": convex half-space planes from
        the linked mesh (via _vol_planes), plus an optional cull-radius. Add the
        field to any actor to give it a volume trigger.
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
                dl = dest_obj.location
                dx = round(dl.x * 4096, 2)
                dy = round(dl.z * 4096, 2)
                dz = round(-dl.y * 4096, 2)
                tkey = lp.get("pairs_with")
                t    = float(o.get(tkey, -1.0)) if tkey else -1.0
                fw   = t if t >= 0 else 0.5   # fly time in seconds (engine reads W as seconds)
                out[lp["key"]] = ["vector", [dx, dy, dz, fw]]
        # need_vol: convex half-space planes from a linked mesh
        elif f.get("type") == "object_ref" and isinstance(lp, dict) and lp.get("type") == "vol-mesh":
            vol_name = o.get(f["key"], "")
            vol_obj  = bpy.data.objects.get(vol_name) if vol_name else None
            if vol_obj and getattr(vol_obj, "type", None) == "MESH":
                planes, cull_r = _vol_planes(vol_obj)
                if planes:
                    out[lp["key"]] = ["vector-vol"] + planes
                    ckey = lp.get("cull_radius_key")
                    if ckey:
                        out[ckey] = ["meters", cull_r]
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
    level_objs = _level_objects(scene)
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
        # levels with no collection populated. Applies ping-pong reversal
        # if og_waypoint_pingpong is set.
        path_pts = _collect_waypoint_points(o)

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

        # ── Path lump (needs_path=True) ───────────────────────────────────────
        # process-drawable enemies that error without a path lump.
        # Also used by nav-enemies that patrol (snow-bunny, muse etc.).
        # Waypoints tagged _wp_00, _wp_01 ... drive this lump.
        # For needs_path enemies with no waypoints we log a warning — the level
        # will likely crash or error at runtime without at least 1 waypoint.
        # Platforms handle their own path lump below — skip them here to avoid double-emit
        if (einfo.get("needs_path") or (_schema_db.nav_unsafe(etype) and path_pts)) and einfo.get("cat") != "Platforms":
            if path_pts:
                lump["path"] = ["vector4m"] + path_pts
                log(f"  [path] {o.name}  {len(path_pts)} points")
            elif einfo.get("needs_path"):
                log(f"  [WARNING] {o.name} needs a path but has no waypoints — will crash/error at runtime!")

        # ── Second path lump (needs_pathb=True — swamp-bat only) ─────────────
        # swamp-bat reads 'pathb' for its second patrol route for bat slaves.
        # Tag secondary waypoints as ACTOR_swamp-bat_<uid>_wpb_00 etc.
        if einfo.get("needs_pathb"):
            wpb_prefix = o.name + "_wpb_"
            wpb_objects = sorted(
                [sc_obj for sc_obj in bpy.data.objects
                 if sc_obj.name.startswith(wpb_prefix) and sc_obj.type == "EMPTY"],
                key=lambda sc_obj: sc_obj.name
            )
            pathb_pts = []
            for wp in wpb_objects:
                wl = wp.location
                pathb_pts.append([round(wl.x, 4), round(wl.z, 4), round(-wl.y, 4), 1.0])
            if pathb_pts:
                lump["pathb"] = ["vector4m"] + pathb_pts
                log(f"  [pathb] {o.name}  {len(pathb_pts)} points")
            else:
                log(f"  [WARNING] {o.name} (swamp-bat) needs 'pathb' waypoints (_wpb_00, _wpb_01 ...) — will error at runtime!")

        # ── Platform: sync lump ───────────────────────────────────────────────
        # plat / plat-eco / side-to-side-plat use a 'sync' res lump to control
        # path timing.  Format: [period_s, phase, ease_out, ease_in]
        # Only emitted when the platform has waypoints — without waypoints the
        # engine ignores sync and the platform spawns idle.
        if einfo.get("needs_sync"):
            period   = float(o.get("og_sync_period",   4.0))
            phase    = float(o.get("og_sync_phase",    0.0))
            ease_out = float(o.get("og_sync_ease_out", 0.15))
            ease_in  = float(o.get("og_sync_ease_in",  0.15))
            if path_pts:
                lump["sync"] = ["float", period, phase, ease_out, ease_in]
                wrap = bool(o.get("og_sync_wrap", False))
                if wrap:
                    # fact-options wrap-phase: bit 3 of the options uint64
                    # GOAL: (defenum fact-options :bitfield #t  (wrap-phase 3))
                    # value = 1 << 3 = 8
                    # Read via: (res-lump-value ent 'options fact-options)
                    lump["options"] = ["uint32", 8]
                log(f"  [sync] {o.name}  period={period}s  phase={phase}  ease={ease_out}/{ease_in}  wrap={wrap}")
            else:
                log(f"  [sync-platform] {o.name}  no waypoints — will spawn idle (add ≥2 waypoints to make it move)")

        # ── Platform: path lump (plat-button) ────────────────────────────────
        # plat-button follows a path when pressed. Requires ≥2 waypoints.
        # Uses needs_path flag and is a Platform, distinguishing from enemy paths.
        if einfo.get("needs_path") and einfo.get("cat") == "Platforms":
            if path_pts:
                lump["path"] = ["vector4m"] + path_pts
                log(f"  [plat-path] {o.name}  {len(path_pts)} points")
            else:
                log(f"  [WARNING] {o.name} (plat-button) needs ≥2 waypoints or it will not move!")

        # ── Platform: sync path (plat / plat-eco) ────────────────────────────
        # When a sync platform has waypoints, also emit the path lump so the
        # engine can evaluate the curve.
        if einfo.get("needs_sync") and path_pts and "path" not in lump:
            lump["path"] = ["vector4m"] + path_pts
            log(f"  [sync-path] {o.name}  {len(path_pts)} points")

        # ── Smooth-curve knots (path-k) ──────────────────────────────────────
        # When Path Mode = SMOOTH and a 'path' lump was emitted, also emit the
        # matching 'path-k' knot vector. curve-control actors (plat, plat-eco,
        # plat-button, and curve-control enemies) then load as a cubic B-spline
        # and glide along the path. Without path-k they silently downgrade to a
        # linear path-control (path-h.gc: "downgrade us to a path-control, we
        # got cverts but no knots"). Emitting it for a plain path-control actor
        # is harmless — only curve-control reads path-k.
        # A cubic needs >= 4 control points; fewer falls back to linear.
        if getattr(o, "og_path_mode", "LINEAR") == "SMOOTH" and "path" in lump:
            n_cv = len(path_pts)
            if n_cv > 256:
                # Engine clamps cverts to MAX_CURVE_CONTROL_POINTS (256) in
                # res.gc but would NOT clamp the knots — emitting path-k here
                # would desync num-cverts vs num-knots. Skip path-k so the
                # actor stays a safe linear path-control instead.
                log(f"  [WARNING] {o.name} Path Mode=Smooth has {n_cv} points "
                    f"(>256 engine limit) — exporting linear (no path-k)")
            elif n_cv >= 4:
                lump["path-k"] = ["float"] + _make_path_knots(n_cv)
                log(f"  [path-k] {o.name}  smooth B-spline  {n_cv} cverts  {n_cv + 4} knots")
            else:
                log(f"  [WARNING] {o.name} Path Mode=Smooth needs ≥4 waypoints "
                    f"(has {n_cv}) — exporting linear (no path-k)")

        # ── Trait fields ──────────────────────────────────────────────────────
        # Behaviours shared across many actors by predicate: idle-distance +
        # vis-dist (enemies), num-lurkers (spawners), notice-dist
        # (needs_notice_dist). Driven by the DB's TraitFields section and applied
        # to every matching actor, regardless of schema_export.
        for _tk, _tv in emit_schema_lumps(
                lambda k, d=None: o.get(k, d),
                _schema_db.trait_fields(etype),
                etype=etype).items():
            lump[_tk] = _tv

        # Bsphere radius controls vis-culling distance.  nav-enemy run-logic?
        # only processes AI/collision events when draw-status was-drawn is set,
        # which requires the bsphere to pass the renderer's cull test.
        # Custom levels lack a proper BSP vis system.
        bsph_r = 10.0  # Rockpool uses 10m for all entities; 120m caused merc renderer crashes

        # water-vol: bsphere must enclose the full activation box so the process
        # isn't culled before it can run point-in-vol checks each frame.
        # Use o.scale — empties have no dimensions, scale is the half-extent.
        if etype == "water-vol":
            hx     = abs(o.scale.x)
            hz     = abs(o.scale.y)
            bsph_r = max((hx ** 2 + hz ** 2) ** 0.5, 10.0)  # minimum 10m

        # ── Oracle / pontoon: alt-task ────────────────────────────────────────
        if etype == "pontoon":  # oracle is schema-driven; pontoon not yet migrated
            task = str(o.get("og_alt_task", "none"))
            if task and task != "none":
                lump["alt-task"] = ["enum-uint32", f"(game-task {task})"]
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

        # ── Schema-driven lumps (migrated actors) ────────────────────────────
        # If this actor is flagged `schema_export` in the DB, its declared
        # fields[] drive its value lumps directly from the schema — no per-actor
        # code path and no gates (e.g. `sync` exports regardless of waypoints).
        # The schema is AUTHORITATIVE over the legacy hardcoded branches (it
        # overrides them), but yields to computed entity links and to explicit
        # user custom lump rows (both in _protected_keys). Actors WITHOUT the
        # flag are untouched. Schema output was validated equal to the hardcoded
        # output for every migrated actor, so this only changes behaviour where
        # the legacy path was buggy (e.g. sync dropped for pathless platforms).
        _arec = _schema_db.find_actor(etype)
        if _schema_db.schema_export_enabled(etype):
            for _lk, _lv in emit_schema_lumps(
                    lambda k, d=None: o.get(k, d),
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

        out.append({
            "trans":     [gx, gy, gz],
            "etype":     etype,
            "game_task": "(game-task none)",
            "quat":      [aqx, aqy, aqz, aqw],
            "vis_id":    0,
            "bsphere":   [gx, gy, gz, bsph_r],
            "lump":      lump,
        })

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
                    lambda k, d=None: o.get(k, d),
                    _schema_db.inherited_fields(etype),
                    etype=etype,
                    choice_tables={"CratePickups": _schema_db.crate_pickups()}).items():
                lump_v[_lk] = _lv
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

    # ── WATER_ mesh volumes ───────────────────────────────────────────────────
    # WATER_<name> meshes define swimmable water zones.  The mesh shape (any
    # scaled / rotated cube) drives the vol-control activation AABB.
    # Custom props on the mesh:
    #   og_water_surface  — world Y of the water surface (auto-set by sync op)
    #   og_water_wade     — depth in meters below surface (default 0.5)
    #   og_water_swim     — depth in meters below surface (default 1.0)
    #   og_water_bottom   — world Y of the kill floor
    #   og_water_attack   — damage type symbol string (default: 'drown)
    # All heights are absolute world Y (meters).  The vol planes are built from
    # the mesh AABB so rotation and non-uniform scale are fully supported.
    water_meshes = [o for o in level_objs
                    if o.type == "MESH" and o.name.startswith("WATER_")]
    for idx, o in enumerate(sorted(water_meshes, key=lambda x: x.name)):
        xmin, xmax, ymin, ymax, zmin, zmax, cx, cy, cz, _ = _vol_aabb(o)

        # Heights.
        # og_water_surface = absolute world Y of the water surface (defaults to mesh top)
        # og_water_wade    = depth in meters below surface where wading starts (default 0.5)
        # og_water_swim    = depth in meters below surface where swimming starts (default 1.0)
        # og_water_bottom  = absolute world Y of the kill floor (defaults to mesh bottom)
        #
        # Engine logic (water.gc):
        #   wade triggers when: jak_foot_y <= (surface - wade_depth)
        #   swim triggers when: jak_foot_y <= (surface - swim_depth)
        # So wade/swim are DEPTHS subtracted from surface — small positive values.
        surface    = float(o.get("og_water_surface", ymax))
        wade_depth = float(o.get("og_water_wade",    0.5))
        swim_depth = float(o.get("og_water_swim",    1.0))
        bottom     = float(o.get("og_water_bottom",  ymin))
        attack     = str(o.get("og_water_attack",    "drown"))

        # bsphere: XZ half-diagonal + 5m padding so process is never culled
        bsph_r = round((((xmax-xmin)/2)**2 + ((ymax-ymin)/2)**2 + ((zmax-zmin)/2)**2)**0.5 + 5.0, 2)

        lump = {
            "name":         f"water-vol-{idx}",
            # 5-value form with explicit flags — REQUIRED because logior! wt23 always runs
            # before the (zero? flags) auto-set check, so wt02/wt03 must be set explicitly.
            "water-height": ["water-height", surface, wade_depth, swim_depth, "(water-flags wt02 wt03 wt05 wt22)"],
            "attack-event": f"'{attack}",
            "vol": [
                "vector-vol",
                # point-in-vol? returns #f when dot(P,N) - w > 0
                # So normals must point OUTWARD. Inside = negative side of each plane.
                [ 0,  1,  0,  surface ],   # top:   outward +Y, inside when P.y <= surface
                [ 0, -1,  0, -bottom  ],   # floor: outward -Y, inside when P.y >= bottom
                [ 1,  0,  0,  xmax    ],   # +X:    outward +X, inside when P.x <= xmax
                [-1,  0,  0, -xmin    ],   # -X:    outward -X, inside when P.x >= xmin
                [ 0,  0,  1,  zmax    ],   # +Z:    outward +Z, inside when P.z <= zmax
                [ 0,  0, -1, -zmin    ],   # -Z:    outward -Z, inside when P.z >= zmin
            ],
        }
        out.append({
            "trans":     [cx, cy, cz],
            "etype":     "water-vol",
            "game_task": "(game-task none)",
            "quat":      [0, 0, 0, 1],
            "vis_id":    0,
            "bsphere":   [cx, cy, cz, bsph_r],
            "lump":      lump,
        })
        log(f"  [water] {o.name}  surface={surface:.2f}m  wade={wade_depth}m  swim={swim_depth}m  bottom={bottom:.2f}m  box={xmax-xmin:.1f}x{zmax-zmin:.1f}m")
    return out
