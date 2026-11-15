# Entity pass feedback follow-up — November 7, 2026

Test using test-modbase/data. No installed game files were changed during development.

## Changes

- Exit chamber: optional path and travel time; no path preserves animated travel.
  Path is world-space, starts at its first point, keeps the placed rotation and
  travels backwards on return. Time excludes the one-second door-closing delay.
  Optional linked CAMERA_ is active during either ride mode, returning to base
  camera afterwards. Starts closed is optional. External trigger/open unlocks;
  only the built-in button starts a ride. Five vanilla charger notifications
  also unlock the door. Removed a leftover vanilla continue-point write and
  disabled the unrelated assistant hint.
- Gorge start: required task/finish controls now appear in the warning popup,
  and required field labels appear beside the controls. Corrected the preview
  filename to rolling-start-whole-lod0.glb. Optional Direct cell reward spawns
  at the finish on a winning run and uses the Movie Position panel for its
  destination/collection animation. A saved win restores an uncollected cell.
- Snow switch: default movie position at the switch origin, rather than ground
  selected by the cell's fallback; the Movie Position panel overrides it.
  Exact visual alignment with the switch top remains a runtime check.
- Snow bumper: Movie Position panel controls the last bumper's cell destination;
  removed its uncontrolled launch velocity when no position is supplied.
- Snow fort gate: prev/next links exposed; previous switch/gate can open it,
  opening propagates to the next gate, and opening is saved per entity.
- Fisherman's boat: preview mapping added. Restored vanilla docked buoyancy and
  player-force handling on the custom waterline; path rides now explicitly
  maintain Jak's deck-relative position instead of relying on process-grab alone.
- Pelican: missing-path warnings now include descriptions of the named routes.
- Link order: Edit order beside chaining and multi-link lists; staged popup
  supports drag grips and top/up/down/bottom buttons. Confirm applies the order;
  cancelling leaves actor links alone. Rechaining clears stale endpoint links.
- Required and soft warning buttons both display count followed by the triangle.

## Evidence and limits

Reviewed the existing edited actors, matching vanilla modbase GOAL functions,
database panels, link operators, warning UI and exported asset filenames.
All seven relevant edited actor files compile. Existing 12 schema tests and
the original Blender export smoke test pass. A new Blender regression script
checks required popup labels, path descriptions, movie-position exports, chamber
fields, direct reward setting, ordered links, endpoint clearing, staged edits
and registered UI icons. These are compile/export checks, not gameplay tests.

Assumption (80% confidence, based on the existing boat camera mechanism): the
requested POV link means an addon CAMERA_ object. This implementation switches
to that camera; it does not create a separate animated pov-camera actor.

Manual acceptance still needed: chamber travel/collision and camera tracking,
both endpoints and save/reload; charger and button events; race reward on win,
loss and reload; snow cell visual positions; boat landing response and rider
attachment on turns; popup mouse dragging and cancel in the visible Blender UI.
Compilation cannot establish those runtime/interaction results.

## Compact tester checklist

1. Install this branch's addon, restart Blender, point the test blend to modbase.
2. Chamber: test Starts closed + external trigger, then internal button. Try a
   3D path with 7.5s travel and return; repeat with no path and with a linked camera.
3. Race: leave task/finish blank and open warnings; then fill them, enable Direct
   cell reward and set Movie Position. Win, collect, save/reload; also reload
   after a win before collecting and verify no duplicate reward after collection.
4. Snow: collect switch cell with default/explicit movie position; chain a switch
   and two gates; finish bumpers in different orders with a movie position on each.
5. Boat: verify preview, jump on different parts while docked, ride a curved route
   and return without sliding off. Confirm camera restoration on arrival.
6. Links: mix actor names/types, drag and use all four reorder buttons, cancel,
   reopen and confirm; check exported prev/next and multi-link order.
7. Check Pelican path explanations and matching required/soft warning formatting.

Later baking/lighting/export/audit branches have not been started. This follow-up
stays on claude/entity-pass-2 for acceptance testing.
