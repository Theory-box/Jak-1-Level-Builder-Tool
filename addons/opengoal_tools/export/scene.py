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
    NAV_UNSAFE_TYPES, NEEDS_PATH_TYPES, NEEDS_PATHB_TYPES, IS_PROP_TYPES,
    needed_tpages, LUMP_REFERENCE, ACTOR_LINK_DEFS,
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
                    "bound-xmin":  ["meters", xmin],
                    "bound-xmax":  ["meters", xmax],
                    "bound-ymin":  ["meters", ymin],
                    "bound-ymax":  ["meters", ymax],
                    "bound-zmin":  ["meters", zmin],
                    "bound-zmax":  ["meters", zmax],
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
                    "bound-xmin":  ["meters", xmin],
                    "bound-xmax":  ["meters", xmax],
                    "bound-ymin":  ["meters", ymin],
                    "bound-ymax":  ["meters", ymax],
                    "bound-zmin":  ["meters", zmin],
                    "bound-zmax":  ["meters", zmax],
                },
            })
            log(f"  [vol-trigger] {vol.name} → {entry.target_name} (lump: {target_lump_name})")
    return out

def collect_cameras(scene):
    """Build camera actor list from CAMERA_ camera objects.

    Returns (camera_actors, trigger_actors) where both are JSONC actor dicts.
    camera_actors  -- camera-marker entities (hold position/rotation)
    trigger_actors -- camera-trigger entities (AABB polling, birth on level load)

    A volume can hold multiple links. We iterate every VOL_ mesh's links and
    emit one camera-trigger actor per (volume, camera_link) pair.
    """
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
                    vols_by_cam.setdefault(entry.target_name, []).append(o)

    camera_actors  = []
    trigger_actors = []

    for cam_obj in cam_objects:
        cam_name = cam_obj.name

        loc = cam_obj.matrix_world.translation
        gx = round(loc.x, 4)
        gy = round(loc.z, 4)
        gz = round(-loc.y, 4)

        # Blender -> game camera quaternion.
        #
        # 1. Determine the look direction in world space:
        #    - If the camera has a look-at target, aim at the target
        #      (target_world - camera_world).  Otherwise use the Blender
        #      camera's own -local_Z axis (its native orientation).
        # 2. Remap to game space: bl(x,y,z) -> game(x,z,-y)
        # 3. Build canonical rotation via forward-down->inv-matrix style
        #    (world-down = (0,-1,0) roll reference).
        # 4. Conjugate the result (negate xyz) — the game's quaternion->matrix
        #    reads the inverse convention from what standard math produces.
        #
        # Steps 2-4 confirmed empirically via nREPL inv-camera-rot readback.
        # Step 1's look-at branch is the fix for the look-at-target UI:
        # previously the quat was always built from the Blender camera's own
        # rotation, with a separate 'interesting' lump for the target.  But
        # the engine's 'interesting' lump only acts as a POI *bias* on cameras
        # that have a follow-pt (gameplay follow-cams); for fixed cameras it's
        # effectively a no-op.  The only way to make a fixed camera actually
        # face a point is to bake the look direction into the quat itself.
        look_at_name = cam_obj.get("og_cam_look_at", "").strip()
        look_obj = scene.objects.get(look_at_name) if look_at_name else None
        if look_obj:
            # Aim from camera toward target in Blender world space, then remap.
            tgt = look_obj.matrix_world.translation
            bl_look = mathutils.Vector((tgt.x - loc.x, tgt.y - loc.y, tgt.z - loc.z))
            if bl_look.length < 1e-6:
                # Degenerate: target at same position as camera, fall back to
                # the camera's native rotation so we don't emit a bad quat.
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
        game_mat = mathutils.Matrix([right, up, gl])
        gq = game_mat.to_quaternion()
        qx = round(-gq.x, 6)
        qy = round(-gq.y, 6)
        qz = round(-gq.z, 6)
        qw = round( gq.w, 6)

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
                        "bound-xmin": ["meters", xmin],
                        "bound-xmax": ["meters", xmax],
                        "bound-ymin": ["meters", ymin],
                        "bound-ymax": ["meters", ymax],
                        "bound-zmin": ["meters", zmin],
                        "bound-zmax": ["meters", zmax],
                    },
                })
                log(f"  [camera] {cam_name} + trigger {vol_obj.name}")
        else:
            log(f"  [camera] {cam_name} -- no trigger volume")

    return camera_actors, trigger_actors

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
