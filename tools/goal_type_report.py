"""goal_type_report.py — print what the game code does with an etype.

For each etype: defining file + parent chain, every res-lump / entity-actor
lookup inside methods/states/behaviors of that type (and its parents up to a
common engine base), skelgroups it initializes, and other process types it
spawns. Source-of-truth helper for writing DB entries.

  python tools/goal_type_report.py --data <OpenGOAL data dir> ETYPE [ETYPE...]
"""
import argparse, re
from pathlib import Path

STOP = {"process-drawable", "process", "process-hidden", "process-taskable",
        "basic", "structure", "nav-enemy"}
LUMP_RX = re.compile(r"\((res-lump-(?:float|struct|data|value)|entity-actor-lookup|entity-actor-count|"
                     r"lookup-tag-idx|get-property-(?:value-float|struct|value|data))\s+((?:\((?:[^()]|\([^()]*\))*\)|[^\s()]+))\s+'([a-z0-9-]+)")
SKEL_RX = re.compile(r"initialize-skeleton\s+[^\s()]+\s+(\*[a-z0-9-]+\*)")
SPAWN_RX = re.compile(r"\(process-spawn\s+([a-z0-9-]+)|\(manipy-spawn|\(ja-play-spooled|\(spawn-projectile-blue|"
                      r"\(birth-pickup-at-point|\(process-new\s+([a-z0-9-]+)")
HEAD_RX = re.compile(r"^\((defmethod|defstate|defbehavior|defun|deftype)\s+([^\s()]+)\s*(\(\(?\s*[^\s()]+\s+([^\s()]+)|\(([^\s()]+)\))?", re.M)


def forms(text):
    """Yield (kind, name, owner_type, body) for top-level forms."""
    starts = [m.start() for m in re.finditer(r"^\(", text, re.M)] + [len(text)]
    for a, b in zip(starts, starts[1:]):
        body = text[a:b]
        m = HEAD_RX.match(body)
        if not m:
            continue
        kind, name = m.group(1), m.group(2)
        owner = m.group(4) or m.group(5)
        if kind == "defmethod" and not owner:
            mm = re.match(r"\(defmethod\s+\S+\s+([^\s()]+)", body)
            owner = mm.group(1) if mm else None
        if kind == "deftype":
            mm = re.match(r"\(deftype\s+\S+\s+\(([^\s()]+)\)", body)
            owner = mm.group(1) if mm else None  # parent
        yield kind, name, owner, body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--body", action="store_true", help="print init-from-entity! bodies")
    ap.add_argument("etypes", nargs="+")
    a = ap.parse_args()
    base = Path(a.data) / "goal_src" / "jak1"
    parents, deffile, by_owner = {}, {}, {}
    for gc in base.rglob("*.gc"):
        txt = gc.read_text(encoding="utf-8", errors="replace")
        txt = re.sub(r";[^\n]*", "", txt)
        rel = gc.relative_to(base).as_posix()
        for kind, name, owner, body in forms(txt):
            if kind == "deftype":
                if name not in deffile or deffile[name].endswith("-h.gc"):
                    parents[name], deffile[name] = owner, rel
            elif owner:
                by_owner.setdefault(owner, []).append((kind, name, rel, body))
    for et in a.etypes:
        chain, t = [], et
        while t and t not in chain:
            chain.append(t)
            if t in STOP:
                break
            t = parents.get(t)
        print(f"=== {et}   file: {deffile.get(et, '?')}   chain: {' > '.join(chain)}")
        for t in chain:
            if t in STOP:
                continue
            for kind, name, rel, body in by_owner.get(t, []):
                lumps = sorted({f"{m.group(3)} [{m.group(1)}]" for m in LUMP_RX.finditer(body)})
                skels = sorted(set(SKEL_RX.findall(body)))
                spawns = sorted({x for m in SPAWN_RX.finditer(body) for x in m.groups() if x})
                if lumps or skels or spawns:
                    print(f"  {t}:{kind} {name} ({rel})")
                    for l in lumps:  print(f"      lump  {l}")
                    for s in skels:  print(f"      skel  {s}")
                    for s in spawns: print(f"      spawn {s}")
                if a.body and name == "init-from-entity!" and t == et:
                    print("      ---- body ----")
                    print("      " + body.strip().replace("\n", "\n      "))
        print()


if __name__ == "__main__":
    main()
