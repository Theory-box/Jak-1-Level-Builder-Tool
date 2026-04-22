# Jak 1 Level Builder — Game Data Audit

**Status:** Draft v1 (audit only, no extraction yet)
**Branch:** `refactoring` (local)
**Goal:** Catalogue everything game-specific baked into the addon code so we can lift it into a single data-driven reference file.

---

## 1. Methodology

"Game-specific" is defined as: **anything that would differ if the same tool were targeting Jak 2 instead of Jak 1**, OR that would differ if a modder defined new actors / levels / audio banks / etc. This includes actor definitions, res-lump schemas, level names, tpage numbers, audio bank names, game task IDs, enemy AI flags, and engine-source file paths that reference `jak1`.

It does **not** include: Blender UI scaffolding, panel registration code, generic math, logging, generic file I/O, or pure addon-internal state (cached previews, temp build paths, etc.). Those stay in code.

"Engine constants" (like the 4096× meters scale) are flagged but treated as a separate concern — they're engine-wide, not game-specific in the Jak 1 vs Jak 2 sense.

I scanned all 12 files under `addons/opengoal_tools/`, took `data.py` as the baseline since it's explicitly "pure data tables", then hunted for game-specific content sitting *outside* `data.py` across the other 11 files.

---

## 2. Summary

| # | Category | Primary Location | Lines | Item Count (approx.) |
|---|---|---|---|---|
| 1 | Actor/Entity definitions | `data.py` ENTITY_DEFS | 39–264 | ~90 actors |
| 2 | Wiki text & images | `data.py` ENTITY_WIKI | 294–328 | 33 entries |
| 3 | Crate item types | `data.py` CRATE_ITEMS + CRATE_PICKUP_ITEMS | 266–285 | 6 + 7 |
| 4 | PAT collision enums | `data.py` pat_surfaces / events / modes | 13–30 | 23 + 7 + 3 |
| 5 | Tpage-per-level tables | `data.py` BEACH_TPAGES … CITADEL_TPAGES | 809–829 | 19 level groups |
| 6 | Tpage-per-etype table | `data.py` ETYPE_TPAGES | 831–1000 | ~80 entries |
| 7 | Global tpage groups | `data.py` GLOBAL_TPAGE_GROUPS | 412 | 4 |
| 8 | Code dependencies (.o/.gc) | `data.py` ETYPE_CODE | 595–790 | ~85 entries |
| 9 | Music flava table | `data.py` MUSIC_FLAVA_TABLE | 1005–1026 | 19 banks |
| 10 | Level sound banks | `data.py` LEVEL_BANKS | 1048–1069 | 20 banks |
| 11 | Per-bank SFX lists (SBK) | `data.py` SBK_SOUNDS | 1071–1092 | 19 banks |
| 12 | All SFX enum | `data.py` ALL_SFX_ITEMS | 1094–2131 | ~1000 items |
| 13 | Res-lump per-actor schema | `data.py` LUMP_REFERENCE | 2139–2579 | ~100 actors |
| 14 | Res-lump universal schema | `data.py` UNIVERSAL_LUMPS | 2580–2589 | 8 |
| 15 | Res-lump type enum | `data.py` LUMP_TYPE_ITEMS | 2863–2888 | 19 types |
| 16 | Hardcoded-lump keys | `data.py` _LUMP_HARDCODED_KEYS | 2893–2897 | 13 |
| 17 | Actor link schema | `data.py` ACTOR_LINK_DEFS | 2632–2741 | ~60 entries |
| 18 | Vertex-export exclusions | `data.py` VERTEX_EXPORT_EXCLUDE / TYPES | 551–564 | 4 + ~? |
| 19 | Aggro events | `data.py` AGGRO_TRIGGER_EVENTS | 2986–2991 | 3 |
| 20 | Texture-browser groups | `textures.py` TPAGE_GROUPS + `properties.py` tex_group | 30–51 / 323–349 | 21 groups |
| 21 | Rope-bridge variants | `panels.py` _ROPEBRIDGE_VARIANTS | 2818–2825 | 6 |
| 22 | Game tasks enum | `panels.py` _GAME_TASKS_COMMON | 3192–3224 | ~30 |
| 23 | Eco-door etype set | `panels.py` + `audit.py` + `export.py` | multiple | 4 |
| 24 | Launcher / spawner etype sets | `export.py` | 1097, 1103 | 2 + 4 |
| 25 | Per-actor export branches | `export.py` | ~1377–1860 | ~25 etype branches |
| 26 | Per-actor UI panel polls | `panels.py` | ~2150–3270 | ~25 actor-specific panels |
| 27 | Entity-cat → collection map | `collections.py` | 41–50 | 8 cats |
| 28 | Level custom-prop key map | `collections.py` _LEVEL_PROP_KEY_MAP | 12–20 | 7 |
| 29 | Level default values | `collections.py` _LEVEL_COL_DEFAULTS | 53+ | ~8 |
| 30 | level-info.gc template | `export.py` patch_level_info | 2359–2443 | 1 template |
| 31 | Engine scale constants | `export.py` + `data.py` | multiple | 2 (4096, 182.044) |
| 32 | "jak1" game/toolchain id | `build.py`, `export.py`, `textures.py`, `model_preview.py` | multiple | ~15 occurrences |

**Total bucket count:** 32 distinct game-data categories across 9 of the 12 addon files.

---

## 3. Findings by Category

### 3.1 — ENTITY_DEFS (actor definitions)

- **Location:** `data.py` lines 39–264
- **Shape:** `{ etype: { label, cat, tpage_group, ag, nav_safe, needs_path, needs_pathb, is_prop, ai_type, color, shape, glb } }`
- **Fields per entry:** 12 (some optional — `ag`, `tpage_group`, `glb` omitted for certain entries)
- **Consumers:** imported by 10 files — `properties.py`, `panels.py`, `operators.py`, `export.py`, `collections.py`, `utils.py`, `audit.py`, `model_preview.py`, `__init__.py`, plus derived lookups within `data.py` itself.
- **Derived sets built from it in `data.py`:**
  - `NAV_UNSAFE_TYPES`, `NEEDS_PATH_TYPES`, `NEEDS_PATHB_TYPES`, `IS_PROP_TYPES` (line 577–580) — computed via dict comprehension
  - `ETYPE_AG` (line 581)
  - `ENTITY_ENUM_ITEMS`, `ENEMY_ENUM_ITEMS`, `PROP_ENUM_ITEMS`, `NPC_ENUM_ITEMS`, `PICKUP_ENUM_ITEMS`, `PLATFORM_ENUM_ITEMS` (built via `_build_entity_enum`, `_build_cat_enum`, etc.)
  - `TPAGE_FILTER_ITEMS` (from `tpage_group` values + `GLOBAL_TPAGE_GROUPS`)
- **Category values used:** `"Enemies"`, `"Bosses"`, `"Platforms"`, `"Props"`, `"Objects"`, `"Debug"`, `"NPCs"`, `"Pickups"`.
- **Fits example schema?** Mostly. Mapping to `Actor_list_example.jsonc`:
  - `label` → `label` ✓
  - `cat` → `category` ✓ (rename)
  - `ag` → `art_group` ✓ (rename, accept string or list)
  - `glb` → `glb` ✓
  - No `etype` key on current dict — the etype is the dict key; in new file it becomes a field.
  - No `description` — currently lives in `ENTITY_WIKI` (see §3.2); merge at import.
- **Fields in current dict NOT in example schema** (need schema extension):
  - `nav_safe`, `needs_path`, `needs_pathb`, `is_prop`, `ai_type` — these are metadata about engine behaviour. `ai_type` overlaps conceptually with the example's `parent` field (parent of `nav-enemy` ⟹ `ai_type == "nav-enemy"`), so `parent` may replace several of these if the Parents section is populated. `is_prop` / `nav_safe` / `needs_path` / `needs_pathb` may still need explicit fields because the parent hierarchy isn't formal yet.
  - `tpage_group` — used for UI filtering (the "enemies grouped by level" picker). See §3.6.
  - `color`, `shape` — Blender viewport display (empty-object color + display shape). Not in example. Propose adding to the schema since they're per-actor presentation data.
- **Parents not modeled:** The example file has a top-level `"Parents"` section (`nav-enemy`, `process-drawable`, etc.). Current addon has no formal parent table — parent semantics are implicit in `ai_type` and the per-etype entries in `LUMP_REFERENCE`/`ACTOR_LINK_DEFS`. Building the Parents section is **new structure**, not extraction from existing data.

### 3.2 — ENTITY_WIKI (help text + images)

- **Location:** `data.py` lines 294–328
- **Shape:** `{ etype: { img: filename|None, desc: str } }`
- **Count:** 33 entries (mostly enemies/bosses + a few NPCs)
- **Image paths:** Stored as bare filenames; actual files live at `<addon_dir>/enemy-images/<filename>`. Worth confirming the folder exists in the repo.
- **Fits example schema?** Yes — maps cleanly to the `description` field of each actor. Image filename is new; add an `image` or `wiki_img` field.
- **Note:** Only 33 of the ~90 actors have wiki entries. The rest currently show no description in the UI. Migration should keep that as-is (absence = no description).

### 3.3 — Per-actor custom UI panels & export logic ⚠ largest hidden surface

This is the biggest non-`data.py` finding. Many actors have **bespoke UI panels** in `panels.py` and **bespoke export branches** in `export.py`, driven by ad-hoc per-etype Python if-chains rather than data. Each one:
1. Gates by checking `parts[1] == "<etype>"` or `parts[1] in {set}` in panel `poll()`.
2. Reads one or more `og_<something>` custom properties from the Blender object.
3. On export, writes specific res-lump keys with formatted values.

**Actor-specific panels in `panels.py`:**

| Line | Class | Gates on etype(s) |
|---|---|---|
| 2154 | OG_PT_ActorCrate | `crate` |
| 2212 | OG_PT_ActorDarkCrystal | `dark-crystal` |
| 2245 | OG_PT_ActorFuelCell | `fuel-cell` |
| 2402 | OG_PT_ActorEcoDoor (sub) | `{eco-door, jng-iris-door, sidedoor, rounddoor}` |
| 2476 | OG_PT_ActorWaterVol | `water-vol` |
| 2587 | OG_PT_ActorLauncherDoor | `launcherdoor` |
| 2650 | OG_PT_ActorSunIrisDoor | `sun-iris-door` |
| 2699 | OG_PT_ActorBasebutton | `basebutton` |
| 2738 | OG_PT_ActorPlatFlip | `plat-flip` |
| 2776 | OG_PT_ActorOrbCacheTop | `orb-cache-top` |
| 2803 | OG_PT_ActorWhirlpool | `whirlpool` |
| 2841 | OG_PT_ActorRopeBridge | `ropebridge` |
| 2871 | OG_PT_ActorOrbitPlat | `orbit-plat` |
| 2899 | OG_PT_ActorSquarePlatform | `square-platform` |
| 2927 | OG_PT_ActorCaveFlamePots | `caveflamepots` |
| 2960 | OG_PT_ActorShover | `shover` |
| 2983 | OG_PT_ActorLavaBalloon | `{lavaballoon, darkecobarrel}` |
| 3019 | OG_PT_ActorWindturbine | `windturbine` |
| 3047 | OG_PT_ActorCaveElevator | `caveelevator` |
| 3082 | OG_PT_ActorMisBoneBridge | `mis-bone-bridge` |
| 3114 | OG_PT_ActorBreakaway | `{breakaway-left, breakaway-mid, breakaway-right}` |
| 3149 | OG_PT_ActorSunkenfisha | `sunkenfisha` |
| 3175 | OG_PT_ActorSharkey | `sharkey` |
| 3236 | OG_PT_ActorTaskGated | `{oracle, pontoon}` |
| 3269+ | … (more downstream — scan to confirm) | … |

**Actor-specific export branches in `export.py`:**

| Line | etype(s) |
|---|---|
| 1377 | eco-door |
| 1396 | fuel-cell |
| 1402 | buzzer |
| 1404 | crate |
| 1424 | money |
| 1538 | dark-crystal |
| 1544 | plat-flip |
| 1553 | `{eco-door, jng-iris-door, sidedoor, rounddoor}` |
| 1578 | sun-iris-door |
| 1589 | basebutton |
| 1626, 1730 | water-vol |
| 1664 | launcherdoor |
| 1743 | plat-flip |
| 1750 | orb-cache-top |
| 1757 | whirlpool |
| 1764 | ropebridge |
| 1770 | orbit-plat |
| 1780 | square-platform |
| 1788 | caveflamepots |
| 1798 | shover |
| 1814 | windturbine |
| 1820 | caveelevator |
| 1830 | mis-bone-bridge |
| 1845 | sunkenfisha |
| 1852 | sharkey |

**Custom-property fields read by these branches** (sample — not exhaustive, needs a proper sweep):

| etype | og_* property | Output lump key | Lump type |
|---|---|---|---|
| dark-crystal | og_crystal_underwater | mode | int32 |
| plat-flip | og_flip_sync_pct | sync-percent | float |
| eco-door (set) | og_door_auto_close / og_door_one_way / og_door_starts_open | flags / perm-status | uint32 |
| sun-iris-door | og_door_proximity / og_door_timeout | proximity / timeout | uint32 / float |
| basebutton | og_button_timeout | timeout | float |
| ropebridge | og_bridge_variant | (art-group swap, not a lump) | n/a |
| orbit-plat | og_orbit_scale / og_orbit_timeout | (TBD) | (TBD) |
| oracle, pontoon | og_alt_task | alt-task | enum-int32 (game-task) |

⚠ **Fits example schema?** **No.** The current example has `links` (generic slot-based references to other actors) and `link_desc`, but doesn't model **scalar/enum/flag fields per actor**. This is the single biggest schema gap.

**Proposed schema extension** (needs your sign-off — see §5): a new `fields` (or `properties`) array per actor, each entry: `{key, label, type (bool/int/float/enum/task), default, lump_key, lump_type, write_if}`.

### 3.4 — Lump reference & lump-type system

- **LUMP_REFERENCE** (`data.py` 2139–2579): `{ etype: [(key, lump_type, description), ...] }` plus sentinel `_enemy` key for shared enemy lumps. ~100 etype entries.
- **UNIVERSAL_LUMPS** (2580–2589): 8 entries applied to every actor.
- **LUMP_TYPE_ITEMS** (2863–2888): 19 lump types (`float`, `meters`, `degrees`, `int32`, `uint32`, `enum-int32`, `enum-uint32`, `vector4m`, `vector3m`, `vector-vol`, `vector`, `movie-pos`, `water-height`, `eco-info`, `cell-info`, `buzzer-info`, `symbol`, `string`, `type`). Each has a description.
- **_LUMP_HARDCODED_KEYS** (2893–2897): 13 keys that the export system always writes; manual lump rows targeting these emit a warning. `{name, path, pathb, sync, options, eco-info, cell-info, buzzer-info, crate-type, nav-mesh-sphere, idle-distance, vis-dist, notice-dist}`.
- **Fits example schema?** Partially. The example's `links[]` array already covers **actor-to-actor references** via `need_*` booleans (task, path, nav, enemy, vol, alt, prev, next, sync, eco-info, pathb). `LUMP_REFERENCE` is broader — it covers *any* res-lump key, not just reference lumps.

  Recommendation: keep the example's `links` structure for reference-style lumps (it's the cleaner schema), and add a sibling `lumps` array for non-reference lumps (things like `mode`, `num-lurkers`, `distance`, `trans-offset`, etc.).

### 3.5 — Actor link definitions (ACTOR_LINK_DEFS)

- **Location:** `data.py` 2632–2741 (plus the big tail from 2741 to 2577 in a second block).
- **Shape:** `{ etype: [(lump_key, slot_index, label, accepted_etypes, required), ...] }`
- **Count:** ~60 entries.
- **Consumers:** `panels.py` (renders the link pickers), `export.py` (emits as string arrays), `operators.py` (link editing ops), `audit.py` (validation — e.g. checks that eco-door state-actors point to basebuttons).
- **Fits example schema?** Sort of. The example's `links[]` array uses boolean `need_*` flags (`need_task`, `need_path`, `need_alt`…). ACTOR_LINK_DEFS is more granular — it models **multiple slots per lump key** (e.g. `cave-trap` has 4 `alt-actor` slots, one per spider-egg) and **accepted target etypes** (e.g. `ogre-bridge` accepts only `ogre-bridgeend`).

  Recommendation: treat the example's `need_alt` style as the coarse bool ("does this actor support alt-actor links at all?"), and add a more detailed structure (`alt_actor_slots`, or a generic `link_slots: [{key, slot, label, accepts, required}]`) for multi-slot / type-constrained actors.

### 3.6 — Texture pages (per-level + per-etype)

- **Per-level tpage arrays** (`data.py` 809–829): `BEACH_TPAGES`, `JUNGLE_TPAGES`, `SWAMP_TPAGES`, `SNOW_TPAGES`, `SUNKEN_TPAGES`, `SUB_TPAGES`, `CAVE_TPAGES`, `ROBOCAVE_TPAGES`, `DARK_TPAGES`, `OGRE_TPAGES`, `MISTY_TPAGES`, `LAVATUBE_TPAGES`, `FIRECANYON_TPAGES`, `ROLLING_TPAGES`, `TRAINING_TPAGES`, `JUNGLEB_TPAGES`, `FINALBOSS_TPAGES`, `CITADEL_TPAGES`. 19 arrays, each with 4–6 tpages.
- **Per-etype tpages** (`ETYPE_TPAGES`, 831–1000): `{ etype: [tpage strings] }`.
- **Global tpage groups** (`GLOBAL_TPAGE_GROUPS`, line 412): `{"Village1", "Village2", "Village3", "Training"}` — groups that are always available and don't eat heap budget for enemies.
- **TPAGE_FILTER_ITEMS** (431): derived list for the enemy-type UI picker.
- **Consumers:** `data.py` itself (derived), `export.py` (needed_tpages → written into the .gd), `operators.py`, `__init__.py`.
- **Fits example schema?** Per-etype tpages fit as a `tpages` field on each actor (example already has this). The per-level arrays are new — they need a top-level `Levels` section (see §3.10).

### 3.7 — Code dependencies (ETYPE_CODE)

- **Location:** `data.py` 595–790
- **Shape:** `{ etype: {o?, gc?, dep?, in_game_cgo?, o_only?} }`
- **Count:** ~85 entries.
- **Purpose:** tells the exporter whether an etype's `.o` needs injecting into the custom DGO, and whether a `goal-src` line needs adding to `game.gp`.
- **Fits example schema?** Add a `code` field per actor. Example already proposes this (`"code":"code-file.o"`). Needs the `in_game_cgo` / `o_only` booleans too. Propose:
  ```
  "code": {"o": "babak.o", "in_game_cgo": true}
  ```
  or omit entirely when nothing is needed.

### 3.8 — Audio (music + SFX)

- **LEVEL_BANKS** (`data.py` 1048–1069): 20 sound bank names — one per engine level (plus `"none"`). Used for both music banks and SFX banks.
- **MUSIC_FLAVA_TABLE** (`data.py` 1005–1026): `{ bank: [flava variant names] }`. 19 banks with 1–10 flavas each.
- **SBK_SOUNDS** (`data.py` 1071–1092): `{ bank: [sfx names] }`. 19 banks; `"common"` is very large (~300 sounds), per-level banks 10–50 each.
- **ALL_SFX_ITEMS** (`data.py` 1094–2131): flat enum of ~1000 SFX items. Each tuple is `(id, label, desc, index)`. The labels include bracketed prefixes like `"[Plyr]"`, `"[Beach]"`, etc. to group sounds in the Blender picker.
- **Consumers:** `properties.py` (EnumProperty items), `operators.py` (sound-zone operators), `panels.py` (sound emitter panel), `export.py` (writes to `*-ag.go`? confirm).
- **Fits example schema?** No — the example is actor-only. Need new top-level sections: `SoundBanks`, `MusicBanks` (with flavas), `SFX` (global enum), and maybe `BankSFX` (bank → sounds mapping, since `SBK_SOUNDS` is used for bank-filtered SFX pickers).
- **Format note:** `ALL_SFX_ITEMS` is ~1000 entries at ~40 bytes each → ~40 KB. This inflates the JSONC considerably. Worth discussing: keep it verbose for editability, or structure as `{bank: [sfx]}` only (and let the enum derive)?

### 3.9 — Game tasks (_GAME_TASKS_COMMON)

- **Location:** `panels.py` 3192–3224
- **Shape:** `[(task_id, label), ...]`
- **Count:** ~30 entries.
- **Purpose:** Task picker for `OG_PT_ActorTaskGated` (oracle alt-task, pontoon sink-task).
- **Consumer:** currently only `panels.py`. The exporter writes tasks via `(game-task <id>)` enum-int32 lump format.
- **Fits example schema?** No — needs a new top-level `GameTasks` section. Note: this list is currently a subset ("common"); the full game-task enum has many more. Decide whether to expand or keep a curated list.

### 3.10 — Levels (not yet a top-level structure)

Multiple scattered sources describe per-level metadata:
- Level names appear in `LEVEL_BANKS`, `MUSIC_FLAVA_TABLE`, `SBK_SOUNDS`, the per-level `*_TPAGES` arrays, and in `panels.py` `_GAME_TASKS_COMMON` labels (prefixed strings like `"Jungle:"`, `"Beach:"`, etc.).
- Level index (`:index 27`), mood (`*village1-mood*`), and moods function are hardcoded into `patch_level_info` in `export.py` 2404–2429. (Actually all custom levels currently get `village1-mood` by default — this is a known placeholder, not a proper table.)
- Texture-browser groups in `textures.py` 30–51 map UI group → tpage folder prefixes; many of them align with level names (`BEACH`, `JUNGLE`, `SWAMP`, etc.).
- `properties.py` `tex_group` (323–349) duplicates the 21 texture-browser group IDs (needs deduplication with `textures.py`).
- Rollup of level names seen across the codebase: `village1, village2, village3, jungle, jungleb, beach, misty, swamp, rolling, ogre, firecanyon, lavatube, snow, sunken, sub, maincave, robocave, darkcave, training, citadel, finalboss, common, effects, characters, hud`.

**Recommendation:** Add a top-level `Levels` section with per-level: `name`, `label`, `tpages`, `sound_bank`, `music_flavas`, `sbk_sfx`, `mood`, `mood_func`, `texture_folders` (for texture browser), `index` (if meaningful).

### 3.11 — Rope bridge variants

- **Location:** `panels.py` 2818–2825
- **Shape:** `[(art_name, label), ...]`, 6 entries.
- **Purpose:** Lets the user pick which `ropebridge-*-ag.go` art is used for a given `ropebridge` actor, which determines its length.
- **Fits example schema?** This is an instance of a per-actor "art variant picker" — a close cousin of the bespoke UI panels covered in §3.3. Suggest modelling it generically: an `art_variants` field on the actor listing acceptable art-group overrides with labels.

### 3.12 — PAT collision enums

- **Location:** `data.py` 13–30
- **Shape:** lists of `(id, label, desc, int_value)` tuples.
- **Three tables:** `pat_surfaces` (23 values), `pat_events` (7), `pat_modes` (3).
- **Purpose:** Collision tag editor in the addon — each face can be tagged with surface type, event behaviour, and mode.
- **Consumer:** used downstream in collision export (needs grep to confirm exact file — likely `export.py`).
- **Fits example schema?** No — needs a new top-level `PAT` or `Collision` section. These enums are engine-wide (shared Jak1/Jak2 likely) but the specific values are game-engine specific.

### 3.13 — Aggro trigger events

- **Location:** `data.py` 2986–2991
- **Shape:** `[(event_name, label, desc)]`, 3 entries.
- **Purpose:** Events sent via `trigger` messages between actors (wake enemy, patrol, freeze).
- **Consumer:** `properties.py` (EnumProperty), `export.py` (writes to path waypoint lumps), `__init__.py`.
- **Fits example schema?** Minor addition — new top-level `AggroEvents` or fold into a broader `TriggerEvents` section.

### 3.14 — Crate contents

- **CRATE_ITEMS** (`data.py` 266–273): 6 crate types (steel, wood, iron, darkeco, barrel, bucket).
- **CRATE_PICKUP_ITEMS** (277–285): 7 pickups that can be put inside a crate (with labels, engine strings, icons, and `supports_multi_amount` flag).
- **Consumer:** `properties.py`, `panels.py` (`OG_PT_ActorCrate`), `operators.py`, `export.py`, `__init__.py`.
- **Fits example schema?** Needs a dedicated `CrateTypes` + `CratePickups` section, or nest under the `crate` actor entry.

### 3.15 — Vertex-export exclusions

- **VERTEX_EXPORT_EXCLUDE** (`data.py` 551): `{crate, fuel-cell, orb-cache-top, powercellalt}` — etypes that skip vertex-lit export.
- **VERTEX_EXPORT_TYPES** (553–564): definition set (needs closer look).
- **Fits example schema?** Could be per-actor flag (`"vertex_export": false`).

### 3.16 — Entity categories → collection paths

- **Location:** `collections.py` 41–50
- **Shape:** `{ entity_cat: collection_path_tuple }`
- **Categories:** `Enemies`, `Bosses`, `Platforms`, `Props`, `Objects`, `Debug`, `NPCs`, `Pickups` → each maps to a nested Blender collection.
- **Fits example schema?** Adjacent — could live under a top-level `Categories` section with `{id, label, collection_path, icon}`. Currently the category names are just strings inside `ENTITY_DEFS["cat"]`; formalizing them in their own section lets us rename/reorder centrally.

### 3.17 — Level defaults & level-info.gc template

- **_LEVEL_COL_DEFAULTS** (`collections.py` 53+): default custom-property values when a new level collection is created.
- **_LEVEL_PROP_KEY_MAP** (`collections.py` 12–20): maps collection custom-property keys → addon `OGProperties` attribute names. 7 mappings: level_name, base_id, bottom_height, vis_nick_override, sound_bank_1/2, music_bank.
- **patch_level_info template** (`export.py` 2359–2443): GOAL `level-load-info` block template with many hardcoded fields (`:index 27`, `:mood '*village1-mood*`, `:mood-func 'update-mood-village1`, `:ocean #f`, `:sky #t`, `:sun-fade 1.0`, `:priority 100`, `:bsp-mask #xffffffffffffffff`, `:tasks '()`, etc.).
- **Fits example schema?** These are a "Level defaults" blob. Could live alongside the `Levels` section.

### 3.18 — Engine scale constants

- **4096.0** — meter-to-internal-units ratio (shared by all OpenGOAL games).
- **182.044** — degrees-to-internal-units ratio.
- **Usage:** 20+ sites in `export.py`; mentioned in lump-type descriptions in `data.py`.
- **Note:** These are **engine** constants, not game-specific. I recommend extracting them to the reference file under an `Engine` section (with a note that they're shared across Jak titles), so there's only one place to change if OpenGOAL ever changes them. Low priority.

### 3.19 — "jak1" toolchain identifiers

- Hardcoded `"jak1"` string appears in:
  - `build.py`: `--game jak1` CLI args to `goalc`/`gk` (lines 353, 380).
  - `export.py`: path segments `goal_src/jak1/`, `custom_assets/jak1/`, `decompiler_out/jak1/` (lines 50–55, 189, 203).
  - `textures.py`: `decompiler_out/jak1/textures/...` (line 10 comment).
  - `model_preview.py`: `decompiler_out/jak1/levels/...` (line 8 comment).
- **Fits example schema?** Belongs in an `Engine`/`Toolchain` section with keys like `game_id`, `goal_src_subdir`, `custom_assets_subdir`, etc. Minor but non-trivial — any Jak 2 fork would flip this.

---

## 4. Derived data (built from primary tables)

These are **not** game data per se — they're derived from the tables above. They do **not** need to move into the reference file; they should be computed at addon load time from the file's contents. Listed here so we don't accidentally treat them as primary data to extract.

| Name | Source | Location |
|---|---|---|
| ENTITY_ENUM_ITEMS | ENTITY_DEFS + tpage_group ordering | data.py 378 |
| ENEMY / PROP / NPC / PICKUP _ENUM_ITEMS | ENTITY_DEFS filtered by cat | data.py 402–405 |
| PLATFORM_ENUM_ITEMS | ENTITY_DEFS filtered by cat==Platforms | data.py 565 |
| NAV_UNSAFE_TYPES, NEEDS_PATH_TYPES, NEEDS_PATHB_TYPES, IS_PROP_TYPES | ENTITY_DEFS flags | data.py 577–580 |
| ETYPE_AG | ENTITY_DEFS["ag"] | data.py 581 |
| TPAGE_FILTER_ITEMS | ENTITY_DEFS tpage_group + GLOBAL_TPAGE_GROUPS | data.py 431 |
| AGGRO_EVENT_ENUM_ITEMS | AGGRO_TRIGGER_EVENTS | data.py 2992 |
| _MUSIC_BANK_ITEMS | LEVEL_BANKS (filter != "none") | operators.py 1270 |
| TPAGE_GROUP_ITEMS | TPAGE_GROUPS | textures.py 53 |

---

## 5. Schema gaps in `Actor_list_example.jsonc`

Ranked by size of the gap:

1. **Per-actor custom fields / lumps (§3.3).** Largest hidden surface. The example's `links[]` covers only reference-style lumps. Current addon has per-actor scalar/bool/enum/task fields (og_bridge_variant, og_crystal_underwater, og_flip_sync_pct, og_door_flags, og_button_timeout, og_orbit_scale, og_alt_task, og_door_proximity, og_door_timeout, og_button_timeout, plus more — a full sweep of panels.py + export.py is needed before this schema is frozen). Needs a new per-actor `fields` (or `properties`) block.

2. **Multi-slot actor links (§3.5).** Example's `need_alt: true` is coarse; current `ACTOR_LINK_DEFS` supports multiple slots per key plus accepted-etype constraints (e.g. `cave-trap` has 4 `alt-actor` slots, each accepting only `spider-egg`). Needs refinement if we want full fidelity.

3. **Top-level sections beyond actors.** The example is actor-centric. Full data set needs top-level sections for: `Levels`, `SoundBanks`, `MusicBanks`, `SFX`, `BankSFX`, `CrateTypes`, `CratePickups`, `GameTasks`, `PAT`, `AggroEvents`, `LumpTypes`, `Categories`, `Engine`.

4. **Category & link-type registries.** The example assumes categories (`"enemy"`, `"collectables"`) and link types (`need_path`, `need_nav`) are open strings. Current code treats them as closed sets. Worth deciding whether the data file should enumerate them.

5. **Art variants.** Ropebridge et al. have picker-style art-group overrides. Not in example. Needs a small addition.

6. **"Default lists" remark in example line 49:** the example already anticipates default lists for ag/code/tpages — that's a good idea. It can subsume `ETYPE_CODE`'s `in_game_cgo` flag (types listed in the default set are skipped at inject time).

---

## 6. Proposed reference file structure (sketch, for discussion)

```
{
  "Engine": { "game_id": "jak1", "meter_scale": 4096, "degree_scale": 182.044 },
  "Defaults": {
    "art_groups":  [...],   // always-available (GAME.CGO)
    "code_files":  [...],
    "tpages":      [...]
  },
  "Categories": [ {id, label, collection_path, icon} ],
  "Levels":     [ {name, label, tpages, sound_bank, music_flavas, sbk_sfx, mood, mood_func, texture_folders, defaults} ],
  "SoundBanks": [...],
  "MusicBanks": [...],
  "SFX":        [...],     // full flat enum (~1000) OR derived from BankSFX
  "BankSFX":    { bank: [sfx] },
  "CrateTypes":   [...],
  "CratePickups": [...],
  "GameTasks":    [...],
  "PAT":        { surfaces, events, modes },
  "AggroEvents": [...],
  "LumpTypes":   [...],
  "UniversalLumps": [...],
  "HardcodedLumpKeys": [...],
  "Parents":   [...],   // as in example
  "Actors":    [
    {
      etype, label, description, category, parent,
      art_group, code, tpages,
      links:        [...],    // as in example
      link_desc:    {...},    // as in example
      link_slots:   [...],    // detailed multi-slot refinement (optional)
      lumps:        [...],    // non-link res-lump entries (from LUMP_REFERENCE)
      fields:       [...],    // custom UI fields with export mapping (from the panels.py / export.py sweep)
      art_variants: [...],    // art-group picker (ropebridge etc.)
      wiki_img, glb, color, shape,
      nav_safe, needs_path, needs_pathb, is_prop, ai_type
    }
  ]
}
```

---

## 7. Open questions before extraction begins

1. **Schema extension policy.** You said "expand it freely" for fields the example doesn't cover. The schema sketch in §6 is a first pass — confirm the overall shape before I start populating it.

2. **Per-actor custom fields (§3.3).** The existing `og_*` properties and their lump-key mappings live scattered across ~25 panels + ~25 export branches. Before populating the `fields` array for each actor, do you want me to first do a **dedicated deep sweep** of `panels.py` and `export.py` to enumerate every `og_*` property + its output lump? That's probably a few hundred lines of audit on its own. It seems worth doing thoroughly since getting it wrong means broken export later.

3. **SFX bloat.** `ALL_SFX_ITEMS` (~1000 entries) dominates file size. Two options: (a) keep it verbose and human-editable, (b) only keep `BankSFX` and derive the flat enum. Preference?

4. **Parents hierarchy.** `nav-enemy`, `process-drawable`, etc. Is there a canonical list, or should I infer it from `ai_type` values plus what `LUMP_REFERENCE`'s `_enemy` sentinel implies? A proper parent chain would simplify many per-actor fields.

5. **Wiki images.** I haven't verified the `enemy-images/` folder exists in the repo or that its filenames match ENTITY_WIKI keys. Worth a sanity check during extraction.

6. **Engine-vs-game separation.** Some items (PAT enums, lump types, meter scale, universal lumps) are arguably engine-wide and would be the same for Jak 2. Keep them in the Jak 1 reference file for now, or split into a separate `engine.jsonc`? I'd lean "keep together for now, split later if it matters."

---

## 8. Next steps (proposed)

- [ ] You review this audit, flag anything I missed or mis-categorized.
- [ ] You answer the 6 open questions in §7.
- [ ] If the `fields` deep-sweep (question #2) is a yes, I do that next and publish a v2 audit addendum.
- [ ] We finalize the reference-file schema based on §6 + your decisions.
- [ ] I start populating `Jak1_Reference.jsonc` (or whatever we name it) section by section, committing to `refactoring` as we go.
- [ ] Only after the reference file contains every item from this audit do we touch the addon code.
