# Load Boundary Visualization — Session Notes

**Branch:** `feature/load-boundary-viz` (off `main`)
**Repo:** `Jak-1-Level-Builder-Tool` (the addon repo)
**Status:** Visual confirmed working in Blender (forward direction matched engine in user test). Defaults 400/−400; boundaries spawn in SOLID display. In-game untested.
**Last updated:** 2026-05-30

> Note: `Claude-Relay` is a stale snapshot of the addon (no load-boundary code,
> pre-split structure). All work is done here, in the addon repo.

---

## Goal
Visualize `LOADBND_` load boundaries in the viewport as 3D walls / filled areas
via a Geometry Nodes modifier, and add per-boundary Top/Bottom height settings
that both drive the visualization and export to `:top`/`:bot`.

## Decisions (from design discussion)
- **Naming:** mesh attributes `top`, `bot`, `closed` (engine-faithful — these
  are the literal `static-load-boundary` keys/flags), plus cosmetic `flip`,
  `wireframe`. UI props: `og_lb_top`, `og_lb_bot`, `og_lb_flip`,
  `og_lb_wireframe`. Open/closed reuses the existing `og_lb_closed`.
- **Export (option A):** settings drive export. `collect_load_boundaries` now
  reads `og_lb_top`/`og_lb_bot` instead of deriving from mesh Z-extent.
- **Units:** Blender metres, ×4096 → game units (addon convention). top/bot are
  measured **relative to the footprint height** (`base_z` = mean world Z of the
  boundary verts), so export matches the viz, which offsets in the object's
  local frame. Defaults 400 / −400 (tall wall).
- **Storage:** object-level, implemented as **uniform** POINT attributes (Blender
  has no scalar/object attribute domain a Named Attribute can read). Written on
  spawn, on any setting change (update callback), and refreshed on Edit-Mode
  exit when the vert count changes.
- **flip / wireframe:** cosmetic, viewport only — never exported.
- **Modifier lifecycle:** auto-added on spawn; stripped during geometry export
  and restored after (try/finally inside `export_glb`, main thread).

## Node group (`OG_LoadBoundaryViz`)
Reproduces the user's provided graph, with these changes:
- Removed the two `Store Named Attribute` (upScale/downScale) nodes; the addon
  writes those attributes now.
- Removed all non-geometry group inputs (Up, Down, Flip Direction, Open vs
  Closed, wireframe). Interface is **Geometry in / Geometry out** only.
- Each control read via **Named Attribute → Sample Index (index 0 on the input
  mesh)** → single uniform value. This sidesteps (a) attribute survival through
  Mesh→Curve→Mesh and (b) Switch conditions needing a single value, not a field.
- `curve_to_mesh → extrude_mesh.Mesh` reconnected directly.
- Kept the `myNorm` FACE store and the per-element arrow-cone pass as-is.

## Files touched
- `boundary_viz.py` (new) — node group builder, attribute writer, modifier
  add/remove, export strip/restore, edit-mode refresh handler.
- `__init__.py` — 4 new props + update callbacks; `og_lb_closed` gets the
  callback too; handler register/unregister; cleanup list.
- `operators/spawn.py` — `add_modifier(o)` on boundary spawn.
- `export/scene.py` — `collect_load_boundaries` reads settings (option A).
- `export/writers.py` — `export_glb` splits into wrapper (strip/restore) + impl.
- `panels/selected.py` — Top/Bottom sliders + Flip/Wireframe toggles.
- `audit.py` — `check_load_boundaries`: ERROR if top ≤ bot.

## To validate in Blender (next session)
1. Spawn a Load Boundary → modifier appears, wall renders between top/bot.
2. Change Top/Bottom → wall updates live; export `:top`/`:bot` match.
3. Toggle Closed → open wall vs filled area. Flip/Wireframe behave cosmetically.
4. Add verts in Edit Mode → uniform attrs backfill on exit.
5. Export → boundaries still export correctly; modifier present afterwards.
6. Confirm Sample-Index reads resolve (the main untested assumption).

## Follow-ups / open
- **Pre-existing boundaries** (made before this feature) have no modifier. A
  small "Attach/Refresh Viz on selected boundaries" operator would cover them —
  not built yet (scope was auto-add-on-spawn). Add if wanted.
- Non-flat polylines: `base_z` uses the mean vert Z — fine for typical flat
  boundaries; revisit if anyone authors sloped boundaries.
