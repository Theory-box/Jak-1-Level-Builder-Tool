# audit.py — Level Audit checks for the OpenGOAL Blender addon.
#
# HOW TO EXTEND THIS SYSTEM
# ──────────────────────────
# 1. New actor type (standard requirements):
#    Add an "audit" block to its ENTITY_DEFS entry in data.py:
#
#      "my-actor": {
#          ...,
#          "audit": {
#              "requires_navmesh":  False,
#              "requires_path":     False,
#              "requires_pathb":    False,
#              "required_links":    [],      # lump_key strings
#              "custom_checks":     [],      # callables: (scene, obj) -> (sev, msg) | None
#          }
#      }
#    run_audit() reads this automatically.
#
# 2. New structural dependency (new prefix, scene-level rule):
#    Add a function to _REGISTERED_CHECKS at the bottom of this file.

from . import db as _db
from .data import (
    ENTITY_DEFS,
    ACTOR_LINK_DEFS,
    _actor_link_slots,
    _actor_get_link,
)
from .collections import _level_objects

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _etype(o):
    if not (o.name.startswith("ACTOR_") and o.type == "EMPTY"):
        return None
    if "_wp_" in o.name or "_wpb_" in o.name:
        return None
    parts = o.name.split("_", 2)
    return parts[1] if len(parts) >= 2 else None

def _actor_objs(scene):
    return [o for o in _level_objects(scene)
            if o.name.startswith("ACTOR_") and o.type == "EMPTY"
            and "_wp_" not in o.name and "_wpb_" not in o.name]

def _vol_objs(scene):
    return [o for o in _level_objects(scene)
            if o.type == "MESH" and o.name.startswith("VOL_")]

def _spawn_objs(scene):
    """The level's "start" checkpoint(s)."""
    from .collections import spawn_uid
    return [o for o in _level_objects(scene)
            if o.name.startswith("CHECKPOINT_") and o.type == "EMPTY"
            and not o.name.endswith("_CAM") and spawn_uid(o) == "start"]

def _checkpoint_objs(scene):
    return [o for o in _level_objects(scene)
            if o.name.startswith("CHECKPOINT_") and o.type == "EMPTY"]

def _camera_objs(scene):
    return [o for o in _level_objects(scene)
            if o.name.startswith("CAMERA_") and o.type == "CAMERA"]

def _issue(severity, message, obj_name=None):
    return {"severity": severity, "message": message, "obj_name": obj_name}


# ---------------------------------------------------------------------------
# Check 2 — Nav-enemy navmesh links
# ---------------------------------------------------------------------------

def check_navmesh_links(scene):
    issues = []
    objects = scene.objects
    for o in _actor_objs(scene):
        et = _etype(o)
        if not et or not _db.nav_unsafe(et):
            continue
        nm_name = o.get("og_navmesh_link", "")
        src = _actor_get_link(o, "nav-mesh-actor", 0)
        if not nm_name and src:
            # nav-mesh copied from another actor: that one needs a navmesh
            t = objects.get(src.target_name)
            if t is None or not (t.get("og_navmesh_link", "") or _actor_get_link(t, "nav-mesh-actor", 0)):
                issues.append(_issue("ERROR",
                    f"'{o.name}' ({et}) uses the nav-mesh of '{src.target_name}', "
                    "which has no navmesh link.", o.name))
        elif not nm_name:
            issues.append(_issue("ERROR",
                f"Nav-enemy '{o.name}' ({et}) has no navmesh link. "
                "It will freeze or crash in-game without one.", o.name))
        elif objects.get(nm_name) is None:
            issues.append(_issue("ERROR",
                f"Nav-enemy '{o.name}' ({et}) navmesh link '{nm_name}' "
                "does not exist in the scene.", o.name))
    return issues


# ---------------------------------------------------------------------------
# Check 3 — Missing required path waypoints
# ---------------------------------------------------------------------------

def check_missing_paths(scene):
    """Required paths (required.py, shared with the panels' warnings)."""
    from .required import missing
    issues = []
    for o in _actor_objs(scene):
        for m in missing(o, scene):
            if m["panel"] == "path":
                issues.append(_issue("ERROR",
                    f"'{o.name}' ({_etype(o)}) requires a {m['key']} path but has none.", o.name))
    return issues


# ---------------------------------------------------------------------------
# Check 4 — Actor link slots (required unset + broken targets)
# ---------------------------------------------------------------------------

def check_actor_links(scene):
    issues = []
    objects = scene.objects
    for o in _actor_objs(scene):
        et = _etype(o)
        if not et:
            continue
        from .required import missing
        for m in missing(o, scene):         # shared with the panels' warnings
            if m["panel"] == "links":
                issues.append(_issue("WARNING",
                    f"'{o.name}' ({et}): required link slot '{m['key']}' is unset.",
                    o.name))
        slots = list(_actor_link_slots(et))
        for lk in getattr(o, "og_actor_links", []):
            if not lk.target_name.strip():
                continue
            tgt = objects.get(lk.target_name)
            if tgt is None:
                issues.append(_issue("ERROR",
                    f"'{o.name}' ({et}): link '{lk.lump_key}' points to "
                    f"'{lk.target_name}' which does not exist.", o.name))
                continue
            # the slot this entry belongs to (allow-multiple slots cover later indices)
            cand = [s for s in slots if s[0] == lk.lump_key and s[1] <= lk.slot_index]
            if not cand:
                continue
            accepts = max(cand, key=lambda s: s[1])[3]
            t_et = _etype(tgt) or ""
            if t_et and not _db.link_accepts(accepts, t_et):
                issues.append(_issue("WARNING",
                    f"'{o.name}' ({et}): link '{lk.lump_key}' → '{lk.target_name}' ({t_et}) is not an "
                    f"expected type ({_db.accepts_text(accepts)}). It may not work in game.", o.name))
    return issues


# ---------------------------------------------------------------------------
# Check 5 — Volume links
# ---------------------------------------------------------------------------

def check_volumes(scene):
    issues = []
    objects = scene.objects
    for vol in _vol_objs(scene):
        links = getattr(vol, "og_vol_links", [])
        if len(links) == 0 and not len(getattr(vol, "og_vol_task_actions", ())):
            issues.append(_issue("WARNING",
                f"Trigger volume '{vol.name}' has no links. "
                "It will export as dead weight.", vol.name))
            continue
        for lk in links:
            target = lk.target_name.strip()
            if not target:
                issues.append(_issue("WARNING",
                    f"Volume '{vol.name}' has a link with an empty target name.", vol.name))
            elif objects.get(target) is None:
                issues.append(_issue("ERROR",
                    f"Volume '{vol.name}' links to '{target}' which does not exist.", vol.name))
    return issues


# ---------------------------------------------------------------------------
# Check 6 — Spawn points
# ---------------------------------------------------------------------------

def check_spawn_points(scene):
    issues = []
    spawns = _spawn_objs(scene)
    if len(spawns) == 0:
        issues.append(_issue("ERROR",
            "No checkpoint named \"start\". The level has no player start position "
            "(Build & Play spawns at <level>-start)."))
    return issues


# ---------------------------------------------------------------------------
# Check 7 — Duplicate actor names
# ---------------------------------------------------------------------------

def check_duplicate_names(scene):
    """Actors whose exported name clashes (the engine finds actors by name), and
    Blender ".001" copies (exported as "<etype>-0.001")."""
    import re
    from .collections import actor_lump_name
    issues = []
    seen = {}
    for o in _actor_objs(scene):
        seen.setdefault(actor_lump_name(o.name, scene), []).append(o.name)
        if re.search(r"\.\d{3,}$", o.name):
            issues.append(_issue("WARNING",
                f"'{o.name}' has a Blender copy name: rename it (or duplicate with Shift+D / the addon's Duplicate).",
                o.name))
    for lump, objs in seen.items():
        if len(objs) > 1:
            issues.append(_issue("ERROR",
                f"{len(objs)} actors export as '{lump}' ({', '.join(objs)}). "
                "The engine resolves actors by name — duplicates cause wrong-entity lookups.",
                objs[0]))
    return issues


# ---------------------------------------------------------------------------
# Check 8 — Camera targets in volumes
# ---------------------------------------------------------------------------

def check_camera_targets(scene):
    issues = []
    objects = scene.objects
    for vol in _vol_objs(scene):
        for lk in getattr(vol, "og_vol_links", []):
            target = lk.target_name.strip()
            if not target:
                continue
            obj = objects.get(target)
            if obj is None:
                continue  # caught by check_volumes
            if target.startswith("CAMERA_") and obj.type != "CAMERA":
                issues.append(_issue("WARNING",
                    f"Volume '{vol.name}' links to '{target}' "
                    "which is named like a camera but is not a Camera object.", vol.name))
    return issues


# ---------------------------------------------------------------------------
# Check 9 — Door system checks (v1.7.0)
# ---------------------------------------------------------------------------

def _is_eco_door(et):
    """eco-door and its children (DB parent tree, not a list)."""
    return et == "eco-door" or any(r.get("etype") == "eco-door" for r in _db.parent_chain(et))

def check_doors(scene):
    issues  = []
    objects = scene.objects
    actors  = _actor_objs(scene)

    # Build set of basebutton names that ARE targeted by a door's state-actor
    used_buttons = set()
    for o in actors:
        et = _etype(o)
        if not _is_eco_door(et):
            continue
        link = _actor_get_link(o, "state-actor", 0)
        if link and link.target_name.strip():
            used_buttons.add(link.target_name.strip())

    for o in actors:
        et = _etype(o)
        if not et:
            continue

        # eco-door family: state-actor target should be a basebutton
        if _is_eco_door(et):
            link = _actor_get_link(o, "state-actor", 0)
            target_name = link.target_name.strip() if link else ""
            if target_name:
                try:
                    target_obj = objects.get(target_name)
                except Exception:
                    target_obj = None
                if target_obj:
                    target_et = _etype(target_obj)
                    if target_et and target_et != "basebutton":
                        issues.append(_issue("INFO",
                            f"'{o.name}' ({et}): state-actor target '{target_name}' "
                            f"is a '{target_et}', not a basebutton. "
                            "This can work but basebutton is the standard controller.",
                            o.name))

        # launcherdoor: needs a continue-name pointing to a real checkpoint
        if et == "launcherdoor":
            cp_name = str(o.get("og_continue_name", "")).strip()
            if not cp_name:
                issues.append(_issue("WARNING",
                    f"'{o.name}' (launcherdoor) has no continue-name set. "
                    "The door won't know which checkpoint to activate when opened.",
                    o.name))
            else:
                # checkpoints export as "<level>-<uid>" (CHECKPOINT_<uid>)
                lvl = str(scene.get("og_level_name", "") or getattr(scene.og_props, "level_name", "")).strip().lower()
                from .collections import spawn_uid
                cps = {spawn_uid(o) for o in objects if o.name.startswith("CHECKPOINT_")}
                ok = (cp_name in cps or any(cp_name == f"{lvl}-{u}" for u in cps)
                      or any(cp_name.endswith("-" + u) for u in cps) or objects.get(cp_name) is not None)
                if not ok:
                    issues.append(_issue("ERROR",
                        f"'{o.name}' (launcherdoor) continue-name '{cp_name}' "
                        "does not exist in the scene.", o.name))

        # basebutton: warn if nothing is listening to it
        if et == "basebutton":
            if o.name not in used_buttons and not _actor_get_link(o, "alt-actor", 0)                     and not _actor_get_link(o, "next-actor", 0) and not _actor_get_link(o, "prev-actor", 0):
                issues.append(_issue("WARNING",
                    f"'{o.name}' (basebutton) has no notify actor or chain and no door uses it "
                    "as state-actor. The button will animate but trigger nothing.",
                    o.name))

    return issues


# ---------------------------------------------------------------------------
# Check 10 — Data-driven custom_checks from ENTITY_DEFS audit blocks
# (future-proof: new features declare their checks in data.py, not here)
# ---------------------------------------------------------------------------

def check_entity_defs_audit_blocks(scene):
    issues = []
    for o in _actor_objs(scene):
        et = _etype(o)
        if not et:
            continue
        info  = ENTITY_DEFS.get(et, {})
        audit = info.get("audit", {})
        for check_fn in audit.get("custom_checks", []):
            try:
                result = check_fn(scene, o)
                if result:
                    sev, msg = result
                    issues.append(_issue(sev, msg, o.name))
            except Exception as exc:
                issues.append(_issue("WARNING",
                    f"Custom audit check for '{et}' raised: {exc}", o.name))
    return issues


def check_axis_not_vertical(scene):
    """DB "axis_not_vertical": "x"|"y"|"z" (game axis): the actor uses that
    local axis as a horizontal direction (swingpole: its pole), so it must
    not point straight up or down."""
    col = {"x": 0, "y": 2, "z": 1}   # game axis -> Blender local axis (game Y = Blender Z)
    issues = []
    for o in _actor_objs(scene):
        ax = (_db.find_actor(_etype(o)) or {}).get("axis_not_vertical")
        if ax in col:
            d = o.matrix_world.to_3x3().col[col[ax]].normalized()
            if abs(d.z) > 0.98:
                issues.append(_issue("WARNING",
                    f"{o.name}: its local {ax.upper()} axis (game) points straight up/down, "
                    f"so it won't work. Rotate it (swingpole: spawn turns it 90° on X).", o.name))
    return issues


def check_sync_period(scene):
    """A sync period under one frame (1/300 s) divides by zero in the game's
    sync code (citb-arm, citb-disc ... crash on load)."""
    issues = []
    for o in _actor_objs(scene):
        v = o.get("og_sync_period")
        if v is not None and _db.has_panel(_etype(o), "sync") and abs(float(v)) < 1.0 / 300.0:
            issues.append(_issue("ERROR", f"{o.name}: sync period {float(v):g} s crashes the game (divide by zero). "
                                          f"Use at least 0.01 s (negative turns the other way).", o.name))
    return issues


def check_texture_sources(scene):
    """DB "texture_sources" (actor or selected variant): textures that only
    draw when the level borrows one of those levels' textures (Level settings
    > Texture source), e.g. Flut Flut eyes, transparent water looks."""
    from .collections import _get_level_prop
    src = str(_get_level_prop(scene, "og_texture_source", "village1") or "village1").strip().lower()
    issues = []
    for o in _actor_objs(scene):
        et = _etype(o)
        var = _db.actor_variant(et, lambda k, d=None: o.get(k, d))
        need = var.get("texture_sources") or (_db.find_actor(et) or {}).get("texture_sources")
        if need and src not in need:
            what = var.get("texture_note") or (_db.find_actor(et) or {}).get("texture_note") or "some of its textures"
            issues.append(_issue("WARNING",
                f"{o.name}: {what} only show with the texture source {' / '.join(need)} "
                f"(Level settings; this level uses {src}). They stay blank otherwise.", o.name))
    return issues


def check_sound_banks(scene):
    """A sound (sound emitter, particle spawner) only plays if its bank is
    loaded: common, or one of the level's two sound banks (required.py,
    shared with the warnings next to Export & Compile). Warn only."""
    from .collections import _level_objects
    from .required import missing_bank, _sound_banks
    banks = _sound_banks(scene)
    loaded = banks[0]
    issues = []
    for o in _level_objects(scene):
        for m in missing_bank(o, scene, banks):
            issues.append(_issue("WARNING",
                f"{o.name}: sound '{m['sound']}' is in the {m['key']} sound bank, which this level doesn't load "
                f"(common + {' / '.join(sorted(loaded - {'common', 'none'})) or 'no level banks'}). Set it as one of the "
                f"level's sound banks or it won't play.", o.name))
    return issues


def check_particle_files(scene):
    """Each vanilla particle file used here is also loaded by its vanilla
    level; if both levels are in memory together, unloading one clears the
    shared particle definitions and can break the other's particles."""
    seen = {}
    for o in _actor_objs(scene):
        if _etype(o) != "part-spawner":
            continue
        var = _db.actor_variant("part-spawner", lambda k, d=None: o.get(k, d))
        if var and var.get("value") != "custom":
            seen.setdefault(var.get("value"), var.get("label", "").split(" (")[0])
    return [_issue("INFO", f"Particle file {f} is also used by vanilla {lvl}: if both levels are loaded at the same "
                           f"time, unloading one can break the other's particles.", None)
            for f, lvl in sorted(seen.items())]


def check_stray_geometry(scene):
    """Only the Geometry collection is exported to the level GLB."""
    from .collections import _active_level_col
    from .export.glb import stray_meshes
    objs = stray_meshes(_active_level_col(scene))
    if not objs:
        return []
    return [_issue("WARNING", f"{len(objs)} mesh(es) outside the Geometry collection aren't exported "
                              f"({', '.join(o.name for o in objs[:4])}{' ...' if len(objs) > 4 else ''}). "
                              f"Build & Play > Move to Geometry.", objs[0].name)]


# ---------------------------------------------------------------------------
# Check 11 — Scene summary (always INFO, always last)
# ---------------------------------------------------------------------------

def check_scene_summary(scene):
    issues  = []
    actors  = _actor_objs(scene)
    vols    = _vol_objs(scene)
    cameras = _camera_objs(scene)
    checkpts= _checkpoint_objs(scene)
    spawns  = _spawn_objs(scene)

    cats = {}
    for o in actors:
        et   = _etype(o)
        info = ENTITY_DEFS.get(et, {}) if et else {}
        cat  = info.get("cat", "Unknown")
        cats[cat] = cats.get(cat, 0) + 1
    cat_str = ", ".join(f"{v} {k}" for k, v in sorted(cats.items())) or "none"

    issues.append(_issue("INFO",
        f"Scene: {len(actors)} actor(s) ({cat_str}), "
        f"{len(vols)} volume(s), {len(cameras)} camera(s), "
        f"{len(checkpts)} checkpoint(s), {len(spawns)} spawn(s)."))

    return issues


# ---------------------------------------------------------------------------
# Registry — all active checks. Append here to add new ones.
# ---------------------------------------------------------------------------

def check_load_boundaries(scene):
    issues = []
    for o in scene.objects:
        if o.type != "MESH" or not o.name.startswith("LOADBND_"):
            continue
        top = float(getattr(o, "og_lb_top",  400.0))
        bot = float(getattr(o, "og_lb_bot", -400.0))
        if top <= bot:
            issues.append(_issue("ERROR",
                f"'{o.name}': Top ({top:g} m) must be above Bottom ({bot:g} m). "
                "The boundary wall has zero or inverted height.", o.name))
    return issues


_BC_SPAWN_PATHS = ("patha", "pathb", "pathc", "pathd", "pathe", "pathf", "pathg", "pathh")


def check_battlecontrollers(scene):
    """Battlecontroller setup: a spawn path, chances, camera variant needs."""
    from .export import battlecontroller as _bc
    issues, citadel = [], []
    for o in _actor_objs(scene):
        if _etype(o) != "battlecontroller":
            continue
        spawn = [p.name.strip() for p in getattr(o, "og_extra_paths", [])
                 if p.name.strip() in _BC_SPAWN_PATHS and len(p.sources)]
        if not spawn:
            issues.append(_issue("ERROR", f"'{o.name}' needs at least one spawn path (patha .. pathh) — "
                                          "Path panel > Add Path.", o.name))
        for w in _bc.percent_problems(o):
            issues.append(_issue("WARNING", f"'{o.name}': {w}.", o.name))
        var = _bc.variant(o)
        if var.get("custom_camera") and not all(_bc.camera(o)):
            issues.append(_issue("ERROR", f"'{o.name}': the custom camera needs a camera art group and an animation.", o.name))
        if var.get("needs_citadel_camera"):
            citadel.append(o)
            if _bc.citadel_camera_object(o) is None:
                issues.append(_issue("ERROR", f"'{o.name}': the citadel camera needs a camera position "
                                              f"({_bc.CITADEL_CAM_NAME}) — the game crashes without it.", o.name))
    if len(citadel) > 1:
        issues.append(_issue("WARNING", f"{len(citadel)} citadel-camera battlecontrollers: they all use the one "
                                        f"'{_bc.CITADEL_CAM_NAME}' position (the first one exported)."))
    return issues


_REGISTERED_CHECKS = [
    check_navmesh_links,
    check_missing_paths,
    check_battlecontrollers,
    check_actor_links,
    check_volumes,
    check_spawn_points,
    check_duplicate_names,
    check_camera_targets,
    check_doors,
    check_load_boundaries,
    check_entity_defs_audit_blocks,
    check_axis_not_vertical,
    check_sync_period,
    check_texture_sources,
    check_sound_banks,
    check_particle_files,
    check_stray_geometry,
    check_scene_summary,   # always last
]

_SEVERITY_ORDER = {"ERROR": 0, "WARNING": 1, "INFO": 2}


def run_audit(scene):
    """Run all registered checks. Returns issues sorted ERROR → WARNING → INFO."""
    issues = []
    for check in _REGISTERED_CHECKS:
        try:
            issues.extend(check(scene))
        except Exception as exc:
            issues.append(_issue("WARNING",
                f"Audit check '{check.__name__}' raised an unexpected error: {exc}"))
    issues.sort(key=lambda i: _SEVERITY_ORDER.get(i["severity"], 99))
    return issues
