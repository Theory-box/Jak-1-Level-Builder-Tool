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
# Current files (see each file's header for why):
#   water-anim.gc   basic water-anim (flat surface) for floating / splashing actors
#   fireboulder.gc  hover sound for every boulder (vanilla: fireboulder-6 only)
#   ogreboss.gc     Klaww with an editable intro trigger / continue point / task
# ───────────────────────────────────────────────────────────────────────
from __future__ import annotations

from pathlib import Path

_DIR = Path(__file__).resolve().parent.parent / "subtypes"
ETYPES = tuple(sorted(p.stem for p in _DIR.glob("*.gc")))


def _used(objects):
    return [e for e in ETYPES
            if any(o.type == "EMPTY" and o.name.startswith(f"ACTOR_{e}_") for o in objects)]


def gc_lines(pfx: str, objects) -> list[str]:
    """GOAL for the level-scoped subtypes the level uses."""
    lines = []
    for e in _used(objects):
        text = (_DIR / f"{e}.gc").read_text(encoding="utf-8")
        lines += [""] + text.replace("__TYPE__", f"{pfx}-{e}").rstrip("\n").split("\n")
    return lines
