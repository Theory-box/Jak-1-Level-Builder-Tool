"""Write docs/guide/actor-list.md from the add-on's game database: every spawnable
actor, grouped like the Spawn Objects tiles. Run from the repo root before a release:

    python tools/gen_actor_list.py
"""
import importlib.util
import re
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "addons" / "opengoal_tools" / "jak1_game_database.jsonc"
OUT = ROOT / "docs" / "guide" / "actor-list.md"

# DB category -> Spawn Objects tile (addons/opengoal_tools/spawn_items.py DB_CAT_TO_TILE)
TILES = [("Enemies", ("Enemies", "Bosses")), ("Platforms", ("Platforms",)),
         ("Interactive Objects", ("Interactive Objects", "Debug")), ("Obstacles", ("Obstacles",)),
         ("Buttons and Doors", ("Buttons and Doors",)), ("Visuals", ("Visuals",)), ("NPCs", ("NPCs",)),
         ("Pickups", ("Pickups",)), ("Effects", ("Particles", "Effects"))]


def short(text, n=170):
    text = " ".join(str(text or "").split())
    m = re.match(r"(.+?[.!?])(\s|$)", text)
    first = m.group(1) if m else text
    return first if len(first) <= n else first[:n - 1].rstrip() + "…"


def load_db():
    """The add-on's db.py (no Blender needed): the same panel / path / nav-mesh rules the add-on uses."""
    pkg = types.ModuleType("_ogt"); pkg.__path__ = [str(DB.parent)]; sys.modules["_ogt"] = pkg
    spec = importlib.util.spec_from_file_location("_ogt.db", DB.parent / "db.py")
    mod = importlib.util.module_from_spec(spec); sys.modules["_ogt.db"] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    dbm = load_db()
    actors = [a for a in dbm.actors() if a.get("category") != "Hidden"]
    lines = ["# Actor list", "",
             f"Every actor you can place from **Spawn Objects** ({len(actors)} in all), grouped like its tiles. "
             "The search in Spawn Objects finds them by name or etype. Notes: **nav-mesh** = an enemy that needs "
             "a nav-mesh to move ([Enemies & nav-meshes](enemies-and-navmesh.md)), **path** = needs a path "
             "([Paths & platforms](paths-and-platforms.md)), **edited** = a vanilla actor made to work in custom "
             "levels ([Edited actors](edited-actors-and-goal-code.md)).", "",
             "*Generated from the add-on's database by `tools/gen_actor_list.py`.*", ""]
    lines += ["Jump to: " + " · ".join(f"[{t}](#{t.lower().replace(' ', '-')})" for t, _c in TILES), ""]
    for tile, cats in TILES:
        rows = sorted((a for a in actors if a.get("category") in cats), key=lambda a: a.get("label", a["etype"]).lower())
        if not rows:
            continue
        lines += [f"## {tile}", "", "| Actor | etype | Notes | What it is |", "|---|---|---|---|"]
        for a in rows:
            notes = []
            if a.get("category") == "Bosses":
                notes.append("boss")
            et = a["etype"]
            if "nav-enemy" in [p.get("etype") for p in dbm.parent_chain(et)]:
                notes.append("nav-mesh")
            if dbm.needs_path(et):
                notes.append("path")
            if a.get("edited") or a.get("custom_actor"):
                notes.append("edited" if not a.get("custom_actor") else "add-on actor")
            desc = short(a.get("description")).replace("|", "\\|")
            lines.append(f"| {a.get('label', a['etype'])} | `{a['etype']}` | {', '.join(notes)} | {desc} |")
        lines.append("")
    lines += ["---", "[← Previous](glossary.md) · [Guide index](README.md)", ""]
    OUT.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"wrote {OUT} ({len(actors)} actors)")


if __name__ == "__main__":
    main()
