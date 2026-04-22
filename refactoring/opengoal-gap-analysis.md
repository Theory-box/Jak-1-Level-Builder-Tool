# refactoring/opengoal-gap-analysis.md

> Written after cloning and grepping the OpenGOAL repo
> (`open-goal/jak-project`) to find missing data in our database. Not a bug
> list — a scope list for future expansion.

## Method

Cloned the repo shallow. Worked off three authoritative sources:

- **`goal_src/jak1/build/all_objs.json`** — 2074-entry manifest mapping every
  GOAL object to its source file, heap size, DGO memberships, and path.
  This is the ground truth for "what art groups exist and which DGOs contain
  them." All `ETYPE_AG` / `ETYPE_CODE` / `ETYPE_TPAGES` entries can be
  validated against this file.
- **`goal_src/jak1/engine/level/level-info.gc`** — 27 level-load-info
  definitions with full per-level metadata (mood, mood-func, priority, sky,
  ocean, continues, tasks, bsphere, packages, run-packages, etc.).
- **`goal_src/jak1/**/*.gc`** — 533 GOAL source files. Per-actor
  `init-from-entity!` methods read their res-lump values via
  `(res-lump-* entity 'lump-name ...)` calls. Grepping these gives an
  authoritative per-actor lump inventory.

## Findings — ranked by impact

### 🔴 HIGH — 4 real art_group gaps

These are actors we had no `art_group` for, but OpenGOAL's `all_objs.json`
confirms they have one. Adding these makes the code-dep + art-group
pipeline correct for these four actors:

| etype          | art_group             | DGO         | level           |
|----------------|-----------------------|-------------|-----------------|
| lightning-mole | `lightning-mole-ag`   | ROL         | levels/rolling  |
| ice-cube       | `ice-cube-ag`         | SNO         | levels/snow     |
| sunkenfisha    | `sunkenfisha-ag`      | SUB,SUN     | levels/sunken   |
| villa-starfish | `villa-starfish-ag`   | VI1         | levels/village1 |

### 🟡 MEDIUM — 11 actors with lump fields we're missing

Engine source reads these from their entity res-lump at init time, but our
DB doesn't document them. Most are small quality-of-life (e.g. rotoffset,
delay, scale). A few could matter for gameplay (next-actor/prev-actor
chains):

| etype          | missing lumps                        | source file                                 |
|----------------|--------------------------------------|---------------------------------------------|
| basebutton     | `extra-id`, `next-actor`, `prev-actor` | engine/common-obs/basebutton.gc           |
| flutflut       | `index`, `rotoffset`                 | levels/flut_common/flutflut.gc              |
| launcher       | `mode`                               | engine/common-obs/generic-obs.gc            |
| cavetrapdoor   | `delay`                              | levels/maincave/maincave-obs.gc             |
| driller-lurker | `driller-lurker` (self-named struct) | levels/maincave/driller-lurker.gc           |
| gnawer         | `rotoffset`                          | levels/maincave/gnawer.gc                   |
| money          | `movie-mask`                         | engine/common-obs/collectables.gc           |
| mother-spider  | `mother-spider` (self-named struct)  | levels/maincave/mother-spider.gc            |
| sun-iris-door  | `trans-offset`                       | levels/sunken/sun-iris-door.gc              |
| yakow          | `water-height`                       | levels/village1/yakow.gc                    |
| test-actor     | `collide-mesh-group`                 | levels/test-zone/test-zone-obs.gc (debug)   |

Additional single miss on **Camera** (ObjectTypes, not Actors): reads
`intro-time` at init. Our Camera fields block has `interpTime` but not
`intro-time` — these are distinct values in the engine.

### 🟢 LARGE SCOPE — Per-level metadata (the "Pass 2 work")

`goal_src/jak1/engine/level/level-info.gc` has a full `level-load-info`
struct for each of 27 levels. We already extracted these fields into
`/home/claude/level_info_parsed.json`. Our DB has none of this — the export
code currently hardcodes `*village1-mood*` for every custom level.

Fields per level:

| field              | example (beach)                       | current coverage |
|--------------------|---------------------------------------|------------------|
| `index`            | `3`                                   | ❌ missing       |
| `visname`          | `'beach-vis`                          | ❌ missing       |
| `nickname`         | `'bea`                                | ❌ missing       |
| `packages`         | `'(beach)`                            | ❌ missing       |
| `sound-banks`      | `'(beach)`                            | ~ have in DB     |
| `music-bank`       | `'beach`                              | ~ have in DB     |
| `ambient-sounds`   | `'()`                                 | ❌ missing       |
| `mood`             | `'*beach-mood*`                       | ❌ missing       |
| `mood-func`        | `'update-mood-village1`               | ❌ missing       |
| `ocean`            | `'*ocean-map-village1*`               | ❌ missing       |
| `sky`              | `#t`                                  | ❌ missing       |
| `sun-fade`         | `1.0`                                 | ❌ missing       |
| `continues`        | 1 continue-point                      | ❌ missing       |
| `priority`         | `100`                                 | ❌ missing       |
| `bsphere`          | `(sphere :x .. :z .. :w ..)`          | ❌ missing       |
| `tasks`            | `'(15 16 17 18 19 20 21 22)`          | ❌ missing       |
| `run-packages`     | `'("common")`                         | ❌ missing       |
| `wait-for-load`    | `#t`                                  | ❌ missing       |
| `alt-load-commands`| (neighbor-level-load rules)           | ❌ missing       |

27 levels total — the 21 we know about plus 6 that aren't user-spawnable
(intro, demo, test-zone, title, level-default, default-level). The 21
user-facing ones all have full metadata here.

### ℹ️ INFORMATIONAL — Confirmed non-gaps

Some apparent gaps are actually correct-by-design. Documenting so we don't
re-investigate later:

1. **Actors with no art_group, correctly**:
   - `eco-yellow`, `eco-red`, `eco-blue`, `eco-green` — eco pickups render
     as particle effects, no mesh art group
   - `cave-trap`, `spider-vent` — defined in `levels/robocave/cave-trap.gc`
     but don't have standalone -ag entries (share a group)
   - `ropebridge` — uses a different art group per variant (ropebridge-32,
     ropebridge-36, snow-bridge-36, vil3-bridge-36). Already captured in the
     `og_bridge_variant` enum; the AG resolution happens at export time
     from the variant string
   - `water-vol` — invisible volume, no mesh
   - `swingpole` — defined in `generic-obs-h.gc` (header file), uses
     engine-provided rendering, no standalone -ag

2. **Actors with no `code` entry, correctly**:
   - `fuel-cell`, `money`, `buzzer`, `orb-cache-top`, `ecovalve`, `crate`
     — all defined in `engine/common-obs/` which is always loaded (GAME.CGO
     or COMMON.CGO). Our old `ETYPE_CODE[etype] = {"in_game_cgo": True}`
     pattern handles this, but during migration these lost their explicit
     marker. Safe to add `in_game_cgo: True` back for clarity, but
     functionally they work without it (the exporter's "skip if not in
     ETYPE_CODE" path hits the same result).
   - `plat`, `plat-eco`, `plat-button` — all in `engine/common-obs` too.
     Same situation.
   - `test-actor` — debug-only, not shipped.

## Proposed next-pass work (scope, not commits)

Three independent enhancements, each of which can land separately:

**Pass 2a: art_group + code cleanups (small, ~1 hour)**
- Add the 4 real art_groups (lightning-mole, ice-cube, sunkenfisha, villa-starfish)
- Mark the 10 always-loaded actors with `in_game_cgo: true` explicitly
- Add 11 actors' missing lump entries to their `lumps[]` arrays
- Add `intro-time` to Camera ObjectType fields

**Pass 2b: per-level metadata (medium, ~2-3 hours)**
- Extend Levels section schema with mood/mood-func/priority/sky/ocean/
  sun-fade/continues/tasks/bsphere/packages/run-packages/wait-for-load
- Populate from `/home/claude/level_info_parsed.json` (already extracted)
- Update `export.py patch_level_info()` to read these values from the DB
  per level instead of hardcoding `*village1-mood*`

**Pass 2c: built-in continue points (medium)**
- `level-load-info.continues` has per-level continue-point definitions
  (trans, quat, camera-trans, camera-rot, nav-mesh). Our addon creates
  CHECKPOINT objects for custom continues but doesn't know about the
  built-in ones. Could become a "default continues" picker in the level
  manager UI.

## Extraction artifacts left on disk

These files remain in `/home/claude/` for reference; they're not committed
because they're reproducible:

- `/home/claude/jak-project/` — shallow OpenGOAL clone (547 MB)
- `/home/claude/extract_goal_lumps.py` — per-actor lump scanner
- `/home/claude/parse_level_info.py` — level-load-info parser
- `/home/claude/opengoal_lump_gap_report.json` — JSON form of the 11-actor
  lump gaps table
- `/home/claude/level_info_parsed.json` — all 27 level-load-info records
  in parsed JSON form
