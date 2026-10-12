# ───────────────────────────────────────────────────────────────────────
# export/subtypes.py — OpenGOAL Level Tools
#
# Level-scoped child types for vanilla types that can't be used as-is in a
# custom level. Each one is a GOAL file in the addon's subtypes/ folder,
# named after the actor's etype (subtypes/<etype>.gc), with __TYPE__ where
# the child type's name goes. A level that uses one of these actors gets the
# file's GOAL in its -obs.gc with __TYPE__ = "<level>-<etype>", and the actor
# exports with that etype (write_jsonc adds the prefix).
#
# A file without "(deftype __TYPE__" is a level patch instead: its GOAL is
# added the same way but the actor keeps its vanilla etype.
#
# Current files (see each file's header for why):
#   water-anim.gc   basic water-anim (flat surface) for floating / splashing actors
#   fireboulder.gc  hover sound for every boulder (vanilla: fireboulder-6 only)
#   ogreboss.gc     Klaww with an editable intro trigger / continue point / task
#   lightning-mole.gc  hole at its peeper, shows up without the geologist
#   robotboss.gc    (patch) yellow shot / light eco heights relative to the boss
#   dark-plant.gc / happy-plant.gc  own task, no freeze on linked plants
#   muse.gc         catching it gives its own task's cell
#   sage-finalboss.gc  ending cutscenes without vanilla positions / final door
# ───────────────────────────────────────────────────────────────────────
from __future__ import annotations

from pathlib import Path

_DIR = Path(__file__).resolve().parent.parent / "subtypes"
FILES = tuple(sorted(p.stem for p in _DIR.glob("*.gc")))
# etypes exported as "<level>-<etype>" (the file defines a child type)
ETYPES = tuple(e for e in FILES if "(deftype __TYPE__" in (_DIR / f"{e}.gc").read_text(encoding="utf-8"))


def _used(objects):
    return [e for e in FILES
            if any(o.type == "EMPTY" and o.name.startswith(f"ACTOR_{e}_") for o in objects)]


def gc_lines(pfx: str, objects) -> list[str]:
    """GOAL for the level-scoped subtypes the level uses."""
    lines = []
    for e in _used(objects):
        text = (_DIR / f"{e}.gc").read_text(encoding="utf-8")
        lines += [""] + text.replace("__TYPE__", f"{pfx}-{e}").rstrip("\n").split("\n")
    return lines
