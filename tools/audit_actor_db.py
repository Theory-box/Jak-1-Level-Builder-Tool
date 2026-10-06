"""
audit_actor_db.py — check every actor in jak1_game_database.jsonc against a
local OpenGOAL install (goal_src + decompiler_out).

Nothing here is guessed: each check is a lookup in the game's own files.

  type     where `(deftype <etype> ...)` is defined -> expected .o file
  code     DB code.o matches the defining file; whether that .o ships in
           GAME.CGO (game.gd) and which level DGOs carry it
  ag       DB art_group exists in some DGO (.gd) — and which ones
  glb      DB preview glb exists under decompiler_out/jak1/
  lumps    lump keys vanilla placements of this etype use (from
           decompiler_out/jak1/entities/*-actors.json) that the DB entry
           does not cover via lumps[] / fields[] / link_slots / exporter
  missing  etypes placed in vanilla levels that are not in the DB at all

Usage:
  python tools/audit_actor_db.py --data <OpenGOAL data dir> [--category NAME]
         [--etype NAME] [--missing] [--json out.json]

<data dir> is the folder holding goal_src/ and decompiler_out/.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "addons" / "opengoal_tools" / "jak1_game_database.jsonc"

# Lump keys every actor carries or the exporter always writes; never "missing".
ALWAYS_KEYS = {"name", "visvol", "vis-dist", "aid", "trans", "quat"}
# Keys the exporter writes from Blender state / shared systems for any actor.
EXPORTER_KEYS = {"path", "path-k", "pathb", "sync", "nav-mesh-sphere", "vol",
                 "options", "idle-distance", "num-lurkers", "notice-dist"}


def load_db() -> dict:
    text = DB_PATH.read_text(encoding="utf-8")
    return json.loads(re.sub(r"^\s*//.*$", "", text, flags=re.M))


def scan_deftypes(goal_src: Path) -> dict[str, tuple[str, str]]:
    """etype -> (defining .gc path relative to goal_src/jak1, parent type)."""
    out: dict[str, tuple[str, str]] = {}
    rx = re.compile(r"^\(deftype\s+([^\s()]+)\s+\(([^\s()]+)\)", re.M)
    base = goal_src / "jak1"
    for gc in base.rglob("*.gc"):
        try:
            txt = gc.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = gc.relative_to(base).as_posix()
        for m in rx.finditer(txt):
            # first definition wins, but prefer non -h files (headers forward-declare)
            if m.group(1) not in out or out[m.group(1)][0].endswith("-h.gc"):
                out[m.group(1)] = (rel, m.group(2))
    return out


def scan_dgos(goal_src: Path) -> dict[str, list[str]]:
    """file name (x.o / x-ag.go / tpage-N.go) -> list of DGO names carrying it."""
    out: dict[str, list[str]] = collections.defaultdict(list)
    for gd in (goal_src / "jak1" / "dgos").glob("*.gd"):
        txt = gd.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'\("([^"]+)"', txt)
        dgo = m.group(1) if m else gd.stem.upper()
        for f in re.findall(r'"([^"]+\.(?:o|go))"', txt):
            out[f].append(dgo)
    return out


def scan_vanilla(decomp: Path) -> dict[str, dict]:
    """etype -> {count, levels:set, lumps: Counter(key), samples: {key: value}}"""
    out: dict[str, dict] = {}
    for f in sorted((decomp / "entities").glob("*-actors.json")):
        level = f.name[: -len("-actors.json")]
        for a in json.loads(f.read_text(encoding="utf-8")) or []:
            e = out.setdefault(a["etype"], {"count": 0, "levels": set(),
                                            "lumps": collections.Counter(),
                                            "samples": {}})
            e["count"] += 1
            e["levels"].add(level)
            for k, v in (a.get("lump") or {}).items():
                e["lumps"][k] += 1
                e["samples"].setdefault(k, v)
    return out


def covered_keys(actor: dict, db: dict) -> set[str]:
    keys = set()
    for l in actor.get("lumps", []):
        keys.add(l.get("key"))
    for f in actor.get("fields", []):
        for lk in ("lump", "lump_bit"):
            lp = f.get(lk)
            if isinstance(lp, dict) and lp.get("key"):
                keys.add(lp["key"])
    for s in actor.get("link_slots", []):
        keys.add(s.get("lump_key"))
    for p in db.get("Parents", []):
        pass
    if actor.get("need_vol"):
        keys.add("vol")
    return {k for k in keys if k}


def code_o(actor: dict) -> str | None:
    c = actor.get("code")
    if isinstance(c, dict):
        return c.get("o")
    if isinstance(c, str):
        return c
    return None


def audit(args) -> int:
    data = Path(args.data)
    goal_src, decomp = data / "goal_src", data / "decompiler_out" / "jak1"
    db = load_db()
    deftypes = scan_deftypes(goal_src)
    dgos = scan_dgos(goal_src)
    vanilla = scan_vanilla(decomp)
    game_cgo = {f for f, ds in dgos.items() if "GAME.CGO" in ds}

    known = {a["etype"] for a in db["Actors"]} | {a["etype"] for a in db.get("OrphanEtypes", [])}
    # Variant choices that switch etype (e.g. OgreStepVariants) also count.
    variant_rows = []  # (table, choice)
    for name, tbl in db.items():
        if isinstance(tbl, list) and tbl and all(isinstance(c, dict) for c in tbl)                 and any("id" in c and ("glb" in c or "etype" in c or "art_group" in c) for c in tbl):
            for c in tbl:
                variant_rows.append((name, c))
                if c.get("etype"):
                    known.add(c["etype"])
    report = []

    for a in db["Actors"]:
        if args.category and a.get("category") != args.category:
            continue
        if args.etype and a["etype"] != args.etype:
            continue
        et = a["etype"]
        issues, notes = [], []
        dt = deftypes.get(et)
        expect_o = (Path(dt[0]).stem + ".o") if dt else None
        if not dt:
            issues.append("type: no (deftype %s ...) in goal_src" % et)
        else:
            notes.append(f"type: {dt[0]} (parent {dt[1]})")
        o = code_o(a)
        if expect_o:
            if o is None and expect_o not in game_cgo:
                issues.append(f"code: none set, type lives in {expect_o}")
            elif o and o != expect_o and not (expect_o.endswith("-h.o")
                                              and o == expect_o[:-4] + ".o"):
                issues.append(f"code: DB {o} but type defined in {expect_o}")
            if expect_o in game_cgo:
                notes.append(f"code: {expect_o} is in GAME.CGO (no injection needed)")
            else:
                notes.append(f"code DGOs: {', '.join(sorted(set(dgos.get(expect_o, [])))) or 'none'}")
        for xo in a.get("extra_code", []) or []:
            if xo not in dgos:
                issues.append(f"extra_code: {xo} not in any DGO")
        ag = a.get("art_group")
        for g in (ag if isinstance(ag, list) else [ag] if ag else []):
            if g not in dgos:
                issues.append(f"ag: {g} not in any DGO")
            else:
                notes.append(f"ag {g} DGOs: {', '.join(sorted(set(dgos[g])))}")
        for xag in a.get("extra_art_groups", []) or []:
            if xag not in dgos:
                issues.append(f"extra_ag: {xag} not in any DGO")
        glb = a.get("glb")
        if isinstance(glb, str) and not (decomp / glb).exists():
            issues.append(f"glb: {glb} missing in decompiler_out")
        v = vanilla.get(et)
        if v:
            cov = covered_keys(a, db) | ALWAYS_KEYS | EXPORTER_KEYS
            miss = [f"{k}({n}/{v['count']})" for k, n in v["lumps"].most_common() if k not in cov]
            notes.append(f"vanilla: {v['count']}x in {', '.join(sorted(v['levels']))}")
            if miss:
                issues.append("lumps not covered: " + " ".join(miss))
        else:
            notes.append("vanilla: never placed in a vanilla level")
        report.append({"etype": a["etype"], "category": a.get("category"),
                       "schema_export": bool(a.get("schema_export")),
                       "issues": issues, "notes": notes})

    if not args.category and not args.etype:
        for name, c in variant_rows:
            probs = []
            if isinstance(c.get("glb"), str) and not (decomp / c["glb"]).exists():
                probs.append(f"glb {c['glb']} missing")
            if isinstance(c.get("art_group"), str) and c["art_group"] not in dgos:
                probs.append(f"ag {c['art_group']} not in any DGO")
            if c.get("etype") and c["etype"] not in deftypes:
                probs.append(f"etype {c['etype']} has no deftype")
            if probs:
                print(f"!! variant {name}/{c.get('id')}: " + "; ".join(probs))

    if args.missing:
        miss = sorted((e, v) for e, v in vanilla.items() if e not in known)
        print(f"== Vanilla etypes not in DB ({len(miss)}) ==")
        for e, v in miss:
            dt = deftypes.get(e)
            src = dt[0] if dt else "?"
            par = dt[1] if dt else "?"
            print(f"  {e:28s} {v['count']:4d}x  {src:40s} ({par})  lumps: {' '.join(k for k, _ in v['lumps'].most_common() if k not in ALWAYS_KEYS)}")
        print()

    for r in report:
        flag = "OK " if not r["issues"] else "!! "
        print(f"{flag}{r['etype']:28s} [{r['category']}]{' schema' if r['schema_export'] else ''}")
        for i in r["issues"]:
            print(f"     - {i}")
        if args.verbose:
            for n in r["notes"]:
                print(f"       {n}")
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=1), encoding="utf-8")
    bad = sum(1 for r in report if r["issues"])
    print(f"\n{len(report)} actors checked, {bad} with issues")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--category")
    ap.add_argument("--etype")
    ap.add_argument("--missing", action="store_true")
    ap.add_argument("--verbose", "-v", action="store_true")
    ap.add_argument("--json")
    sys.exit(audit(ap.parse_args()))
