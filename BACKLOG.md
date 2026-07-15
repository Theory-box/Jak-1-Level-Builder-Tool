# Backlog

Cross-cutting tracking file: untested risks, wanted features, known minor
issues, and cleanup opportunities. Per-feature design discussions live in
`session-notes/`.

---

## Untested risks (recent merges)

Things that compile clean and look right statically but haven't been verified
in-Blender. Bumped here so they're not forgotten.

### Waypoint link source (merged commit `433c299`)

- **`ctx.temp_override` in `OG_OT_WaypointSourceFrame`** — uses the Blender
  4.x context-override API to invoke `view3d.view_selected` while temporarily
  selecting the source object. Should work in 4.4 but unverified. If it
  breaks, fallback is `bpy.ops.view3d.view_selected('INVOKE_DEFAULT')` after
  setting selection directly (less precise context but more compatible).
  Location: `addons/opengoal_tools/operators/links.py`
- **`invoke_props_dialog(width=320)` popup for the curve picker** — visually
  unverified. May be too narrow on hi-DPI or too wide on narrow windows.
  Location: `OG_OT_WaypointSourceLinkCurve.invoke()`
- **UIList row layout with right-aligned point-count sub-row** — the dimmed
  `n pts` label may interact oddly with row selection highlighting.
  Location: `OG_UL_WaypointSources.draw_item()`

---

## Wanted features

### Schema-driven export migration (current focus)
Retire every per-actor hardcoded branch so the jsonc DB is the single source
of truth — behaviour editable from the DB, and any feature copyable onto
another actor by editing data, not code. Full audit with per-item IDs, "what
it blocks", and a data-driven fix for each: `session-notes/hardcoding-audit.md`.

Pattern proven by `eco-info-picker` (crate + green eco vent): for each item,
reproduce the current exported bytes from the DB, prove equality in
`export/test_schema_emit.py`, then delete the branch. Approve items per-ID.

- [x] Reusable computed-encoder pattern established (eco-info-picker, const,
      water-height, target-vector, need_vol)
- [x] **A** · direct migrations done — redundant per-actor branches deleted;
      enemy/spawner/notice-dist via predicate-tagged trait fields (TraitFields)
- [x] **B1** · const-lump encoder (fuel-cell / buzzer / money eco-info)
- [x] **B2** · eco-door flags: link-derived `ecdf00` bit via a computed handler
- [x] **B3** · water-vol unified on the VOL_ system — `is_water` trait +
      `need_vol` (convex `_vol_planes`); legacy WATER_/box paths removed
- [x] **B4** · launcher target-vector encoder (`object_ref` → vector)
- [x] **C** · trait flags moved into the DB (`db.py` trait layer + predicates)
- [x] **D** · launcher / spawner → DB flags (`is_launcher` / `spawns_lurkers`)
- [~] **E** · REVISED per user: bespoke `OG_PT_Actor*` panels are KEPT in code;
      their choice-lists are now DB tables (CrateTypes / BridgeVariants / …).
      STILL OPEN: gate the bespoke panels by a DB flag (e.g. `"panel": "crate"`)
      so attaching one to a new actor is a one-line DB edit rather than code +
      a `DEDICATED_FIELD_UI_ETYPES` / `GENERIC_PANEL_ETYPES` entry.
- [x] **F** · spawn-time defaults seeded from DB `fields[]` (one loop)
- [x] **G** · `export_as` field for abstract remap (eco-door → jng-iris-door)

Beyond the audit, also delivered on this branch: the variant system
(glb / art_group / code / defaults + preview offset + generalised pre-spawn
menu + Mesh Preview Settings), and the Object Settings reorder + multi-select
frame/duplicate/delete.

Deferred actor-specific fixes (need engine source or a manual per-actor pass):
- eco-door one-way / starts-open flag values — needs `baseplat.gc`
- water damage types (drown / dark-eco / lava / electric / tar; `endlessfall`
  is wrong for water) — needs `water.gc`; ideally an extensible DB table
- alt-vector generalisation (launcher + fuel-cell `movie-pos`, `w_mode`
  seconds/angle; grep actor code for other alt-vector users)

### Fuel-cell / scout-fly game-task binding (future)
fuel-cell and buzzer (scout fly) currently export a fixed `(game-task none)`
in their eco-info const lump. To wire them into the task system — so
collecting them actually increments the cell/fly count and drives task-based
logic — the game-task must become settable per instance. Plan: replace the
`const` eco-info lump with a picker-style computed encoder (like
eco-info-picker) that formats a chosen game-task into the cell-info/buzzer-info
lump. Not urgent; noted so the current const implementation isn't mistaken for
final.

### Default camera entities (revisit AFTER the export migration)
Jak 1 now ships built-in camera entities, placed via a top-level `cameras[]`
array (separate from `actors[]`) and triggered by a volume. Mode is chosen by
which lumps are present: `cam-circular` (needs `pivot`, opt. `maxAngle` /
`focalPull`), `cam-standoff` (needs `align`), or `cam-string` (default; any of
the `stringMax/MinLength` / `stringMax/MinHeight` lumps). Generic lumps: `fov`,
`interpTime`, `tiltAdjust`. `flags` takes a `cam-slave-options` enum. Three
volume lumps at keyframe 0: `vol` (active inside), `pvol` (preferred on
overlap), `cutoutvol` (disabled inside); optional `interesting` vector = point
of interest. Documented example (test-zone):
https://github.com/open-goal/jak-project/blob/697337166da69af6515e97c5a9894b8ba2abc93c/custom_assets/jak1/levels/test-zone/test-zone.jsonc#L165

The addon's existing custom camera actor predates this; the built-in form is
likely simpler to emit and needs no custom actor code. If the custom actor has
capabilities the built-in lacks, expose **both**. **Do not start before the
schema-driven migration above is finished** — restructuring is the priority;
this is a feature addition to slot in afterward.

### Sliding tube zones (Snowy Mountain butt-slide style)
The slide mechanic in Jak 1 (snow tubes, Lava Tube, Fire Canyon) is a
**player state** (`target-tube`), not a placeable actor or surface effect.
The `tube` PAT material alone won't trigger it — there has to be code that
pushes Jak into the `target-tube` state when he enters a slide zone.

No new addon feature is strictly required to support this — the three
existing pieces compose into a solution:
- **Custom Types** (`og.spawn_custom_type`) for placing a `tube-zone`
  empty in the level
- **GOAL Code panel** (`og_goal_code_ref`) for attaching the deftype
  + defstate that runs the player-state push
- A collision shape on the actor for the overlap test (or a linked
  volume — collision-shape pattern used by other custom actors)

The shape of the GOAL code:
```
(deftype tube-zone (process-drawable)
  () (:states tube-zone-idle))

(defstate tube-zone-idle (tube-zone)
  :code (behavior ()
    (loop
      ;; if *target* overlaps our shape:
      ;;   (send-event *target* 'change-state target-tube ...)
      ;; — exact incantation TBD, see local source
      (suspend))))
```

**Blocker before this is buildable:** the exact GOAL idiom for forcing
Jak into `target-tube` from an external process. Need to check the
local OpenGOAL source — `target-tube.gc` for the entry signature, and
either `snow-bumper.gc`, `lavatube.gc`, or the firecanyon sled setup
to see what the engine itself does at the entry points.

Optional follow-on: pre-baked "tube-zone" template added to the GOAL
boilerplate generator so users get the skeleton with commented TODOs
instead of starting from the generic actor boilerplate.

### Heap-budget audit
Audit the level's estimated heap usage and warn when nearing the ~11 MB
limit. Three sketches discussed (A/B/C in audit conversation); recommended
**A + C combined**: refine the existing tpage-group check to also count
auto-included groups (collectables, generic-obs, etc.) AND show which
actors contribute each group when the warning fires. Skipped during the
spawn-panel branch since the user wanted to ship.

### Loop / cycle-mode for paths
Currently we have ping-pong (forward + reverse). A separate "explicit loop"
mode would need engine investigation — most patrol enemies already loop by
default per their hardcoded GOAL code, so a generic toggle would either be
a no-op or need per-actor-type support to be meaningful.

### Manager panel for cameras / triggers
The Camera and Triggers panels were deleted during the spawn-panel branch
because they were `bl_parent_id` children of the Spawn picker. Per-selection
editing lives in Object Settings now, but **level-wide views are lost**:
- "All cameras in level" list with inline mode/FOV editing
- "All trigger volumes" list with link status overview
- The `og.clean_orphaned_links` button is only reachable via F3 search
- (the operator itself still exists)

A future "Level Manager" sub-panel would resurrect these views.

### Mesh as waypoint source
Currently curves only. Meshes considered but skipped because vertex order
isn't always meaningful (creation order; breaks with merge-by-distance).
If added, choose between:
- Vertex creation order (simple, brittle for complex meshes)
- Follow edge connectivity to derive ordered path (more code, more correct
  for arbitrary loops/paths)

### Preview Models toggle placement
Lives in addon Preferences right now (Edit > Preferences > Add-ons >
opengoal_tools). Was inside the deleted Enemies sub-panel before. Might be
more discoverable as a small toggle in the spawn picker.

---

## Known minor issues

### Engine-side: `ice` material crashes with `ground` or `obstacle` mode
Confirmed in-game (2026-05-26): setting a surface to `collide_material=ice`
combined with `collide_mode=ground` or `collide_mode=obstacle` crashes
when the player touches it. `collide_mode=wall` works fine.

The addon doesn't pack PAT integers itself — `collide_material/event/mode`
are stored as Blender custom properties and reach the engine via the GLB
`extras` field, where the OpenGOAL level compiler reads them. So this
bug lives either in the level compiler (bad PAT encoding for ice+ground)
or in the engine runtime (likely a null-deref in the ground-friction
dispatch for ice surfaces).

Workaround: use `ice` only on walls. For slippery floors, try `tube`
or one of the other 22 surface materials.

Could add a pre-export audit warning in `audit.py` (slot next to
`check_tpage_budget` etc.) to flag the combo before it crashes.

### Stale favorites in spawn picker
If a future addon update removes an entry from `SPAWN_INDEX` that the user
had favorited, the stale entry sits in `spawn_favorites` forever. Harmless
because the UI ignores unknown spawn_ids — but it's dead data. ~5 lines to
prune at population time.

### Two "NavMesh" sub-panels under Object Settings
`OG_PT_actor_navmesh` (for actors that use a navmesh) and
`OG_PT_selected_navmesh_tag` (for the NAVMESH_ mesh itself) — poll-gated to
different selection types so they don't both appear at once, but the
duplicate label could confuse if you select multiple things. Pre-existing,
not from any recent branch.

### Undo-stack churn on category / favorite toggles
`og.toggle_spawn_category` and `og.toggle_spawn_favorite` register an undo
entry per click because `UNDO` is in `bl_options`. Same behavior as the
previous `prop(toggle=True)` so not a regression — but shift-clicking
through several tiles creates many undo entries. Removing `UNDO` would
flatten the stack at the cost of not being able to Ctrl-Z a tile toggle.

### Path B (swamp-bat) still on legacy waypoint system
The waypoint-link-source refactor intentionally left Path B (`_wpb_NN`
empties on swamp-bat) on the legacy name-grep export path. Only swamp-bat
uses it. Migrating Path B to the new list system is busywork; punt until
someone needs it.

---

## Cleanup opportunities

### Dead helpers in `data.py`
After the spawn picker refactor, ~7 `_build_*_enum`-style functions and
their generated module constants (`ENEMY_ENUM_ITEMS`, `PROP_ENUM_ITEMS`,
etc.) are still in `data.py`. They're used internally by `data.py` to build
the constants, but the constants themselves are no longer referenced by
the spawn panel. Verify before removing — might still be reached by
operators that read `props.entity_type` from per-category source props.

### Dead imports across `panels/*.py`
Several panels still import `_draw_entity_sub`, `_draw_platform_settings`,
`_header_sep` from `utils.py` even though only `_draw_platform_settings`
is actually called (from `actor.py` and `selected.py`). The other two are
dead. Harmless but stale.

### Stale `entity_search*` properties
On `OGProperties`. Only `panels/tools.py` uses `entity_search` (one shared
search bar). The other three (`entity_search_selected`, `show_search_results`,
`entity_search_results`) appear unused after the spawn-panel refactor.
Verify before removing.

### Dead unregister cleanup
Already pruned 44 names from the Object-attr cleanup loop. The remaining
20 names should all be live (they correspond to registered typed
properties); verify next time someone passes through.

---

## Resolved (kept for traceability)

- **"Category sort breaks list"** — root cause: `TILE_CATEGORIES` was
  removed from imports during a cleanup pass but still referenced inside
  the `CATEGORY` sort branch of `_compute_sort_order`, raising NameError
  silently. Resolved by removing the option entirely per user request.
- **`bpy.data.scenes` not accessible during `register()`** — Blender wraps
  `bpy.data` in `_RestrictData` during addon load. Fixed via a zero-delay
  `bpy.app.timers.register` callback that populates after restrictions lift.
- **Stale unregister `delattr` loop** — 44 names removed (`og_alt_task`,
  `og_spring_height`, etc. — never actually registered as typed properties;
  the `try/except` was always swallowing the AttributeError).
- **`OG_PT_Triggers` + `OG_PT_Camera` appearing under new Spawn picker** —
  they were children via `bl_parent_id = "OG_PT_spawn"` from before the
  refactor. Both deleted in `feature/spawn-panel-ui-update`.
- **Duplicate Waypoints panel** — `OG_PT_Waypoints` in `panels/tools.py`
  was a standalone copy of the actor-selected version. Removed.
- **Camera anchor confusion** — removed from spawn picker (was the only
  picker item requiring viewport selection). The per-spawn camera-anchor
  workflow still exists via the "Add Camera" button when a `SPAWN_/CHECKPOINT_`
  empty is selected in Object Settings.
