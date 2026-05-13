# Import Panel — Session Notes

**Branch:** `feature/import-panel`
**Repo:** `Jak-1-Level-Builder-Tool`
**Status:** Implemented, awaiting user test
**Last updated:** 2026-05-12

---

## Goal
Add an Import panel to the OpenGOAL sidebar that lets the user bring
vanilla level GLBs into the scene as reference geometry, so when
building a custom level they can see existing-world layout and place
their stuff relative to it.

## Empirical findings (from user-driven test before coding)
- GLBs at `<decompiler_out>/jak1/glb_out/<name>.glb` import via the
  native Blender GLTF importer with **no scaling, no offset**. Units
  and origins line up.
- Multi-level imports sit next to each other correctly in world space.
  No per-level placement table needed.
- Each GLB produces ~5 parent objects with everything parented to them.

## Design (agreed before coding)
- One parent panel `OG_PT_Import` (DEFAULT_CLOSED) with two subpanels:
  - `OG_PT_ImportSearch` — generic name search, live filter, capped row count
  - `OG_PT_ImportLevels` — alphabetical list of every GLB in glb_out/
- Imports land in `Imports/<basename>/` at scene root (NOT inside a
  level collection). The export pipeline only walks
  `<active_level>/Geometry/`, so this is implicitly safe — no
  `og_no_export` flag needed.
- Re-importing the same GLB creates additional copies in the same
  sub-collection (per user's preference, no dedup logic).
- Live filter via `og_props.glb_search_filter: StringProperty` —
  Blender redraws automatically when the user types.
- GLB list cache lives at module-level in `operators/imports.py`,
  populated on first access and on Rescan button.

## Files added
- `panels/imports.py` (146 lines) — three Panel classes + CLASSES tuple
- `operators/imports.py` (155 lines) — `OG_OT_RescanGlbs`,
  `OG_OT_ImportGlb`, the cache, scan helpers

## Files modified (additive only — no existing logic touched)
- `properties.py` — added `glb_search_filter` to OGProperties
- `panels/__init__.py` — wired the new module into ALL_CLASSES + re-exports
- `operators/__init__.py` — same

## Automated checks (pre-test)
- Full addon AST parse: green (0 errors across all .py files)
- Cross-module import resolution for the two new files: all names
  imported from siblings/parents are defined there
- bl_idname collision check: 176 unique idnames total, 5 new ones added,
  no clashes
- Panel package CLASSES imports: 9 (was 8); operators 7 (was 6)

## User verification — to do
1. Install zip, addon enables without traceback. The Import panel
   appears in the OpenGOAL sidebar category, DEFAULT_CLOSED.
2. Open it. The Rescan button is in the parent panel header. Click it
   once — should report "Found N GLBs in glb_out/" with N matching
   `ls <decompiler_path>/glb_out/*.glb | wc -l`. If N is 0, the
   decompiler hasn't been run with `rip_levels: true`, not an addon
   bug.
3. Open the Search subpanel. Type "vil" — the list narrows to
   GLBs whose basename contains "vil" (case-insensitive). Empty query
   shows everything (capped at 25).
4. Click one — should import; a new `Imports/<name>/` collection
   appears in the Outliner with the imported meshes inside. Geometry
   appears at correct world coords.
5. Click the same import a second time → produces more copies in the
   same sub-collection.
6. Switch to the Levels subpanel — same content as unfiltered Search.
   Click an import to verify.
7. Export a custom level (any one) — the build runs without trying to
   include anything from `Imports/` (export only walks the active
   level's Geometry sub-collection, so this should "just work").

## Known small-risk areas
- The `Imports` root collection is created if missing on first import.
  If the user already has a different collection literally named
  `Imports` for unrelated reasons, we re-use it (and place GLB
  sub-collections inside). Acceptable; if they want isolation, they
  can rename theirs first.
- `model_preview._import_glb` requires a VIEW_3D area. If the user
  has no 3D viewport open (very unusual), the import will hit the
  fallback path which may error. Same constraint as the existing
  actor-preview feature.
- Filter result cap is 25 rows. If `glb_out/` ever grows past that,
  the user will need to type a refining substring to see the rest.
  Cap chosen because Blender side panel rows above ~30 become hard
  to scroll.

## Possible follow-ups (not in this PR)
- Broaden the scan beyond `glb_out/` — `decompiler_out/jak1/<level>/`
  also holds per-actor GLBs (`<actor>-lod0.glb`) which would be useful
  for prop reference. Would slot in as another subpanel.
- Add a "delete imports" button that wipes the `Imports/` collection.
- Hide-on-import toggle (auto-hide newly imported meshes in the
  viewport to keep the scene snappy).

---

## Update — first-time setup flow

After the first preview build the user pointed out: on a fresh install
the addon's paths aren't configured yet, so the panel just shows "no
GLBs found" with no way to fix it without leaving for Preferences.

Added a wizard-style setup flow that lives inside the Import panel.
Two stages, automatic transition:

- **Stage A — first open.** Empty cache + `_FIND_ATTEMPTED == False`.
  Single big button: **📂 Find Models**. Clicking opens a DIR picker
  for the OpenGOAL install root. On confirm the operator:
  1. Writes the path into `og_root_path`
  2. Runs the existing `og.scan_paths` to derive exe/data folders
  3. Refreshes the GLB cache
  4. Sets `_FIND_ATTEMPTED = True`
  5. Forces a viewport redraw

- **Stage B — auto-detect tried but cache still empty.** Manual fallback:
  inline DIR pickers for `og_root_path` and `decompiler_path` (override),
  plus a Re-pick install button and a Rescan button. Shows only after a
  failed first attempt — keeps the initial UI clean.

- **Success.** Once any path produces a non-empty cache, the setup box
  vanishes and the normal Rescan-button-only header appears. Subpanels
  hide via `poll() → bool(get_glb_cache())` during setup so they don't
  spam "no GLBs found" messages.

State: `_FIND_ATTEMPTED` is a module-level flag, resets on Blender
restart. Once GLBs are found the flag is irrelevant — `cache` is the
authoritative gate.

New operator: `OG_OT_FindModels` (`og.find_models`, INTERNAL).
