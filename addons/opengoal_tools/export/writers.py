# ───────────────────────────────────────────────────────────────────────
# export/writers.py — OpenGOAL Level Tools
#
# File writers and patchers: write the GOAL source / JSONC / DGO spec files, patch the engine's level-info.gc and game.gp, generate continue-points, export collision/visibility geometry as GLB.
# ───────────────────────────────────────────────────────────────────────

from __future__ import annotations

import bpy, os, re, json, math, mathutils
from pathlib import Path
from ..data import (
    ENTITY_DEFS, ETYPE_CODE, ETYPE_TPAGES, ETYPE_AG, VERTEX_EXPORT_TYPES,
    NAV_UNSAFE_TYPES, NEEDS_PATH_TYPES, NEEDS_PATHB_TYPES, IS_PROP_TYPES,
    needed_tpages, LUMP_REFERENCE, ACTOR_LINK_DEFS,
    MOOD_FUNC_OVERRIDES,
    _lump_ref_for_etype, _actor_link_slots, _actor_has_links,
    _actor_links, _actor_get_link, _actor_set_link,
    _actor_remove_link, _build_actor_link_lumps,
    _parse_lump_row, _aggro_event_id, AGGRO_TRIGGER_EVENTS,
    _LUMP_HARDCODED_KEYS, _is_custom_type, GLOBAL_TPAGE_GOS,
)
from ..collections import (
    _get_level_prop, _level_objects,
    _active_level_col, _classify_object, _col_path_for_entity,
    _ensure_sub_collection, _recursive_col_objects,
    _ensure_level_index, _migrate_all_level_indices,
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
from .levels import (
    needed_ags,
)
from .paths import (
    _game_gp,
    _goal_src,
    _iso,
    _ldir,
    _level_info,
    _load_boundary_data,
    _nick,
    log,
)


def _effective_nick(scene, name):
    """Resolve the active level's vis-nick: explicit override if set, else auto-derived from name.

    Mirrors collections._resolve_vis_nick but operates via _get_level_prop so it sees
    the override of the level currently being exported (which is always the active level
    in single-level export flows). Falls back to the safe auto-derived value when
    scene is None or the override is unset/empty.
    """
    if scene is not None:
        try:
            ov = str(_get_level_prop(scene, "og_vis_nick_override", "") or "").strip().lower()
            if ov:
                return ov
        except Exception:
            pass
    return _nick(name)


# Cross-module imports (siblings in the export package)


def make_fog_actor_dict(spawns):
    """Build the synthetic fog-control actor dict for injection into the JSONC.

    Placed at the average spawn position so it births alongside the player on
    level load.  Once alive, the fog-control loop teleports it to the player's
    position every frame so it never falls out of birth-distance.

    `spawns` is the list returned by collect_spawns(); each entry has 'x'/'y'/'z'
    fields.  Falls back to world origin if no spawns are present.
    Returns a dict ready to append to the actors list passed to write_jsonc.
    """
    if spawns:
        cx = sum(s["x"] for s in spawns) / len(spawns)
        cy = sum(s["y"] for s in spawns) / len(spawns)
        cz = sum(s["z"] for s in spawns) / len(spawns)
    else:
        cx = cy = cz = 0.0
    return {
        "trans":     [cx, cy, cz],
        "etype":     "fog-control",
        "game_task": 0,
        "quat":      [0.0, 0.0, 0.0, 1.0],
        "vis_id":    0,
        "bsphere":   [cx, cy, cz, 1.0],
        "lump":      {"name": "fog-control-0"},
    }


def write_gc(name, has_triggers=False, has_checkpoints=False, has_aggro_triggers=False, has_custom_triggers=False, has_fog_override=False, scene=None):
    """Write obs.gc: always emits camera-marker type; if has_triggers also
    emits camera-trigger type; if has_checkpoints emits checkpoint-trigger type;
    if has_aggro_triggers emits aggro-trigger type;
    if has_custom_triggers emits vol-trigger type (sends 'trigger/'untrigger to custom actors).
    If has_fog_override emits fog-control type (overrides *math-camera* fog
    values every frame from baked-in panel values).
    If scene is provided, any ACTOR_ empties with an og_goal_code_ref text block
    assigned (and enabled) have their code appended after the addon's types.
    All types birth automatically via entity-actor.birth! — no nREPL needed.
    """
    d = _goal_src() / "levels" / name
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}-obs.gc"

    lines = [
        ";;-*-Lisp-*-",
        "(in-package goal)",
        f";; {name}-obs.gc -- auto-generated by OpenGOAL Level Tools",
        "",
        ";; camera-marker: inert entity that holds camera position/rotation.",
        "(deftype camera-marker (process-drawable)",
        "  ()",
        "  (:states camera-marker-idle))",
        "",
        "(defstate camera-marker-idle (camera-marker)",
        "  :code (behavior () (loop (suspend))))",
        "",
        "(defmethod init-from-entity! ((this camera-marker) (arg0 entity-actor))",
        "  (set! (-> this root) (new (quote process) (quote trsqv)))",
        "  (process-drawable-from-entity! this arg0)",
        "  (go camera-marker-idle)",
        "  (none))",
        "",
    ]

    if has_triggers:
        lines += [
            ";; camera-trigger: AABB volume entity that switches the active camera.",
            ";; Reads bounds from meters lumps; reads cam-name string lump.",
            ";; No nREPL call needed -- births automatically on level load.",
            "(deftype camera-trigger (process-drawable)",
            "  ((cam-name    string  :offset-assert 176)",
            "   (cull-radius float   :offset-assert 180)",
            "   (xmin        float   :offset-assert 184)",
            "   (xmax        float   :offset-assert 188)",
            "   (ymin        float   :offset-assert 192)",
            "   (ymax        float   :offset-assert 196)",
            "   (zmin        float   :offset-assert 200)",
            "   (zmax        float   :offset-assert 204)",
            "   (inside      symbol  :offset-assert 208))",
            "  :heap-base #x70",
            "  :size-assert #xd4",
            "  (:states camera-trigger-active))",
            "",
            "(defstate camera-trigger-active (camera-trigger)",
            "  :code",
            "  (behavior ()",
            "    (loop",
            "      (when (and *target* (zero? (mod (-> *display* base-frame-counter) 4)))",
            "        (let* ((pos  (-> *target* control trans))",
            "               (dx   (- (-> pos x) (-> self root trans x)))",
            "               (dy   (- (-> pos y) (-> self root trans y)))",
            "               (dz   (- (-> pos z) (-> self root trans z)))",
            "               (cr   (-> self cull-radius))",
            "               (in-vol (and",
            "                 (< (+ (* dx dx) (* dy dy) (* dz dz)) (* cr cr))",
            "                 (< (-> self xmin) (-> pos x)) (< (-> pos x) (-> self xmax))",
            "                 (< (-> self ymin) (-> pos y)) (< (-> pos y) (-> self ymax))",
            "                 (< (-> self zmin) (-> pos z)) (< (-> pos z) (-> self zmax)))))",
            "          (cond",
            "            ((and in-vol (not (-> self inside)))",
            "             (set! (-> self inside) #t)",
            "             (format 0 \"[cam-trigger] enter -> ~A~%\" (-> self cam-name))",
            "             (send-event *camera* (quote change-to-entity-by-name) (-> self cam-name)))",
            "            ((and (not in-vol) (-> self inside))",
            "             (set! (-> self inside) #f)",
            "             (format 0 \"[cam-trigger] exit ~A~%\" (-> self cam-name))",
            "             (send-event *camera* (quote clear-entity))))))",
            "      (suspend))))",
            "",
            "(defmethod init-from-entity! ((this camera-trigger) (arg0 entity-actor))",
            "  (set! (-> this root) (new (quote process) (quote trsqv)))",
            "  (process-drawable-from-entity! this arg0)",
            "  (set! (-> this cam-name) (res-lump-struct arg0 (quote cam-name) string))",
            "  (set! (-> this xmin) (res-lump-float arg0 (quote bound-xmin)))",
            "  (set! (-> this xmax) (res-lump-float arg0 (quote bound-xmax)))",
            "  (set! (-> this ymin) (res-lump-float arg0 (quote bound-ymin)))",
            "  (set! (-> this ymax) (res-lump-float arg0 (quote bound-ymax)))",
            "  (set! (-> this zmin) (res-lump-float arg0 (quote bound-zmin)))",
            "  (set! (-> this zmax) (res-lump-float arg0 (quote bound-zmax)))",
            "  (let* ((hx (* 0.5 (- (-> this xmax) (-> this xmin))))",
            "         (hy (* 0.5 (- (-> this ymax) (-> this ymin))))",
            "         (hz (* 0.5 (- (-> this zmax) (-> this zmin)))))",
            "    (set! (-> this cull-radius) (sqrtf (+ (* hx hx) (* hy hy) (* hz hz)))))",
            "  (set! (-> this inside) #f)",
            "  (format 0 \"[cam-trigger] armed: ~A cull-r ~M~%\" (-> this cam-name) (-> this cull-radius))",
            "  (go camera-trigger-active)",
            "  (none))",
            "",
        ]
        log(f"  [write_gc] camera-trigger type embedded")

    if has_checkpoints:
        lines += [
            ";; checkpoint-trigger: sets continue point when Jak enters the volume.",
            ";; After firing it enters a 5-second cooldown then re-arms automatically,",
            ";; so if the player dies and respawns in the same zone it fires again.",
            ";; Two modes: sphere (default) or AABB (has-volume lump = 1).",
            "(deftype checkpoint-trigger (process-drawable)",
            "  ((cp-name     string  :offset-assert 176)",
            "   (cull-radius float   :offset-assert 180)",
            "   (radius      float   :offset-assert 184)",
            "   (use-vol     symbol  :offset-assert 188)",
            "   (was-near    symbol  :offset-assert 192)",
            "   (xmin        float   :offset-assert 196)",
            "   (xmax        float   :offset-assert 200)",
            "   (ymin        float   :offset-assert 204)",
            "   (ymax        float   :offset-assert 208)",
            "   (zmin        float   :offset-assert 212)",
            "   (zmax        float   :offset-assert 216))",
            "  :heap-base #x70",
            "  :size-assert #xdc",
            "  (:states checkpoint-trigger-active checkpoint-trigger-wait-exit))",
            "",
            ";; Wait-for-exit state: fired, now waiting for player to leave the volume.",
            ";; Re-arms the moment they step out — zero overhead while inside, instant",
            ";; re-arm on exit. No timer needed.",
            "(defstate checkpoint-trigger-wait-exit (checkpoint-trigger)",
            "  :code",
            "  (behavior ()",
            "    (loop",
            "      (when (and *target* (zero? (mod (-> *display* base-frame-counter) 4)))",
            "        (let* ((pos  (-> *target* control trans))",
            "               (dx   (- (-> pos x) (-> self root trans x)))",
            "               (dy   (- (-> pos y) (-> self root trans y)))",
            "               (dz   (- (-> pos z) (-> self root trans z)))",
            "               (cr   (-> self cull-radius))",
            "               (still-inside (and",
            "                 (< (+ (* dx dx) (* dy dy) (* dz dz)) (* cr cr))",
            "                 (if (-> self use-vol)",
            "                   (and",
            "                     (< (-> self xmin) (-> pos x)) (< (-> pos x) (-> self xmax))",
            "                     (< (-> self ymin) (-> pos y)) (< (-> pos y) (-> self ymax))",
            "                     (< (-> self zmin) (-> pos z)) (< (-> pos z) (-> self zmax)))",
            "                   (let ((r (-> self radius)))",
            "                     (< (+ (* dx dx) (* dy dy) (* dz dz)) (* r r)))))))",
            "          (when (not still-inside)",
            "            (format 0 \"[cp-trigger] ~A re-armed~%\" (-> self cp-name))",
            "            (go checkpoint-trigger-active))))",
            "      (suspend))))",
            "",
            "(defstate checkpoint-trigger-active (checkpoint-trigger)",
            "  :code",
            "  (behavior ()",
            "    (loop",
            "      (when (and *target* (zero? (mod (-> *display* base-frame-counter) 4)))",
            "        (let* ((pos  (-> *target* control trans))",
            "               (dx   (- (-> pos x) (-> self root trans x)))",
            "               (dy   (- (-> pos y) (-> self root trans y)))",
            "               (dz   (- (-> pos z) (-> self root trans z)))",
            "               (cr   (-> self cull-radius))",
            "               (near (< (+ (* dx dx) (* dy dy) (* dz dz)) (* cr cr)))",
            "               (inside (and near",
            "                 (if (-> self use-vol)",
            "                   (and",
            "                     (< (-> self xmin) (-> pos x)) (< (-> pos x) (-> self xmax))",
            "                     (< (-> self ymin) (-> pos y)) (< (-> pos y) (-> self ymax))",
            "                     (< (-> self zmin) (-> pos z)) (< (-> pos z) (-> self zmax)))",
            "                   (let ((r (-> self radius)))",
            "                     (< (+ (* dx dx) (* dy dy) (* dz dz)) (* r r)))))))",
            "          (when (and near (not inside) (not (-> self was-near)))",
            "            (format 0 \"[cp-trigger] ~A sphere-hit AABB-miss~%\" (-> self cp-name)))",
            "          (set! (-> self was-near) near)",
            "          (when inside",
            "            (format 0 \"[cp-trigger] fired -> ~A~%\" (-> self cp-name))",
            "            (set-continue! *game-info* (-> self cp-name))",
            "            (go checkpoint-trigger-wait-exit))))",
            "      (suspend))))",
            "",
            "(defmethod init-from-entity! ((this checkpoint-trigger) (arg0 entity-actor))",
            "  (set! (-> this root) (new (quote process) (quote trsqv)))",
            "  (process-drawable-from-entity! this arg0)",
            "  (set! (-> this cp-name)  (res-lump-struct arg0 (quote continue-name) string))",
            "  (set! (-> this radius)   (res-lump-float  arg0 (quote radius) :default 12288.0))",
            "  (set! (-> this use-vol)  (!= 0 (the int (res-lump-value arg0 (quote has-volume) uint128))))",
            "  (set! (-> this was-near) #f)",
            "  (set! (-> this xmin)     (res-lump-float arg0 (quote bound-xmin)))",
            "  (set! (-> this xmax)     (res-lump-float arg0 (quote bound-xmax)))",
            "  (set! (-> this ymin)     (res-lump-float arg0 (quote bound-ymin)))",
            "  (set! (-> this ymax)     (res-lump-float arg0 (quote bound-ymax)))",
            "  (set! (-> this zmin)     (res-lump-float arg0 (quote bound-zmin)))",
            "  (set! (-> this zmax)     (res-lump-float arg0 (quote bound-zmax)))",
            "  (let* ((hx (* 0.5 (- (-> this xmax) (-> this xmin))))",
            "         (hy (* 0.5 (- (-> this ymax) (-> this ymin))))",
            "         (hz (* 0.5 (- (-> this zmax) (-> this zmin))))",
            "         (r  (-> this radius)))",
            "    (set! (-> this cull-radius)",
            "      (if (-> this use-vol)",
            "        (sqrtf (+ (* hx hx) (* hy hy) (* hz hz)))",
            "        (* r 1.2))))",
            "  (format 0 \"[cp-trigger] armed: ~A~%\" (-> this cp-name))",
            "  (go checkpoint-trigger-active)",
            "  (none))",
            "",
        ]
        log(f"  [write_gc] checkpoint-trigger type embedded")

    if has_aggro_triggers:
        lines += [
            ";; aggro-trigger: AABB volume entity that sends a wakeup event to a target enemy.",
            ";; On rising edge (player enters volume), looks up target enemy by name via",
            ";; (process-by-ename ...) and sends one of three quoted symbols based on event-id:",
            ";;   0 = 'cue-chase        — wake enemy + chase player",
            ";;   1 = 'cue-patrol       — return to patrol",
            ";;   2 = 'go-wait-for-cue  — freeze until next cue",
            ";; Re-fires every time the player re-enters (inside flag clears on exit).",
            ";; Only nav-enemies respond to these events (engine: nav-enemy.gc line 142).",
            "(deftype aggro-trigger (process-drawable)",
            "  ((target-name string  :offset-assert 176)",
            "   (cull-radius float   :offset-assert 180)",
            "   (event-id    int32   :offset-assert 184)",
            "   (xmin        float   :offset-assert 188)",
            "   (xmax        float   :offset-assert 192)",
            "   (ymin        float   :offset-assert 196)",
            "   (ymax        float   :offset-assert 200)",
            "   (zmin        float   :offset-assert 204)",
            "   (zmax        float   :offset-assert 208)",
            "   (inside      symbol  :offset-assert 212))",
            "  :heap-base #x70",
            "  :size-assert #xd8",
            "  (:states aggro-trigger-active))",
            "",
            "(defstate aggro-trigger-active (aggro-trigger)",
            "  :code",
            "  (behavior ()",
            "    (loop",
            "      (when (and *target* (zero? (mod (-> *display* base-frame-counter) 4)))",
            "        (let* ((pos  (-> *target* control trans))",
            "               (dx   (- (-> pos x) (-> self root trans x)))",
            "               (dy   (- (-> pos y) (-> self root trans y)))",
            "               (dz   (- (-> pos z) (-> self root trans z)))",
            "               (cr   (-> self cull-radius))",
            "               (in-vol (and",
            "                 (< (+ (* dx dx) (* dy dy) (* dz dz)) (* cr cr))",
            "                 (< (-> self xmin) (-> pos x)) (< (-> pos x) (-> self xmax))",
            "                 (< (-> self ymin) (-> pos y)) (< (-> pos y) (-> self ymax))",
            "                 (< (-> self zmin) (-> pos z)) (< (-> pos z) (-> self zmax)))))",
            "          (cond",
            "            ((and in-vol (not (-> self inside)))",
            "             (set! (-> self inside) #t)",
            "             (format 0 \"[aggro-trigger] enter -> ~A~%\" (-> self target-name))",
            "             (let ((proc (process-by-ename (-> self target-name))))",
            "               (when proc",
            "                 (cond",
            "                   ((zero? (-> self event-id))",
            "                    (send-event proc 'cue-chase))",
            "                   ((= (-> self event-id) 1)",
            "                    (send-event proc 'cue-patrol))",
            "                   ((= (-> self event-id) 2)",
            "                    (send-event proc 'go-wait-for-cue))))))",
            "            ((and (not in-vol) (-> self inside))",
            "             (set! (-> self inside) #f)",
            "             (format 0 \"[aggro-trigger] exit ~A~%\" (-> self target-name))))))",
            "      (suspend))))",
            "",
            "(defmethod init-from-entity! ((this aggro-trigger) (arg0 entity-actor))",
            "  (set! (-> this root) (new (quote process) (quote trsqv)))",
            "  (process-drawable-from-entity! this arg0)",
            "  (set! (-> this target-name) (res-lump-struct arg0 (quote target-name) string))",
            "  (set! (-> this event-id)    (the int (res-lump-value arg0 (quote event-id) uint128)))",
            "  (set! (-> this xmin)        (res-lump-float arg0 (quote bound-xmin)))",
            "  (set! (-> this xmax)        (res-lump-float arg0 (quote bound-xmax)))",
            "  (set! (-> this ymin)        (res-lump-float arg0 (quote bound-ymin)))",
            "  (set! (-> this ymax)        (res-lump-float arg0 (quote bound-ymax)))",
            "  (set! (-> this zmin)        (res-lump-float arg0 (quote bound-zmin)))",
            "  (set! (-> this zmax)        (res-lump-float arg0 (quote bound-zmax)))",
            "  (set! (-> this inside)      #f)",
            "  (let* ((hx (* 0.5 (- (-> this xmax) (-> this xmin))))",
            "         (hy (* 0.5 (- (-> this ymax) (-> this ymin))))",
            "         (hz (* 0.5 (- (-> this zmax) (-> this zmin)))))",
            "    (set! (-> this cull-radius) (sqrtf (+ (* hx hx) (* hy hy) (* hz hz)))))",
            "  (format 0 \"[aggro-trigger] armed: ~A cull-r ~M~%\" (-> this target-name) (-> this cull-radius))",
            "  (go aggro-trigger-active)",
            "  (none))",
            "",
        ]
        log(f"  [write_gc] aggro-trigger type embedded")

    if has_custom_triggers:
        lines += [
            ";; vol-trigger: AABB volume entity that sends 'trigger/'untrigger to a custom actor.",
            ";; On rising edge (player enters volume), sends 'trigger to target by name.",
            ";; On falling edge (player exits volume), sends 'untrigger to target by name.",
            ";; Target is looked up each poll via process-by-ename — safe if target dies.",
            ";; Mirrors the aggro-trigger pattern (proven working): *target* guard + frame throttle.",
            "(deftype vol-trigger (process-drawable)",
            "  ((target-name string  :offset-assert 176)",
            "   (cull-radius float   :offset-assert 180)",
            "   (xmin        float   :offset-assert 184)",
            "   (xmax        float   :offset-assert 188)",
            "   (ymin        float   :offset-assert 192)",
            "   (ymax        float   :offset-assert 196)",
            "   (zmin        float   :offset-assert 200)",
            "   (zmax        float   :offset-assert 204)",
            "   (inside      symbol  :offset-assert 208))",
            "  :heap-base #x70",
            "  :size-assert #xd4",
            "  (:states vol-trigger-active))",
            "",
            "(defstate vol-trigger-active (vol-trigger)",
            "  :code",
            "  (behavior ()",
            "    (loop",
            "      (when (and *target* (zero? (mod (-> *display* base-frame-counter) 4)))",
            "        (let* ((pos  (-> *target* control trans))",
            "               (dx   (- (-> pos x) (-> self root trans x)))",
            "               (dy   (- (-> pos y) (-> self root trans y)))",
            "               (dz   (- (-> pos z) (-> self root trans z)))",
            "               (cr   (-> self cull-radius))",
            "               (in-vol (and",
            "                 (< (+ (* dx dx) (* dy dy) (* dz dz)) (* cr cr))",
            "                 (< (-> self xmin) (-> pos x)) (< (-> pos x) (-> self xmax))",
            "                 (< (-> self ymin) (-> pos y)) (< (-> pos y) (-> self ymax))",
            "                 (< (-> self zmin) (-> pos z)) (< (-> pos z) (-> self zmax)))))",
            "          (cond",
            "            ((and in-vol (not (-> self inside)))",
            "             (set! (-> self inside) #t)",
            "             (format 0 \"[vol-trigger] enter -> ~A~%\" (-> self target-name))",
            "             (let ((proc (process-by-ename (-> self target-name))))",
            "               (when proc (send-event proc 'trigger))))",
            "            ((and (not in-vol) (-> self inside))",
            "             (set! (-> self inside) #f)",
            "             (format 0 \"[vol-trigger] exit ~A~%\" (-> self target-name))",
            "             (let ((proc (process-by-ename (-> self target-name))))",
            "               (when proc (send-event proc 'untrigger)))))))",
            "      (suspend))))",
            "",
            "(defmethod init-from-entity! ((this vol-trigger) (arg0 entity-actor))",
            "  (set! (-> this root) (new (quote process) (quote trsqv)))",
            "  (process-drawable-from-entity! this arg0)",
            "  (set! (-> this target-name) (res-lump-struct arg0 (quote target-name) string))",
            "  (set! (-> this xmin)        (res-lump-float arg0 (quote bound-xmin)))",
            "  (set! (-> this xmax)        (res-lump-float arg0 (quote bound-xmax)))",
            "  (set! (-> this ymin)        (res-lump-float arg0 (quote bound-ymin)))",
            "  (set! (-> this ymax)        (res-lump-float arg0 (quote bound-ymax)))",
            "  (set! (-> this zmin)        (res-lump-float arg0 (quote bound-zmin)))",
            "  (set! (-> this zmax)        (res-lump-float arg0 (quote bound-zmax)))",
            "  (set! (-> this inside)      #f)",
            "  (let* ((hx (* 0.5 (- (-> this xmax) (-> this xmin))))",
            "         (hy (* 0.5 (- (-> this ymax) (-> this ymin))))",
            "         (hz (* 0.5 (- (-> this zmax) (-> this zmin)))))",
            "    (set! (-> this cull-radius) (sqrtf (+ (* hx hx) (* hy hy) (* hz hz)))))",
            "  (format 0 \"[vol-trigger] armed -> ~A~%\" (-> this target-name))",
            "  (go vol-trigger-active)",
            "  (none))",
            "",
        ]
        log(f"  [write_gc] vol-trigger type embedded")

    if has_fog_override and scene is not None:
        # Bake panel values into GOAL constants.  fog_color stored 0..1 in
        # Blender props; *fog-color* expects 0..255 byte channels.  fog_max
        # also 0..1 in panel; *math-camera*.fog-max is 0..255 internally.
        _fog_r     = float(_get_level_prop(scene, "og_fog_color", (0.376, 0.502, 0.627))[0]) * 255.0
        _fog_g     = float(_get_level_prop(scene, "og_fog_color", (0.376, 0.502, 0.627))[1]) * 255.0
        _fog_b     = float(_get_level_prop(scene, "og_fog_color", (0.376, 0.502, 0.627))[2]) * 255.0
        _fog_start = float(_get_level_prop(scene, "og_fog_start", 25.0))
        _fog_end   = float(_get_level_prop(scene, "og_fog_end",   200.0))
        _fog_max   = float(_get_level_prop(scene, "og_fog_max",   0.95)) * 255.0
        _fog_min   = float(_get_level_prop(scene, "og_fog_min",   0.10))
        lines += [
            ";; fog-control: per-frame override of *math-camera* fog values.",
            ";; Values are baked at export from the Lighting panel — to change them,",
            ";; tweak the panel and re-export.  Tracks player position each frame so",
            ";; it never gets culled out of birth-distance.",
            "(deftype fog-control (process-drawable)",
            "  ()",
            "  (:states fog-control-active))",
            "",
            "(defstate fog-control-active (fog-control)",
            "  :code",
            "  (behavior ()",
            "    (loop",
            "      ;; Track the player so we never leave birth-dist.",
            "      (when *target*",
            "        (set! (-> self root trans quad) (-> *target* control trans quad)))",
            "      ;; Override math-camera fog values.",
            f"      (set! (-> *math-camera* fog-start) (meters {_fog_start:.3f}))",
            f"      (set! (-> *math-camera* fog-end)   (meters {_fog_end:.3f}))",
            f"      (set! (-> *math-camera* fog-max)   {_fog_max:.3f})",
            f"      (set! (-> *math-camera* fog-min)   {_fog_min:.3f})",
            f"      (set! (-> *fog-color* r) {_fog_r:.3f})",
            f"      (set! (-> *fog-color* g) {_fog_g:.3f})",
            f"      (set! (-> *fog-color* b) {_fog_b:.3f})",
            "      (suspend))))",
            "",
            "(defmethod init-from-entity! ((this fog-control) (arg0 entity-actor))",
            "  (set! (-> this root) (new (quote process) (quote trsqv)))",
            "  (process-drawable-from-entity! this arg0)",
            "  (format 0 \"[fog-control] armed (start ~Mm end ~Mm)~%\""
            f" (-> *math-camera* fog-start) (-> *math-camera* fog-end))",
            "  (go fog-control-active)",
            "  (none))",
            "",
        ]
        log(f"  [write_gc] fog-control type embedded "
            f"(start={_fog_start:.1f} end={_fog_end:.1f} "
            f"max={_fog_max:.1f} min={_fog_min:.2f} "
            f"rgb=({_fog_r:.0f},{_fog_g:.0f},{_fog_b:.0f}))")

    # ── Custom GOAL code injection ────────────────────────────────────────
    # Scan all ACTOR_ empties in the scene for text blocks assigned via
    # og_goal_code_ref.  Deduplicate by text block name so shared blocks are
    # only emitted once.  Each block is appended verbatim after the addon's
    # own generated types.
    if scene is not None:
        seen_blocks   = set()
        custom_blocks = []
        for obj in _level_objects(scene):
            if not (obj.type == "EMPTY"
                    and obj.name.startswith("ACTOR_")
                    and "_wp_" not in obj.name
                    and "_wpb_" not in obj.name):
                continue
            ref = getattr(obj, "og_goal_code_ref", None)
            if ref is None:
                continue
            txt = ref.text_block
            if txt is None or not ref.enabled:
                continue
            if txt.name in seen_blocks:
                continue
            seen_blocks.add(txt.name)
            custom_blocks.append((txt.name, txt.as_string()))

        if custom_blocks:
            lines += [
                "",
                f";; --- custom GOAL code ({len(custom_blocks)} block(s)) ---",
            ]
            for block_name, block_code in custom_blocks:
                lines += [
                    "",
                    f";; block: {block_name}",
                    "",
                ]
                lines += block_code.splitlines()
            log(f"  [write_gc] injected {len(custom_blocks)} custom GOAL code block(s): "
                f"{', '.join(n for n, _ in custom_blocks)}")

    new_text = "\n".join(lines)
    if p.exists() and p.read_text() == new_text:
        log(f"Skipped {p} (unchanged)")
    else:
        p.write_text(new_text)
        log(f"Wrote {p}")

def write_jsonc(name, actors, ambients, camera_actors=None, base_id=10000, scene=None):
    d = _ldir(name); d.mkdir(parents=True, exist_ok=True)
    all_actors = list(actors) + (camera_actors or [])
    ags = needed_ags(actors)  # camera-tracker has no art group, so only scan regular actors
    data = {
        "long_name": name, "iso_name": _iso(name), "nickname": _effective_nick(scene, name),
        "gltf_file": f"custom_assets/jak1/levels/{name}/{name}.glb",
        "automatic_wall_detection": True, "automatic_wall_angle": 45.0,
        "double_sided_collide": False, "base_id": base_id,
        "art_groups": [g.replace(".go","") for g in ags],
        "custom_models": [], "textures": [["village1-vis-alpha"]],
        "tex_remap": "village1", "sky": "village1", "tpages": [],
        "ambients": ambients, "actors": all_actors,
    }
    p = d / f"{name}.jsonc"
    new_text = f"// OpenGOAL custom level: {name}\n" + json.dumps(data, indent=2)
    if p.exists() and p.read_text() == new_text:
        log(f"Skipped {p} (unchanged)")
    else:
        p.write_text(new_text)
        log(f"Wrote {p}  ({len(actors)} actors + {len(camera_actors or [])} cameras)")

def write_gd(name, ags, code_deps, tpages=None, scene=None, extras_ags=None):
    """Write .gd file.

    code_deps is a list of (o_file, gc_path, dep) from needed_code().
    Each enemy .o is inserted before the art groups so it links first.

    ags          — entity-own art groups (from needed_ags). Drives DGO bundling
                   AND the JSONC art_groups field (which controls merc extraction
                   in goalc's build_level).
    extras_ags   — extra art groups Jak/target needs bundled (from
                   needed_extras_ags). DGO-only — NEVER goes in the JSONC
                   because build_level.cpp's find_art_groups would then try to
                   extract merc data from them and animation-only +0-ag files
                   have none. Bundled at the end of the file list so they link
                   after entity art (order doesn't matter for the loader, but
                   keeping vanilla-like ordering helps readability).

    FIX v0.5.0 (Bug 1): The opening paren for the inner file list is now its
    own line so that the first file entry keeps correct indentation.  The old
    code concatenated ' (' + files[0].lstrip() which produced a malformed
    S-expression when enemy .o entries were present and caused GOALC to crash.

    FIX (vis-nick): DGO name (e.g. MYL.DGO) and on-disk .gd filename now honor
    og_vis_nick_override, so two levels with colliding auto-derived nicks
    (e.g. my-level and my-level2 both auto-derive to 'myl') can build
    alongside each other. Also sweeps stale .gd siblings from previous
    exports with a different nick — leaving them in place causes the build
    to see two .gd files producing the same DGO and abort with
    'multiple ways to make output'.
    """
    d = _ldir(name); d.mkdir(parents=True, exist_ok=True)
    nick     = _effective_nick(scene, name)
    dgo_name = f"{nick.upper()}.DGO"
    code_o   = [f'  "{o}"' for o, _, _ in code_deps]
    # Global (always-loaded) tpages — e.g. the Village1 sky tpages
    # [398,400,399,401,1470] — must NOT be baked into a level DGO. The engine
    # keeps them resident at all times and build-level auto-logins them from the
    # level's textures, so the level still gets them. Baking them duplicates the
    # tpage object: a single level tolerates the duplicate, but two co-resident
    # custom levels crash when the second re-links an already-loaded tpage
    # (segfault right after <name>-obs, on tpage-398). So exclude every global
    # tpage from the DGO file list.
    level_tpages = [f'  "{tp}"' for tp in (tpages or [])
                    if tp not in GLOBAL_TPAGE_GOS]
    extras_lines = [f'  "{g}"' for g in (extras_ags or [])]
    files = (
        [f'  "{name}-obs.o"']
        + code_o
        + level_tpages
        + [f'  "{g}"' for g in ags]
        + extras_lines
        + [f'  "{name}.go"']
    )
    lines = (
        [f';; DGO for {name}', f'("{dgo_name}"', ' (']
        + files
        + ['  )', ' )']
    )
    p = d / f"{nick}.gd"
    # Sweep stale .gd siblings left by previous exports with a different nick.
    for stale in d.glob("*.gd"):
        if stale.name != p.name:
            try:
                stale.unlink()
                log(f"Removed stale {stale}")
            except OSError as e:
                log(f"WARNING: could not remove stale {stale}: {e}")
    new_text = "\n".join(lines) + "\n"
    if not p.exists() or p.read_text() != new_text:
        p.write_text(new_text)
        log(f"Wrote {p}  (enemy .o files: {[o for o,_,_ in code_deps]})")
    else:
        log(f"Skipped {p} (unchanged)")

def _make_continues(name, spawns):
    """Build the GOAL :continues list for level-load-info.

    Each spawn dict carries full quat + camera data from collect_spawns, plus
    per-checkpoint continue-point settings (cp_lev0/disp0/lev1/disp1/vis_nick/
    flags/load_commands). Spawns include both SPAWN_ (primary) and CHECKPOINT_
    empties.

    Defaults preserve a working single-level checkpoint: lev0 = this level
    (displayed), lev1 = none, vis-nick = this level's nickname.

    vis-nick: defaults to the level nickname (NOT 'none). Per Kuitar, vis is
    also how the engine tracks which level you're "in" (music / which menu
    opens), so a real nick is wanted even though custom levels lack vis BSP
    data. Override per-checkpoint via the Vis Nickname field.
    """
    def _lev(val):
        v = (val or "").strip()
        if v in ("", "none", "#f"):
            return "#f"
        if v == "self":
            return f"'{name}"
        return f"'{v}"

    def _disp(val, lev_sym):
        if lev_sym == "#f":
            return "#f"
        v = (val or "").strip()
        if v in ("", "off", "#f"):
            return "#f"
        return f"'{v}"            # 'display or 'special

    def cp(sp):
        cr = sp.get("cam_rot", [1,0,0, 0,1,0, 0,0,1])
        cr_str = " ".join(str(v) for v in cr)
        # Resident-level slots. lev0 should always name a level (respawn needs
        # the home level at minimum); "self"/blank → this level.
        lev0 = _lev(sp.get("cp_lev0", "self"))
        if lev0 == "#f":
            lev0 = f"'{name}"
        lev1  = _lev(sp.get("cp_lev1", "none"))
        disp0 = _disp(sp.get("cp_disp0", "display"), lev0)
        disp1 = _disp(sp.get("cp_disp1", "off"),     lev1)
        # vis-nick: blank → this level's nickname. Per Kuitar, vis is also how
        # the game knows which level you're in (music/menu), so don't use 'none.
        vn = (sp.get("cp_vis_nick") or "").strip()
        vis_nick = f"'{vn}" if vn else f"'{_nick(name)}"
        # load-commands: blank → empty list; else raw GOAL passthrough.
        lc = (sp.get("cp_load_commands") or "").strip()
        load_cmds = lc if lc else "'()"
        # flags: optional continue-flags passthrough (advanced).
        fl = (sp.get("cp_flags") or "").strip()
        flags_line = f"             :flags (continue-flags {fl})\n" if fl else ""
        return (f"(new 'static 'continue-point\n"
                f"             :name \"{name}-{sp['name']}\"\n"
                f"             :level '{name}\n"
                f"{flags_line}"
                f"             :trans (new 'static 'vector"
                f" :x (meters {sp['x']:.4f}) :y (meters {sp['y']:.4f}) :z (meters {sp['z']:.4f}) :w 1.0)\n"
                f"             :quat (new 'static 'quaternion"
                f" :x {sp.get('qx',0.0)} :y {sp.get('qy',0.0)} :z {sp.get('qz',0.0)} :w {sp.get('qw',1.0)})\n"
                f"             :camera-trans (new 'static 'vector"
                f" :x (meters {sp.get('cam_x', sp['x']):.4f})"
                f" :y (meters {sp.get('cam_y', sp['y']+4.0):.4f})"
                f" :z (meters {sp.get('cam_z', sp['z']):.4f}) :w 1.0)\n"
                f"             :camera-rot (new 'static 'array float 9 {cr_str})\n"
                f"             :load-commands {load_cmds}\n"
                f"             :vis-nick {vis_nick}\n"
                f"             :lev0 {lev0}\n"
                f"             :disp0 {disp0}\n"
                f"             :lev1 {lev1}\n"
                f"             :disp1 {disp1})")

    if spawns:
        return "'(" + "\n             ".join(cp(s) for s in spawns) + ")"

    # No spawns placed — emit a safe default at origin + 10m up
    return (f"'((new 'static 'continue-point\n"
            f"             :name \"{name}-start\"\n"
            f"             :level '{name}\n"
            f"             :trans (new 'static 'vector :x 0.0 :y (meters 10.) :z 0.0 :w 1.0)\n"
            f"             :quat (new 'static 'quaternion :w 1.0)\n"
            f"             :camera-trans (new 'static 'vector :x 0.0 :y (meters 14.) :z 0.0 :w 1.0)\n"
            f"             :camera-rot (new 'static 'array float 9 1.0 0.0 0.0 0.0 1.0 0.0 0.0 0.0 1.0)\n"
            f"             :load-commands '()\n"
            f"             :vis-nick '{_nick(name)}\n"
            f"             :lev0 '{name}\n"
            f"             :disp0 'display\n"
            f"             :lev1 #f\n"
            f"             :disp1 #f))")

def patch_level_info(name, spawns, scene=None):
    p = _level_info()
    if not p.exists(): log(f"WARNING: {p} not found"); return
    # Audio settings from scene props (if scene provided)
    if scene is not None:
        # Lazy-migrate: give any old levels missing og_level_index a unique value
        _migrate_all_level_indices(scene)
        _bank      = str(_get_level_prop(scene, "og_music_bank",    "none") or "none")
        _music_val = f"'{_bank}" if _bank and _bank != "none" else "#f"
        _sb1       = str(_get_level_prop(scene, "og_sound_bank_1",  "none") or "none")
        _sb2       = str(_get_level_prop(scene, "og_sound_bank_2",  "none") or "none")
        _sb_list   = [s for s in [_sb1, _sb2] if s and s != "none"]
        _sbanks    = " ".join(_sb_list)
        _sbanks_val = f"'({_sbanks})" if _sbanks else "'()"
        _bot_h     = float(_get_level_prop(scene, "og_bottom_height", -20.0))
        _vis_ov    = str(_get_level_prop(scene, "og_vis_nick_override", "") or "").strip()
        _vnick     = _vis_ov if _vis_ov else _nick(name)
        _lindex    = int(_get_level_prop(scene, "og_level_index", 100))
        # Lighting (mood + sky)
        _mood      = str(_get_level_prop(scene, "og_mood", "village1") or "village1")
        _sky_bool  = bool(_get_level_prop(scene, "og_sky", True))
    else:
        _music_val = "#f"
        _sbanks_val = "'()"
        _bot_h   = -20.0
        _vnick   = _nick(name)
        _lindex  = 100
        _mood    = "village1"
        _sky_bool = True
    _mood_func = MOOD_FUNC_OVERRIDES.get(_mood, _mood)
    _sky_val   = "#t" if _sky_bool else "#f"

    # ── Auto-compute bsphere from spawn positions ────────────────────────────
    # Centre = mean of all spawn XZ positions, Y = mean spawn Y + 2m.
    # Radius = max distance from centre to any spawn + 64m padding so the
    # engine considers the level "nearby" well before the player reaches it.
    # Fallback when no spawns: a very large sphere (40km radius) that always passes.
    if spawns:
        xs  = [s["x"] for s in spawns]
        ys  = [s["y"] for s in spawns]
        zs  = [s["z"] for s in spawns]
        cx  = sum(xs) / len(xs)
        cy  = sum(ys) / len(ys) + 2.0
        cz  = sum(zs) / len(zs)
        r   = max(
            math.sqrt((s["x"]-cx)**2 + (s["y"]-cy)**2 + (s["z"]-cz)**2)
            for s in spawns
        ) + 64.0
        # Convert to game units (4096 per metre) for the sphere :w value
        bsphere_w = round(r * 4096.0, 1)
        bsphere_str = (f"(new 'static 'sphere"
                       f" :x {round(cx*4096.0, 1)} :y {round(cy*4096.0, 1)} :z {round(cz*4096.0, 1)}"
                       f" :w {bsphere_w})")
    else:
        bsphere_str = "(new 'static 'sphere :w 167772160000.0)"  # ~40km radius

    block = (f"\n(define {name}\n"
             f"  (new 'static 'level-load-info\n"
             f"       :index {_lindex}\n"
             f"       :name '{name}\n"
             f"       :visname '{name}-vis\n"
             f"       :nickname '{_vnick}\n"
             f"       :packages '()\n"
             f"       :sound-banks {_sbanks_val}\n"
             f"       :music-bank {_music_val}\n"
             f"       :ambient-sounds '()\n"
             f"       :mood '*{_mood}-mood*\n"
             f"       :mood-func 'update-mood-{_mood_func}\n"
             f"       :ocean #f\n"
             f"       :sky {_sky_val}\n"
             f"       :sun-fade 1.0\n"
             f"       :continues\n"
             f"       {_make_continues(name, spawns)}\n"
             f"       :tasks '()\n"
             f"       :priority 100\n"
             f"       :load-commands '()\n"
             f"       :alt-load-commands '()\n"
             f"       :bsp-mask #xffffffffffffffff\n"
             f"       :bsphere {bsphere_str}\n"
             f"       :bottom-height (meters {_bot_h:.1f})\n"
             f"       :run-packages '()\n"
             f"       :wait-for-load #t))\n"
             f"\n(cons! *level-load-list* '{name})\n")
    txt = p.read_text(encoding="utf-8")
    txt = re.sub(rf"\n\(define {re.escape(name)}\b.*?\(cons!.*?'{re.escape(name)}\)\n",
                 "", txt, flags=re.DOTALL)
    marker = ";;;;; CUSTOM LEVELS"
    new_txt = (txt.replace(marker, marker+block, 1) if marker in txt
               else txt + "\n;;;;; CUSTOM LEVELS\n" + block)
    original = p.read_text(encoding="utf-8")
    if new_txt != original:
        p.write_text(new_txt, encoding="utf-8")
        log("Patched level-info.gc")
    else:
        log("Skipped level-info.gc (unchanged)")


# ---------------------------------------------------------------------------
# Load boundaries  (feature/load-boundaries-checkpoints — Task 2)
# ---------------------------------------------------------------------------
# Boundaries are static data, not runtime entities. The engine's
# load-boundary-data.gc defines *static-load-boundary-list* via the
# static-lb-list / static-load-boundary macros, then runs
#   (doarray (i ...) (load-boundary-from-template (the-as (array object) i)))
# to build runtime boundaries into *load-boundary-list*. This is exactly what
# the in-game editor (---lb-save) regenerates and what shipped mods edit.
#
# Rather than splice into the stock static-lb-list, we append our own managed
# per-level block (its own static-lb-list + doarray). Stock entries untouched;
# idempotent re-export via per-level markers.

def _lb_cmd_form(cmd, lev0, lev1, disp, name, level):
    """Return the GOAL (cmd a1 a2) form for a boundary direction, or None.

    Level args are emitted as BARE symbols (the macro quotes the whole list).
    "self" -> this level, ""/"none" -> #f.
    """
    def _sym(v):
        v = (v or "").strip()
        if v in ("", "none", "#f"):
            return "#f"
        if v == "self":
            return level
        return v
    cmd = (cmd or "none").strip()
    if cmd in ("", "none", "invalid"):
        return None
    if cmd == "load":
        return f"(load {_sym(lev0)} {_sym(lev1)})"
    if cmd == "display":
        d = (disp or "").strip()
        d = "#f" if d in ("", "off", "#f") else d           # display / display-no-wait
        return f"(display {_sym(lev0)} {d})"
    if cmd == "vis":
        nick = (name or "").strip() or _nick(level)
        return f"(vis {nick} #f)"
    if cmd == "force-vis":
        return f"(force-vis {_sym(lev0)} #t)"
    if cmd == "checkpt":
        cn = (name or "").strip()
        return f'(checkpt "{cn}" #f)'
    return None


def _make_static_boundary(b, level):
    """One (static-load-boundary ...) form from a collected boundary dict.

    b keys: closed(bool), player(bool), custom_flags(str), top, bot (game units),
            points (flat list of game-unit floats x0 z0 x1 z1 ...),
            fwd_*/bwd_* command fields.
    """
    flags = []
    if b.get("player", True):
        flags.append("player")
    if b.get("closed", False):
        flags.append("closed")
    cf = (b.get("custom_flags") or "").strip()
    if cf:
        flags.extend(cf.split())
    flags_str = " ".join(flags)

    pts = " ".join(f"{v:.4f}" for v in b.get("points", []))

    fwd = _lb_cmd_form(b.get("fwd_cmd"), b.get("fwd_lev0"), b.get("fwd_lev1"),
                       b.get("fwd_disp"), b.get("fwd_name"), level)
    bwd = _lb_cmd_form(b.get("bwd_cmd"), b.get("bwd_lev0"), b.get("bwd_lev1"),
                       b.get("bwd_disp"), b.get("bwd_name"), level)

    lines = [f"(static-load-boundary :flags ({flags_str})",
             f"                      :top {b.get('top', 524288.0):.4f}"
             f" :bot {b.get('bot', -524288.0):.4f}",
             f"                      :points ({pts})"]
    if fwd:
        lines.append(f"                      :fwd {fwd}")
    if bwd:
        lines.append(f"                      :bwd {bwd}")
    return "\n          ".join(lines) + ")"


_LB_BEGIN = ";; ===== OG CUSTOM BOUNDARIES: {n} ====="
_LB_END   = ";; ===== END OG CUSTOM BOUNDARIES: {n} ====="

def patch_load_boundaries(name, boundaries, scene=None):
    """Insert/replace this level's load boundaries in load-boundary-data.gc.

    Appends a managed block (own static-lb-list + doarray) keyed by level name.
    Empty `boundaries` removes the block. Stock entries are never touched.
    """
    p = _load_boundary_data()
    if not p.exists():
        log(f"WARNING: {p} not found — skipping load boundaries")
        return
    txt = p.read_text(encoding="utf-8")

    begin = _LB_BEGIN.format(n=name)
    end   = _LB_END.format(n=name)
    # Strip any existing block for this level.
    txt = re.sub(rf"\n{re.escape(begin)}.*?{re.escape(end)}\n", "\n", txt, flags=re.DOTALL)

    if boundaries:
        entries = "\n        ".join(_make_static_boundary(b, name) for b in boundaries)
        sym = "*og-custom-lb-" + re.sub(r"[^a-z0-9-]", "-", name.lower()) + "*"
        # Match the stock pattern: define a named static list, then doarray over
        # the symbol. doarray substitutes its array arg multiple times, so it
        # must be a variable, not an inline (static-lb-list ...) expression.
        block = (f"\n{begin}\n"
                 f"(define {sym}\n"
                 f"  (static-lb-list\n        {entries}))\n"
                 f"(doarray (i {sym}) (load-boundary-from-template (the-as (array object) i)))\n"
                 f"{end}\n")
        txt = txt.rstrip() + "\n" + block

    original = p.read_text(encoding="utf-8")
    if txt != original:
        p.write_text(txt, encoding="utf-8")
        log(f"Patched load-boundary-data.gc ({len(boundaries)} boundaries for {name})")
    else:
        log("Skipped load-boundary-data.gc (unchanged)")


def patch_game_gp(name, code_deps=None, scene=None):
    """Patch game.gp to build our custom level and compile enemy code files.

    code_deps: list of (o_file, gc_path, dep) from needed_code().
    For each enemy type not in GAME.CGO we add a goal-src line so GOALC
    compiles and links its code into our DGO.  Without this the type is
    undefined at runtime and the entity spawns as a do-nothing process.

    FIX (vis-nick): the DGO name and .gd path referenced from game.gp now
    honor og_vis_nick_override so multi-level blends with colliding
    auto-derived nicks build cleanly.
    """
    p = _game_gp()
    if not p.exists(): log(f"WARNING: {p} not found"); return
    raw  = p.read_bytes()
    crlf = b"\r\n" in raw
    txt  = raw.decode("utf-8").replace("\r\n", "\n")
    nick = _effective_nick(scene, name)
    dgo  = f"{nick.upper()}.DGO"

    # goal-src lines for enemy code (de-duplicated)
    # Skip o_only entries (gc=None) — vanilla game.gp already has their goal-src lines.
    extra_goal_src = ""
    if code_deps:
        seen_gc = set()
        for o, gc, dep in code_deps:
            if gc is None:
                continue  # o_only: .o injected into DGO but no goal-src needed
            if gc not in seen_gc:
                seen_gc.add(gc)
                extra_goal_src += f'(goal-src "{gc}" "{dep}")\n'

    correct_block = (
        f'(build-custom-level "{name}")\n'
        f'(custom-level-cgo "{dgo}" "{name}/{nick}.gd")\n'
        f'(goal-src "levels/{name}/{name}-obs.gc" "process-drawable")\n'
        + extra_goal_src
    )

    # Strip any previously written block for this level
    txt = re.sub(r'\(build-custom-level "' + re.escape(name) + r'"\)\n', '', txt)
    txt = re.sub(r'\(custom-level-cgo "[^"]*" "' + re.escape(name) + r'/[^"]+"\)\n', '', txt)
    # FIX v0.5.0 (Bug 2): was r'/[^"]+\"[^)]*\)' — the \" was a literal
    # backslash+quote so the regex never matched, leaving stale goal-src lines
    # in game.gp across exports which caused duplicate-compile crashes in GOALC.
    txt = re.sub(r'\(goal-src "levels/' + re.escape(name) + r'/[^"]+"[^)]*\)\n', '', txt)
    # Strip ALL enemy goal-src lines that could have been injected by any previous export.
    # This catches leftover entries even if the dep changed between exports.
    # We match any goal-src line whose path matches a known ETYPE_CODE gc file.
    for _etype_info in ETYPE_CODE.values():
        _gc = _etype_info.get("gc", "")
        if _gc:
            txt = re.sub(r'\(goal-src "' + re.escape(_gc) + r'"[^)]*\)\n', '', txt)

    if correct_block in txt:
        log("game.gp already correct"); return

    for anchor in ['(build-custom-level "test-zone")', '(group-list "all-code"']:
        if anchor in txt:
            txt = txt.replace(anchor, correct_block + "\n" + anchor, 1)
            break
    else:
        txt += "\n" + correct_block

    if crlf:
        txt = txt.replace("\n", "\r\n")
    p.write_bytes(txt.encode("utf-8"))
    log(f"Patched game.gp  (extra goal-src: {[gc for _,gc,_ in (code_deps or []) if gc is not None]})")

def export_glb(ctx, name):
    d = _ldir(name); d.mkdir(parents=True, exist_ok=True)

    level_col = _active_level_col(ctx.scene)
    if level_col is not None:
        # Collection mode — export only objects inside the Geometry sub-collection,
        # excluding anything under the Reference sub-collection (og_no_export=True).
        # We select only those objects, export with use_selection=True, then restore.
        geo_col = None
        for c in level_col.children:
            if c.name == "Geometry":
                geo_col = c
                break

        # Gather exportable objects: meshes in Geometry (and its children) except Reference
        if geo_col is not None:
            export_objs = _recursive_col_objects(geo_col, exclude_no_export=True)
            export_objs = [o for o in export_objs if o.type == "MESH"]
        else:
            # No Geometry sub-collection yet — fall back to all meshes in the level.
            # Exclude WATER_ volumes (invisible helpers, not renderable geometry).
            _HELPER_PREFIXES = ("WATER_", "VOL_", "CPVOL_", "NAVMESH_", "LOADBND_")
            export_objs = [o for o in _recursive_col_objects(level_col, exclude_no_export=True)
                           if o.type == "MESH"
                           and not any(o.name.startswith(p) for p in _HELPER_PREFIXES)
                           and not o.get("og_preview_mesh")
                           and not o.get("og_waypoint_preview_mesh")]

        # Save selection state
        prev_active    = ctx.view_layer.objects.active
        prev_selected  = [o for o in ctx.scene.objects if o.select_get()]

        # Deselect all, select export targets
        for o in ctx.scene.objects:
            o.select_set(False)
        for o in export_objs:
            o.select_set(True)
        if export_objs:
            ctx.view_layer.objects.active = export_objs[0]

        bpy.ops.export_scene.gltf(
            filepath=str(d / f"{name}.glb"), export_format="GLB",
            export_vertex_color="ACTIVE", export_normals=True,
            export_materials="EXPORT", export_texcoords=True,
            export_apply=True, use_selection=True,
            export_yup=True, export_skins=False, export_animations=False,
            export_extras=True)

        # Restore selection state
        for o in ctx.scene.objects:
            o.select_set(False)
        for o in prev_selected:
            o.select_set(True)
        ctx.view_layer.objects.active = prev_active

    else:
        # Fallback: v1.1.0 behaviour — export entire scene, but exclude preview meshes
        prev_active   = ctx.view_layer.objects.active
        prev_selected = [o for o in ctx.scene.objects if o.select_get()]

        # Select everything except og_preview_mesh objects
        for o in ctx.scene.objects:
            o.select_set(False)
        export_objs = [o for o in ctx.scene.objects
                       if o.type == "MESH" and not o.get("og_preview_mesh")
                       and not o.name.startswith("LOADBND_")]
        for o in export_objs:
            o.select_set(True)
        if export_objs:
            ctx.view_layer.objects.active = export_objs[0]

        bpy.ops.export_scene.gltf(
            filepath=str(d / f"{name}.glb"), export_format="GLB",
            export_vertex_color="ACTIVE", export_normals=True,
            export_materials="EXPORT", export_texcoords=True,
            export_apply=True, use_selection=True,
            export_yup=True, export_skins=False, export_animations=False,
            export_extras=True)

        for o in ctx.scene.objects:
            o.select_set(False)
        for o in prev_selected:
            o.select_set(True)
        ctx.view_layer.objects.active = prev_active

    log("Exported GLB")
