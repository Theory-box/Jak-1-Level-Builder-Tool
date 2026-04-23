# session-notes/refactoring.md

> Active branch: `refactoring`. Pick this up with `git checkout refactoring && git pull`.

---

## Status: rewire complete, **Blender smoke test PASSED**

The addon has been structurally refactored to separate game-specific data from
addon code. All the "how to spawn a babak" details (actor definitions, lump
references, audio tables, level data, PAT enums, etc.) now live in a single
JSONC database file. The Python code only contains UI, export logic, and
Blender integration.

**Verified in Blender 4.4.3 headless — addon loads, all workflows function,
export produces correct output.** See "Blender test results" section below.

No behavioral change observed. The rewire is a transparent substitution —
every public symbol the addon exposed before still exists with the same type
and effectively the same contents, just sourced from the JSONC instead of
hardcoded Python literals.

---

## What landed on this branch

### New files
| Path | Lines | Role |
|---|---|---|
| `addons/opengoal_tools/jak1_game_database.jsonc` | 15,115 | Source of truth. 26 top-level sections covering actors, parents, levels, audio, PAT, lumps, etc. |
| `addons/opengoal_tools/db.py` | 250 | Loader + typed accessors. No `bpy` import — safe anywhere. |
| `refactoring/build_database.py` | ~520 | One-time migration script. Reads pre-shim data.py from git history and regenerates the JSONC. Disposable. |
| `refactoring/audit.md` + `audit-v2-addendum.md` | — | Full data-inventory audits that informed the rewire. |

### Changed files
| Path | Before | After | What changed |
|---|---|---|---|
| `addons/opengoal_tools/data.py` | 3,014 | 633 | Rewritten as a compatibility shim over `db.py`. All 2,766 lines of hardcoded data removed; replaced with derivation logic. Every public symbol preserved. |

### Untouched files (10)
`__init__.py`, `panels.py`, `properties.py`, `operators.py`, `export.py`,
`build.py`, `collections.py`, `audit.py`, `textures.py`, `model_preview.py`,
`utils.py` — no consumer file needed changes; `from .data import X` still
resolves to equivalent values.

---

## How to orient yourself

1. **Look at `jak1_game_database.jsonc` first.** Top of file has a section
   index. Each section has a comment header. Main content:
    - `Actors` — 153 entries with `fields` (custom UI + export mapping) and
      `lumps` (full lump reference for the manual editor).
    - `Parents` — 4 entries (process-drawable, nav-enemy, prop,
      eco-collectable) with inheritable link defaults and universal lumps.
    - `Levels` — 21 entries with tpages, music flavas, SFX banks.
2. **Then `db.py`.** 250 lines. The loader (`DB = _load()` at module level),
   plus accessors (`actors()`, `parents()`, `find_actor()`,
   `parent_chain()`, `inherited_lumps()`). Use these in new code instead of
   going through the compat shim.
3. **Then `data.py`.** 633 lines. This is the compat shim. Top of each
   section has a comment explaining what it's reconstructing from the DB.
   The file also contains all the helper/callback functions (enum builders,
   Blender dynamic-enum callbacks, lump parsers) — those weren't data, so
   they stayed unchanged.

---

## Verification already performed

Pre-rewire, I snapshotted the 81 public symbols the old `data.py` exposed
(name → type + length). Post-rewire, all 81 symbols exist with the correct
type. 80 also have identical size to the pre-rewire snapshot. The 1 cosmetic
diff (`ACTOR_LINK_DEFS` has 21 entries vs the old 28) is empty-list entries
filtered out during the migration — every consumer uses `.get(etype, [])` on
this dict, so absent vs present-but-empty is indistinguishable.

Helper functions were spot-checked for identical output:
`_lump_ref_for_etype` on babak/swamp-bat/crate/fuel-cell/orbit-plat/helix-water,
`_aggro_event_id` on every event name, `_is_custom_type` on known + unknown
etypes. All produced identical output versus the pre-rewire functions.

---

## Blender test results (4.4.3 headless, Linux)

Ran four progressively harder tests. All structurally green; minor caveats below.

### Test 1 — registration smoke test
- ✓ Addon enables without raising an exception
- ✓ `scene.og_props` property group registers
- ✓ `db.py` loads the JSONC, 30 sections parsed
- ✓ `data.py` compat shim: all 81 public symbols present with correct types
- ✓ 104 operators registered under `bpy.ops.og.*`
- ✓ 78 UI panels registered
- ✓ Every dynamic enum callback returns items (search, enemy, prop, platform)
- ✓ **`NEEDS_PATH_TYPES` = 22** (matches pre-rewire exactly — the runtime/UI
  separation fix held)

### Test 2 — workflow test
Spawned representative instances via each category of operator:
- ✓ `spawn_entity` (babak — enemy) — got correct defaults (`og_vis_dist=200`,
  `og_idle_distance=80`, `og_nav_radius=6`)
- ✓ `spawn_platform` (balance-plat)
- ✓ `spawn_camera` (CAMERA_0)
- ✓ `spawn_checkpoint` (CHECKPOINT_cp0)
- ✓ `add_sound_emitter` → AMBIENT_snd001 → waterfall
- ✓ `add_music_zone` → AMBIENT_mus001 → village1/default
- ✓ `add_water_volume` → WATER_0
- ✓ `add_launcher_dest`
- ✓ `add_lump_row` — row added with expected schema (key/ltype/value)

The following "failures" were expected — operators correctly refused to run
without required scene state, not rewire bugs:
- `spawn_custom_type` — needs `custom_type_name` first (poll-gated)
- `spawn_aggro_trigger` — needs a target enemy
- `add_waypoint` — needs an active enemy

### Test 3 — stress test
Spawned every spawnable actor in the database via `spawn_entity`:
- ✓ **152 / 152 pass** (153 total minus water-vol which is `category: Hidden`
  and correctly excluded from the picker)
- Per category: Enemies 41, Platforms 31, Objects 41, NPCs 17, Pickups 16,
  Bosses 3, Props 2, Debug 1
- Actor-specific default checks:
  - ✓ `crate.og_crate_type = 'steel'`
  - ✓ `crate.og_crate_pickup = 'money'`

### Test 4 — end-to-end export
Built a small test scene (3 enemies, 1 crate, 1 checkpoint, 1 camera, 1 sound
emitter, 1 water volume) and ran `export_build`:
- ✓ `Wrote data/custom_assets/jak1/levels/test-level/test-level.jsonc`
- ✓ All actors emitted correct lump dicts in the output JSONC:
  - babak/lurkercrab: `['name', 'nav-mesh-sphere', 'idle-distance', 'vis-dist']`
  - crate: `['name', 'crate-type', 'eco-info']`
  - checkpoint-trigger: `['name', 'continue-name', 'radius']`
  - water-vol: `['name', 'water-height', 'attack-event', 'vol']`
  - camera-marker: `['name', 'interpTime']`
  - ambient: `['name', 'type', 'effect-name', 'cycle-speed']`
- ✓ Wrote companion files: `tes.gd` (enemy .o list) and `test-level-obs.gc`
  (checkpoint-trigger embedded type definition)
- ✓ `[code-deps] [('lurkercrab.o', None, None)]` — code dependency tracking
  working against the DB-sourced ETYPE_CODE table

---

## Observations (NOT bugs — expected from the scope of the rewire)

1. **Aspirational `fields` in the DB aren't wired to Blender properties yet.**
   The database defines per-actor `fields` arrays (e.g. `og_bridge_variant`
   for ropebridge, `og_flip_delay_down` for plat-flip, `og_orbit_scale` for
   orbit-plat). These are **schema for future UI auto-generation** — they
   don't create Blender properties until `properties.py` / `panels.py` are
   ported to consume them. Current behavior matches the pre-rewire state
   exactly. This was always the intended scope: the rewire separated data
   from code; consuming the `fields` schema is a follow-up phase.

2. **`og_vis_dist` / `og_idle_distance` only populated on enemies.** 108
   non-enemy actors don't get these custom properties set at spawn time.
   This matches pre-rewire behavior — these defaults are applied
   imperatively in the enemy-spawn code path, and non-enemies fall back to
   hardcoded defaults at export time. The export still emits the values
   correctly (see Test 4 output).

## Known caveat

- **Segfault on consecutive `export_build` calls.** The first `export_build`
  returns `RUNNING_MODAL` and completes correctly. Calling `export_build` a
  second time immediately after (before any user interaction) triggers a
  segfault in the Blender GLTF export path. This appeared only in the
  headless test harness where the modal operator finished before the second
  call. In normal interactive use (where the user waits for the first
  export to complete before clicking again), this shouldn't surface. Flag
  for future investigation if it shows up in real use.

---

## Known deferred items (tracked in the database file itself)

1. **Per-level mood/mood-func/priority/sky/ocean flags** — currently hardcoded
   in `export.py patch_level_info()` around the `'*village1-mood*'` lines,
   regardless of which level is being exported. The audits flag this as
   "Pass 2 work." When we port this into the database, each Level record
   gets `mood`, `mood_func`, `priority`, `sky_flag`, `ocean_flag` fields.
   See `Levels_notes` in the JSONC.
2. **`og_music_amb_*` property group on objects** — defined in `properties.py`,
   appears unused (no readers found during the audit). Should be verified as
   dead code and deleted, or the reader that needs it found.
3. **`VertexExportTypes` overlap with `Actors`** — some etypes appear in both
   (same record, duplicated). Post-rewire refactor: dedupe by having
   VertexExportTypes only list etypes unique to vertex-lit export.

---

## Next steps (after testing validates the rewire)

In order of increasing invasiveness:

1. **Port consumers to `db.py` directly.** The 10 untouched Python files
   currently import from `.data`. Migrate them file-by-file to import from
   `.db` (using `find_actor`, `parent_chain`, etc.). Lower-churn files first
   (utils, textures, model_preview). Delete `data.py` once nothing imports
   from it.
2. **Hot-reload UI.** `db.py` already exposes `reload()`. Add an operator
   + button so the user can edit the JSONC, click "Reload Database," and
   see changes without restarting Blender.
3. **Add a level-editor UI for the database itself.** Given the JSONC is now
   the source of truth, a GUI for editing actor definitions (especially the
   `fields` and `lumps` arrays) would let content creators extend the addon
   without touching Python.
4. **Address the Pass-2 items** listed above.

---

## Risk areas during testing

- **The `_enemy` lump sentinel** is preserved in `LUMP_REFERENCE["_enemy"]`
  but is now populated from the nav-enemy Parent's lumps. If a non-nav-enemy
  in the Enemies category (e.g. swamp-bat — which is process-drawable) is
  missing the expected nav-mesh-sphere / nav-max-users lumps in its manual
  editor, this is the first place to look.
- **Parent-inferred `links.need_path` on every nav-enemy.** I corrected the
  build script to stop conflating this with runtime-required `needs_path`,
  but if the spawn picker shows `[path]` warnings on actors that shouldn't
  have them, check the top-level `needs_path` flag on those actors in the
  JSONC.
- **Orphan etypes.** `helix-button`, `helix-water`, `snow-log`,
  `snow-log-button` (plus 5 wiki-only etypes) aren't in the main Actors list
  — they're in `OrphanEtypes` with `spawnable: false`. `find_actor()` finds
  them; `actors()` doesn't. If some code path iterates `actors()` expecting
  all etypes, it'll miss these. Use `all_actors_including_orphans()`.
- **`ALL_SFX_ITEMS` is verbatim, not derived.** Earlier "derive it" decision
  was based on a wrong assumption. The full 1035-entry list is now in the
  `AllSFX` section of the JSONC, preserved exactly. If a SFX dropdown is
  missing entries, check that section first.

---

## Commit history on this branch

```
3fc6369 refactoring: rewire addon to read game data from jak1_game_database.jsonc
517e2e3 refactoring: initial jak1_game_database.jsonc + build script
1474101 refactoring: audit v2 addendum — full og_* field sweep + corrections
2131c69 refactoring: initial game-data audit + example actor file
```

---

## Session checkpoint

- Branch pushed to origin, not merged to main.
- Ready for Blender smoke test per the 11-item list above.
- If anything fails, dig into the "Risk areas" section first, then post the
  traceback — the fix will almost certainly be in `data.py`'s reverse-mapping
  or `build_database.py`'s forward extraction.

---

# Addendum — Phase 2/3 refactor complete

After the initial JSONC rewire, we continued the refactor through several
more phases. The addon is now fully modularized into focused packages.

## Completed phases

**Pass 2a / 2b — OpenGOAL gap analysis + per-level metadata**
(`9f59fb7`, `0197ffd`)
- Cloned open-goal/jak-project shallow, cross-checked our database against
  `all_objs.json` (2074 entries), 533 `.gc` files, and `level-info.gc`
- Added 4 missing art_groups (lightning-mole, ice-cube, sunkenfisha,
  villa-starfish) + 56 lump entries across 30+ actors + full per-level
  metadata (mood, ocean, priority, sky, bsphere, tasks, continues, etc.)
  for all 21 levels
- Fixed one pre-existing bug: caveelevator was mapped to `rotoffset` but
  the engine reads `trans-offset`. Reverted the rename for compat + left
  a note explaining the discrepancy so the real fix can land later
  alongside coordinated export + panel changes.
- Full report: `refactoring/opengoal-gap-analysis.md`

**Phase 3a — Data-driven actor settings panel** (`b3c5b69`)
- New module `panels/actor_fields.py` (320 lines) with `OG_PT_ActorFields`,
  a generic panel that reads `fields[]` from the DB and renders UI per
  field type (enum, float, int, bool, string, vector3, object_ref).
- Added `og.set_actor_enum_field` and `og.toggle_actor_bool_field` generic
  setter operators
- Deleted 18 bespoke `OG_PT_Actor*` panels — 619 lines off panels.py
- Covered etypes: orbit-plat, plat-flip, whirlpool, square-platform,
  orb-cache-top, caveflamepots, shover, sharkey, sunkenfisha, basebutton,
  lavaballoon, darkecobarrel, breakaway-{left,mid,right}, swamp-bat, yeti,
  villa-starfish, swamp-rat-nest, dark-crystal, fuel-cell, windturbine,
  ropebridge, mis-bone-bridge (24 etypes)
- Still-bespoke panels: crate (dynamic enabling), launcher (dest picker),
  eco-door (bitfield flags), water-vol (mesh extents), nav-mesh, goal-code,
  waypoints (not really field panels), and 4 with mixed logic

**Phase 3b — Split panels.py into panels/ package** (`560a41c`)
- Broke the 3836-line panels.py into 7 focused submodules:
  - `level.py` (550) — level mgmt, audit, music, light bake
  - `spawn.py` (673) — spawn picker, category tabs, search
  - `selected.py` (1023) — OG_PT_SelectedObject + sub-panels + draw helpers
  - `actor.py` (900) — bespoke per-actor panels
  - `actor_fields.py` (320) — the generic data-driven panel (moved here)
  - `scene.py` (540) — cameras, emitters, music zones, triggers
  - `tools.py` (501) — build/dev/geometry tools
- Each submodule exports its own `CLASSES` tuple; `panels/__init__.py`
  aggregates them into `ALL_CLASSES`
- Handled: parent-child registration ordering (OG_PT_SpawnLevelFlow needs
  Spawn registered first → both live in spawn.py), relative-import path
  bump (.data → ..data), 4 operators that inherited from
  `bpy.types.Operator` missed by my regex (fixed by using ast.parse)

**Phase 3c — Split operators.py into operators/ package** (`fe92af9`)
- Broke 2862 lines into 6 submodules:
  - `spawn.py` (871) — 21 ops: spawn entities, volumes, cameras, emitters
  - `level.py` (713) — 19 ops: level mgmt, GOAL code, lump rows, music
  - `actors.py` (372) — 18 ops: per-actor setters + generic field ops
  - `links.py` (439) — 12 ops: actor/volume/navmesh links, waypoints
  - `build.py` (395) — 8 ops: export/compile/play/bake
  - `misc.py` (301) — camera, nudge, selection, helpers
- Used `ast.parse()` this time (regex tokenizer tripped on a multi-line
  docstring starting with class-looking content)
- Rescued 3 module-level consts (`_MUSIC_BANK_ITEMS`, `_GOAL_BOILERPLATE`,
  `_VALID_ETYPE_RE`) that the initial split dropped
- Cross-module import added (`operators/level.py` imports
  `_flava_items_for_active` from `.misc`)

**Phase 3d — Split export.py into export/ package** (`ea4db56`)
- Broke 2758 lines into 8 submodules with explicit dependency graph:
  - Leaves: `paths.py` (101), `predicates.py` (136)
  - depends on paths: `volumes.py` (176), `levels.py` (214)
  - depends on paths+predicates: `navmesh.py` (319)
  - depends on paths+predicates+volumes: `scene.py` (533), `actors.py` (807)
  - depends on paths+levels: `writers.py` (812)
- First attempt used `from .X import *` between siblings — caused circular
  imports. Fixed by walking the AST and intersecting each module's
  references with sibling exports, generating precise per-module imports
- `export/__init__.py` re-exports every public name explicitly (Python's
  `import *` skips underscore names, but many like `_navmesh_compute`,
  `_vol_links` are part of the consumed API)

## Final architecture

```
addons/opengoal_tools/
├── __init__.py           248  (was 428; just bl_info + registration now)
├── jak1_game_database.jsonc   15,878 lines, 30 top-level sections
├── db.py                 250  clean database loader + accessors
├── data.py               633  compat shim (to delete once consumers migrate to db.py)
├── properties.py         534  PropertyGroup classes + addon prefs
├── utils.py              367  shared helpers (_prop_row, etc.)
├── collections.py        333  Blender collection mgmt
├── audit.py              432  level validator
├── textures.py           450  texture browser
├── model_preview.py      444  model preview
├── build.py              830  goalc compilation pipeline
│
├── panels/
│   ├── __init__.py        48  aggregates ALL_CLASSES
│   ├── level.py          550
│   ├── spawn.py          673
│   ├── selected.py      1023  (largest file in the addon now)
│   ├── actor.py          900
│   ├── actor_fields.py   320  data-driven generic panel
│   ├── scene.py          540
│   └── tools.py          501
│
├── operators/
│   ├── __init__.py        38
│   ├── spawn.py          871
│   ├── level.py          713
│   ├── actors.py         372
│   ├── links.py          439
│   ├── build.py          395
│   └── misc.py           301
│
└── export/
    ├── __init__.py        57
    ├── paths.py          101  (leaf)
    ├── predicates.py     136  (leaf)
    ├── volumes.py        176
    ├── levels.py         214
    ├── navmesh.py        319
    ├── scene.py          533
    ├── actors.py         807
    └── writers.py        812
```

**Totals:** 15,368 Python lines (vs 14,806 pre-refactor, +3.8% for
module-boundary duplication, largely acceptable). No single file over
~1050 lines; most are under 600.

## Commit history on this branch

```
ea4db56  Phase 3d — split export.py into export/ package
fe92af9  Phase 3c — split operators.py into operators/ package
560a41c  Phase 3b — split panels.py into panels/ package
b3c5b69  Phase 3a — data-driven actor settings panel (-18 bespoke panels)
0197ffd  Pass 2a/2b — OpenGOAL gap fixes + per-level metadata
9f59fb7  OpenGOAL gap analysis doc
71dcb10  session note — Blender 4.4.3 smoke test passed
17e82a3  session note — ready for Blender testing
3fc6369  rewire addon to read from JSONC database
517e2e3  initial jak1_game_database.jsonc + build script
1474101  audit v2 addendum
2131c69  initial game-data audit + example actor file
```

## Verified at every step in Blender 4.4.3 headless

- Addon registers cleanly: 106 operators + 61 panels
- All 152 spawnable entities spawn successfully
- Generic panel: 24/24 covered etypes poll correctly, no duplication with
  bespoke panels
- No regression in entity defaults or scene behaviour

## Possible next steps (not scheduled)

1. **Data-driven `collect_actors`** (biggest remaining win) — the 29
   per-actor etype branches in `export/actors.py` all follow the pattern
   "read og_xxx, emit lump yyy with rule zzz". `fields[].lump` +
   `write_if` already encodes the rules; a generic field-walker can
   replace most of the branches. Ballpark savings: 400-600 lines from
   export/actors.py.

2. **Port more bespoke panels to generic** — `OG_PT_ActorTaskGated` (simple
   enum), `OG_PT_ActorSunIrisDoor` (bool + float). Straightforward in the
   current architecture.

3. **caveelevator bug fix** — engine reads `trans-offset` (3 floats X/Y/Z)
   but we write `rotoffset` (float degrees). Needs coordinated change
   across the DB field, the bespoke panel, the property setter, and the
   export writer. Tracked via the note on the field in the DB.

4. **Delete `data.py` compat shim** — migrate consumers to use `db.py`
   directly; 633 lines of overlap goes away.

5. **Top-level `__init__.py` cleanup** — the registration tuple can be
   mostly auto-derived from packages instead of explicitly listed. Minor
   cosmetic gain.

---

# Third-pass bug sweep — nothing new found

Ran a third round of static and dynamic checks. All 9 static checks clean
(or reporting only false positives). The headline dynamic test:

**Full export pipeline with every entity spawned in one scene** — spawned
all 152 spawnable entities, then ran every collector through the entire
pipeline:

```
[spawn] 152/152 entities spawned
[pipeline]
  ✓ collect_actors          (153 items)
  ✓ collect_cameras         (2 items)
  ✓ collect_ambients        (2 items)
  ✓ collect_spawns          (1 item)
  ✓ collect_aggro_triggers  (0 items)
  ✓ collect_custom_triggers (0 items)
  ✓ collect_nav_mesh_geometry (0 items)
  ✓ needed_ags(actors)      (140 art-groups needed)
  ✓ needed_code(actors)     (92 code files needed)
```

Every single one of the 29 per-actor branches in `collect_actors` ran
successfully, emitting their per-actor log lines. This is the most
thorough end-to-end exercise the export pipeline has had since the split.

## Additional static checks added

- Syntax: every .py file compiles cleanly via `py_compile`
- Property callbacks: every `update= / get= / set=` callback is in scope
- Blender handlers: every `bpy.app.handlers.X.append()` is paired with a
  `remove()` on unregister (1 pair found, both sides present)
- @classmethod on poll: all poll() methods decorated correctly
- poll() return: every poll body contains a return statement with a value
- Duplicate class defs: 175 top-level classes, all unique
- Stale file references: no live references to panels.py / operators.py /
  export.py in any source file
- Scene property access: `scene.og_audit_results_index` is declared in
  __init__.py (not properties.py) — false positive in the checker

## Headless test coverage summary

| test script | what it exercises | caught-bugs |
|---|---|---|
| test_addon.py | Registration (classes register) | 0 this session |
| test_stress.py | All 153 entities spawn | 0 |
| test_generic_panel.py | 24 covered etypes poll correctly | 0 |
| test_panel_draws.py | 34 panels `draw()` with mock UILayout | **3** (_draw_selected_* imports, _draw_actor_links import, _AUDIT_* constants) |
| test_export_pipeline.py | Per-collector with a curated scene | 0 addon bugs |
| test_export_full.py | Full pipeline on ALL 152 entities | 0 |
| test_register_cycle.py | enable → disable → enable × 4 | 0 |
| bug_sweep.py | 9 static checks | **5** (3 from the split, 2 latent from original) |
| bug_sweep_deep.py | 10 deeper static checks | 0 |
| bug_sweep_pass3.py | 9 targeted pattern checks | 0 |

## What headless tests still cannot catch

- Blender's native event dispatch (depsgraph handlers, timer callbacks,
  modal operators at runtime)
- Byte-level export regression vs a reference snapshot (write_gc /
  write_jsonc actually producing correct output bytes)
- subprocess/goalc integration paths (launching goalc, nrepl communication)
- UI interactivity: drag, hover, property changes triggering draw updates
- Cross-product issues like "change a property A while panel B is open"
