# Code audit (branch claude/audit) — plan, waiting for Kuitar

Three read-only passes over addons/opengoal_tools (~38k lines): old-version code, per-frame work,
duplicated code. Findings below are from those passes (file:line at commit c87b37d); each is checked
again when it's worked on.

## 1. Old-version (addon) code to remove
Data loss on old .blend files marked [loses].
- __init__ _migrate_legacy_props (og_sync_wrap, og_cell_skip_jump, og_scale_* -> object scale) on every
  load [loses], + the 2 dead operators that still write the old names (operators/actors.py
  toggle_cell_skip_jump / toggle_platform_wrap) and 5 more unused pre-panel operators.
- db.py: refactoring/ DB fallback path; code_files() dict / extra_code formats; _record_panels() rebuild
  from old DB keys (resolved panels identical without it); legacy_keys() + DB "legacy_key" [loses old
  fact-option values]; trait_fields() + empty "TraitFields"; unused *_types() sets; migration-window
  headers (db.py, DB file); refactoring/build_database.py + its stale DB copy.
- data.py: unused *_TPAGES constants, PROP_ENUM_ITEMS / _prop_enum_cb aliases; utils._PROP_CATS alias;
  operators/ and panels/ __init__ `import *` re-exports.
- export/volumes._vol_links: old single og_vol_link -> list, run on every call (also in panel draws)
  [loses very old volume links].
- Old `_wp_NN` waypoint fallback (path_modes.gather_sources name search, unused
  _collect_waypoint_points, links.py auto-add + Migrate operator, actor panel legacy header / button,
  required.py check) [loses: actors whose _wp_ empties were never listed export no path].
- collections: _ensure_level_index / _migrate_all_level_indices (levels before og_level_index) [loses:
  index 100]; "v1.1.0" no-level-collection fallback (check the fresh-scene case first).
- project_settings: the None cleanup entry (my progress-pc mistake) + first-version tag regex.
- docs/backward-compat.md: brought up to date (or emptied).
Keep: OpenGOAL / Blender version support (versions.py, legacy cameras < v0.3.4, Blender 5 cases,
old decompiler glb_out layout), schema_emit min / max clamp (safety), AllSFX (still drives the SFX list).

## 2. Per-frame / per-redraw work
High:
- H1 db.actor_panels() and everything on it (has_panel, panel_fields, inherited_fields, link_slots,
  prop_getter ...) re-resolve the DB every call (linear finds, parent chain, deep copies); ~22 panel
  polls per sidebar redraw. Fix: dict indexes at load + caches cleared on db.reload().
- H2 actor panel headers (4) run missing() / soft() each redraw, incl. 2 nav-mesh computes + scans of
  all objects. Fix: read level_missing's per-actor results; cache nav analysis per mesh (geometry gen).
- H3 required.level_missing(): whole level every second while Build & Play redraws (_MAX_AGE 1 s) and
  on any non-transform update; O(N^2) linked-by scan. Fix: dirty set from depsgraph updates + reverse
  link index; explicit mark_dirty from link operators.
- H4 Build & Play (always open): checkpoint enum walks all objects (spawn_uid per checkpoint), stray
  mesh scan, disk exists() for gk / goalc / game.gp, uncached version probe. Fix: structure-generation
  cache, disk checks cached / invalidated by the path prefs.
- H5 preview depsgraph handler: 2 full object loops per update (every drag frame) + race_rings /
  distribute full scans on any object update. Fix: selected_objects, skip on transform-only updates,
  registries + reverse maps.
Medium: navmesh panels (4 triangulations, 2 nav computes per redraw); path / waypoint / checkpoint /
volume-link panels scanning all objects (one shared index); water handler scanning bpy.data.objects on
every mesh update; versions probes reading game-info.gc per redraw; palette fix sliders rewriting every
mesh per tick (debounce); GOAL Code panel globbing + stat per redraw.
Low: level-rename warning globbing; _prop_row timers piling up; spawn list favourites lookups;
Import panel rglob in draw(); several dynamic enum callbacks returning unreferenced lists (garbled
labels: correctness).

## 3. Duplicated code -> one function (about 650-750 lines)
1. etype from name (~85 copies, 4 helpers; 19 identical panel polls) -> collections.actor_etype(o|name)
   + active_actor_etype(ctx).
2. object kind tests (ACTOR / waypoint / VOL / CHECKPOINT / CAMERA, ~65 copies; audit.py has private
   versions) -> is_actor / is_waypoint / is_volume / is_checkpoint / is_camera + level_actors(...).
3. preferences (22 sites bypass paths_core.prefs; preview_models check x9) -> pref(), previews_on(),
   try_attach_preview().
4. file rewrite keeping CRLF / write-if-changed (~20, tasks_export._rewrite already does it) ->
   export/fileio.py; shared level-info / load-boundary / game.gp regexes.
5. Blender <-> game coords / quats / x4096 (~35; remap matrix defined 4x) -> coords.py.
6. level name read / clean (~30, 3 helpers) -> level_name(col), clean_level_name(s).
7. level create / assign / edit validation + defaults (3 copies) -> _validate_level, _init_level_col.
8. select-only / frame-selected (~15) -> utils.select_only, frame_selected.
9. redraw loops / show text in editor -> utils.redraw, show_text.
10. corner -> vertex index (8), sRGB <-> linear (3 copies) -> bake.loop_verts, one pair in palette.
11. unique object name (9) -> free_object_name(width=).
12. new helper empty + link to sub-collection (11) -> collections.new_empty.
13. link-target classification (3 copies) -> one.
Smaller: path wrappers in build / versions, print() vs log(), level enum items in tasks.py, unused
import blocks (~200 lines).

## Proposed order (one commit per step, tests after each)
1. DB caches (H1): one place, speeds everything, easy to test (resolved panels identical before/after).
2. Old-version code (part 1).
3. Duplicates 1-2 (etype / object kinds), then H2 / H3 / H5 on top of them, then H4 + medium items.
4. Remaining duplicates 3-13, small items, import cleanup.
