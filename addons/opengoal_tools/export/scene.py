# ───────────────────────────────────────────────────────────────────────
# export/scene.py — OpenGOAL Level Tools
#
# Collectors for non-actor scene objects: cameras, ambient sound emitters, spawn/checkpoint entities, aggro triggers, custom triggers.
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
    _classify_target,
)
from .volumes import (
    _vol_aabb,
    _vol_planes,
    _vol_links,
)


# Cross-module imports (siblings in the export package)


def _camera_aabb_to_planes(b_min, b_max):
    """Convert an AABB in game-space meters to 6 half-space plane equations.

    Each plane is [nx, ny, nz, d_meters] where a point P (meters) is INSIDE
    the volume when dot(P, normal) <= d for ALL planes.

    The C++ loader (vector_vol_from_json) multiplies the w component by 4096,
    so we provide values in meters here.
    """
    mn = tuple(min(b_min[i], b_max[i]) for i in range(3))
    mx = tuple(max(b_min[i], b_max[i]) for i in range(3))
    return [
        [ 1.0,  0.0,  0.0,  mx[0]],  # +X wall
        [-1.0,  0.0,  0.0, -mn[0]],  # -X wall
        [ 0.0,  1.0,  0.0,  mx[1]],  # +Y ceiling
        [ 0.0, -1.0,  0.0, -mn[1]],  # -Y floor
        [ 0.0,  0.0,  1.0,  mx[2]],  # +Z back
        [ 0.0,  0.0, -1.0, -mn[2]],  # -Z front
    ]

def collect_aggro_triggers(scene):
    """Build aggro-trigger actor list from VOL_ meshes whose og_vol_links
    contain at least one nav-enemy ACTOR_ target.

    One actor is emitted per (volume, enemy_link) pair. The actor's lump holds
    the target enemy's name (string), an event-id integer (0=cue-chase,
    1=cue-patrol, 2=go-wait-for-cue), and 6 AABB bound-* floats.

    The target-name lump must match the *emitted name lump* on the target
    actor (which is f"{etype}-{uid}", e.g. "babak-1"), NOT the Blender object
    name (e.g. "ACTOR_babak_1"). The engine's entity-by-name walks all loaded
    actors and matches the 'name lump string verbatim — this lookup is what
    process-by-ename uses at runtime.

    At runtime the aggro-trigger polls AABB; on rising edge it calls
    (process-by-ename target-name) and sends the appropriate event symbol.
    Implemented entirely with res-lumps — no engine patches required.

    Engine refs:
      nav-enemy.gc:142 — 'cue-chase, 'cue-patrol, 'go-wait-for-cue handlers
      entity.gc:92    — entity-by-name lookup
      entity.gc:167   — process-by-ename helper
    """
    out = []
    counter = 0
    for vol in _level_objects(scene):
        if vol.type != "MESH" or not vol.name.startswith("VOL_"):
            continue
        for entry in _vol_links(vol):
            if _classify_target(entry.target_name) != "enemy":
                continue
            target_obj = scene.objects.get(entry.target_name)
            if not target_obj:
                log(f"  [WARNING] aggro-trigger {vol.name}: target '{entry.target_name}' not in scene — skipped")
                continue
            # Convert Blender object name to the actor's emitted 'name lump.
            # ACTOR_<etype>_<uid> -> <etype>-<uid>  (matches collect_actors line ~3170)
            parts = entry.target_name.split("_", 2)
            if len(parts) < 3:
                log(f"  [WARNING] aggro-trigger {vol.name}: malformed target name '{entry.target_name}' — skipped")
                continue
            target_lump_name = f"{parts[1]}-{parts[2]}"
            xmin, xmax, ymin, ymax, zmin, zmax, cx, cy, cz, rad = _vol_aabb(vol)
            planes, cull_r = _vol_planes(vol)
            if not planes:
                log(f"  [WARNING] aggro-trigger {vol.name}: no usable faces "
                    f"(needs a closed convex mesh) — skipped")
                continue
            event_id = _aggro_event_id(entry.behaviour)
            uid = counter
            counter += 1
            out.append({
                "trans":     [cx, cy, cz],
                "etype":     "aggro-trigger",
                "game_task": "(game-task none)",
                "quat":      [0, 0, 0, 1],
                "vis_id":    0,
                "bsphere":   [cx, cy, cz, rad],
                "lump": {
                    "name":        f"aggrotrig-{uid}",
                    "target-name": target_lump_name,
                    "event-id":    ["uint32", event_id],
                    "cull-radius": ["meters", cull_r],
                    "vol":         ["vector-vol"] + planes,
                },
            })
            log(f"  [aggro-trigger] {vol.name} → {entry.target_name} (lump: {target_lump_name}, {entry.behaviour})")
    return out

def collect_custom_triggers(scene):
    """Build vol-trigger actor list from VOL_ meshes whose og_vol_links target
    custom (non-built-in) ACTOR_ empties.

    One vol-trigger actor is emitted per (volume, custom_link) pair.
    On enter: sends 'trigger to the target process.
    On exit:  sends 'untrigger to the target process.

    The target-name lump uses the entity lump name convention:
      ACTOR_<etype>_<uid>  ->  <etype>-<uid>
    This matches what process-by-ename looks up at runtime.
    """
    out = []
    counter = 0
    for vol in _level_objects(scene):
        if vol.type != "MESH" or not vol.name.startswith("VOL_"):
            continue
        for entry in _vol_links(vol):
            if _classify_target(entry.target_name) != "custom":
                continue
            target_obj = scene.objects.get(entry.target_name)
            if not target_obj:
                log(f"  [WARNING] vol-trigger {vol.name}: target '{entry.target_name}' not in scene — skipped")
                continue
            parts = entry.target_name.split("_", 2)
            if len(parts) < 3:
                log(f"  [WARNING] vol-trigger {vol.name}: malformed target name '{entry.target_name}' — skipped")
                continue
            target_lump_name = f"{parts[1]}-{parts[2]}"
            xmin, xmax, ymin, ymax, zmin, zmax, cx, cy, cz, rad = _vol_aabb(vol)
            planes, cull_r = _vol_planes(vol)
            if not planes:
                log(f"  [WARNING] vol-trigger {vol.name}: no usable faces "
                    f"(needs a closed convex mesh) — skipped")
                continue
            uid = counter
            counter += 1
            out.append({
                "trans":     [cx, cy, cz],
                "etype":     "vol-trigger",
                "game_task": "(game-task none)",
                "quat":      [0, 0, 0, 1],
                "vis_id":    0,
                "bsphere":   [cx, cy, cz, rad],
                "lump": {
                    "name":        f"voltrig-{uid}",
                    "target-name": target_lump_name,
                    "cull-radius": ["meters", cull_r],
                    "vol":         ["vector-vol"] + planes,
                },
            })
            log(f"  [vol-trigger] {vol.name} → {entry.target_name} (lump: {target_lump_name})")
    return out

def _camera_game_quat(cam_obj, scene):
    """Game-space camera quaternion for a CAMERA_ object.

    Returns (qx, qy, qz, qw, look_obj, look_at_name).

    1. Look direction in world space: towards the look-at target if one is
       set (target_world - camera_world), else the camera's own -local_Z.
    2. Remap to game space: bl(x,y,z) -> game(x,z,-y)
    3. Build the rotation forward-down->inv-matrix style (world-down =
       (0,-1,0) roll reference).
    4. Conjugate (negate xyz) — the game's quaternion->matrix reads the
       inverse convention from what standard math produces.

    Steps 2-4 confirmed empirically via nREPL inv-camera-rot readback. The
    look-at branch bakes the aim into the quat because the engine's
    'interesting' lump is only a POI bias for follow cams — for fixed cameras
    it is effectively a no-op. Built-in camera entities store this quat at
    the same offset as an actor's, read through cam-slave-get-rot, so the same
    convention applies to both camera systems.
    """
    loc = cam_obj.matrix_world.translation
    look_at_name = cam_obj.get("og_cam_look_at", "").strip()
    look_obj = scene.objects.get(look_at_name) if look_at_name else None
    if look_obj:
        tgt = look_obj.matrix_world.translation
        bl_look = mathutils.Vector((tgt.x - loc.x, tgt.y - loc.y, tgt.z - loc.z))
        if bl_look.length < 1e-6:
            # Degenerate: target at the camera position -> native rotation.
            bl_look = -cam_obj.matrix_world.to_3x3().col[2]
    else:
        bl_look = -cam_obj.matrix_world.to_3x3().col[2]
    gl = mathutils.Vector((bl_look.x, bl_look.z, -bl_look.y))
    gl.normalize()
    game_down = mathutils.Vector((0.0, -1.0, 0.0))
    right = gl.cross(game_down)
    if right.length < 1e-6:
        right = mathutils.Vector((1.0, 0.0, 0.0))  # degenerate: straight up/down
    right.normalize()
    up = gl.cross(right)
    up.normalize()
    gq = mathutils.Matrix([right, up, gl]).to_quaternion()
    return (round(-gq.x, 6), round(-gq.y, 6), round(-gq.z, 6), round(gq.w, 6),
            look_obj, look_at_name)


# ── Camera system: built-in entities vs legacy marker/trigger actors ─────────
# Built-in camera entities need OpenGOAL v0.3.4+ (jak-project PR #4310), which
# changed entity-camera's `connect` field to an inline `quat`. That change in
# the install's goal_src is how we detect support.
_CAM_SUPPORT_CACHE: dict = {}


def builtin_cameras_supported() -> bool:
    from .paths import _goal_src
    p = _goal_src() / "engine" / "entity" / "entity-h.gc"
    try:
        key = (str(p), p.stat().st_mtime)
    except OSError:
        return False
    if key not in _CAM_SUPPORT_CACHE:
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
            _CAM_SUPPORT_CACHE.clear()
            _CAM_SUPPORT_CACHE[key] = bool(re.search(
                r"\(deftype entity-camera \(entity\)\s*\(\(quat\s+quaternion", txt))
        except OSError:
            return False
    return _CAM_SUPPORT_CACHE[key]


def camera_system(scene) -> str:
    """"builtin" or "legacy" for this scene (Developer Tools > Camera system)."""
    try:
        choice = scene.og_props.og_camera_system
    except Exception:
        choice = "AUTO"
    if choice == "BUILTIN":
        return "builtin"
    if choice == "LEGACY":
        return "legacy"
    return "builtin" if builtin_cameras_supported() else "legacy"


def _cam_vols_by_role(level_objs):
    """cam_name -> {"vol": [vol_obj...], "pvol": [...], "cutoutvol": [...]}"""
    out = {}
    for o in level_objs:
        if o.type == "MESH" and o.name.startswith("VOL_"):
            for entry in _vol_links(o):
                if _classify_target(entry.target_name) == "camera":
                    role = getattr(entry, "cam_role", "vol") or "vol"
                    out.setdefault(entry.target_name, {}).setdefault(role, []).append(o)
    return out


def collect_builtin_cameras(scene):
    """Built-in camera entities for the level .jsonc "cameras" array.

    One entry per CAMERA_ object, driven by the DB "Cameras" section (fields +
    flags). Volumes come from linked VOL_ meshes by role, at keyframe 0 as the
    engine reads them ('exact 0.0 in in-cam-entity-volume?). A JSON lump key
    can only appear once, so a camera with several "vol" volumes is exported
    as one entry per volume with identical settings ("<name>", "<name>-1", ...).
    pvol / cutoutvol use the first linked volume of that role.
    """
    from .. import db as _db
    from .schema_emit import emit_schema_lumps
    from .actors import _to_game_coords
    from . import path_modes as _pm
    cam_db = _db.cameras()
    fields = cam_db.get("fields", [])
    flags = cam_db.get("flags", [])

    level_objs = _level_objects(scene)
    cam_objects = sorted([o for o in level_objs
                          if o.name.startswith("CAMERA_") and o.type == "CAMERA"],
                         key=lambda o: o.name)
    vols = _cam_vols_by_role(level_objs)
    out = []
    for cam_obj in cam_objects:
        name = cam_obj.name
        mode = cam_obj.get("og_cam_mode", "fixed")
        loc = cam_obj.matrix_world.translation
        trans = [round(loc.x, 4), round(loc.z, 4), round(-loc.y, 4)]
        qx, qy, qz, qw, look_obj, look_at_name = _camera_game_quat(cam_obj, scene)

        lump = {"name": name}
        # DB fields for this mode (visible_if.og_cam_mode lists the modes).
        def _applies(f):
            modes = (f.get("visible_if") or {}).get("og_cam_mode")
            return modes is None or mode in (modes if isinstance(modes, list) else [modes])
        lump.update(emit_schema_lumps(lambda k, d=None: cam_obj.get(k, d),
                                      [f for f in fields if _applies(f)]))

        on = [f["id"] for f in flags if cam_obj.get("og_cam_flag_" + f["id"], False)]
        if on:
            lump["flags"] = ["enum-uint32", "(cam-slave-options " + " ".join(on) + ")"]

        def _g(o):
            p = o.matrix_world.translation
            return [round(p.x, 4), round(p.z, 4), round(-p.y, 4)]

        if look_obj:
            lump["interesting"] = ["vector3m", _g(look_obj)]
        elif look_at_name:
            log(f"  [camera] WARNING: look-at object '{look_at_name}' not found in scene")

        if mode == "standoff":
            a = scene.objects.get(name + "_ALIGN")
            if a:
                lump["align"] = ["vector3m", _g(a)]
            else:
                log(f"  [camera] WARNING: {name} side-scroll but no {name}_ALIGN — exports as fixed")
        elif mode == "orbit":
            pv = scene.objects.get(name + "_PIVOT")
            if pv:
                lump["pivot"] = ["vector3m", _g(pv)]
            else:
                log(f"  [camera] WARNING: {name} orbit but no {name}_PIVOT — exports as fixed")
        elif mode == "spline":
            # Same path modes as actors. The camera always reads a curve
            # (campath + campath-k), so a linear result becomes straight
            # Bezier segments — exactly the same lines.
            raw, knots, pmode, pwarn = _pm.build(
                _pm.gather_sources(cam_obj), getattr(cam_obj, "og_path_mode", "AUTO"))
            if pwarn:
                log(f"  [camera] {name}: {pwarn}")
            if knots is None and len(raw) >= 2:
                raw, knots = _pm.straight_bezier(raw)
            if knots and len(raw) <= _pm.MAX_CVERTS:
                lump["campath"] = ["vector4m"] + [_to_game_coords(mathutils.Vector(p)) for p in raw]
                lump["campath-k"] = ["float"] + knots
            else:
                log(f"  [camera] WARNING: {name} path mode needs 2+ path points "
                    f"(has {len(raw)}) — exports as fixed")

        def _planes(o):
            planes, _r = _vol_planes(o)
            if not planes:
                log(f"  [WARNING] camera {name}: volume {o.name} has no usable faces "
                    f"(needs a closed convex mesh) — skipped")
            return planes

        roles = vols.get(name, {})
        for role in ("pvol", "cutoutvol"):
            for o in roles.get(role, [])[:1]:
                pl = _planes(o)
                if pl:
                    lump[role] = ["vector-vol@0"] + pl
            if len(roles.get(role, [])) > 1:
                log(f"  [camera] WARNING: {name} has {len(roles[role])} '{role}' volumes — "
                    f"only {roles[role][0].name} is used")
        vol_planes = [p for p in (_planes(o) for o in roles.get("vol", [])) if p]
        if not vol_planes:
            log(f"  [camera] WARNING: {name} has no trigger volume — it will never activate")
            vol_planes = [None]
        for i, pl in enumerate(vol_planes):
            l = dict(lump)
            if i:
                l["name"] = f"{name}-{i}"
            if pl:
                l["vol"] = ["vector-vol@0"] + pl
            out.append({"trans": trans, "quat": [qx, qy, qz, qw], "lump": l})
        log(f"  [camera] {name} ({mode}) built-in, {len(vol_planes)} entr"
            f"{'y' if len(vol_planes) == 1 else 'ies'}")
    return out


def collect_cameras(scene):
    """Build camera actor list from CAMERA_ camera objects.

    Returns (camera_actors, trigger_actors) where both are JSONC actor dicts.
    camera_actors  -- camera-marker entities (hold position/rotation)
    trigger_actors -- camera-trigger entities (AABB polling, birth on level load)

    A volume can hold multiple links. We iterate every VOL_ mesh's links and
    emit one camera-trigger actor per (volume, camera_link) pair.
    """
    if camera_system(scene) == "builtin":
        return [], []          # exported as level "cameras" (collect_builtin_cameras)
    level_objs = _level_objects(scene)

    cam_objects = sorted(
        [o for o in level_objs
         if o.name.startswith("CAMERA_") and o.type == "CAMERA"],
        key=lambda o: o.name,
    )

    # Build cam_name -> [vol_obj, ...] from VOL_ meshes' og_vol_links collections.
    # One camera can be linked from multiple volumes (Scenario A from design discussion).
    vols_by_cam = {}
    for o in level_objs:
        if o.type == "MESH" and o.name.startswith("VOL_"):
            for entry in _vol_links(o):
                if _classify_target(entry.target_name) == "camera":
                    # Preferred / cut-out roles are built-in-camera features; the
                    # legacy trigger can only switch a camera ON inside a volume.
                    role = getattr(entry, "cam_role", "vol") or "vol"
                    if role != "vol":
                        log(f"  [camera] WARNING: {o.name} is a '{role}' volume for "
                            f"{entry.target_name} — legacy cameras ignore it (needs built-in cameras)")
                        continue
                    vols_by_cam.setdefault(entry.target_name, []).append(o)

    camera_actors  = []
    trigger_actors = []

    for cam_obj in cam_objects:
        cam_name = cam_obj.name

        loc = cam_obj.matrix_world.translation
        gx = round(loc.x, 4)
        gy = round(loc.z, 4)
        gz = round(-loc.y, 4)

        qx, qy, qz, qw, look_obj, look_at_name = _camera_game_quat(cam_obj, scene)

        cam_mode = cam_obj.get("og_cam_mode",  "fixed")
        interp_t = float(cam_obj.get("og_cam_interp", 1.0))
        fov_deg  = float(cam_obj.get("og_cam_fov",    0.0))

        lump = {"name": cam_name}
        lump["interpTime"] = ["float", round(interp_t, 3)]
        if fov_deg > 0.0:
            lump["fov"] = ["degrees", round(fov_deg, 2)]

        # Look-at target: still emit 'interesting' as a secondary hint.  For
        # fixed-cams the quat now encodes the aim (step 1 above), but if the
        # engine ever routes this camera through a state that uses POI (e.g.
        # a follow-cam base mode), the bias still points the right way.
        if look_obj:
            lt = look_obj.matrix_world.translation
            lump["interesting"] = ["vector3m", [round(lt.x,4), round(lt.z,4), round(-lt.y,4)]]
            log(f"  [camera] {cam_name} look-at -> {look_at_name} game({lump['interesting'][1]})")
        elif look_at_name:
            log(f"  [camera] WARNING: look-at object '{look_at_name}' not found in scene")
        if cam_mode == "standoff":
            # Side-scroller / standoff mode.  The engine's cam-standoff-read-entity
            # reads BOTH 'trans and 'align from the camera entity, then computes:
            #     offset   = entity.trans - entity.align
            #     cam_pos  = player_pos  + offset
            # So:
            #     'trans : camera's world position  (where the view sits)
            #     'align : player-anchor position   (where Jak is expected to be)
            # The offset is implicit — the vector from ALIGN to the camera.
            # (Previously this addon had these two swapped, which made the
            # camera spawn at the ALIGN position = inside the player.)
            align_name = cam_name + "_ALIGN"
            align_obj  = scene.objects.get(align_name)
            if align_obj:
                al = align_obj.matrix_world.translation
                lump["trans"] = ["vector3m", [gx, gy, gz]]
                lump["align"] = ["vector3m", [round(al.x,4), round(al.z,4), round(-al.y,4)]]
                log(f"  [camera] {cam_name} standoff -- align={align_name}")
            else:
                log(f"  [camera] WARNING: {cam_name} standoff but no {align_name}")
        elif cam_mode == "orbit":
            pivot_name = cam_name + "_PIVOT"
            pivot_obj  = scene.objects.get(pivot_name)
            if pivot_obj:
                pl = pivot_obj.matrix_world.translation
                lump["trans"] = ["vector3m", [gx, gy, gz]]
                lump["pivot"] = ["vector3m", [round(pl.x,4), round(pl.z,4), round(-pl.y,4)]]
                log(f"  [camera] {cam_name} orbit -- pivot={pivot_name}")
            else:
                log(f"  [camera] WARNING: {cam_name} orbit but no {pivot_name}")
        elif cam_mode == "follow":
            # Gameplay follow camera (cam-string, a.k.a. *camera-base-mode*).
            # cam-state-from-entity routes a camera to *camera-base-mode* when
            # stringMaxLength > 0, and master-base-region then reads these
            # five lumps.  The camera's own trans/rot are not consumed by
            # cam-string — position is derived from Jak every frame — but
            # we still emit trans because the entity record requires it and
            # it's used by region-activation logic and the debug overlay.
            min_len    = float(cam_obj.get("og_cam_string_min_length",   5.0))
            max_len    = float(cam_obj.get("og_cam_string_max_length",  12.5))
            min_height = float(cam_obj.get("og_cam_string_min_height",   1.0))
            max_height = float(cam_obj.get("og_cam_string_max_height",   3.0))
            cliff      = float(cam_obj.get("og_cam_string_cliff_height", 40.0))
            lump["stringMinLength"] = ["meters", round(min_len, 4)]
            lump["stringMaxLength"] = ["meters", round(max_len, 4)]
            lump["stringMinHeight"] = ["meters", round(min_height, 4)]
            lump["stringMaxHeight"] = ["meters", round(max_height, 4)]
            lump["stringCliffHeight"] = ["meters", round(cliff, 4)]
            log(f"  [camera] {cam_name} follow -- len=[{min_len},{max_len}] h=[{min_height},{max_height}] cliff={cliff}")

        camera_actors.append({
            "trans":     [gx, gy, gz],
            "etype":     "camera-marker",
            "game_task": 0,
            "quat":      [qx, qy, qz, qw],
            "vis_id":    0,
            "bsphere":   [gx, gy, gz, 30.0],
            "lump":      lump,
        })

        vol_list = vols_by_cam.get(cam_name, [])
        if vol_list:
            for vol_obj in vol_list:
                xmin, xmax, ymin, ymax, zmin, zmax, cx, cy, cz, rad = _vol_aabb(vol_obj)
                planes, cull_r = _vol_planes(vol_obj)
                if not planes:
                    log(f"  [WARNING] camera-trigger {cam_name}: volume {vol_obj.name} "
                        f"has no usable faces (needs a closed convex mesh) — skipped")
                    continue
                trigger_actors.append({
                    "trans":     [cx, cy, cz],
                    "etype":     "camera-trigger",
                    "game_task": 0,
                    "quat":      [0, 0, 0, 1],
                    "vis_id":    0,
                    "bsphere":   [cx, cy, cz, rad],
                    "lump": {
                        "name":       f"camtrig-{cam_name.lower()}-{vol_obj.get('og_vol_id', 0)}",
                        "cam-name":   cam_name,
                        "cull-radius": ["meters", cull_r],
                        "vol":        ["vector-vol"] + planes,
                    },
                })
                log(f"  [camera] {cam_name} + trigger {vol_obj.name}")
        else:
            log(f"  [camera] {cam_name} -- no trigger volume")

    return camera_actors, trigger_actors

def _cp_level_value(o, enum_attr, custom_attr):
    """Resolve a checkpoint level slot to its stored value.

    Returns "self" / "none" / a project level name, OR — when the dropdown is
    set to "custom" — the user-typed level symbol (lowercased, dashed). An empty
    custom string falls back to "none".
    """
    val = str(getattr(o, enum_attr, "") or "")
    if val == "custom":
        s = str(getattr(o, custom_attr, "") or "").strip().lower().replace(" ", "-")
        return s or "none"
    return val


def collect_spawns(scene):
    """Collect SPAWN_ empties into continue-point data dicts.

    Each dict contains:
      name       — uid string (e.g. "start", "spawn1", or custom SPAWN_<name>)
      x/y/z      — game-space position (metres, Blender→game remap applied)
      qx/qy/qz/qw — game-space facing quaternion from the empty's rotation
      cam_x/cam_y/cam_z — camera-trans position (from linked SPAWN_<uid>_CAM empty,
                          or defaults to spawn pos + 4m up)
      cam_rot    — camera 3x3 row-major matrix as flat list of 9 floats
                   (from linked SPAWN_<uid>_CAM empty, or identity)
      is_checkpoint — True if this is a CHECKPOINT_ empty (auto-assigned mid-level)
    """
    # R_remap: Blender(x,y,z) → game(x,z,-y), stored as a 3×3 row matrix.
    # Used to conjugate Blender rotation matrices into game space:
    #   game_rot = R_remap @ bl_rot @ R_remap^T
    # Verified: identity Blender empty → identity game quat (x:0 y:0 z:0 w:1).
    R_remap = mathutils.Matrix(((1,0,0),(0,0,1),(0,-1,0)))

    out = []
    for o in sorted(_level_objects(scene), key=lambda o: o.name):
        # BUG FIX: _CAM anchor empties share the SPAWN_/CHECKPOINT_ prefix.
        # Skip them here — they are not spawns/checkpoints themselves.
        if o.name.endswith("_CAM"):
            continue

        is_spawn      = o.name.startswith("SPAWN_")      and o.type == "EMPTY"
        is_checkpoint = o.name.startswith("CHECKPOINT_") and o.type == "EMPTY"
        if not (is_spawn or is_checkpoint):
            continue

        if is_spawn:
            uid = o.name[6:] or "start"
        else:
            uid = o.name[11:] or "cp0"

        l = o.location
        gx = round(l.x,  4)
        gy = round(l.z,  4)
        gz = round(-l.y, 4)

        # ── Facing quaternion ────────────────────────────────────────────────
        # Both SPAWN_ (ARROWS) and CHECKPOINT_ (SINGLE_ARROW) empties encode
        # Jak's horizontal facing direction via rotation around Blender Z.
        # The arrow on CHECKPOINT_ points straight up — it marks where Jak
        # stands, not which way to aim. Facing = Z rotation of the empty.
        #
        # Remap: game_rot = R_remap @ bl_rot @ R_remap^T
        # Maps Blender Z-rotation → game Y-rotation (yaw). No conjugate —
        # the similarity transform already produces the correct orientation.
        # (The previous conjugate was erroneously borrowed from the camera
        # system; it inverted facing for all non-0°/180° angles.)
        m3      = o.matrix_world.to_3x3()
        # Offset 180° on Z so the cone tip direction matches spawn facing.
        m3      = mathutils.Matrix.Rotation(math.pi, 3, 'Z') @ m3
        game_m3 = R_remap @ m3 @ R_remap.transposed()
        gq      = game_m3.to_quaternion()
        qx = round(gq.x, 6)
        qy = round(gq.y, 6)
        qz = round(gq.z, 6)
        qw = round(gq.w, 6)

        # ── Camera empty (optional) ──────────────────────────────────────────
        # User can place a SPAWN_<uid>_CAM or CHECKPOINT_<uid>_CAM empty to
        # set the camera position/orientation at respawn.
        # If absent, we default to spawn pos + 4m up, identity rotation.
        cam_suffix = "_CAM"
        cam_name   = o.name + cam_suffix
        cam_obj    = scene.objects.get(cam_name)

        if cam_obj and cam_obj.type == "EMPTY":
            cl = cam_obj.location
            cam_x = round(cl.x,  4)
            cam_y = round(cl.z,  4)
            cam_z = round(-cl.y, 4)
            # Build camera rotation matrix (same conjugate formula as camera system)
            cm3      = cam_obj.matrix_world.to_3x3()
            bl_look  = -cm3.col[2]                            # camera looks along -local_Z
            gl = mathutils.Vector((bl_look.x, bl_look.z, -bl_look.y))
            gl.normalize()
            game_down = mathutils.Vector((0.0, -1.0, 0.0))
            cr = gl.cross(game_down)
            if cr.length < 1e-6:
                cr = mathutils.Vector((1.0, 0.0, 0.0))
            cr.normalize()
            cu = gl.cross(cr)
            cu.normalize()
            # camera-rot is a 3x3 row-major matrix stored as 9 floats
            cam_rot = [
                round(cr.x, 6), round(cr.y, 6), round(cr.z, 6),
                round(cu.x, 6), round(cu.y, 6), round(cu.z, 6),
                round(gl.x, 6), round(gl.y, 6), round(gl.z, 6),
            ]
        else:
            # Default: camera sits 4m above spawn, looks forward (identity-ish)
            cam_x, cam_y, cam_z = gx, gy + 4.0, gz
            cam_rot = [1.0, 0.0, 0.0,  0.0, 1.0, 0.0,  0.0, 0.0, 1.0]

        out.append({
            "name":          uid,
            "x": gx, "y": gy, "z": gz,
            "qx": qx, "qy": qy, "qz": qz, "qw": qw,
            "cam_x": cam_x, "cam_y": cam_y, "cam_z": cam_z,
            "cam_rot":       cam_rot,
            "is_checkpoint": is_checkpoint,
            # Continue-point level/display settings (feature/load-boundaries-checkpoints).
            # Enum values are identifier strings ("self"/"none"/<level name>);
            # resolved to GOAL symbols in _make_continues, which knows the level name.
            "cp_lev0":          _cp_level_value(o, "og_cp_lev0", "og_cp_lev0_custom"),
            "cp_disp0":         str(getattr(o, "og_cp_disp0", "display") or "display"),
            "cp_lev1":          _cp_level_value(o, "og_cp_lev1", "og_cp_lev1_custom"),
            "cp_disp1":         str(getattr(o, "og_cp_disp1", "off") or "off"),
            "cp_vis_nick":      str(getattr(o, "og_cp_vis_nick", "") or "").strip(),
            "cp_flags":         str(getattr(o, "og_cp_flags", "") or "").strip(),
            "cp_load_commands": str(getattr(o, "og_cp_load_commands", "") or "").strip(),
        })
    return out


def _lb_edge_chain(me):
    """Order an edge-only mesh's vertices into a path (open boundary).

    Falls back to vertex-index order if the edges don't form a simple chain.
    """
    if len(me.edges) == 0:
        return list(range(len(me.vertices)))
    from collections import defaultdict
    adj = defaultdict(list)
    for e in me.edges:
        a, b = e.vertices
        adj[a].append(b); adj[b].append(a)
    start = next((v for v in adj if len(adj[v]) == 1), None)  # an endpoint
    if start is None:
        start = next(iter(adj))
    chain, seen, cur = [start], {start}, start
    while True:
        nxt = next((n for n in adj[cur] if n not in seen), None)
        if nxt is None:
            break
        chain.append(nxt); seen.add(nxt); cur = nxt
    if len(chain) != len(me.vertices):
        return list(range(len(me.vertices)))
    return chain


def collect_load_boundaries(scene):
    """Collect LOADBND_ mesh objects into static-load-boundary data dicts.

    Footprint: the mesh vertices give the horizontal game X/Z polyline/polygon.
    :top/:bot come from the per-object og_lb_top/og_lb_bot settings (Blender
    metres), measured relative to the footprint's height so they match the
    OG Boundary Viz modifier (which offsets the wall in the object's local
    frame). Emitted in game units (metres * 4096): game_x = bx, game_z = -by.
    """
    M = 4096.0

    out = []
    for o in _level_objects(scene):
        if not (o.name.startswith("LOADBND_") and o.type == "MESH"):
            continue
        me, mw = o.data, o.matrix_world
        closed = bool(getattr(o, "og_lb_closed", False))
        if closed and len(me.polygons) > 0:
            idxs = list(me.polygons[0].vertices)   # closed area drawn as a face → loop
        else:
            idxs = _lb_edge_chain(me)              # open polyline / edge-ring / fallback
        verts = [mw @ me.vertices[i].co for i in idxs]
        if len(verts) < 2:
            continue

        base_z = sum(v.z for v in verts) / len(verts)
        top = (base_z + float(getattr(o, "og_lb_top",  400.0))) * M
        bot = (base_z + float(getattr(o, "og_lb_bot", -400.0))) * M

        points = []
        for v in verts:
            points.append(round(v.x * M, 4))    # game X
            points.append(round(-v.y * M, 4))   # game Z

        out.append({
            "name":         o.name[8:] or "bnd",
            "closed":       closed,
            "player":       bool(getattr(o, "og_lb_player", True)),
            "custom_flags": str(getattr(o, "og_lb_custom_flags", "") or "").strip(),
            "top":          round(top, 4),
            "bot":          round(bot, 4),
            "points":       points,
            "fwd_cmd":      str(getattr(o, "og_lb_fwd_cmd", "none") or "none"),
            "fwd_lev0":     str(getattr(o, "og_lb_fwd_lev0", "none") or "none"),
            "fwd_lev1":     str(getattr(o, "og_lb_fwd_lev1", "none") or "none"),
            "fwd_disp":     str(getattr(o, "og_lb_fwd_disp", "display") or "display"),
            "fwd_name":     str(getattr(o, "og_lb_fwd_name", "") or "").strip(),
            "bwd_cmd":      str(getattr(o, "og_lb_bwd_cmd", "none") or "none"),
            "bwd_lev0":     str(getattr(o, "og_lb_bwd_lev0", "none") or "none"),
            "bwd_lev1":     str(getattr(o, "og_lb_bwd_lev1", "none") or "none"),
            "bwd_disp":     str(getattr(o, "og_lb_bwd_disp", "display") or "display"),
            "bwd_name":     str(getattr(o, "og_lb_bwd_name", "") or "").strip(),
        })
    return out


def collect_ambients(scene):
    out = []
    for o in _level_objects(scene):
        if not (o.name.startswith("AMBIENT_") and o.type == "EMPTY"):
            continue
        l = o.location
        gx, gy, gz = round(l.x, 4), round(l.z, 4), round(-l.y, 4)

        if o.get("og_sound_name"):
            # Sound emitter — placed via the Audio panel
            radius   = float(o.get("og_sound_radius", 15.0))
            mode     = str(o.get("og_sound_mode", "loop"))
            snd_name = str(o["og_sound_name"]).lower().strip()

            # cycle-speed: ["float", base_secs, random_range_secs]
            # Negative base = looping (ambient-type-sound-loop) — confirmed working
            # Positive base = one-shot interval (ambient-type-sound) — engine bug, crashes
            if mode == "loop":
                cycle_speed = ["float", -1.0, 0.0]
            else:
                cycle_speed = ["float",
                               float(o.get("og_cycle_min", 5.0)),
                               float(o.get("og_cycle_rnd", 2.0))]

            out.append({
                "trans":   [gx, gy, gz, radius],
                "bsphere": [gx, gy, gz, radius],
                "lump": {
                    "name":        o.name[8:].lower() or "ambient",
                    "type":        "'sound",
                    "effect-name": ["symbol", snd_name],
                    "cycle-speed": cycle_speed,
                },
            })

        elif o.get("og_music_bank"):
            # Music zone — placed via the Music Zones panel
            bank     = str(o["og_music_bank"]).lower().strip()
            flava    = str(o.get("og_music_flava", "default")).lower().strip()
            priority = float(o.get("og_music_priority", 10.0))
            radius   = float(o.get("og_music_radius", 40.0))

            # flava index: look up position in MUSIC_FLAVA_TABLE for this bank
            from ..data import MUSIC_FLAVA_TABLE
            flava_list  = MUSIC_FLAVA_TABLE.get(bank, ["default"])
            flava_index = float(flava_list.index(flava) if flava in flava_list else 0)

            out.append({
                "trans":   [gx, gy, gz, radius],
                "bsphere": [gx, gy, gz, radius],
                "lump": {
                    "name":        o.name[8:].lower() or "music-zone",
                    "type":        "'music",
                    # 'music' lump: the engine reads this as a symbol (e.g. 'village1)
                    # and passes it to (set-setting! 'music <symbol> 0.0 0).
                    # ["symbol", bank] is correct — ResSymbol stores the GOAL symbol ptr.
                    "music":       ["symbol", bank],
                    "flava":       ["float", flava_index],
                    "priority":    ["float", priority],
                    # effect-name is listed in the lump quick-ref for music ambients.
                    # Some vanilla ambient code reads it. Include defensively as a no-op
                    # symbol — ambient-type-music ignores it but it won't cause a crash.
                    "effect-name": ["symbol", bank],
                },
            })
        else:
            # Legacy hint emitter — unchanged behaviour
            out.append({
                "trans":   [gx, gy, gz, 10.0],
                "bsphere": [gx, gy, gz, 15.0],
                "lump": {
                    "name":      o.name[8:].lower() or "ambient",
                    "type":      "'hint",
                    "text-id":   ["enum-uint32", "(text-id fuel-cell)"],
                    "play-mode": "'notice",
                },
            })
    return out
