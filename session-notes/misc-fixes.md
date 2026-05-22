# Misc Fixes — Tracking

**Branch:** `feature/misc-fixes`
**Repo:** `Jak-1-Level-Builder-Tool`
**Status:** Open — research pass done 2026-05-22; no code changes yet
**Last updated:** 2026-05-22

A grab-bag tracking branch for several user-reported issues and feature ideas.
Each item has the original description plus research notes from poking around
the code.

---

## 1. Warn on conflicting level ID / level index

**Type:** Polish / safety
**Status:** Open, wires into item 2

When a user changes `og_base_id` or `og_level_index` for a level, mismatches
against earlier-built state can silently break entity-actor AID linking — most
visibly, the `custom-nav-mesh-check-and-setup` case arms patched into
`engine/entity/entity.gc` go stale and assigned navmeshes stop being applied.

Context: this is what bit the user during the lurkercrab waypoint debug
session on 2026-05-22 — base_id change + full recompile resolved it once the
patched entity.gc AIDs realigned with the exported JSONC AIDs.

### Research notes (2026-05-22)

The level-index half of this is already solved. `collections.py` from the
`fix/level-index-nickname` branch shipped:

- `_level_index_in_use(scene, idx, exclude=...)`
- `_next_free_level_index(scene)`
- `_migrate_all_level_indices(scene)`
- `_vis_nick_in_use` / `_suggest_unique_vis_nick`
- Edit-level dialog rejects collisions; Settings subpanel shows red warnings

What's missing for **base_id**:

- No `_base_id_in_use` / `_next_free_base_id` helpers
- `OG_OT_CreateLevel`, `OG_OT_AssignCollectionAsLevel`, `OG_OT_EditLevel` don't
  validate base_id at all
- Settings subpanel doesn't show a base_id collision warning

The straightforward fix: copy/paste the index pattern, swap the prop name to
`og_base_id`. ~30 LOC + Settings subpanel row. Safe to do standalone — doesn't
depend on item 2. **Could land first as a small standalone PR.**

The harder half is the AID-mismatch detection (entity.gc's case arms going
stale). Two ways to catch it:

- **Export-time check.** After `patch_entity_gc` runs, parse the generated
  case arms back, compare against the JSONC's `base_id` + actor count.
  Mismatch → log a loud warning. This is bulletproof but lives at export, so
  the user only sees it after a build.
- **Settings-change-time check.** When base_id changes via the Settings
  subpanel setter, mark entity.gc as dirty and require a clean rebuild
  before next launch. Means tracking the `base_id` that was used for the
  last patch — could store in a sidecar file or as a level collection prop
  like `og_last_built_base_id`.

Recommendation: do both. Export-time warning is cheap insurance; settings-time
flag is the better UX (catches the problem before it happens).

---

## 2. Level Manager rework — view all custom levels + their files

**Type:** Feature / UX
**Status:** Open

Current level manager only lists levels in the currently-open .blend; doesn't
surface what's on disk, what's healthy, what's stale.

### Research notes (2026-05-22)

Half the work is already done — `export/levels.py:89` defines
`discover_custom_levels()` which scans the filesystem and returns one dict per
on-disk level:

```python
{
  "name":      <folder name>,
  "nick":      <3-char>,
  "dgo":       "MYL.DGO",
  "has_glb":   bool,    # .glb on disk
  "has_jsonc": bool,
  "has_gd":    bool,
  "has_obs":   bool,    # -obs.gc on disk
  "has_gp":    bool,    # entry in game.gp
  "conflict":  bool,    # DGO nick collides with another level
}
```

This already does nick-collision detection. It's just not wired to any UI —
the session note from the level-index-nickname-fix branch explicitly flagged
this: "defined and imported in 7 modules but called from zero".

**What's missing from the data**, for the rework:

- `base_id` — not currently surfaced. Easy to grab from each level's
  `.jsonc`'s top-level `"base_id"` field.
- `level_index` — not currently surfaced. Read from the level-info.gc
  block's `:index N`. The block is delimited by
  `(define <name> ...)` ... `(cons! *level-load-list* '<name>)` (see
  `patch_level_info` for the exact shape).
- `last_built` — timestamp of `.jsonc` mtime is a cheap proxy.

**Existing in-Blender level manager:** `OG_PT_LevelManagerSub` in
`panels/level.py:161`. Just lists in-file level collections with a "set
active" toggle. The rework can either replace it or live alongside as
"On-Disk Levels" vs "In-File Levels".

**Suggested shape:**

```
🗂  Level Manager
├─ In-File Levels (this .blend)
│   ◉ my-level         (active)
│   ○ my-level2
│   [Add Level] [Assign Existing]
└─ On-Disk Levels (scanned)
    my-level     ✓glb ✓jsonc ✓gd ✓obs ✓gp   id=100  base=100  [Open]
    old-test     ✓glb ✓jsonc ✗gd  ✗obs ✓gp   id=?    base=?    [Clean]
    my-level2    ✓glb ✓jsonc ✓gd  ✓obs ✗gp   id=101  base=200  [Open] ⚠ no game.gp entry
```

Per-row buttons:
- **Open** — `os.startfile` / `xdg-open` on the level directory
- **Clean** — calls `remove_level(name)` (already exists in levels.py:145)
- **Refresh** — re-runs `discover_custom_levels`

**Scope estimate:** 200-300 LOC, mostly UI. The data-gathering helpers
(parsing JSONC base_id, parsing level-info.gc index block) are small.

---

## 3. Level-ID verification (wired into item 2)

**Type:** Polish
**Status:** Open, depends on items 1 + 2

Once items 1 and 2 exist, this is one pass over the per-level dicts grouping
by `base_id` and by `level_index`, flagging duplicates.

### Research notes (2026-05-22)

Once item 2 surfaces `base_id` and `level_index` per on-disk level, the
verification logic is literally:

```python
def _check_level_id_collisions(levels):
    by_base = {}
    by_idx  = {}
    for L in levels:
        by_base.setdefault(L["base_id"], []).append(L["name"])
        by_idx .setdefault(L["index"],   []).append(L["name"])
    for bid, names in by_base.items():
        if len(names) > 1:
            yield ("base_id", bid, names)
    for idx, names in by_idx.items():
        if len(names) > 1:
            yield ("index",   idx, names)
```

Render as red warning rows under each colliding level in the manager panel.

Also: detect base_id-collides-with-vanilla — vanilla levels have base_id 0-99
(roughly). Anything in the manager < 100 → warning. The level-index fix doc
notes "Starting index = 100. Knowledge base docs advise 'must not collide
with vanilla' and use 99 as an example; 100+ is safe."

---

## 4. Pole platform broken

**Type:** Bug / docs
**Status:** Open — partially design-intent, partially real bug

User reports: `pole-plat` is invisible at runtime, Jak turns invisible when
interacting, game crashes shortly after.

### Research notes (2026-05-22)

Two findings:

**1. Invisibility is by design in vanilla.** The actual GOAL etype is
`swingpole` (not `pole-plat` — the addon's label is misleading). Vanilla
definition in `goal_src/jak1/engine/common-obs/generic-obs-h.gc:142`:

```lisp
(deftype swingpole (process)              ; ← extends process, NOT process-drawable
  ((root        trsq)
   (dir         vector :inline)
   (range       meters)
   (edge-length meters))
  (:states swingpole-active swingpole-stance))
```

No skeleton, no art group, no `initialize-skeleton` call in
`init-from-entity!`. Swingpoles are invisible LOGIC entities — vanilla levels
place a visible pole MESH in level geometry and put the swingpole entity at
the same spot. The swingpole defines the swing-physics anchor; the pole is
purely visual.

So the addon's "Pole Platform" UI label is misleading. The database entry
correctly has `art_group: null`, but the user-facing experience needs:

- Rename label "Pole Platform" → "Swing Pole" in `jak1_game_database.jsonc`
- Add a description in the spawn picker explaining "invisible logic entity —
  place a pole mesh in level geometry at the same spot for visuals"
- Consider adding a visualization helper: when an `ACTOR_swingpole_*` is
  selected, draw a debug cylinder (range × edge-length) in the viewport.
  These are hardcoded in vanilla as `range=3m`, `edge-length=2m`.

**2. The crash and "Jak turns invisible" are separate.** Vanilla's
`init-from-entity!` (`generic-obs.gc:102-116`) hardcodes range/edge-length
and doesn't read any lumps. Vanilla's `swingpole-stance` (`generic-obs.gc:82`)
sends `'pole-grab` to `*target*` when the player is in range; target's
pole-grab handler is what makes Jak transition to the swing animation.

The "Jak invisible" + "game crash" pattern is almost certainly target-side:
the pole-grab handler expects something about the swingpole's transform or
collide-shape that the addon isn't setting. Suspect:

- The hardcoded `range/edge-length` defaults work in vanilla because the pole
  is part of level geometry with collision; custom-spawned swingpoles may
  have no parent collide-shape to attach to.
- The `dir` field is computed from quat in init-from-entity. If the addon
  exports an identity quat, `dir` ends up degenerate (zero vector).

**Action plan:**
1. Quick win: rename + description + viewport cylinder
2. Diagnostic: spawn a swingpole, watch game console for what error fires
   when Jak hits the grab range. Need runtime to debug; likely needs the
   user to capture a stderr dump.
3. Hypothesis: facing-direction (quat) gets exported as identity for actors
   the user hasn't rotated — patch the export to detect this and warn, or
   default to a sane non-identity rotation on spawn.

---

## 5. Flip platform settings panel gone

**Type:** Maybe-bug, needs user confirmation
**Status:** Open

User reports `plat-flip`'s settings UI is gone; had to set lumps manually.

### Research notes (2026-05-22)

**Pipeline looks intact.** All three layers wire up correctly:

- **Database** (`jak1_game_database.jsonc`) — plat-flip has a `fields[]`
  schema with `og_flip_sync_pct`, `og_flip_delay_down`, `og_flip_delay_up`
  and correct `lump` mappings.
- **Panel** (`panels/actor_fields.py:242`) — plat-flip IS in
  `GENERIC_PANEL_ETYPES`, so the generic data-driven panel polls true.
- **Exporter** (`export/actors.py:250-254, 449-453`) — reads
  `og_flip_sync_pct`, `og_flip_delay_down`, `og_flip_delay_up` and writes
  `sync-percent` + `delay` lumps correctly.

Strongest hypothesis: the panel **is** there, but the user missed it. The
`OG_PT_ActorFields` panel has `bl_options = {"DEFAULT_CLOSED"}` and lives as
a sub-panel under the selected-object panel. If collapsed, it just shows the
"▶ Actor Settings" header and is easy to overlook.

**Next step:** ask the user to select a plat-flip actor and screenshot the
full N panel side panel — should see "Actor Settings" as a collapsed
sub-panel. If it's not even there in collapsed form, then poll is failing
and there's a real bug.

**Real broader concern though:** I audited all DB actors with `fields[]`
schemas and found 13 etypes with fields but NOT in `GENERIC_PANEL_ETYPES`.
Most have bespoke panels in `panels/actor.py` (crate, launcher, eco-door,
launcherdoor, sun-iris-door, water-vol, caveelevator), but these have NO
panel found by greps:

- `pontoon`
- `springbox`
- `oracle`

These three probably have silently-broken settings UIs — fields defined,
nobody draws them. Worth confirming and either adding to GENERIC_PANEL_ETYPES
or building bespoke panels.

---

## 6. Launch level at a specific checkpoint

**Type:** Feature
**Status:** Open

### Research notes (2026-05-22)

**This is basically already wired** — the launch flow at `build.py:642`
already sends a parameterised checkpoint spawn:

```python
goalc_send(
  f"(start 'play (or (get-continue-by-name *game-info* \"{name}-start\") "
  f"(get-or-create-continue! *game-info*)))"
)
```

It defaults to `"<name>-start"`. To launch at any checkpoint, change
`"{name}-start"` to whatever checkpoint name the user picked.

**Checkpoint naming convention** is defined in `export/actors.py:629,652`:

```python
level_name_for_cp = _get_level_prop(scene, "og_level_name", "")
cp_name = f"{level_name_for_cp}-{uid}"
```

where `uid` is the CHECKPOINT_<uid> empty's suffix. So a checkpoint named
`CHECKPOINT_arena` in level `my-level` becomes continue-point
`"my-level-arena"`.

**What needs building:**

1. Scene-level StringProperty `og_launch_checkpoint` (default = `"<name>-start"`)
2. Dropdown in the build/launch panel populated from `CHECKPOINT_` empties
   in the active level + an option for the default start
3. The launch flow reads this property instead of the hardcoded string

Scope: ~50 LOC. Self-contained — doesn't actually need item 7's REPL UI
since the launch path already uses `goalc_send` internally.

---

## 7. Send REPL commands from Blender

**Type:** Feature
**Status:** Open — plumbing already exists

### Research notes (2026-05-22)

**The hard part is already done.** `build.py` has:

- `goalc_send(cmd, timeout=10)` — sends arbitrary GOAL expression via the
  OpenGOAL nrepl wire format `[u32 length LE][u32 type=10 LE][utf-8 string]`
  and returns the response string. Reference impl mirrors
  `common/repl/nrepl/ReplClient.cpp` in jak-project.
- `goalc_ok()` — health-check (sends `(+ 1 1)`)
- `launch_goalc(wait_for_nrepl=...)` — spawns goalc and waits for nrepl
  ready
- `_find_free_nrepl_port()` — picks a free port; tracked in `GOALC_PORT`
- `_load_port_file()` — restores port from disk so a Blender restart can
  rejoin a still-running goalc

So no socket work needed. The `(lt)` step the user mentioned is already
automated: launch writes a `startup.gc` that runs `(lt)` first, then
runs anything after a `;; og:run-below-on-listen` sentinel after gk
connects.

**What needs building:**

1. New panel `OG_PT_ReplConsole` (or sub-panel under Tools), with:
   - StringProperty `og_repl_input` (text field)
   - "Send" button that calls `goalc_send` and stores the response in
     `og_repl_last_output`
   - Status indicator: green if `goalc_ok()`, red otherwise (cache the
     check; calling it every redraw is expensive)
   - Quick buttons: `(lt)`, `(mi)`, `(kill-current)`, `(bg '<active-level>-vis)`
2. Last response shown in-panel (truncated to ~5 lines) + full output goes
   to item 8 (text datablock)

Scope: ~150 LOC for the panel + operators. Trivial because all real work is
existing helpers.

---

## 8. View REPL output in Blender

**Type:** Feature
**Status:** Open, depends on item 7

### Research notes (2026-05-22)

`goalc_send` returns the response string already. The send-and-show loop is
request/response, not a continuous tail — that limits us to "show what we
just received" unless we open a second listener socket. Worth it? Probably
not for v1.

**Three plausible UX shapes, low → high effort:**

**A. Last-response panel field.** Just show the last `goalc_send` return
value inline. Single text area, refreshed on each send. ~10 LOC.

**B. Persistent scrollback via Blender Text datablock.** Append each
"command → response" pair to a text block named `OG-REPL`. User can open the
Text editor in Blender to scroll history. ~30 LOC, no threading needed.

**C. Live background tail.** Open a separate socket to nrepl's broadcast
output (if available — need to check the nrepl protocol — `common/repl/nrepl`
in jak-project), poll on a timer, append to the text block. Requires either
a modal operator or `bpy.app.timers.register`. Risky on Blender's threading
model, easy to crash if done wrong.

Recommendation: ship B (text datablock scrollback) in v1, escalate to C
only if the user wants live `printf` output from `(start)` flows etc.

---

## Dependency graph

```
2 (level manager rework)
├── 1 (id/index warnings)   — item 1's base_id half can ship standalone
└── 3 (id verification)     — fully gated on item 2

7 (send REPL commands)      — plumbing already exists; just needs panel
├── 6 (launch at checkpoint) — could skip 7, uses goalc_send directly
└── 8 (view REPL output)     — easiest as text-datablock scrollback (option B)
```

Items 4 and 5 are standalone bugs, no dependencies.

## Suggested execution order

Cheapest → most expensive, and pick off independent ones first:

1. **Item 6** — ~50 LOC, fully self-contained, immediate quality-of-life win
2. **Item 1 (base_id half only)** — ~30 LOC, mirrors existing level-index pattern
3. **Item 5 audit** — confirm panel-vs-missing for plat-flip with user; check
   pontoon/springbox/oracle for missing panels in same pass
4. **Item 7 + 8B** — ~180 LOC together, opens the door for runtime debugging
   of every other item
5. **Item 4** — quick win on the label/description, then runtime crash work
6. **Item 2** — bigger UI lift, ~250 LOC
7. **Item 3** — falls out of item 2 once data is surfaced
