# Curve Spline Paths (path-k) — Tracking

**Branch:** `feature/curve-spline-paths`
**Repo:** `Jak-1-Level-Builder-Tool`
**Status:** Implemented, not yet merged to main
**Last updated:** 2026-05-30

Add a "smooth" path option so curve-control platforms glide along a cubic
B-spline instead of stepping linearly between waypoints. Driven by emitting a
`path-k` knot lump alongside the existing `path` lump.

---

## Problem

The exporter emitted only the `path` lump (one `vector4m` per curve control
point). In jak1, `plat`, `plat-eco`, and `plat-button` construct a
`curve-control`, which reads BOTH `path` (control vertices) and `path-k`
(knots). With `path-k` absent, the constructor downgrades itself to a plain
linear `path-control` (`engine/geometry/path-h.gc`: *"downgrade us to a
path-control, we got cverts but no knots"*). So every "should be smooth"
platform silently moved in straight segments.

## Ground truth (from OpenGOAL `goal_src/jak1`)

- `path-control.eval-path-curve!` → `vector-lerp!` = piecewise linear.
- `curve-control.eval-path-curve!` → `curve-evaluate!` = cubic B-spline.
- `curve-control` instantiators: `engine/common-obs/plat.gc`, `plat-eco.gc`,
  `plat-button.gc` (and several curve-control enemies).
- `res.gc:get-curve-data!` loads `path` into `cverts` and `path-k` into `knots`.

## Knot format — VERIFIED (this is the bit the old notes got wrong)

Clamped uniform cubic (degree-3) B-spline, **num_knots = N + 4**:

    [0,0,0,0, 1,2,...,N-4, (N-3),(N-3),(N-3),(N-3)]

`knowledge-base/research/opengoal/lump-system.md` previously documented **N+8**
(4 zeros + `0..N-1` + 4×`N-1`). That is WRONG for jak1 — it pushes the
control-vertex index past the end of the array inside `curve-evaluate!`.

Verified by porting `curve-evaluate!` and `calculate-basis-functions-vector!`
to Python and checking, for N = 4..9: (a) all knot/cvert accesses in bounds,
(b) basis weights sum to 1, (c) the curve interpolates the first and last
control point. N+4 is the only candidate that passes; N+8 is out of bounds.

No real `path-k` example exists to diff against — the original game's curve
data is binary in the level files (not in goal_src), the tool's game database
is schema-only, and no public custom level has authored `path-k` yet (GitHub
code search returned zero `.jsonc` hits). Hence the by-simulation verification.

## Interior points (answers the open design question)

A B-spline does NOT pass through its interior control points — it touches only
the first and last waypoint and cuts the corners of everything between. So
"smooth" = organic gliding motion, NOT "smoothly hits each waypoint." If we
ever need smooth AND on-the-waypoints, that requires an interpolating spline
(pre-subdivide the control net); the engine doesn't do it natively. Out of
scope here.

## Changes

- `__init__.py` — new `og_path_mode` EnumProperty (`LINEAR` default / `SMOOTH`)
  on the actor object; added to the unregister cleanup tuple.
- `export/actors.py` — `_make_path_knots(n)` helper (clamped cubic, N+4);
  emits `lump["path-k"] = ["float"] + knots` when `og_path_mode == SMOOTH`
  and a `path` lump exists with >= 4 control points. < 4 → warn, fall back to
  linear (no path-k). Emitting path-k for a plain path-control actor is
  harmless — only curve-control reads it.
- `panels/actor.py` — "Path Mode" dropdown in the Waypoints panel, below the
  ping-pong toggle, with a hint explaining corner-cutting and the >=4 minimum.
- `knowledge-base/research/opengoal/lump-system.md` — corrected the path-k
  section (N+8 → N+4) with the verification note; flipped the quick-ref entry
  to implemented.

## Defaults / scope decisions

- Default is LINEAR — existing levels are unchanged unless the user opts in.
- The mode drives the PRIMARY path only. `swamp-bat`'s second `pathb` stays
  linear for now (it is also a curve-control; could be extended later).
- Ping-pong + smooth: the knot count is derived from the final (post-pingpong)
  control-point count, so they compose correctly.

## Follow-ups / open

- Optional `pathb` smooth support for swamp-bat.
- Optional "smooth through waypoints" mode via pre-subdivision (interpolating
  spline) if users expect the platform to hit each point.
- In-Blender preview of the resulting B-spline would help users see the
  corner-cutting before exporting.
