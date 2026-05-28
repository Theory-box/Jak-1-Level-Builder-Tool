# Load Boundaries + Checkpoint Settings — Design Notes

**Branch:** `feature/load-boundaries-checkpoints`
**Repo:** `Jak-1-Level-Builder-Tool` (the addon repo — NOT `Claude-Relay`;
the addon copy in Claude-Relay is a stale snapshot, do not patch it)
**Status:** Task 1 + Task 2 **implemented** — see §9 log. Untested in Blender.
**Last updated:** 2026-05-28

Goal: expose per-checkpoint level/display settings, and add a placeable
Load Boundary object, so custom levels can stream multiple levels the way
the base game and shipped mods (Kuitar's *the-forgotten-lands*) do.

---

## 1. Verified engine mechanics (jak-project + TFL reference)

### What actually loads a level
Loading is driven **only** by the `*load-state*` two-slot `want` buffer.
The three things that write to it:
1. `target-continue` (spawn / death-respawn) — copies the active
   continue-point's `lev0`/`lev1`/`disp0`/`disp1` into the buffer and
   blocks until both report `'active`. (`target-death.gc`)
2. Load boundaries — on crossing, fire their `cmd-fwd`/`cmd-bwd`.
3. Explicit scripted `want-levels` / `want-display-level` calls (buttons,
   doors, elevators, cutscenes).

### bsphere is NOT a load trigger (correction)
Earlier assumption was wrong. The `level-load-info` `:bsphere` feeds
`inside-sphere?`, the camera `level-distance`, and `level-get-target-inside`
(which level you count as being "in" → mood / vis / draw priority). It does
**not** cause a level to load. A single custom level loads because its
continue-point wants it, and stays loaded because nothing requests it out.
Action item: fix the misleading "considers the level nearby" comment in
`export/writers.py` (bsphere should bound the geometry, not be inflated to
"trigger loading").

### continue-point fields (the checkpoint)
`name level trans quat camera-trans camera-rot load-commands vis-nick
lev0 disp0 lev1 disp1` (+ `flags`).
- `lev0`/`lev1`: up to two resident levels (engine buffer is exactly 2).
- `disp0`/`disp1`: `display` / `special` / off (`#f`).
- `vis-nick`: see correction below.
- `level`: the checkpoint's home level (music/settings lookup) — separate
  from the resident set.

### vis-nick (Kuitar correction)
Do **not** default `vis-nick` to `'none`. `vis` is also how the game knows
which level you're "in" for music and which menu opens, etc. Default it to
the **short nickname of the home level** (same value the addon already
computes for `level-load-info :nickname`), and keep it editable.
Open question to validate in a build: custom levels lack real vis BSP data,
so confirm a real nick on a custom level behaves (Kuitar ships it this way,
so it should be fine).

---

## 2. How load boundaries are really authored

Not runtime entities (earlier idea was wrong). They are **static data** in a
single shared file:
- `goal_src/jak1/engine/level/load-boundary-data.gc`
- Built through a `static-load-boundary` macro, wrapped in
  `*static-load-boundary-list*` via `static-lb-list`.
- The file resets `*load-boundary-list*` then defines the static list; it is
  **regeneratable by an in-game boundary editor** (`---lb-save`).
- Shipped mods edit this same file. TFL added valley/mines boundaries here.

### `static-load-boundary` keys
- `:flags` — list of `load-boundary-flags` symbols: `closed`, `player`
  (player-cross vs camera-cross), plus any **custom flags** the build adds.
- `:top` / `:bot` — float heights (game units, 4096/m).
- `:points` — flat list of horizontal vertex coords (2 floats per vertex).
- `:fwd` / `:bwd` — crossing command, one of:
  - `(load lev0 lev1)`
  - `(display lev0 <mode>)`   modes: `display`, `display-no-wait`, off
  - `(vis <nick> #f)`
  - `(force-vis lev0 <onoff>)`
  - `(checkpt "<continue-name>" #f)`
  - `invalid` / `(invalid #f #f)` = no command

### Geometry semantics depend on the `closed` flag (Kuitar correction)
- **Open** (no `closed`): `:points` are a polyline in the horizontal plane;
  the line is **extruded vertically between `:top` and `:bot`** to form a
  wall the player/camera crosses. 2 points = a single wall segment.
- **Closed** (`closed` set): `:points` form a **flat horizontal polygon**;
  only **one** height value is used to place that polygon (believed to be
  `:top` — confirm in `check-closed-boundary`). Used for "am I inside this
  area" region tests, not a crossing wall.

So the addon must interpret a placed Load Boundary object differently by
flag: open → take the object's edge/polyline footprint + vertical extent;
closed → take the object's flat polygon footprint + a single height.
Reuse the addon's existing Blender(Z-up) → GOAL(Y-up) + meters conversion
that spawns already use; horizontal footprint = GOAL X/Z, height = GOAL Y.

---

## 3. Multi-level streaming model (validates "design for multi")

A custom level streams in by being referenced from sibling levels, not by
its own bsphere. In TFL, `valley`:
- appears as `:lev1` on base-game continue-points,
- is loaded/displayed by `(load …)` / `(display …)` boundary commands in
  `load-boundary-data.gc`,
- is toggled at runtime by scripted `want-display-level 'valley …` calls.

So: streaming = continue `lev0`/`lev1` + boundary `load`/`display` commands,
both referencing sibling levels. Level pickers must enumerate all project
levels (`_all_level_collections(scene)`), which the addon already supports.

---

## 4. Addon current state

- `export/writers.py::_make_continues` already emits a continue-point per
  spawn/checkpoint empty, but hardcodes `vis-nick 'none`, `lev0 = self`,
  `disp0 'display`, `lev1 #f`, `disp1 #f`, `load-commands '()`, no flags.
- No load-boundary system at all. Loading currently relies on the
  continue-point (and the inflated bsphere comment).
- `checkpoint-trigger` / `camera-trigger` process types are generated in
  `write_gc` (pattern reference, though boundaries will be static data, not
  a process).

---

## 5. Design — checkpoint settings (low risk)

Extend the checkpoint/spawn empty; `_make_continues` reads these instead of
hardcoding. Defaults preserve a working single-level checkpoint.

| Property        | Type            | Default            | Notes |
|-----------------|-----------------|--------------------|-------|
| `lev0`          | level enum      | self               | maps self→level name |
| `disp0`         | enum            | `display`          | display / special / off |
| `lev1`          | level enum+none | none (`#f`)        | second resident slot |
| `disp1`         | enum            | off                | display / special / off |
| `vis-nick`      | string          | **home level nick**| editable; not `none` |
| `flags`         | text (symbols)  | none               | continue-flags passthrough (advanced) |
| `load-commands` | text (GOAL)     | `()`               | spliced verbatim |

**No save-point toggle.** Verified the jak1 `continue-flags` enum
(`contf00 contf01 warp demo intro sage-intro sage-demo-convo title contf08
contf09 game-start sage-ecorocks`) — there is no save-point flag; Jak 1
checkpoints are just continue-points. Dropped the planned toggle; advanced
flag needs go through the free-text `flags` field instead.

Export: `collect_spawns` gathers the props; `_make_continues` emits them;
validate `lev0`/`lev1` against known levels with a clear export warning on a
dangling reference.

---

## 6. Design — load boundary (new "Load Boundary" in Level Flow)

A placeable plane/mesh, like trigger volumes. Export emits
`static-load-boundary` entries into `load-boundary-data.gc` via a managed
marker block (same technique as the level-info "CUSTOM LEVELS" block) — NOT
runtime entities.

Per-boundary properties:
- `closed` (bool) — switches geometry interpretation (wall vs flat region).
- `player_cross` (bool, default on) — player vs camera activation.
- `top` / `bot` (float, meters) — vertical extents; for `closed`, only the
  height value is used.
- Forward command: enum `none/load/display/vis/force-vis/checkpt`
  + `fwd_lev0`, `fwd_lev1`, `fwd_disp_mode`, `fwd_continue_name`.
- Backward command: same set, independent.
- **`custom_flags` (advanced, free text/multi-select)** — extra
  `load-boundary-flags` symbols spliced into `:flags`. Easy to support
  (the macro just splices a symbol list); the only requirement is that those
  symbols exist in the build's `load-boundary-flags` enum (Kuitar's TFL adds
  its own). Surfaced as an advanced field so TFL-style custom flags work.

Geometry extraction:
- open: object's edge/polyline footprint → `:points`; vertical extent → top/bot.
- closed: object's flat polygon footprint → `:points`; one height → top.

---

## 7. Open items to verify in-build (before/early in implementation)

1. **Macro/enum parity.** TFL carries a "TFL note: added custom flags"
   comment, so `load-boundary-flags` (and possibly the macro) differ from
   vanilla jak-project. Target whatever base the addon's builds use; confirm
   `load-boundary-data.gc` exists there and `static-load-boundary` matches.
2. **closed height field** — confirm `:top` (vs `:bot`) is the one used for
   closed polygons (`check-closed-boundary`).
3. **vis-nick on custom levels** — confirm a real nick (not `none`) behaves
   given custom levels have no vis BSP data.
4. **Where to patch** — single global `load-boundary-data.gc` with a managed
   block keyed per level, so re-export of one level doesn't clobber others.

---

## 8. Implementation order

1. **Checkpoint settings** end-to-end (props → `collect_spawns` →
   `_make_continues`, incl. vis-nick default = nick, flags, load-commands).
   Low risk, immediately testable, exercises the multi-level picker.
2. **Load Boundary** object: placed-plane → `:points` extraction (both open
   and closed), export into `load-boundary-data.gc` managed block, command
   UI (fwd/bwd) + flags incl. custom-flags passthrough. Prototype one open
   `load`/`display` boundary between two test levels before full UI.

---

## 9. Implementation log

### Task 1 — checkpoint settings (done 2026-05-28)
Per-checkpoint continue-point settings now editable on SPAWN_/CHECKPOINT_
empties; `_make_continues` reads them instead of hardcoding.

Files changed:
- `properties.py` — `CP_DISP_ITEMS`, `_cp_lev0_items`, `_cp_lev1_items`
  (level pickers from `_all_level_collections`).
- `__init__.py` — registered Object props `og_cp_lev0/disp0/lev1/disp1/
  vis_nick/flags/load_commands` (+ unregister cleanup). Dynamic-items enums
  take no `default=`; first item ("self"/"none") is the default.
- `export/scene.py::collect_spawns` — emits the `cp_*` keys into spawn dicts.
- `export/writers.py::_make_continues` — resolves self/none→symbols,
  off→`#f`; vis-nick blank → level nick; flags/load-commands passthrough.
  No-spawns default branch vis-nick also changed `none` → level nick.
- `panels/selected.py` — shared `_draw_continue_settings` block on both the
  spawn and checkpoint panels.

Verified by executing the real `_make_continues` source against sample
settings (default / two-level / load-only / flags+load-cmds / lev0-elsewhere
/ no-spawns). All emit correct GOAL.

Not yet done: in-Blender register test (needs Blender), and an end-to-end
export+compile of a level. Dynamic-enum int-storage caveat applies — if a
referenced level is renamed/deleted the stored slot may shift; export should
later warn on an unknown lev0/lev1 (TODO).

### Task 2 — load boundaries (done 2026-05-28)
Placeable LOADBND_ mesh exporting to `static-load-boundary` entries in
`load-boundary-data.gc`. Approach: append a managed per-level block (own
`static-lb-list` + `doarray (load-boundary-from-template …)`) keyed by markers;
stock entries untouched; idempotent. Confirmed vanilla jak-project uses the
same macro/format and ends with the `doarray … load-boundary-from-template`
that builds runtime boundaries — so the addon's base matches.

Files changed:
- `export/paths.py` — `_load_boundary_data()` path helper.
- `export/scene.py` — `collect_load_boundaries` + `_lb_edge_chain`. Footprint
  from mesh verts (polygon loop if faces = closed; edge-walk if edges = open);
  game X = bx, game Z = -by, height = bz; ×4096 to game units. Flat-drawn open
  boundary gets a default wall extent (+30m/-128m) so it still works.
- `export/writers.py` — `_make_static_boundary` + `_lb_cmd_form` (emits
  load/display/vis/force-vis/checkpt; level args BARE symbols since the macro
  quotes the list; self→level, none→#f; display off→#f), and
  `patch_load_boundaries` (marker block, idempotent, removes block when empty).
- `export/__init__.py` — export the three new symbols.
- `spawn_items.py` — "Load Boundary" item in Level Flow (og.spawn_load_boundary).
- `operators/spawn.py` — `OG_OT_SpawnLoadBoundary` (plane mesh, wire, orange)
  + registered in CLASSES.
- `properties.py` — `LB_CMD_ITEMS`, `LB_DISP_ITEMS`, `_lb_level_items`.
- `__init__.py` — registered Object props og_lb_closed/player/custom_flags +
  fwd/bwd cmd/lev0/lev1/disp/name (+ unregister cleanup).
- `panels/selected.py` — `_draw_selected_load_boundary` +
  `OG_PT_LoadBoundarySettings` panel (+ CLASSES, managed-object, routing).
- `build.py` — `patch_load_boundaries(name, collect_load_boundaries(scene),
  scene)` after each of the 3 `patch_level_info` sites.

Verified by executing real `_make_static_boundary` / `_lb_cmd_form` /
`patch_load_boundaries` against sample open+closed boundaries: correct flags,
command forms, and idempotent block insert/replace/remove. All files compile.

### Known items to confirm when testing
- **Fwd vs bwd side** is decided by the engine from point winding / the
  computed rejector — not emitted by us. If a boundary fires the wrong
  direction, reverse the mesh's vertex/edge order.
- `(meters …)` not used for boundary floats — raw game units (×4096) to match
  the vanilla/editor format exactly.
- Open boundary needs vertical extent: draw a wall mesh, or rely on the
  flat-fallback extent.
- Dynamic-enum int-storage caveat (level refs) applies to boundary level
  pickers too; export-time validation/warn still a TODO.
- Closed-polygon height uses :top (zmax); :bot set below. Confirm against
  `check-closed-boundary` if closed areas misbehave.

### Pre-test audit (2026-05-28)
Full review of both tasks. Issues found and fixed:

1. **doarray inline expression (compile bug).** `patch_load_boundaries`
   emitted `(doarray (i (static-lb-list …)) …)`. The doarray macro substitutes
   its array arg multiple times (`(-> arr length)`, `(-> arr i)`), so an inline
   `(static-lb-list …)` would allocate the static array several times. Fixed:
   emit a named `(define *og-custom-lb-<level>* (static-lb-list …))` then
   `(doarray (i *og-custom-lb-<level>*) …)` — matches the stock pattern.

2. **LOADBND_ meshes leaking into level geometry (invisible walls).**
   `export_glb` fallback used a prefix allow-list missing LOADBND_, and the
   v1.1.0 whole-scene fallback excluded only preview meshes. In normal
   collection mode LOADBND_ is safe (it lives in Triggers, outside the Geometry
   collection), but the fallbacks would have exported it as geometry. Added
   LOADBND_ to both exclusions.

3. **Sort Collection misrouting.** `_classify_object` would route a LOADBND_
   mesh to Geometry/Solid. Added a LOADBND_ → Triggers case.

4. **Orphaned boundaries on level delete.** `remove_level` cleaned level-info.gc
   and game.gp but not the boundary block. Added a marker-based strip of the
   level's load-boundary-data.gc block.

Verified safe / no regressions:
- `_level_objects` is scoped to the active level → no multi-level
  cross-contamination in collect_load_boundaries.
- Only one continue-point emitter (`_make_continues`); cp_* keys read with
  defaults, so old/foreign spawn dicts are unaffected.
- Picker dispatch (`OG_OT_SpawnSelected`) invokes item.operator generically.
- No dynamic-items EnumProperty given `default=` (would error at register).
- No circular import (properties → collections only).
- audit.py is class-prefix-specific → does not flag or crash on LOADBND_.
- All 13 touched modules byte-compile.

Still-open (non-blocking) TODOs:
- Export-time warning for unknown lev0/lev1 / boundary level refs (dynamic-enum
  int-storage can shift on level rename/delete).
- force-vis emits onoff #t only; display with lev0=none emits (display #f …).
- No audit check yet for a boundary that has a command but no level/name set.

### Second audit (2026-05-28)
Verified the emission format against the runtime consumer and fixed a default-
geometry mismatch.

Confirmed correct (read `load-boundary-from-template` in jak-project):
- Template = 4-element array [flags-binteger, float-array, fwd-list, bwd-list].
- float-array = [top, bot, x0, z0, x1, z1, …]; num-points = len/2 − 1; points
  read as (x, z) pairs. Our emission (top, bot, then game-X/game-Z pairs)
  matches exactly. flags = elem0/8, cmd = car/8 — matches the macro. So the
  data we write is what the engine expects.

Fixed:
- **Default geometry mismatch.** The operator made a plane (a face), and
  collect branched on "has faces", so the Closed toggle was effectively ignored
  (always polygon path). Now: operator creates a 2-vertex EDGE (open wall, the
  default), and collect branches on the Closed flag — Closed+face → polygon
  loop; otherwise edge-walk (open polyline or closed edge-ring).

Workflow caveat (not a bug):
- The in-game boundary editor's `---lb-save` regenerates the WHOLE
  load-boundary-data.gc from the live `*load-boundary-list*`, which by then
  includes our loaded custom boundaries. If a user edits boundaries in-game and
  saves, then re-exports from Blender, the addon's managed block would be added
  again on top of the editor's regenerated list → duplicates. For now the addon
  owns boundary authoring; don't mix with the in-game editor on the same level.

All touched modules byte-compile.

### UI revision (2026-05-28)
- Checkpoint Load Level 0/1 pickers gained a **Custom\u2026** option; selecting it
  reveals a string field (`og_cp_lev0_custom` / `og_cp_lev1_custom`) for an
  arbitrary level symbol. `collect_spawns` resolves it via `_cp_level_value`
  (lowercased/dashed; blank custom \u2192 none). Picker still offers self / none /
  project levels for convenience.
- Checkpoint **Advanced** (flags + load-commands) is now a collapsible subpanel
  via `layout.panel()` (Blender 4.1+), with an inline fallback on older Blender.
- Boundary settings unchanged (confirmed good).

### Root cause of two-custom-level co-load crash (2026-05-28)
Symptom: a checkpoint (or boundary) co-loading two *different* custom levels
crashed during the second level's DGO link, right after `<name>-obs`, with no
GOAL error (native segfault). Each level loaded fine alone; index/base-id were
unique; load-vs-display made no difference.

Cause: `write_gd` hardcoded the Village1 sky tpages [398,400,399,401,1470] into
EVERY level's DGO (`base_tpages`, "always present"), ordered immediately after
`<name>-obs`. Those tpages are an always-loaded global group (db
`global_tpage_groups` / `always_loaded_tpage_group`). One level tolerates the
duplicate; two co-resident levels crash when the second re-links the
already-resident `tpage-398`. The DGO order (obs -> tpage-398 -> ...) matches the
crash point precisely. Not the checkpoint/boundary feature — those work.

Fix: `data._collect_global_tpage_gos()` builds `GLOBAL_TPAGE_GOS` (all tpages of
always-loaded groups; 19 .go files). `write_gd` no longer bakes the hardcoded
village1 set and filters every global tpage out of the DGO file list. The engine
keeps them resident and build-level auto-logins them from the level's textures,
so levels still get them without baking.

REGRESSION CHECK before merge: re-export each level and confirm it still loads
AND renders textures correctly *alone* (the bake was redundant only if the
globals are truly always-resident during custom-level gameplay). Then test the
two-level co-load.

### Real fix: per-level texture/sky source (2026-05-28)
Verified against Kuitar's the-forgotten-lands: his co-resident areas never share
a borrowed texture/sky source. valley + crystal-cave + energy-bay use
tex_remap/sky = "none" (vertex colors); open-mines borrows "misty"; only
village1-based areas use village1, and they are not co-resident with each other.

Root cause in this addon: write_jsonc HARDCODED tex_remap/sky/textures = village1
for every level. build-level then auto-logins village1's tpages for each level,
and two co-resident custom levels both try to LINK the same tpage objects
(tpage-398.go ...) -> native segfault during the second level's tpage login
(removing them from the DGO only moved the duplicate to the auto-login path).

Fix: per-level `og_texture_source` (default "village1" for back-compat; "none"
borrows nothing). write_jsonc emits tex_remap/sky/textures from it ("none" ->
all none/empty -> no auto-login -> no shared tpages). Exposed in Create / Assign
/ Edit Level dialogs (TEXTURE_SOURCE_ITEMS: none + common vanilla bases). New
levels default to "none" (custom geometry is vertex-colored anyway). Existing
levels read the "village1" default until edited.

To co-load two levels: give them DIFFERENT sources, or set one/both to "none".

### Texture source now editable in the Settings subpanel (2026-05-28)
The per-level texture source was only on the level operator dialogs (Add/Edit
Level), but the UI edits level settings live in the "⚙ Settings" subpanel
(OG_PT_LevelSettings) via og_props proxy props — so the option was invisible
there. Added og_props.texture_source as a live get/set-proxied EnumProperty
(_get/_set_texture_source_live in collections.py, reading/writing the active
level's og_texture_source like level_name/base_id do), canonical
TEXTURE_SOURCE_ITEMS/VALUES moved to data.py, and shown in the Settings subpanel
under Death Plane. Operators import the shared items list.

User-facing: Level panel > ⚙ Settings > Texture/Sky Source. Set streamed levels
to "None (vertex colors)". Verify success: the build log for that level no longer
prints "login tpages automatically set to [398, 400, 399, 401, 1470]".
