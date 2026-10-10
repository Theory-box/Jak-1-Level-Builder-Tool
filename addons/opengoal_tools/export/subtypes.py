# ───────────────────────────────────────────────────────────────────────
# export/subtypes.py — OpenGOAL Level Tools
#
# Level-scoped child types written into the level's -obs.gc for actors whose
# vanilla type can't be used as-is. Each etype below exports as
# "<level>-<etype>" (write_jsonc adds the prefix); its GOAL is only written
# when the level has one.
#
#   water-anim   Floating / splashing actors call get-ripple-height on their
#                linked water. water-vol doesn't implement it (the game jumps
#                to address 0) and the vanilla water-anim needs a "look"
#                skeleton from a vanilla level, so this is a water-vol whose
#                ripple height is its flat water height (looks come later).
#   fireboulder  With a closed task it hovers and updates its sound every
#                frame, but only an actor named fireboulder-6 creates that
#                sound (village2-obs.gc) -> crash for any other name. The
#                child creates the sound for every boulder.
# ───────────────────────────────────────────────────────────────────────
from __future__ import annotations

_GOAL = {
    "water-anim": [
        ";; water-anim (basic): a water volume whose ripple height is its flat water height",
        "(deftype {t} (water-vol) ())",
        "",
        "(defmethod get-ripple-height ((this {t}) (arg0 vector))",
        "  (-> this water-height))",
    ],
    "fireboulder": [
        ";; fireboulder that has its hover sound whatever its name (vanilla: only fireboulder-6)",
        "(deftype {t} (fireboulder) ())",
        "",
        "(defmethod initialize-skeleton ((this {t}) (arg0 skeleton-group) (arg1 pair))",
        "  (if (zero? (-> this sound))",
        "    (set! (-> this sound) (new 'process 'ambient-sound (static-sound-spec \"rock-hover\" :fo-max 30) (-> this root trans))))",
        "  (call-parent-method this arg0 arg1))",
    ],
}
ETYPES = tuple(_GOAL)


def _used(objects):
    return [e for e in ETYPES
            if any(o.type == "EMPTY" and o.name.startswith(f"ACTOR_{e}_") for o in objects)]


def gc_lines(pfx: str, objects) -> list[str]:
    """GOAL for the level-scoped subtypes the level uses."""
    lines = []
    for e in _used(objects):
        lines += [""] + [l.format(t=f"{pfx}-{e}") for l in _GOAL[e]]
    return lines
