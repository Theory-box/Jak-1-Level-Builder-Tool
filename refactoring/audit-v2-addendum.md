# Audit Addendum v2 — `og_*` field sweep + corrections

**Status:** Second pass. Deep sweep of per-actor custom fields + fixes to v1 findings.
**Scope:** Answers the biggest open question from v1 (§3.3 / §7 Q2): *what are the full per-actor custom fields, and where does each go?*

---

## A. Corrections to v1

Items I got wrong or under-counted in `audit.md`.

### A.1 — ENTITY_DEFS entry count

v1 said "~90 actors." Actual count is **153 entries**.

### A.2 — ENTITY_DEFS categories

v1 listed 8 categories. Actual is **9**: `Bosses, Debug, Enemies, Hidden, NPCs, Objects, Pickups, Platforms, Props`. I missed `Hidden` — need to check how it's used; likely items that shouldn't appear in the spawn picker but do exist as etypes (maybe internal / parent types masquerading as entries).

### A.3 — ENTITY_DEFS flag fields

v1 listed `nav_safe / needs_path / needs_pathb / is_prop / ai_type`. Two more exist that I missed:

- `needs_sync` — platform reads the `sync` res-lump (period/phase/easing). Used by `plat`, `plat-eco`, `side-to-side-plat`.
- `needs_notice_dist` — platform reads the `notice-dist` res-lump. Used by `plat-eco` only.

Full ENTITY_DEFS field set is therefore: `label, cat, tpage_group, ag, code?, tpages?, nav_safe, needs_path, needs_pathb, needs_sync, needs_notice_dist, is_prop, ai_type, color, shape, glb`. (16 fields; most entries use only a subset.)

### A.4 — `ai_type` values (implicit parent hierarchy)

Only three distinct values across all 153 entries: `nav-enemy`, `process-drawable`, `prop`. These are effectively the **current de facto parent list** for the addon's purposes. The example file's `"Parents"` section should start with at least these three. (In the real OpenGOAL type system there are more — e.g. `eco-collectable`, `baseplat`, `fact-info-enemy` — but the addon doesn't distinguish them anywhere, so they're not needed yet.)

### A.5 — `enemy-images/` folder is missing from the repo

`ENTITY_WIKI` (data.py 294–328) references image filenames like `Babak render.jpg` with the comment "Images live in `<addon_dir>/enemy-images/`". **That folder does not exist** in the cloned repo. Either it was never committed, was removed in a cleanup, or lives outside the repo. Needs a decision:
- (a) Locate and re-import the images.
- (b) Drop the `img` field from the new schema and only keep `desc`.
- (c) Keep the `img` field pointing at remote URLs (fandom wiki) rather than local files.

### A.6 — Hardcoded `ECO_DOOR_TYPES` appears **three** times

In v1 §3 I noted it appears in `audit.py` 261 and `panels.py` 2402. It also appears as a literal tuple in `export.py` 1553. Three duplicates of the same game-data set in three files. The new reference file should make this kind of duplication impossible.

---

## B. Full `og_*` property inventory

Every custom Blender-object property the addon reads. 81 distinct `og_*` names after filtering. Grouped by purpose.

### B.1 — Global addon state (not game data — stays in code)

| Property | Purpose |
|---|---|
| `og_active_data`, `og_active_version` | Selected toolchain/data folder |
| `og_props`, `og_root_path` | Addon prefs |
| `og_audit_results`, `og_audit_results_index` | Level-validation panel state |
| `og_managed_object` | Flag for addon-managed objects |
| `og_preview_mesh`, `og_waypoint_preview_mesh` | Flags on imported GLB previews |
| `og_waypoint_for` | Waypoint → parent-actor back-reference |
| `og_vertex_export_etype`, `og_vertex_export_search` | Vertex-lit export panel state |
| `og_goal_code_ref` | Goal-code snippet picker state |
| `og_no_export` | Per-object "skip export" toggle |
| `og_is_level` | Marks a collection as a level |

### B.2 — Level-collection metadata (per-level config; not per-actor)

Lives on the level collection (not individual actors). Covered in v1 §3.17 — the reference file's `Levels` section holds these **defaults**, while the actual values stay on the user's collections.

| Property | Default | Reference-file role |
|---|---|---|
| `og_level_name` | `"my-level"` | n/a (user-defined) |
| `og_base_id` | `10000` | n/a (user-defined) |
| `og_bottom_height` | `-20.0` | default in `Levels.defaults` |
| `og_vis_nick_override` | `""` | n/a (user-defined) |
| `og_sound_bank_1`, `og_sound_bank_2` | `"none"` | choices come from `SoundBanks` |
| `og_music_bank` | `"none"` | choices come from `MusicBanks` |
| `og_continue_name` | `""` | used as the per-actor continue-name too (see B.5) |

### B.3 — Generic actor slots (apply to many actors; driven by flags in ENTITY_DEFS)

These are *universal or flag-driven* — not per-actor bespoke. They stay driven by ENTITY_DEFS flags, no new schema needed.

| Property | Condition | Default | Lump key | Lump type |
|---|---|---|---|---|
| `og_nav_radius` | etype in `NAV_UNSAFE_TYPES` | `6.0` | `nav-mesh-sphere` (w component) | vector4m |
| `og_idle_distance` | cat in {Enemies, Bosses} | `80.0` | `idle-distance` | meters |
| `og_vis_dist` | cat in {Enemies, Bosses} | `200.0` | `vis-dist` | meters |
| `og_notice_dist` | `needs_notice_dist` | `-1.0` | `notice-dist` | meters |
| `og_sync_period` | `needs_sync` | `4.0` | `sync[0]` | (combined float array) |
| `og_sync_phase` | `needs_sync` | `0.0` | `sync[1]` | |
| `og_sync_ease_out` | `needs_sync` | `0.15` | `sync[2]` | |
| `og_sync_ease_in` | `needs_sync` | `0.15` | `sync[3]` | |
| `og_sync_wrap` | `needs_sync` | `False` | `options` bit 3 (value 8) | uint32 |

### B.4 — Generic entity-link slots (not per-actor; driven by ACTOR_LINK_DEFS)

| Property | Purpose |
|---|---|
| `og_actor_links` | Generic actor-link CollectionProperty (fed by ACTOR_LINK_DEFS) |
| `og_navmesh_link` | Nav-mesh reference |
| `og_navmesh` | Boolean tag: "this mesh IS a nav-mesh" |
| `og_vol_link`, `og_vol_links`, `og_vol_id` | Volume references (trigger / water volume cross-links) |
| `og_cp_link` | Checkpoint link |
| `og_lump_rows`, `og_lump_rows_index` | Manual lump-row editor (generic) |

### B.5 — Per-actor custom fields ⭐ THE BIG TABLE

This is the v1 §3.3 gap enumerated. All fields below are **game-specific per-actor data** that needs to move into the reference file's new `fields:` (or equivalent) array per actor.

**Format:** `actor → [(og_prop, default, lump_key, lump_type, write_condition, ui_widget)]`

| Actor(s) | Blender property | Default | Output lump key | Lump type | Write condition | UI panel line |
|---|---|---|---|---|---|---|
| **fuel-cell** | `og_cell_skip_jump` | `False` | `options` | uint32=4 | if True | panels.py:2250 |
| **crate** | `og_crate_type` | `"steel"` | `crate-type` | raw `'<sym>` | always | panels.py:2159 |
| crate | `og_crate_pickup` | `"money"` | `eco-info` | eco-info | if != "none" | panels.py:2160 |
| crate | `og_crate_pickup_amount` | `1` | (part of eco-info above) | — | forced to 1 if pickup=="buzzer" | |
| **dark-crystal** | `og_crystal_underwater` | `False` | `mode` | int32=1 | if True | panels.py:2217 |
| **plat-flip** | `og_flip_sync_pct` | `0.0` | `sync-percent` | float | if != 0.0 | (see panels for eyes) |
| plat-flip | `og_flip_delay_down` | `2.0` | `delay[0]` | float | always | |
| plat-flip | `og_flip_delay_up` | `2.0` | `delay[1]` | float | always | |
| **eco-door + jng-iris-door + sidedoor + rounddoor** | `og_door_auto_close` | `False` | `flags` (bit 4) | uint32 | combined | panels.py:2433 |
| (same set) | `og_door_one_way` | `False` | `flags` (bit 8) | uint32 | combined | |
| (same set) | `og_door_starts_open` | `False` | `perm-status` | uint32=64 | if True | |
| **sun-iris-door** | `og_door_proximity` | `False` | `proximity` | uint32=1 | if True | panels.py:2665 |
| sun-iris-door | `og_door_timeout` | `0.0` | `timeout` | float | if > 0 | |
| **basebutton** | `og_button_timeout` | `0.0` | `timeout` | float | if > 0 | panels.py:2716 |
| **water-vol** | `og_water_surface` | mesh ymax | `water-height[0]` | water-height | always | panels.py:2493–2563 |
| water-vol | `og_water_wade` | `0.5` | `water-height[1]` | | | |
| water-vol | `og_water_swim` | `1.0` | `water-height[2]` | | | |
| water-vol | `og_water_bottom` | mesh ymin | (volume plane — not a lump field) | | | |
| water-vol | `og_water_attack` | `"drown"` | `attack-event` | symbol | always | |
| **launcherdoor** | `og_continue_name` | `""` | `continue-name` | string | if non-empty | |
| **launcher + springbox** | `og_spring_height` | `-1.0` | `spring-height` | meters | if ≥ 0 | panels.py:2288 |
| **launcher** | `og_launcher_dest` | `""` | `alt-vector[xyz]` | vector | if object exists | panels.py:2300 |
| launcher | `og_launcher_fly_time` | `-1.0` | `alt-vector[w]` | (frames = s × 300) | | |
| **swamp-bat, yeti, villa-starfish, swamp-rat-nest** | `og_num_lurkers` | `-1` | `num-lurkers` | int32 | if ≥ 0 | panels.py:2377 |
| **orb-cache-top** | `og_orb_count` | `20` | `orb-cache-count` | int32 | always | |
| **whirlpool** | `og_whirl_speed` | `0.3` | `speed[0]` | float | always | |
| whirlpool | `og_whirl_var` | `0.1` | `speed[1]` | | | |
| **ropebridge** | `og_bridge_variant` | `"ropebridge-32"` | `art-name` | symbol | always | panels.py:2846 (6 variants — see v1 §3.11) |
| **orbit-plat** | `og_orbit_scale` | `1.0` | `scale` | float | if != 1.0 | |
| orbit-plat | `og_orbit_timeout` | `10.0` | `timeout` | float | if != 10.0 | |
| **square-platform** | `og_sq_down` | `-2.0` | `distance[0]` | float (×4096) | always | |
| square-platform | `og_sq_up` | `4.0` | `distance[1]` | float (×4096) | | |
| **caveflamepots** | `og_flame_shove` | `2.0` | `shove` | meters | always | |
| caveflamepots | `og_flame_period` | `4.0` | `cycle-speed[0]` | float | always | |
| caveflamepots | `og_flame_phase` | `0.0` | `cycle-speed[1]` | | | |
| caveflamepots | `og_flame_pause` | `2.0` | `cycle-speed[2]` | | | |
| **shover** | `og_shover_force` | `3.0` | `shove` | meters | always | |
| shover | `og_shover_rot` | `0.0` | `rotoffset` | degrees | if != 0 | |
| **lavaballoon, darkecobarrel** | `og_move_speed` | `3.0` (lavaballoon) / `15.0` (darkecobarrel) | `speed` | meters | always | panels.py:2983 |
| **windturbine** | `og_turbine_particles` | `False` | `particle-select` | uint32=1 | if True | panels.py:3024 |
| **caveelevator** | `og_elevator_mode` | `0` | `mode` | uint32 | if != 0 | panels.py:3052 |
| caveelevator | `og_elevator_rot` | `0.0` | `rotoffset` | degrees | if != 0 | |
| **mis-bone-bridge** | `og_bone_bridge_anim` | `0` | `animation-select` | uint32 | if != 0 | panels.py:3087 |
| **breakaway-left/mid/right** | `og_breakaway_h1` | `0.0` | `height-info[0]` | float | if either != 0 | panels.py:3114 |
| breakaway | `og_breakaway_h2` | `0.0` | `height-info[1]` | float | | |
| **sunkenfisha** | `og_fish_count` | `1` | `count` | uint32 | if != 1 | |
| **sharkey** | `og_shark_scale` | `1.0` | `scale` | float | if != 1.0 | |
| sharkey | `og_shark_delay` | `1.0` | `delay` | float | always | |
| sharkey | `og_shark_distance` | `30.0` | `distance` | meters | always | |
| sharkey | `og_shark_speed` | `12.0` | `speed` | meters | always | |
| **oracle, pontoon** | `og_alt_task` | `"none"` | `alt-task` | enum-uint32 `(game-task <t>)` | if != "none" | panels.py:3249 |

**28 distinct actors (or actor-groups) with custom fields. ~55 per-actor properties.**

### B.6 — Non-actor object types (cameras, sound emitters, music zones, checkpoints)

These aren't actors in the `ACTOR_<etype>_<uid>` sense — they're special object types with their own prefix (`CAMERA_`, `AMBIENT_`, `CHECKPOINT_`…). Worth treating as distinct entries in the reference file because their fields are game-specific too.

| Object type | Property | Default | Output | Notes |
|---|---|---|---|---|
| **CAMERA** | `og_cam_mode` | `"fixed"` | selects export path | values: `fixed / standoff / orbit` |
| CAMERA | `og_cam_interp` | `1.0` | `interpTime` | float |
| CAMERA | `og_cam_fov` | `0.0` | `fov` | degrees (if > 0) |
| CAMERA | `og_cam_look_at` | `""` | `interesting` | resolves a named object → vector3m |
| **AMBIENT (sound emitter)** | `og_sound_name` | (required) | `effect-name` | symbol |
| AMBIENT | `og_sound_mode` | `"loop"` | selects cycle-speed form | values: `loop / oneshot` |
| AMBIENT | `og_sound_radius` | `15.0` | bsphere radius | float |
| AMBIENT | `og_cycle_min` | `5.0` | `cycle-speed[0]` | float (non-loop only) |
| AMBIENT | `og_cycle_rnd` | `2.0` | `cycle-speed[1]` | float (non-loop only) |
| **AMBIENT (music zone)** | `og_music_bank` | (required) | `music`, `effect-name` | symbol (choice from LEVEL_BANKS) |
| AMBIENT (music) | `og_music_flava` | `"default"` | `flava` | index lookup via MUSIC_FLAVA_TABLE |
| AMBIENT (music) | `og_music_priority` | `10.0` | `priority` | float |
| AMBIENT (music) | `og_music_radius` | `40.0` | bsphere radius | float |
| **AMBIENT (music zone — alt property set)** | `og_music_amb_bank` | `"village1"` | (same output as og_music_bank) | likely a newer rename — see B.7 |
| AMBIENT (music-amb) | `og_music_amb_flava` | `"default"` | | |
| AMBIENT (music-amb) | `og_music_amb_priority` | `10.0` | | |
| AMBIENT (music-amb) | `og_music_amb_radius` | `40.0` | | |
| **CHECKPOINT** | `og_checkpoint_radius` | `3.0` | bsphere radius | float |
| CHECKPOINT | `og_continue_name` | `""` | checkpoint continue label | string |

### B.7 — Property-name duplication (smells)

Two near-duplicate sets found during the sweep; flagging for cleanup:

1. **Music zone: `og_music_*` vs `og_music_amb_*`.** The `og_music_*` set is what `export.py` actually reads (line 2137–2142). The `og_music_amb_*` set is defined in `properties.py` (lines 288–296) but I haven't found where it's read. Likely a half-finished rename or a UI-only property that operators copy into `og_music_*` before export. Worth investigating during extraction — one of them is probably dead code.
2. **Level sound/music props on collections vs on objects.** Level-wide banks live on the level collection (`og_sound_bank_1/2`, `og_music_bank`). But `og_music_bank` is also read from AMBIENT objects (line 2137) for music *zones*. Same property name, two scopes. Not a bug — but it means the new schema needs to be clear that "music_bank" appears both as a Level default and as a zone-actor field.

### B.8 — `og_*` referenced but never read back (potential dead code)

These appear in the grep but I didn't find a corresponding read in `export.py`/`panels.py`:

- `og_music_amb_*` (see B.7)

Not a major finding but worth verifying during rewiring — if truly dead, delete.

---

## C. Answers to v1 §7 open questions

I tackled the ones I could investigate without your input. Remaining ones need your call.

### Q1. Schema extension policy — **unchanged (your call)**
Need your review of the §6 sketch before I freeze schema.

### Q2. Deep per-actor field sweep — **done (this doc)**
§B.5 and §B.6 above. 28 actor families + 4 non-actor object types. Every `og_*` property is accounted for and mapped to its output.

### Q3. SFX bloat — **investigated, leaning toward derived**
`ALL_SFX_ITEMS` (~1000 entries) and `SBK_SOUNDS` (bank → sounds) contain overlapping information: `SBK_SOUNDS` already groups sounds by bank, and `ALL_SFX_ITEMS` is just the flat list with pre-sorted `[Plyr]`/`[Beach]`/etc. labels. In principle we can keep only `SBK_SOUNDS` in the reference file and derive the flat enum at addon load. **Recommendation:** keep only `BankSFX` in the data file; build `ALL_SFX_ITEMS` equivalent at load time. Saves ~40 KB of file size. Your call — say "yes derive" or "no keep both" and I'll go with it.

### Q4. Parents hierarchy — **investigated, minimal set sufficient**
Only three distinct `ai_type` values across all 153 entries: `nav-enemy`, `process-drawable`, `prop`. Adding a fourth (`fact-info-enemy`) wouldn't gain anything — the addon already handles the enemy case via `cat in {Enemies, Bosses}` rather than via a parent check. **Recommendation:** start with 3 parent entries matching the ai_types, plus maybe a 4th `eco-collectable` if we want pickups to be parented too. Can grow later.

### Q5. Wiki images — **investigated, folder missing**
See §A.5. Your decision: re-import the images, drop the field, or use remote URLs.

### Q6. Engine-vs-game separation — **leaning: keep together**
Items like `meter_scale (4096)`, `LUMP_TYPE_ITEMS`, `AGGRO_TRIGGER_EVENTS`, `pat_surfaces/events/modes` are shared across Jak 1 / Jak 2 / Daxter (all OpenGOAL titles). But keeping them separate right now would fragment the data before we even ship v1 of the reference file. **Recommendation:** single file, single top-level `"Engine"` section that's clearly labeled as "shared across OpenGOAL games" — easy to split out later if we ever fork for Jak 2.

---

## D. Final audit pass — cross-references resolved

As a final sanity check I re-read every `.py` file's imports-from-data and confirmed that every imported symbol is accounted for in either v1 audit §3 or this addendum §B. Summary:

| File | Imports from data.py | All accounted for? |
|---|---|---|
| `__init__.py` | 16 symbols | ✓ |
| `audit.py` | 7 symbols | ✓ |
| `build.py` | 1 (`needed_tpages`) + 10 from export | ✓ |
| `collections.py` | 1 (ENTITY_DEFS) | ✓ |
| `export.py` | 17 symbols | ✓ |
| `model_preview.py` | 1 (ENTITY_DEFS) | ✓ |
| `operators.py` | 27 symbols | ✓ |
| `panels.py` | 22 symbols | ✓ |
| `properties.py` | 16 symbols | ✓ |
| `textures.py` | 0 from data.py (owns its own TPAGE_GROUPS) | ✓ — flagged as duplicate in v1 §3.10 |
| `utils.py` | 10 symbols | ✓ |

No missed imports. No orphan data modules.

---

## E. Ready-to-start check

Before I start populating `Jak1_Reference.jsonc`, I need from you:

1. **Go/no-go on the schema sketch** in `audit.md` §6. Especially the proposed `fields:` array per actor (this doc §B.5 shows what it has to carry).
2. **SFX derivation** (Q3): derive flat enum from `BankSFX` — yes or no?
3. **Wiki images** (Q5): include field / drop field / use remote URLs — which?
4. **File naming.** I've been calling it `Jak1_Reference.jsonc` informally. Any preferred name? `game_data.jsonc`? `jak1.jsonc`?
5. **Any additions or pushback** on the audit — things I still missed, things that shouldn't actually move, etc.

Once those are settled, I'll build the reference file section-by-section, committing to the `refactoring` branch as each section lands. Suggested build order: Engine → Levels → Categories → SoundBanks/MusicBanks/BankSFX → CrateTypes/CratePickups → PAT → LumpTypes → UniversalLumps → AggroEvents → GameTasks → Parents → Actors (biggest, last). Each section is editable independently; nothing depends on actors being done first.
