# ---------------------------------------------------------------------------
# export/battlecontroller.py — battlecontroller (ambush) export helpers
#
# Camera variants (DB battlecontroller "og_bc_variant"):
#   basic / misty / swamp / citadel  -> vanilla types (battlecontroller,
#       misty-battlecontroller, swamp-battlecontroller, citb-battlecontroller)
#   custom -> a per-actor child type written into the level's -obs.gc that
#       plays the picked camera animation (pov-camera) at the controller, like
#       the misty / swamp ones do. Type name: <level>-battlecontroller-custom-<uid>.
# The citadel variant reads its camera position from an entity named
# "citadelcam-1"; it is exported as an inert process-hidden actor at the
# linked camera-position empty.
# ---------------------------------------------------------------------------
from __future__ import annotations

from .. import db as _db

CUSTOM_PREFIX = "battlecontroller-custom-"
CITADEL_CAM_NAME = "citadelcam-1"


def _uid(o) -> str:
    parts = o.name.split("_", 2)
    return parts[2] if len(parts) >= 3 else "0"


def variant(o) -> dict:
    return _db.actor_variant("battlecontroller", lambda k, d=None: o.get(k, d))


def is_custom(o) -> bool:
    return bool(variant(o).get("custom_camera"))


def custom_type_base(o) -> str:
    """etype before level scoping (write_jsonc / write_gc add the prefix)."""
    uid = "".join(c if c.isalnum() else "-" for c in _uid(o).lower())
    return CUSTOM_PREFIX + uid


def camera_anims() -> dict:
    """{camera art group: [animations]} (from the game's *cam-ag.go files)."""
    return dict((_db.find_actor("battlecontroller") or {}).get("camera_anims") or {})


def camera(o) -> tuple[str, str]:
    """(art group, animation) picked for a custom-camera controller; the
    "custom" choice of either reads the typed name."""
    ag = str(o.get("og_bc_cam", "") or "")
    if ag == "custom":
        ag = str(o.get("og_bc_cam_custom", "") or "").strip()
    anim = str(o.get("og_bc_anim", "") or "")
    if anim == "custom":
        anim = str(o.get("og_bc_anim_custom", "") or "").strip()
    if ag.endswith("-ag.go"):
        ag = ag[:-len("-ag.go")]
    return ag, anim


def custom_controllers(objects) -> list:
    """Custom-camera battlecontroller empties among `objects`."""
    out = []
    for o in objects:
        if o.type != "EMPTY" or not o.name.startswith("ACTOR_battlecontroller_"):
            continue
        if is_custom(o):
            out.append(o)
    return out


def gc_lines(pfx: str, objects) -> list[str]:
    """GOAL for every custom-camera controller: a battlecontroller child
    whose intro plays the picked camera at the controller."""
    lines = []
    for o in custom_controllers(objects):
        ag, anim = camera(o)
        if not ag or not anim:
            continue
        t = f"{pfx}-{custom_type_base(o)}"
        sg = f"*{t}-cam-sg*"
        lines += [
            "",
            f";; {o.name}: battlecontroller with a custom intro camera ({ag} / {anim})",
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
            f"      (let ((gp-1 (ppointer->handle (process-spawn pov-camera (-> self root trans) {sg} \"{anim}\" 0 #f '() :to self))))",
            "        (while (handle->process (the-as handle gp-1))",
            "          (suspend)))",
            "      (go-virtual battlecontroller-active)))",
        ]
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
