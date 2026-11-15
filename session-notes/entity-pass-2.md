# Second entity pass: continuation

Base: `claude/entity-pass-2`, `53c3f03`. Test target: the user's
`Documents/JakAndDaxter/test-modbase/data` installation (corrected by the user;
the active install was read only for initial source research).

## Plan before changes

1. Reconcile Actor Notes with the database and prior commits. The nav-enemy
   spawn changes, edited-file selection, shared code placement, and drop-platform
   grid are already implemented. Older onboarding and migration notes are history,
   not the current architecture.
2. Research missing placeable actors against the local GOAL source. Add database
   records and separate `subtypes/*.gc` files where vanilla behavior depends on
   story tasks, fixed positions, named cameras, or other vanilla entities.
   Do not rewrite vanilla source files. Keep data in the bundled JSONC database;
   do not regenerate it with the historical migration builder.
3. Start with the missing trigger/linked actors (Citadel stairs/controller,
   silo steps, mirror, beach rock, precursor arm, pontoons), then inspect the
   coupled Helix/exit-chamber puzzles, egg and race controller. Distinguish
   actors that are intentionally spawned by another process from independently
   placeable actors; do not expose incomplete records just to clear a list.
4. Check the remaining hidden/story actors and record real prerequisites or
   unsupported behavior explicitly. Keep particles and enemy drops in their
   separately requested passes.
5. Repair the existing standalone schema test harness, add focused validation
   for the newly supported records/edited code and export modes, and smoke-test
   registration/export in background Blender. Compile against available GOAL
   tooling in an isolated location where practical.
6. Package the addon and provide a focused in-game checklist covering triggers,
   custom tasks, linked objects, per-level/shared code, and save/reload. Runtime
   behavior remains unverified until those tests are performed.

## Baseline

- Checkout was clean. No AGENTS.md or CLAUDE.md present in the repository.
- Blender 4.5 and its Python 3.11 are installed; the default Windows Python
  alias is unusable. Use the bundled interpreter for non-Blender tests.
- `export/test_schema_emit.py` currently fails importing `db` from the task
  encoder because it imports `schema_emit` outside its package.
- `citb-drop-plat` already has its database entry, `reacts_to: trigger`, and
  `plat-grid` UI. Actor Notes incorrectly lists it as missing.

## Implemented and checked (2026-11-05)

- Added 13 actor records; restored Gol, Maia and Green Sage to the NPC picker.
  Added 15 separate edited GOAL files; database records select them. No vanilla
  actor source files were edited in either installed game directory.
- Details and deliberate limits are in Actor Notes. Exit chamber is ride-only;
  Green Sage is rescue-only. Particles, enemy drops and the older documented
  limitations remain separate work. Preview meshes are not runtime-verified.
- Schema encoder now respects a water ripple field's declared default.
  Required-field audit supports schema task and object-reference fields.
- Fixed shared edited-file registrations when dependencies change: replace
  the tagged goal-src line by its source path and remove duplicates, rather
  than creating conflicting build targets. Unrelated registrations are kept.
- Populated new actors' non-common sound requirements using the existing code
  scanner and available raw art strings. The scan is conservative because it
  includes parent methods even when a child replaces them.
- Repaired standalone schema tests for the current panel/inheritance schema:
  12 tests pass. Blender 4.5 factory-startup registration/export smoke passes:
  all 15 actors, links, custom race task, required fields, coordinate conversion,
  JSONC, DGO inclusion, obs/shared/vanilla selection, idempotence and changed
  dependency registration. Repro: tools/test_entity_pass_blender.py with a
  disposable source-copy directory (never an installed data folder).
- All 15 new .gc files compiled after __TYPE__ substitution with test-modbase's
  goalc. All 15 generated shared lt-*.gc targets also compiled in fresh compiler
  processes using their exported dependencies. The isolated check bootstraps
  pckernel-impl first: direct process-drawable builds otherwise hit the upstream
  pad.gc *pc-settings* ordering issue. Silo Step's missing battlecontroller
  dependency was caught and added. No game was launched for these checks.
- All compilation and export writes stayed under work/goal-check. Both active
  and test-modbase installs remain untouched. The intended in-game test target
  is Documents/JakAndDaxter/test-modbase/data, per the user's correction.
- git diff --check passes. Runtime acceptance is pending, not marked done in
  the ordered ToDo list. Branch remains claude/entity-pass-2; the user requested
  a push after validation for another tester. See entity-pass-2-testing.md.
