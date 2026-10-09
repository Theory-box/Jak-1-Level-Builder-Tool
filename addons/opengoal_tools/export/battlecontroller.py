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


def citadel_camera_object(o):
    """The camera-position empty linked to a citadel-variant controller."""
    import bpy
    name = str(o.get("og_bc_campos", "") or "")
    return bpy.data.objects.get(name) if name else None
