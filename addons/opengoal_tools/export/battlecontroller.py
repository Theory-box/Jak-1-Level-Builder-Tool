# ---------------------------------------------------------------------------
# export/battlecontroller.py — battlecontroller (ambush) export helpers
#
# Camera variants (DB battlecontroller "og_bc_variant"):
#   basic -> the plain battlecontroller (no intro camera).
#   misty / swamp / citadel / custom -> a battlecontroller child type written
#       into the level's -obs.gc (no vanilla -obs.o is bundled): it plays the
#       variant's camera animation (pov-camera) and keeps the vanilla extras
#       (misty collision hack, swamp/citadel "complete" on death, citadel
#       hint + 35 m activation). Controllers with the same setup share a type,
#       named <level>-battlecontroller-<n> (n from 1).
# The citadel variant reads its camera position from an entity named
# "citadelcam-1"; it is exported as an inert process-hidden actor at the
# linked camera-position empty.
# ---------------------------------------------------------------------------
from __future__ import annotations

from .. import db as _db

GEN_PREFIX = "battlecontroller-"     # + n; write_jsonc / write_gc add the level prefix
CITADEL_CAM_NAME = "citadelcam-1"


def variant(o) -> dict:
    return _db.actor_variant("battlecontroller", lambda k, d=None: o.get(k, d))


def is_custom(o) -> bool:
    return bool(variant(o).get("custom_camera"))


def camera_anims() -> dict:
    """{camera art group: [animations]} (from the game's *cam-ag.go files)."""
    return dict((_db.find_actor("battlecontroller") or {}).get("camera_anims") or {})


def camera(o) -> tuple[str, str]:
    """(art group, animation) of the controller's intro camera: the variant's
    fixed one, or the picked one for "custom" (whose "custom" choices read
    the typed names). ("", "") for the basic variant."""
    var = variant(o)
    if not var.get("custom_camera"):
        cam = var.get("intro_camera") or {}
        return str(cam.get("art_group", "")), str(cam.get("anim", ""))
    ag = str(o.get("og_bc_cam", "") or "")
    if ag == "custom":
        ag = str(o.get("og_bc_cam_custom", "") or "").strip()
    anim = str(o.get("og_bc_anim", "") or "")
    if anim == "custom":
        anim = str(o.get("og_bc_anim_custom", "") or "").strip()
    if ag.endswith("-ag.go"):
        ag = ag[:-len("-ag.go")]
    return ag, anim


def _spec(o):
    """What decides the generated type: (variant id, art group, animation),
    or None for a plain battlecontroller / an unfinished custom camera."""
    var = variant(o)
    if not var.get("generated_type"):
        return None
    ag, anim = camera(o)
    return (str(var.get("id", "")), ag, anim) if ag and anim else None


def _controllers(objects):
    return [o for o in objects if o.type == "EMPTY" and o.name.startswith("ACTOR_battlecontroller_")]


def generated_types(objects) -> dict:
    """{spec: type base name} for the controllers among `objects` that need
    a generated type; equal specs share one, numbered in a stable order."""
    specs = sorted({sp for sp in map(_spec, _controllers(objects)) if sp})
    return {sp: f"{GEN_PREFIX}{i}" for i, sp in enumerate(specs, 1)}


def type_base(o, objects):
    """Generated type base name for this controller (None: plain type)."""
    return generated_types(objects).get(_spec(o))


def gc_lines(pfx: str, objects) -> list[str]:
    """GOAL for every generated battlecontroller type."""
    lines = []
    for (vid, ag, anim), base in generated_types(objects).items():
        t = f"{pfx}-{base}"
        sg = f"*{t}-cam-sg*"
        cam_at = (f'(-> (entity-by-name "{CITADEL_CAM_NAME}") extra trans)' if vid == "citadel"
                  else "(-> self root trans)")
        pre = {"swamp": ["      (suspend)", "      (process-drawable-delay-player (seconds 1))"],
               "citadel": ['      (level-hint-spawn (text-id citadel-battle) "sksp0383" (the-as entity #f) *entity-pool* (game-task none))',
                           "      (suspend)"]}.get(vid, [])
        lines += [
            "",
            f";; battlecontroller with the {vid} intro camera ({ag} / {anim})",
            f"(deftype {t} (battlecontroller) ())",
            "",
            f"(defskelgroup {sg}",
            f"  {ag}",
            f"  {ag}-lod0-jg",
            f"  {ag}-{anim}-ja",
            f"  (({ag}-lod0-mg (meters 999999)))",
            "  :bounds (static-spherem 0 0 0 20))",
            "",
            f"(defstate battlecontroller-play-intro-camera ({t})",
            "  :virtual #t",
            "  :code",
            "    (behavior ()",
            *pre,
            f"      (let ((gp-1 (ppointer->handle (process-spawn pov-camera {cam_at} {sg} \"{anim}\" 0 #f '() :to self))))",
        ]
        if vid == "citadel":
            lines += ["        (send-event (handle->process (the-as handle gp-1)) 'mask 2048)",
                      "        (while (handle->process (the-as handle gp-1))",
                      "          (logclear! (-> *target* state-flags) (state-flags invulnerable))",
                      "          (suspend)))"]
        else:
            lines += ["        (while (handle->process (the-as handle gp-1))",
                      "          (suspend)))"]
        lines.append("      (go-virtual battlecontroller-active)))")
        if vid in ("swamp", "citadel"):     # the vanilla ones mark the entity complete on death
            lines += ["",
                      f"(defstate battlecontroller-die ({t})",
                      "  :virtual #t",
                      "  :code",
                      "    (behavior ()",
                      "      (process-entity-status! self (entity-perm-status complete) #t)",
                      "      (call-parent-state-handler code)))"]
        if vid in ("misty", "citadel"):
            body = ("  (set! (-> this misty-ambush-collision-hack) #t)" if vid == "misty"
                    else "  (set! (-> this activate-distance) (meters 35))")
            lines += ["",
                      f"(defmethod battlecontroller-method-27 ((this {t}))",
                      "  (call-parent-method this)",
                      body,
                      "  0",
                      "  (none))"]
    return lines


MAX_LURKER_TYPES = 4            # creature-type-array size
PICKUP_VALUES = {"none": 0, "eco-yellow": 1, "eco-red": 2, "eco-blue": 3, "eco-green": 4, "money": 5,
                 "fuel-cell": 6, "eco-pill": 7, "buzzer": 8, "eco-pill-random": 9}


def lurkers(o) -> list:
    """The controller's lurker entries (at most 4 are read by the game)."""
    return [e for e in getattr(o, "og_bc_lurkers", []) if e.etype][:MAX_LURKER_TYPES]


def percent_problems(o) -> list[str]:
    """Warnings: the lurker spawn chances should add up to 1.0 (special eco
    chances are per lurker and don't)."""
    ls = lurkers(o)
    out = []
    if ls:
        s = sum(e.percent for e in ls)
        if abs(s - 1.0) > 0.001:
            out.append(f"Spawn chances add up to {s:.2f}, not 1.0")
    if len(getattr(o, "og_bc_lurkers", [])) > MAX_LURKER_TYPES:
        out.append(f"Only the first {MAX_LURKER_TYPES} lurkers are used")
    return out


def lumps(o) -> dict:
    """Computed lumps: the slot-aligned lurker arrays and final-pickup."""
    out = {}
    ls = lurkers(o)
    if ls:
        out["lurker-type"] = ["type"] + [e.etype for e in ls]
        out["percent"] = ["float"] + [round(e.percent, 4) for e in ls]
        out["pickup-percent"] = ["float"] + [round(e.pickup_percent, 4) for e in ls]
        out["pickup-type"] = ["int32"] + [PICKUP_VALUES.get(e.pickup_type, 0) for e in ls]
        out["max-pickup-count"] = ["int32"] + [int(e.max_pickup_count) for e in ls]
    end = bool(o.get("og_bc_end_pickup", True))
    fp = str(o.get("og_bc_final_pickup", "fuel-cell") or "fuel-cell") if end else "none"
    out["final-pickup"] = ["enum-int32", f"(pickup-type {fp})"]
    return out


def lurker_assets(o) -> tuple[list, list, list]:
    """(code, art groups, tpages) of the lurker types: the level must bundle
    them or the controller can't spawn anything."""
    from ..data import ETYPE_AG
    code, ags, tps = [], [], []
    for e in lurkers(o):
        rec = _db.find_actor(e.etype) or {}
        code += [c for c in _db.code_files(rec) if c not in code]
        ags += [g for g in ETYPE_AG.get(e.etype, []) if g not in ags]
        tps += [t for t in _db.actor_tpages(e.etype) if t not in tps]
    return code, ags, tps


def citadel_camera_object(o):
    """The camera-position empty linked to a citadel-variant controller."""
    import bpy
    name = str(o.get("og_bc_campos", "") or "")
    return bpy.data.objects.get(name) if name else None
