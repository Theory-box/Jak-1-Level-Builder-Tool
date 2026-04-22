# session-notes/refactoring.md

> Active branch: `refactoring`. Pick this up with `git checkout refactoring && git pull`.

---

## Status: rewire complete, ready for Blender testing

The addon has been structurally refactored to separate game-specific data from
addon code. All the "how to spawn a babak" details (actor definitions, lump
references, audio tables, level data, PAT enums, etc.) now live in a single
JSONC database file. The Python code only contains UI, export logic, and
Blender integration.

**No behavioral change is expected.** The rewire is a transparent
substitution — every public symbol the addon exposed before still exists with
the same type and effectively the same contents, just sourced from the JSONC
instead of hardcoded Python literals.

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

## What to test in Blender

Loading the addon, then exercising each major feature in a fresh .blend:

1. **Addon registers without errors** — boot Blender, enable addon, check
   console for any import errors. Most likely failure mode if anything's
   wrong: `KeyError` in `ENTITY_DEFS` or `LUMP_REFERENCE` at module load.
2. **Spawn picker** — open any spawn panel (Enemies, Platforms, Pickups,
   etc.) and confirm every entity still appears with correct labels and
   tooltips. Compare against current main branch visually if anything looks
   off.
3. **Quick search** — type partial names into the search box and confirm
   matches appear in the dropdown.
4. **Tpage filter** — enable the limit filter, pick 2 groups, confirm the
   spawn picker filters correctly.
5. **Spawn a babak** (or any nav-enemy) — confirm it spawns, gets the right
   empty display (color/shape), and the lump reference panel shows the
   correct set of lumps (universal + enemy + actor-specific).
6. **Spawn a crate** — confirm the Crate Type and Pickup dropdowns populate
   correctly, and the Amount field appears.
7. **Spawn a ropebridge** — confirm the Variant dropdown has all 6 options.
8. **Manual lump editor** — add a lump row with type `meters`, confirm the
   parser accepts "5.0" and emits `["meters", 5.0]` on export.
9. **Link slots** — spawn an eco-door, add a basebutton, link the door to
   the button via the actor-links panel, confirm it exports correctly.
10. **Audio** — open a sound emitter or music zone, confirm the bank/flava
    pickers populate from the database.
11. **Export** — export a small level, confirm no crash and the output JSONC
    structure looks right.

If all 11 pass, the rewire is behaviorally complete.

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
