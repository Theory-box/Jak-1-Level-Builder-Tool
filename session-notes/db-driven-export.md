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

## Progress — feature/schema-driven-export
- `export/schema_emit.py` — schema-driven emit engine (pure, no Blender). Builds
  lump dict from an actor's `fields[]` (write_if rules, slot arrays, value_if_true).
- `export/test_schema_emit.py` — standalone tests; output matches hardcoded shapes
  for plat-flip (sync-percent/delay), steam-cap (sync/percent), dark-crystal (mode).
- `export/actors.py` — gated hook: actors flagged `schema_export:true` in the DB
  emit their fields[] lumps via the engine. Additive + inert until a flag is set,
  so existing export is unchanged. Needs in-Blender verification before relying on it.

## Blockers / decisions needed before wiring the steam-cap pilot
- BASE BRANCH: main's steam-cap has only `percent` (no sync/needs_sync). The sync
  fields/props live on `platform-fixes`. Need to decide the restructure base
  (branch off platform-fixes, or merge it) before adding steam-cap fields[].
- DB hygiene: eco-blue/eco-red/eco-yellow each have 2 near-identical Actor records
  (dedupe). steam-cap/windmill-one also appear in a second catalog array.
