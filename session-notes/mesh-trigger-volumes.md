# Mesh Trigger Volumes (convex `vector-vol`)

**Branch:** `feature/mesh-trigger-volumes`
**Status:** Implemented, NOT yet build-tested in-engine (no goalc/Blender in dev env).
**Scope:** Replace axis-aligned AABB with arbitrary **convex** mesh volumes for all
trigger volumes EXCEPT water (water left on its existing path for now).

## What changed
Every trigger that used `bound-xmin..bound-zmax` (axis-aligned box) now emits a
`vol` (`vector-vol`) plane set built from the linked `VOL_` mesh's faces, and the
generated GOAL tests the point against those planes instead of the box.

Trigger types converted (all tool-generated GOAL in `<level>-obs.gc`):
- `camera-trigger`  (scene.py `collect_cameras`)
- `vol-trigger`     (scene.py `collect_custom_triggers`)
- `aggro-trigger`   (scene.py `collect_aggro_triggers`)
- `checkpoint-trigger` (actors.py) — keeps its **sphere fallback** when no `VOL_`
  mesh is linked; volume mode now uses planes.

Load boundaries are a separate level-streaming system and were NOT touched.

## Format / ground truth
- `vector-vol` element = `[nx, ny, nz, d]`. Build (`Entity.cpp vector_vol_from_json`)
  stores normal RAW and multiplies `d` by `METER_LENGTH` (4096). So export emits
  `d` in METERS; positions at runtime are internal units → dot/compare consistent.
- Convention (matches engine `point-in-vol?` and existing water code): OUTWARD unit
  normals; point is INSIDE iff `dot(N,P) - w <= 0` for EVERY plane.
- Plane extraction mirrors the user's `mesh-to-VOL` script: per face,
  `n = world3x3 @ face.normal` (normalized), `d = face_center . n`, axes mapped
  Blender→game `(x, z, -y)`. `d` is rotation-invariant so it's computed pre-map.

## Key code
- `export/volumes.py :: _vol_planes(vol_obj)` → `(planes, cull_radius)`.
  Merges coincident planes (triangulated quad → 1 plane; tri-box → 6). Skips
  degenerate faces. `cull_radius` = bounding-sphere from AABB centre + 1 m.
- `export/scene.py` / `export/actors.py`: emit `"vol": ["vector-vol"] + planes`
  and `"cull-radius": ["meters", cull_r]` in place of the 6 `bound-*` lumps.
  Guard: empty plane list → WARNING + skip (aggro/vol/camera) or sphere fallback
  (checkpoint).
- `export/writers.py`: shared `(defun point-in-planes? ((planes (inline-array vector))
  (num-planes int) (pt vector)) ...)` emitted once when any trigger present. Each
  trigger deftype drops the box floats, adds `(num-planes int32)` +
  `(planes (inline-array vector))`; init reads them via
  `(res-lump-data arg0 'vol (inline-array vector) :tag-ptr (& tag))` with
  `num-planes = (-> tag elt-count)`; the per-frame test keeps the cheap
  `cull-radius` distance pre-check then calls `point-in-planes?`.

## Layout decision
Regenerated deftypes WITHOUT `:offset-assert`/`:size-assert` (kept no heap-base,
matching the existing `camera-marker` type in the same file, which also allocates
a `trsqv`). The compiler computes the layout — removes hand-offset risk.

## Verification done (no engine available)
- All edited Python files `ast.parse` clean.
- All 21 generated GOAL top-level forms paren-balanced (script-checked). Fixed one
  extra `)` on the vol-trigger exit `send-event` line during the pass.
- `res-lump-data ... (inline-array vector) :tag-ptr` confirmed against engine usage
  (collectables `movie-pos`, sync-info, water `vol`). Unit scaling traced end-to-end.

## NOT yet verified — needs an in-engine build
- Compiles under goalc; `point-in-planes?` in scope for the defstates (defined
  earlier in same file — expected OK).
- Runtime correctness of the plane test in a live level.
- **Recommend testing `aggro-trigger` first** (simplest enter/exit), then camera,
  vol-trigger, checkpoint.

## Caveats / limits to tell users
- CONVEX only. Concave volumes need splitting into multiple convex meshes (engine
  `vol-control` can union multiple `vol` tags, but the tool currently emits one).
- Face normals must point OUTWARD (Recalculate Outside). Inverted normals → an
  inside-out volume.
- Non-uniform object scale skews normals (apply scale first). Same limit as the
  original mesh-to-vol approach.
- Each face = one runtime plane test (throttled every 4 frames, cheap), but keep
  hulls low-poly.

## Old behaviour removed
`bound-*` lumps no longer emitted for these four trigger types; their GOAL no longer
reads them. Water and load boundaries unaffected.
