# Misc Fixes — Tracking

**Branch:** `feature/misc-fixes`
**Repo:** `Jak-1-Level-Builder-Tool`
**Status:** Items 4 (swing pole) and 6 (launch dropdown) shipped to main 2026-05-23; 6 items open
**Last updated:** 2026-05-23

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

## 4. Swing pole broken — Jak disappears, game crashes

**Type:** Bug
**Status:** Fix landed 2026-05-22 (pending user runtime test)

User reports: spawn a swing pole, jump on it, Jak disappears and the game
crashes.

### Root cause (2026-05-22)

The crash signature in `jak1_2026-05-22T19-28-26.log:1127` is `dummy-19 bad`,
emitted from exactly one place in the codebase: `evaluate-joint-control` in
`goal_src/jak1/engine/common-obs/process-drawable.gc:620`. It fires when a
process-drawable's animation channel has a `frame-group` set but its type is
NOT `art-joint-anim` — i.e. the anim symbol couldn't resolve because its
backing art group isn't loaded.

The crash isn't from the swingpole itself (swingpole extends `process`, has
no anims). It's target-side. The sequence:

1. `swingpole-stance` sends `'pole-grab` to `*target*`
2. `target-handler.gc` routes 'pole-grab → `go target-pole-cycle`
3. `target-pole-cycle` runs `(ja-no-eval :group! eichar-pole-cycle-ja ...)`
4. Symbol `eichar-pole-cycle-ja` doesn't link (art group not loaded)
5. `evaluate-joint-control` art-joint-anim type check fails
6. `process-drawable-art-error` state replaces target's `:code` with a
   debug-text loop — no draw, no input → "Jak disappears"
7. Subsequent crash from physics/camera/sidekick interacting with a frozen
   target

The pole animations:

```
eichar-pole-cycle-ja          art-elts.gc:735  index 80
eichar-pole-flip-up-ja        art-elts.gc:736  index 81
eichar-pole-flip-forward-ja   art-elts.gc:737  index 82
eichar-pole-jump-loop-ja      art-elts.gc:738  index 83
```

live in art group **`eichar-pole+0-ag`** — NOT in Jak's main `eichar-ag`.
It's a level-loaded extension, bundled in exactly three vanilla DGOs:

```
goal_src/jak1/dgos/swa.gd  → SWA.DGO  (Swamp)
goal_src/jak1/dgos/sno.gd  → SNO.DGO  (Lost Precursor City)
goal_src/jak1/dgos/rob.gd  → ROB.DGO  (Klaww section)
```

The user's MYL.DGO loaded `my-level-obs, lurkercrab, lurkerworm,
generic-obs, tpages…` — no `eichar-pole+0-ag`. The tool's `needed_ags()` in
`export/levels.py` only walked each entity's own `art_group` field; there
was no slot for "art the target needs when this entity is in the level".

The prior hypothesis (degenerate `dir` from identity quat / missing
collide-shape) doesn't fit: the user's pole quat is
`[0.20724, 0.180129, 0.038854, 0.960778]` — not identity. "dummy-19 bad" is
strictly an art-link failure, not a transform/collide issue. The crash
happens before any physics path would matter.

The "Pole Platform → Swing Pole" rename mentioned in earlier notes was
already done (DB has `"label": "Swing Pole"`). The invisibility-by-design
observation is correct: swingpole IS an invisible logic entity (extends
`process`, no skeleton, no `initialize-skeleton` in `init-from-entity!`).
Vanilla levels place a visible pole mesh in level geometry. For custom
levels the user still needs to model their own pole mesh at the same
position — separate cosmetic concern.

### Fix landed

New schema field `extra_art_groups` on actor records. Bundled with the .gd
(DGO contents) only — NEVER with the JSONC `art_groups` field, because
goalc's `find_art_groups` in `build_level.cpp` treats JSONC `art_groups`
entries as merc-extraction sources and animation-only +0-ag files have no
merc data.

Changes:

- `addons/opengoal_tools/jak1_game_database.jsonc` — swingpole gets
  `"extra_art_groups": ["eichar-pole+0-ag.go"]`
- `addons/opengoal_tools/data.py` — `_entity_info_from_actor` reads
  `extra_art_groups`, exposes `info["extras_ag"]`; new derived lookup
  `ETYPE_EXTRAS_AG`
- `addons/opengoal_tools/__init__.py` + `export/__init__.py` — re-export
  `ETYPE_EXTRAS_AG` and `needed_extras_ags`
- `addons/opengoal_tools/export/levels.py` — new `needed_extras_ags(actors)`
  alongside the unchanged `needed_ags(actors)`
- `addons/opengoal_tools/export/writers.py` — `write_gd()` gains optional
  `extras_ags` kwarg, inserts extras into the .gd file list (after entity
  art, before the level .go)
- `addons/opengoal_tools/build.py` — all three `write_gd` call sites
  (full build, build-changed, build-incremental) compute extras and pass
  them; `write_jsonc` is untouched (extras stay out of the JSONC)

Verified by simulation against user's level: `eichar-pole+0-ag.go` lands
in the .gd's file list right after `lurkerworm-ag.go` and right before
`my-level.go`; the JSONC `art_groups` field stays `["lurkercrab-ag",
"lurkerworm-ag"]` (no extras leakage).

### Lurking cases for same bug class

`game.gp` has 5 more `+0-ag` art groups following the same pattern. Any of
these entity types added to a custom level will hit the same crash unless
they get their own `extra_art_groups` entry:

```
eichar-racer+0-ag   (zoomer)
eichar-flut+0-ag    (flutflut bird mount)
eichar-fish+0-ag    (fishermans-boat-ride)
eichar-pole+0-ag    (swing pole)         ← fixed
eichar-tube+0-ag    (snow tube)
eichar-ice+0-ag     (ice-skating section)
```

When/if these entities are wired into the tool, add the corresponding
`extra_art_groups` entry to the DB. The schema is in place.

### Cosmetic followups (deferred)

- Description in spawn picker explaining "invisible logic entity — place a
  pole mesh in level geometry at the same spot for visuals"
- Viewport visualization: draw a debug cylinder showing `range=3m` ×
  `edge-length=2m` (hardcoded in `init-from-entity!`) so the user can
  position the pole mesh accurately

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
**Status:** ✅ Shipped to main 2026-05-23

### What landed

- New `og_launch_checkpoint` EnumProperty on `OGProperties`, populated by
  `_launch_checkpoint_items` which walks the active level's `SPAWN_*` and
  `CHECKPOINT_*` empties. "(None — bare launch)" is the default; selecting
  any continue-point switches the launch into the full-spawn flow.
- `OG_OT_Play` (formerly two operators) merged: `cp == "none"` → bare launch
  via `launch_gk()`; otherwise spawn-at-continue-point through `_bg_play()`
  in a background thread. `OG_OT_PlayAutoLoad` removed as redundant.
- Dropdown rendered right under the Launch Game button in `OG_PT_BuildPlay`.
- Double-click guard added: clicking again while a launch is in flight gets
  rejected with "Launch already in progress — please wait", which prevents
  the "loads then loads again" bug from a second queued (start) firing
  after the first one finally lands.

### Architecture notes for future maintenance

**nREPL EVAL is fire-and-forget.** `common/repl/nrepl/ReplClient::eval` only
writes the form; never reads anything back. Same on the server side —
ReplServer processes EVAL messages but only sends PING/ERROR responses to
clients, never eval results. All eval output (compile errors, return values,
`printf` like "already connected!") goes to goalc's own console window. We
cannot poll goalc state from outside. Several iterations of this fix
chased "the response that doesn't exist" before we found the ReplClient
source.

**GK boot has no observable ready signal from outside.** GK opens its
DECI2 listener port (8112) early in boot, well before the GOAL kernel
can handle the listener handshake. We tried TCP-probing the port; it
returned success and then `(lt)` hung at "Waiting for version...". The
only reliable approach is a fixed wall-clock sleep between `launch_gk`
and `(lt)`. We exposed this as `og_launch_boot_wait` (default 4s) in
the Developer Tools panel so users can tune for slower hardware.
`og_launch_listener_wait` (default 1s) controls the (lt)→(start) gap.

**Why we don't kill GOALC and relaunch.** A fresh goalc only loads
`goal-lib.gc` + user's `user.gc`; it doesn't know `*game-info*` /
`get-continue-by-name` until something parses `game-info-h.gc`, which
only happens during `(mi)`. So the spawn form fails to compile in a
fresh goalc. We rely on goalc being preserved from a prior Export &
Compile run — `goalc_ok()` check up front bails out with a clear hint
if it isn't.

**Cold-start time on dev machine: ~6s** (launch + 4s boot wait + (lt) + 1s + (start)).
**Warm-start time: ~3s** ((lt) + 1s + (start)).

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

Items 4 and 5 are standalone bugs, no dependencies. Item 4 fixed 2026-05-22.

## Suggested execution order

Cheapest → most expensive, and pick off independent ones first:

1. ~~**Item 4**~~ — done 2026-05-22; pending user test
2. **Item 6** — ~50 LOC, fully self-contained, immediate quality-of-life win
3. **Item 1 (base_id half only)** — ~30 LOC, mirrors existing level-index pattern
4. **Item 5 audit** — confirm panel-vs-missing for plat-flip with user; check
   pontoon/springbox/oracle for missing panels in same pass
5. **Item 7 + 8B** — ~180 LOC together, opens the door for runtime debugging
   of every other item
6. **Item 2** — bigger UI lift, ~250 LOC
7. **Item 3** — falls out of item 2 once data is surfaced
