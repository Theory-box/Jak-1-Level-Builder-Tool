# Load Boundaries + Checkpoint Settings — Design Notes

**Branch:** `feature/load-boundaries-checkpoints`
**Repo:** `Jak-1-Level-Builder-Tool` (the addon repo — NOT `Claude-Relay`;
the addon copy in Claude-Relay is a stale snapshot, do not patch it)
**Status:** Planning / research complete — no code written yet
**Last updated:** 2026-05-28

Goal: expose per-checkpoint level/display settings, and add a placeable
Load Boundary object, so custom levels can stream multiple levels the way
the base game and shipped mods (Kuitar's *the-forgotten-lands*) do.

---

## 1. Verified engine mechanics (jak-project + TFL reference)

### What actually loads a level
Loading is driven **only** by the `*load-state*` two-slot `want` buffer.
The three things that write to it:
1. `target-continue` (spawn / death-respawn) — copies the active
   continue-point's `lev0`/`lev1`/`disp0`/`disp1` into the buffer and
   blocks until both report `'active`. (`target-death.gc`)
2. Load boundaries — on crossing, fire their `cmd-fwd`/`cmd-bwd`.
3. Explicit scripted `want-levels` / `want-display-level` calls (buttons,
   doors, elevators, cutscenes).

### bsphere is NOT a load trigger (correction)
Earlier assumption was wrong. The `level-load-info` `:bsphere` feeds
`inside-sphere?`, the camera `level-distance`, and `level-get-target-inside`
(which level you count as being "in" → mood / vis / draw priority). It does
**not** cause a level to load. A single custom level loads because its
continue-point wants it, and stays loaded because nothing requests it out.
Action item: fix the misleading "considers the level nearby" comment in
`export/writers.py` (bsphere should bound the geometry, not be inflated to
"trigger loading").

### continue-point fields (the checkpoint)
`name level trans quat camera-trans camera-rot load-commands vis-nick
lev0 disp0 lev1 disp1` (+ `flags`).
- `lev0`/`lev1`: up to two resident levels (engine buffer is exactly 2).
- `disp0`/`disp1`: `display` / `special` / off (`#f`).
- `vis-nick`: see correction below.
- `level`: the checkpoint's home level (music/settings lookup) — separate
  from the resident set.

### vis-nick (Kuitar correction)
Do **not** default `vis-nick` to `'none`. `vis` is also how the game knows
which level you're "in" for music and which menu opens, etc. Default it to
the **short nickname of the home level** (same value the addon already
computes for `level-load-info :nickname`), and keep it editable.
Open question to validate in a build: custom levels lack real vis BSP data,
so confirm a real nick on a custom level behaves (Kuitar ships it this way,
so it should be fine).

---

## 2. How load boundaries are really authored

Not runtime entities (earlier idea was wrong). They are **static data** in a
single shared file:
- `goal_src/jak1/engine/level/load-boundary-data.gc`
- Built through a `static-load-boundary` macro, wrapped in
  `*static-load-boundary-list*` via `static-lb-list`.
- The file resets `*load-boundary-list*` then defines the static list; it is
  **regeneratable by an in-game boundary editor** (`---lb-save`).
- Shipped mods edit this same file. TFL added valley/mines boundaries here.

### `static-load-boundary` keys
- `:flags` — list of `load-boundary-flags` symbols: `closed`, `player`
  (player-cross vs camera-cross), plus any **custom flags** the build adds.
- `:top` / `:bot` — float heights (game units, 4096/m).
- `:points` — flat list of horizontal vertex coords (2 floats per vertex).
- `:fwd` / `:bwd` — crossing command, one of:
  - `(load lev0 lev1)`
  - `(display lev0 <mode>)`   modes: `display`, `display-no-wait`, off
  - `(vis <nick> #f)`
  - `(force-vis lev0 <onoff>)`
  - `(checkpt "<continue-name>" #f)`
  - `invalid` / `(invalid #f #f)` = no command

### Geometry semantics depend on the `closed` flag (Kuitar correction)
- **Open** (no `closed`): `:points` are a polyline in the horizontal plane;
  the line is **extruded vertically between `:top` and `:bot`** to form a
  wall the player/camera crosses. 2 points = a single wall segment.
- **Closed** (`closed` set): `:points` form a **flat horizontal polygon**;
  only **one** height value is used to place that polygon (believed to be
  `:top` — confirm in `check-closed-boundary`). Used for "am I inside this
  area" region tests, not a crossing wall.

So the addon must interpret a placed Load Boundary object differently by
flag: open → take the object's edge/polyline footprint + vertical extent;
closed → take the object's flat polygon footprint + a single height.
Reuse the addon's existing Blender(Z-up) → GOAL(Y-up) + meters conversion
that spawns already use; horizontal footprint = GOAL X/Z, height = GOAL Y.

---

## 3. Multi-level streaming model (validates "design for multi")

A custom level streams in by being referenced from sibling levels, not by
its own bsphere. In TFL, `valley`:
- appears as `:lev1` on base-game continue-points,
- is loaded/displayed by `(load …)` / `(display …)` boundary commands in
  `load-boundary-data.gc`,
- is toggled at runtime by scripted `want-display-level 'valley …` calls.

So: streaming = continue `lev0`/`lev1` + boundary `load`/`display` commands,
both referencing sibling levels. Level pickers must enumerate all project
levels (`_all_level_collections(scene)`), which the addon already supports.

---

## 4. Addon current state

- `export/writers.py::_make_continues` already emits a continue-point per
  spawn/checkpoint empty, but hardcodes `vis-nick 'none`, `lev0 = self`,
  `disp0 'display`, `lev1 #f`, `disp1 #f`, `load-commands '()`, no flags.
- No load-boundary system at all. Loading currently relies on the
  continue-point (and the inflated bsphere comment).
- `checkpoint-trigger` / `camera-trigger` process types are generated in
  `write_gc` (pattern reference, though boundaries will be static data, not
  a process).

---

## 5. Design — checkpoint settings (low risk)

Extend the checkpoint/spawn empty; `_make_continues` reads these instead of
hardcoding. Defaults preserve a working single-level checkpoint.

| Property        | Type            | Default            | Notes |
|-----------------|-----------------|--------------------|-------|
| `lev0`          | level enum      | self               | maps self→level name |
| `disp0`         | enum            | `display`          | display / special / off |
| `lev1`          | level enum+none | none (`#f`)        | second resident slot |
| `disp1`         | enum            | off                | display / special / off |
| `vis-nick`      | string          | **home level nick**| editable; not `none` |
| `save-point`    | bool            | off                | sets continue-flags |
| `flags`         | multi-toggle    | none               | sage-intro / title / … |
| `load-commands` | text (GOAL)     | `()`               | spliced verbatim |

Export: `collect_spawns` gathers the props; `_make_continues` emits them;
validate `lev0`/`lev1` against known levels with a clear export warning on a
dangling reference.

---

## 6. Design — load boundary (new "Load Boundary" in Level Flow)

A placeable plane/mesh, like trigger volumes. Export emits
`static-load-boundary` entries into `load-boundary-data.gc` via a managed
marker block (same technique as the level-info "CUSTOM LEVELS" block) — NOT
runtime entities.

Per-boundary properties:
- `closed` (bool) — switches geometry interpretation (wall vs flat region).
- `player_cross` (bool, default on) — player vs camera activation.
- `top` / `bot` (float, meters) — vertical extents; for `closed`, only the
  height value is used.
- Forward command: enum `none/load/display/vis/force-vis/checkpt`
  + `fwd_lev0`, `fwd_lev1`, `fwd_disp_mode`, `fwd_continue_name`.
- Backward command: same set, independent.
- **`custom_flags` (advanced, free text/multi-select)** — extra
  `load-boundary-flags` symbols spliced into `:flags`. Easy to support
  (the macro just splices a symbol list); the only requirement is that those
  symbols exist in the build's `load-boundary-flags` enum (Kuitar's TFL adds
  its own). Surfaced as an advanced field so TFL-style custom flags work.

Geometry extraction:
- open: object's edge/polyline footprint → `:points`; vertical extent → top/bot.
- closed: object's flat polygon footprint → `:points`; one height → top.

---

## 7. Open items to verify in-build (before/early in implementation)

1. **Macro/enum parity.** TFL carries a "TFL note: added custom flags"
   comment, so `load-boundary-flags` (and possibly the macro) differ from
   vanilla jak-project. Target whatever base the addon's builds use; confirm
   `load-boundary-data.gc` exists there and `static-load-boundary` matches.
2. **closed height field** — confirm `:top` (vs `:bot`) is the one used for
   closed polygons (`check-closed-boundary`).
3. **vis-nick on custom levels** — confirm a real nick (not `none`) behaves
   given custom levels have no vis BSP data.
4. **Where to patch** — single global `load-boundary-data.gc` with a managed
   block keyed per level, so re-export of one level doesn't clobber others.

---

## 8. Implementation order

1. **Checkpoint settings** end-to-end (props → `collect_spawns` →
   `_make_continues`, incl. vis-nick default = nick, flags, load-commands).
   Low risk, immediately testable, exercises the multi-level picker.
2. **Load Boundary** object: placed-plane → `:points` extraction (both open
   and closed), export into `load-boundary-data.gc` managed block, command
   UI (fwd/bwd) + flags incl. custom-flags passthrough. Prototype one open
   `load`/`display` boundary between two test levels before full UI.
