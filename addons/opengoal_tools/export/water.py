# ───────────────────────────────────────────────────────────────────────
# export/water.py — OpenGOAL Level Tools
#
# Basic water-anim. Actors that float on or splash in water (ogre-isle /
# ogre-step via rigid-body water-actor, square-platform splashes) call
# get-ripple-height on the linked water. water-vol has no such method (the
# game jumps to address 0), and the vanilla water-anim needs a "look"
# skeleton from a vanilla level. So the addon's "water-anim" actor exports
# as a level-scoped child of water-vol whose ripple height is its flat
# water height. Looks / animated surfaces can come later.
# ───────────────────────────────────────────────────────────────────────
from __future__ import annotations

ETYPE = "water-anim"


def _water_anims(objects):
    return [o for o in objects if o.type == "EMPTY" and o.name.startswith(f"ACTOR_{ETYPE}_")]


def gc_lines(pfx: str, objects) -> list[str]:
    """GOAL for the level's water-anim type (only when the level uses one)."""
    if not _water_anims(objects):
        return []
    t = f"{pfx}-{ETYPE}"
    return [
        "",
        ";; water-anim (basic): a water volume whose ripple height is its flat water height",
        f"(deftype {t} (water-vol) ())",
        "",
        f"(defmethod get-ripple-height ((this {t}) (arg0 vector))",
        "  (-> this water-height))",
    ]
