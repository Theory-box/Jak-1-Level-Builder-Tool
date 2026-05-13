# Level Index + Nickname Fix — Session Notes

**Branch:** `fix/level-index-nickname`
**Repo:** `Jak-1-Level-Builder-Tool` (the addon repo — NOT `Claude-Relay`)
**Status:** Shipped — merged to main 2026-05-12, branch deleted
**Last updated:** 2026-05-12

---

## Previous miss
An earlier branch of the same name on the `Claude-Relay` repo patched a
stale flat-file copy of the addon. `Claude-Relay/addons/opengoal_tools`
does not match the real addon in `Jak-1-Level-Builder-Tool` — it's an
older snapshot. That branch should be abandoned; the code it changes
isn't used. This branch is the correct port against the live split
package structure.

## Problems addressed
1. **Level index hardcoded to 27.** Every level exported with the same
   `:index 27` in `level-load-info`, colliding in multi-level blends.
2. **Nicknames could collide.** `og_vis_nick_override` existed as a
   collection prop but was not surfaced at level creation time; the
   default 3-letter auto-derived nick (first 3 chars of the name, dashes
   stripped) collided when two level names shared a prefix.

## Approach
- New `og_level_index` level-collection property (default 100).
- Collision helpers iterate `_all_level_collections(scene)` and
  reject or auto-suggest values.
- Surfaced index + vis_nick in Create, Assign, and Edit dialogs.
- Lazy migration: old levels missing `og_level_index` get a unique
  value assigned at export time or when the Edit dialog opens.
- Edit Level dialog's inline form moved into a live-editable Settings
  subpanel. The pencil icon on OG_PT_Level is gone.

## Files changed
- `addons/opengoal_tools/collections.py`
  - `og_level_index` added to `_LEVEL_COL_DEFAULTS` + `_LEVEL_PROP_KEY_MAP`
  - New helpers: `_next_free_level_index`, `_level_index_in_use`,
    `_resolve_vis_nick`, `_vis_nick_in_use`, `_suggest_unique_vis_nick`,
    `_ensure_level_index`, `_migrate_all_level_indices`
  - New live get/set proxies for the Settings subpanel:
    `_get_level_name_live/_set_level_name_live`,
    `_get_base_id_live/_set_base_id_live`,
    `_get_level_index_live/_set_level_index_live`,
    `_get_vis_nick_live/_set_vis_nick_live`
- `addons/opengoal_tools/properties.py`
  - New `level_index: IntProperty` with live get/set
  - Existing `level_name`, `base_id`, `vis_nick_override` now use live
    get/set so the subpanel edits the active collection directly
- `addons/opengoal_tools/operators/level.py`
  - `OG_OT_CreateLevel`, `OG_OT_AssignCollectionAsLevel`,
    `OG_OT_EditLevel` all take `level_index` + `vis_nick`, auto-populate
    on invoke, reject collisions on execute
  - EditLevel now calls `_migrate_all_level_indices` on invoke so
    collision checks see real values
- `addons/opengoal_tools/export/writers.py`
  - `patch_level_info` reads `og_level_index` (replaces hardcoded 27)
  - Calls `_migrate_all_level_indices(scene)` before reading
- `addons/opengoal_tools/panels/level.py`
  - `OG_PT_Level` header: dropped pencil icon and redundant info block
  - New `OG_PT_LevelSettings` subpanel (default-closed) with live-editable
    Name / Base ID / Level Index / Vis Nickname / Death Plane rows plus
    derived info and collision warnings
  - `OG_PT_LevelSettings` registered in the file's `CLASSES` tuple (picked
    up automatically by `panels/__init__.py`'s `ALL_CLASSES` aggregation)

## Design choices
- Starting index = 100. Knowledge base docs advise "must not collide with
  vanilla" and use 99 as an example; 100+ is safe.
- Collision = **reject at dialog execute** (Create/Assign/Edit operators),
  but only **warn** in the Settings subpanel. Keystroke-level rejection
  would be hostile. Export-time validation remains the authoritative gate.
- Lazy migration rather than big-bang: `_migrate_all_level_indices` walks
  all level collections and fills in missing `og_level_index` values;
  safe to call repeatedly. Fired from export and Edit-Level invoke.
- Settings subpanel uses live get/set proxies (same pattern as the
  existing `bottom_height` field) rather than re-plumbing operator
  properties. Edits are live; no Apply button.

## Verification done (automated)
- All five modified files pass `ast.parse`.

## Verification NOT done (user to test)
1. Install the zip — Blender should register without errors.
2. Open an existing multi-level blend, open **⚙ Settings** under Level.
   Existing levels should show distinct indices (100, 101, 102, …) rather
   than all the same value. The lazy migration runs when Edit Level or an
   export touches them; the subpanel relies on migrated values for its
   collision warnings.
3. Export a level, open the produced `level-info.gc`, confirm `:index` is
   no longer `27`.
4. Create two new levels with similar names (`training-a`, `training-b`).
   The second Add Level dialog should pre-suggest a non-colliding 3-char
   nick (e.g. `tr0` instead of `tra`).
5. In the Settings subpanel, type a colliding index or nick — a red
   warning should appear, export should reject.
6. Rename a level in the Settings subpanel; the Blender collection should
   rename in sync (Blender may auto-suffix on name conflicts; clean name
   still written to `og_level_name` so exports stay correct).

## Known small-risk areas
- `properties.py`: adding get/set to existing fields can trigger schema
  issues on addon reload. If Blender logs a registration error, disabling
  and re-enabling the addon in Preferences usually clears it.
- The `level_name` setter renames `col.name` and updates
  `scene.og_props.active_level`. If the user types a name that collides
  with another Blender collection (not a level — any collection), Blender
  silently suffixes with `.001`. The clean name still goes into
  `og_level_name` so exports are unaffected, but the dropdown may show the
  suffixed name briefly. Not worth blocking over.

## After user confirms
On approval, merge to `main`:
```
git checkout main && git merge fix/level-index-nickname && git push origin main
git branch -d fix/level-index-nickname
git push origin --delete fix/level-index-nickname
```

## Follow-up context
- The inheritance/database refactor we discussed is already done in the
  live tree — `db.py` + `jak1_game_database.jsonc`. That conversation is
  retired.
- The stale `fix/level-index-nickname` branch on `Claude-Relay` should
  be deleted; it patches dead code.

---

## 2026-05-12 — Resumed after long gap, two follow-up fixes

### Merge of main (commit c302735)
Branch had sat for ~3 weeks and main moved 24 commits — lighting (mood/sky),
fog override, bake filter, doc reorg, calver, pickup/balance-plat/bone-bridge
fixes. Two textual conflicts (additive overlap, not logical):
- `properties.py` imports from `.collections` — kept both the branch's live
  get/set proxies and main's mood/sky/fog handlers.
- `export/writers.py` `patch_level_info` — kept both `_lindex` (branch) and
  `_mood`/`_sky_bool`/`_mood_func`/`_sky_val` (main) in the if/else.

### Real bug found during user testing (commit 7b257b3)
Original branch only propagated the override into `level-info.gc`. The
file-naming write paths still used `_nick(name)` directly. For two levels
whose names share the same first 3 dash-stripped chars (e.g. `my-level`
and `my-level2` both → `myl`), the override (`my2`) was being ignored
everywhere except `patch_level_info`. Result on first build:
- `level-info.gc` referenced `MY2.DGO` (override honoured)
- `game.gp` wrote `(custom-level-cgo "MYL.DGO" "my-level2/myl.gd")` —
  collided with `my-level`'s same line
- `.gd` file went to disk as `my-level2/myl.gd`

First user run → black screen (engine looking for `MY2.DGO` per
`level-info.gc`, file on disk was `MYL.DGO`). Second run → compile aborted
with "multiple ways to make output `MYL.DGO`" (two `myl.gd` files).

Fix: new `_effective_nick(scene, name)` helper in `export/writers.py` that
prefers `_get_level_prop(scene, "og_vis_nick_override", "")` and falls
back to `_nick(name)`. Threaded an optional `scene` kwarg through
`write_gd`, `patch_game_gp`, and `write_jsonc`. Updated all 8 call sites
in `build.py` to pass `scene=scene`.

`write_gd` also sweeps stale `.gd` siblings from the level dir before
writing — defensive against the failure mode above leaving leftover files
that break the next build.

Self-heals broken installs: the strip regex in `patch_game_gp` keys on
the level name, not the nick, so the wrong `custom-level-cgo` line gets
cleaned up on the next export with no manual intervention.

### Still using `_nick(name)` (left as-is)
- `export/levels.py:120` — `discover_custom_levels` scans disk to report
  what levels exist + flag collisions. No Blender access from this path,
  can't read the override. May misreport collisions for override-using
  levels. Low-impact — runs from the level audit operator, not the build
  pipeline. Leaving for a separate follow-up.
- `export/levels.py:201` — dead local in `remove_level`. The regex
  beside it only uses `name`, the `nick` line is unused. Could remove,
  not worth a commit on its own.

### User verification (2026-05-12)
Tested in Blender with two levels (`my-level` nick `myl`, `my-level2`
nick `my2`):
- ✓ Compiler log built both `myl.gd` and `my2.gd` side-by-side, no
  collision error.
- ✓ Game log `my-level2`: `Got DGO file header for MY2.DGO with 7 objects`
  — loaded successfully (no FAKEISO failure).
- ✓ Game log `my-level`: `Got DGO file header for MYL.DGO with 18 objects`
  — existing level still loads correctly (no regression).

Merged to main.
