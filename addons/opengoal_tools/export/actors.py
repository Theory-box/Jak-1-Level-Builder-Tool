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
    _actor_is_enemy,
    _actor_is_launcher,
    _actor_is_spawner,
    _canonical_actor_objects,
    _classify_target,
)
from .volumes import (
    _vol_aabb,
    _vol_links,
)


# Cross-module imports (siblings in the export package)


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

        # eco-door is abstract (no skeleton, no art group). Remap to its
        # concrete default subclass so the engine gets a working type with a
        # real initialize-skeleton call.
        if etype == "eco-door":
            etype = "jng-iris-door"
        l = o.location
        gx, gy, gz = round(l.x, 4), round(l.z, 4), round(-l.y, 4)

        # ── Facing quaternion ────────────────────────────────────────────────
        # Remap Blender rotation into game space: game_rot = R @ bl_rot @ R^T
        # where R maps Blender(x,y,z) → game(x,z,-y).
        # The engine reads quaternions as the conjugate (negate xyz).
        _R  = mathutils.Matrix(((1,0,0),(0,0,1),(0,-1,0)))
        _m3 = o.matrix_world.to_3x3()
        _gq = (_R @ _m3 @ _R.transposed()).to_quaternion()
        aqx = round(-_gq.x, 6)
        aqy = round(-_gq.y, 6)
        aqz = round(-_gq.z, 6)
        aqw = round( _gq.w, 6)

        lump = {"name": f"{etype}-{uid}"}

        if etype == "fuel-cell":
            lump["eco-info"] = ["cell-info", "(game-task none)"]
            # skip-jump-anim: fact-options bit 2 (value 4)
            if bool(o.get("og_cell_skip_jump", False)):
                lump["options"] = ["uint32", 4]
                log(f"  [fuel-cell] {o.name}  skip-jump-anim=true")
        elif etype == "buzzer":
            lump["eco-info"] = ["buzzer-info", "(game-task none)", 1]
        elif etype == "crate":
            ct     = o.get("og_crate_type",          "steel")
            pickup = o.get("og_crate_pickup",         "money")
            amount = int(o.get("og_crate_pickup_amount", 1))
            lump["crate-type"] = f"'{ct}"
            _CRATE_PICKUP_ENGINE = {
                "none":       "(pickup-type none)",
                "money":      "(pickup-type money)",
                "eco-yellow": "(pickup-type eco-yellow)",
                "eco-red":    "(pickup-type eco-red)",
                "eco-blue":   "(pickup-type eco-blue)",
                "eco-green":  "(pickup-type eco-green)",
                "buzzer":     "(pickup-type buzzer)",
            }
            eng_str = _CRATE_PICKUP_ENGINE.get(pickup, "(pickup-type money)")
            if pickup == "buzzer":
                amount = 1  # engine always spawns exactly 1 scout fly
            if pickup != "none":
                lump["eco-info"] = ["eco-info", eng_str, amount]
            log(f"  [crate] {o.name}  type={ct}  pickup={pickup}  amount={amount}")
        elif etype == "money":
            lump["eco-info"] = ["eco-info", "(pickup-type money)", 1]

        einfo = ENTITY_DEFS.get(etype, {})

        # Collect waypoints for this actor (named ACTOR_<etype>_<uid>_wp_00 etc.)
        wp_prefix = o.name + "_wp_"
        wp_objects = sorted(
            [sc_obj for sc_obj in bpy.data.objects
             if sc_obj.name.startswith(wp_prefix) and sc_obj.type == "EMPTY"],
            key=lambda sc_obj: sc_obj.name
        )
        path_pts = []
        for wp in wp_objects:
            wl = wp.location
            path_pts.append([round(wl.x, 4), round(wl.z, 4), round(-wl.y, 4), 1.0])

        # ── Nav-enemy workaround (nav_safe=False) ────────────────────────────
        # These extend nav-enemy. Without a real navmesh they idle forever.
        # Inject nav-mesh-sphere so the engine doesn't dereference null.
        # entity.gc is also patched separately with a real navmesh if linked.
        if etype in NAV_UNSAFE_TYPES:
            nav_r = float(o.get("og_nav_radius", 6.0))
            if path_pts:
                first = path_pts[0]
                lump["nav-mesh-sphere"] = ["vector4m", [first[0], first[1], first[2], nav_r]]
                log(f"  [nav+path] {o.name}  {len(wp_objects)} waypoints  sphere r={nav_r}m")
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
        if (einfo.get("needs_path") or (etype in NAV_UNSAFE_TYPES and path_pts)) and einfo.get("cat") != "Platforms":
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

        # ── Platform: notice-dist (plat-eco) ─────────────────────────────────
        # Controls how close Jak must be before the platform notices blue eco.
        # Default -1.0 = always active (never needs eco to activate).
        if einfo.get("needs_notice_dist"):
            notice = float(o.get("og_notice_dist", -1.0))
            lump["notice-dist"] = ["meters", notice]
            log(f"  [notice-dist] {o.name}  {notice}m  ({'always active' if notice < 0 else 'eco required'})")

        # ── Dark-crystal: mode lump (underwater variant) ─────────────────────
        if etype == "dark-crystal":
            if bool(o.get("og_crystal_underwater", False)):
                lump["mode"] = ["int32", 1]
                log(f"  [dark-crystal] {o.name}  mode=1 (underwater)")

        # ── Plat-flip: sync-percent (phase offset) ────────────────────────────
        if etype == "plat-flip":
            sync_pct = float(o.get("og_flip_sync_pct", 0.0))
            if sync_pct != 0.0:
                lump["sync-percent"] = ["float", sync_pct]
                log(f"  [plat-flip sync-percent] {o.name}  {sync_pct:.2f}")

        # ── Eco-door: flags lump ─────────────────────────────────────────────
        # eco-door reads a 'flags lump (eco-door-flags bitfield).
        # auto-close = bit 0, one-way = bit 1.
        if etype in ("eco-door", "jng-iris-door", "sidedoor", "rounddoor"):
            # eco-door-flags bitfield: ecdf00=1, ecdf01=2, auto-close=4, one-way=8
            # ecdf00: door is LOCKED when state-actor task is NOT complete (button not pressed)
            # ecdf01: door is LOCKED when state-actor task IS complete (unusual, ignore)
            auto_close  = bool(o.get("og_door_auto_close",  False))
            one_way     = bool(o.get("og_door_one_way",     False))
            starts_open = bool(o.get("og_door_starts_open", False))

            # If a state-actor is linked, auto-set ecdf00 so the door locks until
            # the state-actor's perm-complete is set (i.e. the button is pressed).
            # Without ecdf00, locked=False from the start and the button has no effect.
            # (module-level import of _actor_get_link at the top of this file is used)
            has_state_actor = bool(_actor_get_link(o, "state-actor", 0))
            ecdf00 = 1 if has_state_actor else 0

            flags = ecdf00 | (4 if auto_close else 0) | (8 if one_way else 0)
            if flags:
                lump["flags"] = ["uint32", flags]
            # starts_open: pre-set perm-complete so door spawns already open
            if starts_open:
                lump["perm-status"] = ["uint32", 64]  # entity-perm-status complete = bit 6
            log(f"  [eco-door flags] {o.name}  auto-close={auto_close}  one-way={one_way}  starts-open={starts_open}  state-actor-lock={bool(ecdf00)}  flags=0x{flags:02x}")

        # ── Sun-iris-door: proximity + timeout lumps ─────────────────────────
        # Without 'proximity' the door only opens via 'trigger event (trigger vol or button).
        if etype == "sun-iris-door":
            proximity = bool(o.get("og_door_proximity", False))
            timeout   = float(o.get("og_door_timeout",  0.0))
            if proximity:
                lump["proximity"] = ["uint32", 1]
            if timeout > 0.0:
                lump["timeout"] = ["float", timeout]
            log(f"  [sun-iris-door] {o.name}  proximity={proximity}  timeout={timeout}s")

        # ── Basebutton: timeout lump ──────────────────────────────────────────
        # On press sends 'trigger to notify-actor (the alt-actor link target).
        if etype == "basebutton":
            timeout = float(o.get("og_button_timeout", 0.0))
            if timeout > 0.0:
                lump["timeout"] = ["float", timeout]
            log(f"  [basebutton] {o.name}  timeout={timeout}s")

        # ── Water-vol: water-height + vol lumps ───────────────────────────────
        # water-vol needs two lumps to function:
        #
        # 1. 'water-height  — 5 floats: [surface, wade, swim, flags, bottom]
        #    All in meters; C++ compiler multiplies by METER_LENGTH (4096).
        #    The engine reads these to set Jak's wade/swim thresholds and the
        #    kill-plane depth.
        #
        # 2. 'vol  — 6 "vector-vol" planes defining the activation AABB.
        #    WITHOUT this lump vol-control.pos-vol-count = 0, point-in-vol?
        #    always returns #f, and the zone NEVER activates (root cause of
        #    water-vol appearing broken in custom levels before this fix).
        #
        #    Each plane = [nx, ny, nz, d_meters].  The engine stores planes as
        #    (nx, ny, nz, d_raw) where d_raw = d_meters * 4096.  The C++ lump
        #    compiler handles the × 4096 automatically for "vector-vol" type.
        #    Plane equation: dot(normal, point) >= d  →  point is inside.
        #
        #    Box layout (game coords: X = Blender X, Y = Blender Z up,
        #                             Z = Blender -Y):
        #    All normals point INWARD.  Inside condition: dot(P,N) >= d.
        #      top cap — normal ( 0, -1,  0), d = -surface_y
        #      floor   — normal ( 0, +1,  0), d =  bot_y  (surface + bottom offset)
        #      +X cap  — normal (-1,  0,  0), d = -(cx + hx)
        #      -X cap  — normal (+1,  0,  0), d =  cx - hx
        #      +Z cap  — normal ( 0,  0, -1), d = -(cz + hz)
        #      -Z cap  — normal ( 0,  0, +1), d =  cz - hz
        #
        #    Scale: the empty's world scale sets the XZ half-extents.
        #    The user sizes the empty to cover the water area.  Scale 1 = 1 m
        #    half-extent (2 m total width) — scale up to cover the water mesh.
        if etype == "water-vol":
            # Legacy ACTOR_ water-vol path (hidden from picker — use WATER_ mesh instead).
            # wade/swim are depths below surface (positive meters); bottom is absolute Y.
            surface = float(o.get("og_water_surface", 0.0))
            wade    = float(o.get("og_water_wade",    0.5))
            swim    = float(o.get("og_water_swim",    1.0))
            bottom  = float(o.get("og_water_bottom",  surface - 5.0))
            lump["water-height"] = ["water-height", surface, wade, swim, "(water-flags wt02 wt03 wt05 wt22)", bottom]

            # Build the 6-plane vol box from the empty's world scale.
            # NOTE: o.dimensions returns (0,0,0) for empties (no mesh geometry).
            # Use o.scale directly — actor empties are never parented or rotated
            # in this addon, so local scale == world scale.
            # Scale X → game X half-extent, Scale Y → game Z half-extent.
            # Default scale is (1,1,1) = a 2m×2m box. User should scale the
            # empty to match the water area before exporting.
            hx    = abs(o.scale.x)         # game X half-extent (meters)
            hz    = abs(o.scale.y)         # game Z half-extent (meters)
            top_y = surface                # absolute Y of water surface
            bot_y = bottom                 # absolute Y of kill floor (absolute, not relative)

            lump["vol"] = [
                "vector-vol",
                # Normals point OUTWARD. Inside = negative side of each plane.
                # point-in-vol? returns #f when dot(P,N) - w > 0
                [ 0,  1,  0,   top_y      ],   # top:   P.y <= surface
                [ 0, -1,  0,  -bot_y      ],   # floor: P.y >= bottom
                [ 1,  0,  0,   gx + hx    ],   # +X:    P.x <= cx+hx
                [-1,  0,  0, -(gx - hx)   ],   # -X:    P.x >= cx-hx
                [ 0,  0,  1,   gz + hz    ],   # +Z:    P.z <= cz+hz
                [ 0,  0, -1, -(gz - hz)   ],   # -Z:    P.z >= cz-hz
            ]
            log(f"  [water-vol] {o.name}  surface={surface}m  wade={wade}m  swim={swim}m  "
                f"bottom={bottom}m  box={hx*2:.1f}x{hz*2:.1f}m")

        # ── Launcherdoor: continue-name lump ─────────────────────────────────
        # launcherdoor writes a continue-name string lump to set the active
        # checkpoint when Jak passes through the door.
        if etype == "launcherdoor":
            cp_name = str(o.get("og_continue_name", "")).strip()
            if cp_name:
                lump["continue-name"] = cp_name
                log(f"  [launcherdoor] {o.name}  continue-name='{cp_name}'")
            else:
                log(f"  [launcherdoor] {o.name}  no continue-name set")

        # ── Launcher: spring-height and alt-vector (destination) ─────────────
        # launcher and springbox both read spring-height for launch force.
        # launcher also reads alt-vector: xyz = destination, w = fly_time_frames.
        if _actor_is_launcher(etype):
            height = float(o.get("og_spring_height", -1.0))
            if height >= 0:
                lump["spring-height"] = ["meters", height]
                log(f"  [spring-height] {o.name}  {height}m")

            if etype == "launcher":
                dest_name = o.get("og_launcher_dest", "")
                dest_obj  = bpy.data.objects.get(dest_name) if dest_name else None
                fly_time  = float(o.get("og_launcher_fly_time", -1.0))
                if dest_obj:
                    dl = dest_obj.location
                    # Convert Blender coords → game coords (X, Z, -Y)
                    dx = round(dl.x * 4096, 2)
                    dy = round(dl.z * 4096, 2)
                    dz = round(-dl.y * 4096, 2)
                    # w = fly time in frames (seconds × 300); default 150 if not set
                    fw = round((fly_time if fly_time >= 0 else 0.5) * 300, 2)
                    lump["alt-vector"] = ["vector", [dx, dy, dz, fw]]
                    log(f"  [alt-vector] {o.name}  dest={dest_name}  fly={fw:.0f}frames")

        # ── Spawner: num-lurkers ──────────────────────────────────────────────
        # swamp-bat, yeti, villa-starfish, swamp-rat-nest read num-lurkers to
        # control how many child entities they spawn.
        if _actor_is_spawner(etype):
            count = int(o.get("og_num_lurkers", -1))
            if count >= 0:
                lump["num-lurkers"] = ["int32", count]
                log(f"  [num-lurkers] {o.name}  {count}")

        # ── Enemy: idle-distance ──────────────────────────────────────────────
        # Per-instance activation range. The engine reads this in
        # fact-info-enemy:new (engine fact-h.gc line 191) — when the player is
        # farther than idle-distance from the enemy, the enemy stays in its
        # idle state and won't notice the player. Engine default is 80m.
        # Lower = enemy stays "asleep" longer; higher = enemy wakes up sooner.
        # Applies to all enemies and bosses (they all inherit fact-info-enemy).
        if _actor_is_enemy(etype):
            idle_d = float(o.get("og_idle_distance", 80.0))
            lump["idle-distance"] = ["meters", idle_d]
            log(f"  [idle-distance] {o.name}  {idle_d}m")

                # Bsphere radius controls vis-culling distance.  nav-enemy run-logic?
        # only processes AI/collision events when draw-status was-drawn is set,
        # which requires the bsphere to pass the renderer's cull test.
        # Custom levels lack a proper BSP vis system, so enemies need a large
        # bsphere (120m) to guarantee was-drawn is always true in a play area.
        # Pickups / static props can stay small.
        info     = ENTITY_DEFS.get(etype, {})
        is_enemy = info.get("cat") in ("Enemies", "Bosses")
        bsph_r   = 10.0  # Rockpool uses 10m for all entities; 120m caused merc renderer crashes

        # water-vol: bsphere must enclose the full activation box so the process
        # isn't culled before it can run point-in-vol checks each frame.
        # Use o.scale — empties have no dimensions, scale is the half-extent.
        if etype == "water-vol":
            hx     = abs(o.scale.x)
            hz     = abs(o.scale.y)
            bsph_r = max((hx ** 2 + hz ** 2) ** 0.5, 10.0)  # minimum 10m

        # Add vis-dist for enemies so they stay active at reasonable range.
        # og_vis_dist custom prop overrides; default 200m.
        if is_enemy and "vis-dist" not in lump:
            vis = float(o.get("og_vis_dist", 200.0))
            lump["vis-dist"] = ["meters", vis]

        # ── Plat-flip: delay lump ─────────────────────────────────────────────
        # plat-flip reads 'delay as two floats: [before_down, before_up] in seconds.
        if etype == "plat-flip":
            d_down = float(o.get("og_flip_delay_down", 2.0))
            d_up   = float(o.get("og_flip_delay_up",   2.0))
            lump["delay"] = ["float", d_down, d_up]
            log(f"  [plat-flip delay] {o.name}  down={d_down}s  up={d_up}s")

        # ── Orb-cache: orb-cache-count lump ──────────────────────────────────
        if etype == "orb-cache-top":
            count = int(o.get("og_orb_count", 20))
            lump["orb-cache-count"] = ["int32", count]
            log(f"  [orb-cache] {o.name}  count={count}")

        # ── Whirlpool: speed lump ────────────────────────────────────────────
        # whirlpool reads 'speed as two floats: [base, variation] in internal units.
        if etype == "whirlpool":
            speed = float(o.get("og_whirl_speed", 0.3))
            var   = float(o.get("og_whirl_var",   0.1))
            lump["speed"] = ["float", speed, var]
            log(f"  [whirlpool speed] {o.name}  base={speed}  var={var}")

        # ── Ropebridge: art-name lump ─────────────────────────────────────────
        if etype == "ropebridge":
            variant = str(o.get("og_bridge_variant", "ropebridge-32"))
            lump["art-name"] = ["symbol", variant]
            log(f"  [ropebridge] {o.name}  art-name={variant}")

        # ── Orbit-plat: scale + timeout lumps ────────────────────────────────
        if etype == "orbit-plat":
            scale   = float(o.get("og_orbit_scale",   1.0))
            timeout = float(o.get("og_orbit_timeout", 10.0))
            if scale != 1.0:
                lump["scale"] = ["float", scale]
            if timeout != 10.0:
                lump["timeout"] = ["float", timeout]
            log(f"  [orbit-plat] {o.name}  scale={scale}  timeout={timeout}s")

        # ── Square-platform: distance lump (down, up in raw units) ───────────
        if etype == "square-platform":
            down_m = float(o.get("og_sq_down", -2.0))
            up_m   = float(o.get("og_sq_up",    4.0))
            # convert meters to internal units (×4096)
            lump["distance"] = ["float", down_m * 4096, up_m * 4096]
            log(f"  [square-platform] {o.name}  down={down_m}m  up={up_m}m")

        # ── Caveflamepots: shove + cycle-speed lumps ─────────────────────────
        if etype == "caveflamepots":
            shove  = float(o.get("og_flame_shove",  2.0))
            period = float(o.get("og_flame_period", 4.0))
            phase  = float(o.get("og_flame_phase",  0.0))
            pause  = float(o.get("og_flame_pause",  2.0))
            lump["shove"]       = ["meters", shove]
            lump["cycle-speed"] = ["float", period, phase, pause]
            log(f"  [caveflamepots] {o.name}  shove={shove}m  period={period}s  phase={phase}  pause={pause}s")

        # ── Shover: shove force + rotoffset ──────────────────────────────────
        if etype == "shover":
            shove = float(o.get("og_shover_force", 3.0))
            rot   = float(o.get("og_shover_rot",   0.0))
            lump["shove"] = ["meters", shove]
            if rot != 0.0:
                lump["rotoffset"] = ["degrees", rot]
            log(f"  [shover] {o.name}  shove={shove}m  rot={rot}°")

        # ── Lavaballoon / darkecobarrel: speed lump ──────────────────────────
        if etype in ("lavaballoon", "darkecobarrel"):
            default_speed = 3.0 if etype == "lavaballoon" else 15.0
            speed = float(o.get("og_move_speed", default_speed))
            lump["speed"] = ["meters", speed]
            log(f"  [{etype}] {o.name}  speed={speed}m/s")

        # ── Windturbine: particle-select lump ────────────────────────────────
        if etype == "windturbine":
            if bool(o.get("og_turbine_particles", False)):
                lump["particle-select"] = ["uint32", 1]
                log(f"  [windturbine] {o.name}  particles=on")

        # ── Cave elevator: mode + rotoffset ──────────────────────────────────
        if etype == "caveelevator":
            mode = int(o.get("og_elevator_mode", 0))
            rot  = float(o.get("og_elevator_rot", 0.0))
            if mode != 0:
                lump["mode"] = ["uint32", mode]
            if rot != 0.0:
                lump["rotoffset"] = ["degrees", rot]
            log(f"  [caveelevator] {o.name}  mode={mode}  rot={rot}°")

        # ── Mis-bone-bridge: animation-select ────────────────────────────────
        if etype == "mis-bone-bridge":
            anim = int(o.get("og_bone_bridge_anim", 0))
            if anim != 0:
                lump["animation-select"] = ["uint32", anim]
            log(f"  [mis-bone-bridge] {o.name}  animation-select={anim}")

        # ── Breakaway platforms: height-info ─────────────────────────────────
        if etype in ("breakaway-left", "breakaway-mid", "breakaway-right"):
            h1 = float(o.get("og_breakaway_h1", 0.0))
            h2 = float(o.get("og_breakaway_h2", 0.0))
            if h1 != 0.0 or h2 != 0.0:
                lump["height-info"] = ["float", h1, h2]
            log(f"  [breakaway] {o.name}  h1={h1}  h2={h2}")

        # ── Sunkenfisha: count lump ───────────────────────────────────────────
        if etype == "sunkenfisha":
            count = int(o.get("og_fish_count", 1))
            if count != 1:
                lump["count"] = ["uint32", count]
            log(f"  [sunkenfisha] {o.name}  count={count}")

        # ── Sharkey: scale, delay, distance, speed ────────────────────────────
        if etype == "sharkey":
            scale    = float(o.get("og_shark_scale",    1.0))
            delay    = float(o.get("og_shark_delay",    1.0))
            distance = float(o.get("og_shark_distance", 30.0))
            speed    = float(o.get("og_shark_speed",    12.0))
            if scale != 1.0:
                lump["scale"] = ["float", scale]
            lump["delay"]    = ["float", delay]
            lump["distance"] = ["meters", distance]
            lump["speed"]    = ["meters", speed]
            log(f"  [sharkey] {o.name}  scale={scale}  delay={delay}s  dist={distance}m  speed={speed}m/s")

        # ── Oracle / pontoon: alt-task ────────────────────────────────────────
        if etype in ("oracle", "pontoon"):
            task = str(o.get("og_alt_task", "none"))
            if task and task != "none":
                lump["alt-task"] = ["enum-uint32", f"(game-task {task})"]
                log(f"  [{etype}] {o.name}  alt-task={task}")

        # ── Entity links (alt-actor, water-actor, state-actor, etc.) ─────────
        # Build string-array lumps from og_actor_links CollectionProperty.
        # These are merged before custom lump rows so rows can override them.
        link_lumps = _build_actor_link_lumps(o, etype)
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
            log(f"  [lump-row] {o.name}  '{key}' = {value}")

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
            # AABB mode — derive bounds from volume mesh world-space verts
            xmin, xmax, ymin, ymax, zmin, zmax, cx, cy, cz, rad = _vol_aabb(vol_obj)
            # Slightly tighter padding for checkpoints (matches old behaviour)
            rad = round(max(xmax - xmin, ymax - ymin, zmax - zmin) / 2 + 2.0, 2)
            lump["has-volume"]  = ["uint32", 1]
            lump["bound-xmin"]  = ["meters", xmin]
            lump["bound-xmax"]  = ["meters", xmax]
            lump["bound-ymin"]  = ["meters", ymin]
            lump["bound-ymax"]  = ["meters", ymax]
            lump["bound-zmin"]  = ["meters", zmin]
            lump["bound-zmax"]  = ["meters", zmax]
            out.append({
                "trans":     [cx, cy, cz],
                "etype":     "checkpoint-trigger",
                "game_task": "(game-task none)",
                "quat":      [0, 0, 0, 1],
                "vis_id":    0,
                "bsphere":   [cx, cy, cz, rad],
                "lump":      lump,
            })
            log(f"  [checkpoint] {o.name} → '{cp_name}'  AABB vol={vol_obj.name}")
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
            if etype == "money":
                lump_v["eco-info"] = ["eco-info", "(pickup-type money)", 1]
            elif etype == "buzzer":
                lump_v["eco-info"] = ["buzzer-info", "(game-task none)", 1]
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
