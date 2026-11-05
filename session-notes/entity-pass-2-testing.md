# Second entity pass — tester handoff

Branch: `claude/entity-pass-2` in Theory-box/Jak-1-Level-Builder-Tool.
Test target: `Documents/JakAndDaxter/test-modbase/data`, NOT active/jak1/data.
Status: ready for in-game testing, not yet gameplay-validated.

## What changed

Continued from commit 53c3f03 after reviewing the branch history, Actor Notes,
the ordered ToDo list, database/schema/export architecture and local GOAL source.
The canonical JSONC database remains separate from actor code. New behavior
is in 15 separate `addons/opengoal_tools/subtypes/*.gc` files, selected by each
actor's database `edited` field. No vanilla actor source was overwritten.

Added 13 database records and updated Gol, Maia and Green Sage:

- Citadel stairs: triggerable, adjustable rise distance and delay, no sage gate.
- Silo steps: trigger/trigger-rise, linked steps, no warehouse task or camera.
- Reflector mirror: beam endpoint from an Empty; breaking sends stop to links.
- Citadel camera actor: repurposed as an invisible trigger relay, with optional
  completed-task gate, without the original movie.
- Precursor arm: optional own task and placement-relative behavior.
- Large beach rock: no forced camera/player grab; optional own-task reward.
- All Pontoons: exposed as an invisible cutscene helper, NOT a bridge model.
  The existing edited warrior already tolerates having no helper.
- Helix button, rising dark eco and slide door: linked setup; adjustable rise
  distance/speed; no singleton controller or forced camera/music sequence.
- Flut Flut egg: own task, placement/rotation, fall distance and hatch position.
- Gorge race: own required task and finish Empty, configurable radius and time,
  placed start/finish banners, no vanilla world-space abort planes.
- Exit chamber: unlocked ride-only version with original animation and optional
  own-task cell; no five-charger story puzzle or forced level transition.
- Gol and Maia: available as NPCs, Intro texture pages and own-task support.
- Green Sage: rescue-only, optional beam target, no pre-boss sequence;
  saved completion restores open cage bars and avoids repeating task advancement.

Supporting fixes:

- Water ripple export now respects schema defaults and explicit overrides.
- Required-field warnings cover required schema task and object references.
- Shared edited-code export replaces changed dependency registrations and
  removes duplicates instead of creating conflicting game.gp build targets.
- Added Silo Step's battlecontroller dependency, relay trigger metadata,
  non-common sound requirements and updated actor documentation.
- Repaired the standalone schema tests and added a Blender integration test.

## Validation already done

- 12 standalone schema tests passed; all addon Python files parse.
- Blender 4.5 factory-startup registration/export checks passed for all 15
  edited actors: links, missing required fields, custom task, coordinate
  conversion, JSONC, DGO inclusion, per-level/shared/vanilla code selection,
  repeated export and changed shared dependencies.
- All 15 edited GOAL files compiled with substituted per-level type names.
- All 15 generated shared files compiled in fresh GOALC processes using their
  exported dependencies (after bootstrapping pckernel-impl for the source
  project's existing pad.gc dependency-order requirement).
- Declared art-group files exist in modbase's decompiler raw_obj directory.
- git diff whitespace check passed; packaged ZIP integrity checked.
- All compile/export checks wrote to a disposable source copy under Codex work.
  Neither installed game folder was changed. No in-game tests were performed.

## Suggested test order

1. Install the addon from this branch's `addons/opengoal_tools` folder or the
   supplied addon ZIP. Restart Blender to clear the previous addon modules.
   Point this test blend's Data folder at test-modbase/data. Use a small test
   level and a separate test save. Resolve required-field warnings before play.
2. Test stairs, linked silo steps and the trigger relay. Trigger twice and
   reload. Check saved raised positions and relay task gating. Avoid relay cycles.
3. Break the mirror with its endpoint linked; check stop reaches its receivers.
   Trigger the beach rock and test the precursor arm, both with no task and
   with distinct custom tasks. Verify any reward appears where the actor is.
4. Link Helix button slot 0 to water and slot 1 to the slide door. Set the water
   controller at its initial surface height and match the water-height field.
   Link a volume covering the whole rise. Use Sunken/Sunkenb texture source.
   Check collision, damage, door closure and rise speed; reload should reset it.
   Its alt actors, when used, should be ordered bottom-to-top as in vanilla.
5. Test the egg at a non-vanilla location and rotation. Set a hatch/reload Empty,
   assign a custom task, knock it down and reload before/after collecting its
   reward. Without a hatch reference the broken egg reloads at its placed origin.
6. Give the race its own custom task and a finish Empty. Rotate both gates and
   test start/finish detection, timeout, abort and improved record. Use a
   task-aware reward actor for its cell; the race advances task progress.
7. Test the chamber ride and optional cell at a different location. This is
   deliberately ride-only: it spawns its own button/door and skips the chargers.
8. Link Gol to Maia and test their animations with Intro textures. Send open
   to Green Sage, with and without an optional beam target. Check rescue, task
   advancement and open bars after save/reload. No pre-boss story is expected.
9. Repeat a small level using Shared file placement, then re-export it twice.
   Also test Vanilla selection on one actor. If changing child type definitions
   in an already-running compiler, restart GOALC before rebuilding.
10. Regression check custom-task cells, scout flies, crates containing either,
    oracle alternate tasks and existing edited actors; collect, save and reload.

For failures, share the actor, links/field values, task setup, code placement,
reproduction steps and compiler/game log. Note whether it fails on first load,
after triggering or only after save/reload.

## Still outside this pass

Gameplay, Blender preview meshes, sound playback and save persistence require
the tests above. Sound scanning includes inherited code, so some bank warnings
may be conservative. Texture-source/remap limitations remain. Particles and
enemy drops are separate planned passes. Hidden actors without usable art or
entity initialization remain hidden. Older limits such as gondola routing,
oracle speech and yakow herding remain documented in Actor Notes.
