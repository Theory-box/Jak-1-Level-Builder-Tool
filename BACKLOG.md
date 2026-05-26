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
