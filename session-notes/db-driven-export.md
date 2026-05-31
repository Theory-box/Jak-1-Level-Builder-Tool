# Session notes: schema-driven actor export (DB as single source of truth)

**Branch:** `research/db-driven-export`  ·  **Stage:** research only (no code changes)

## Why
Completing the lump DB doesn't fix the steam-cap class of bug: the exporter
decides per-actor, via hardcoded `if einfo.get("needs_X")` / `if etype == ...`
blocks (and a waypoint gate on `sync`), whether to emit a lump. Set-but-not-
emitted is an export-layer problem, not a data problem. Goal: any actor with a
field set + value emits it, including custom actors added only to the DB jsonc,
with no code edits.

## Artifacts
- `refactoring/research/schema-driven-export.md` — full design research.
- `knowledge-base/research/opengoal/actor-lump-master.md` (on main) — source of
  truth for what each actor actually reads; the gap list that motivates this.
- `tools/extract_lumps_from_goal.py` (on main) — regenerates the master ref;
  intended to also become a build-time DB validator.

## Open questions (see research doc)
write_if vocabulary; emitter registry for computed lumps (path/links/bitfield);
property registration from schema; whether link_slots folds into fields[].

## Next
Lock schema shape + write_if; prototype schema-driven emit for steam-cap behind
a migrated flag; wire extractor diff into build_database.py.
