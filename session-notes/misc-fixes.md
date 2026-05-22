# Misc Fixes — Tracking

**Branch:** `feature/misc-fixes`
**Repo:** `Jak-1-Level-Builder-Tool`
**Status:** Open — issues being collected; no code changes yet
**Last updated:** 2026-05-22

A grab-bag tracking branch for several user-reported issues and feature ideas.
Items aren't being worked yet; this file just records them so they're not lost
between sessions. Each item gets a heading + brief description.

---

## 1. Warn on conflicting level ID / level index

**Type:** Polish / safety
**Status:** Open, wires into item 2

When a user changes `og_base_id` or `og_level_index` for a level, mismatches
against earlier-built state can silently break entity-actor AID linking — most
visibly, the `custom-nav-mesh-check-and-setup` case arms patched into
`engine/entity/entity.gc` go stale and assigned navmeshes stop being applied.
Want a warning at change time and/or export time when:

- Two levels share a `base_id` (already partly handled for level index — extend
  to base_id).
- A level's exported `base_id` differs from the one currently baked into
  `entity.gc`'s injected case arms.

Wire-in depends on item 2 because the warning lives most naturally inside a
beefed-up level manager.

Context: this is what bit the user during the lurkercrab waypoint debug
session on 2026-05-22 — base_id change + full recompile resolved it once the
patched entity.gc AIDs realigned with the exported JSONC AIDs.

---

## 2. Level Manager rework — view all custom levels + their files

**Type:** Feature / UX
**Status:** Open

Current level manager doesn't surface enough. Want a panel/dialog that, for
every custom level on disk, shows:

- Level name, nick, base_id, index
- Path to `.jsonc`, `.gd`, `.glb`, `level-info.gc` block
- Whether art groups / tpages / extra `.o` files referenced in its `.gd`
  actually exist
- Anything `discover_custom_levels` already collects, plus per-level health
  flags

`discover_custom_levels` exists in `export/levels.py` but is currently inert
(defined, imported in 7 modules, called by zero — flagged in
`session-notes/level-index-nickname-fix.md`). This item is essentially
"wire that up + extend it."

---

## 3. Level-ID verification (wired into item 2)

**Type:** Polish
**Status:** Open, depends on items 1 + 2

Once the level manager from item 2 exists, item 1's collision warnings live
there. The manager already has every level's `base_id` + index loaded;
cross-checking is one pass over its data.

---

## 4. Pole platform broken

**Type:** Bug
**Status:** Open

`pole-plat` (the climbable pole) is invisible at runtime. Jak can stand on it
/ interact, but:

- Pole geometry doesn't render
- Jak turns invisible when interacting
- Game crashes shortly after

Suspect: missing art group, missing skeleton init, or wrong actor class. Need
to:

- Check `pole-plat`'s `art_group` entry in `jak1_game_database.jsonc`
- Compare against working vanilla pole instances (search vanilla `.gc` for the
  actual GOAL type)
- Verify the `.go` / art group is in the level's `.gd`

---

## 5. Flip platform settings panel gone

**Type:** Bug / regression
**Status:** Open

`flip-plat` previously displayed a settings UI in the side panel for
configuring `delay` / `sync-percent` etc. That panel is gone in the current
build — user is now forced to add lumps manually to change behavior.

Two concerns:

- Recover the flip-plat panel.
- **Audit other actors for the same regression** — if flip-plat lost its panel
  without anyone noticing, others may have too. Likely root cause: a per-etype
  panel-binding lookup that's broken or stale.

Worth diffing `panels/actor.py` and `panels/selected.py` against an older
known-good archive (e.g. `knowledge-base/archive/opengoal_tools_v9.py`) for
actors whose settings draw blocks were present then and absent now.

---

## 6. Launch level at a specific checkpoint

**Type:** Feature
**Status:** Open

When iterating on a level, having to walk from spawn to the area being tested
each launch wastes a lot of time. Want a UI affordance to pick "launch at
checkpoint X" — passes the correct spawn override to OpenGOAL on game launch.

Likely needs:

- A "launch checkpoint" dropdown on the Build / Launch panel, populated from
  the level's `CHECKPOINT_` empties.
- Selected name is passed to the game (via REPL form, or by setting a
  `start-checkpoint` override in `level-info.gc` before launch).

Depends on item 7 / 8 if we use REPL injection; if we go the level-info route,
this is self-contained.

---

## 7. Send REPL commands from Blender

**Type:** Feature
**Status:** Open

Want to send arbitrary REPL forms from a Blender panel button into a running
game. Need to first verify whether this already exists in the addon (search
for any nrepl / `(lt)` socket code) — half-remembered that this might already
be wired up partially.

The `(lt)` connect form is the standard nrepl handshake — addon would open a
TCP socket to the OpenGOAL listener and send forms over it.

Useful immediately for item 6 (launch-at-checkpoint), and for runtime tweaks
like toggling debug flags from Blender.

---

## 8. View REPL output in Blender

**Type:** Feature
**Status:** Open, depends on item 7

Once item 7 exists, the natural next step is showing the REPL output
(responses, prints, errors) somewhere in Blender. Options:

- A text panel that streams from the same socket as item 7
- A toggleable side panel that tails REPL output
- Just routing it to Blender's Info area / system console

Lowest-friction first: dump to Blender's console; iterate from there.

---

## Dependency graph

```
2 (level manager rework)
├── 1 (id/index warnings)
└── 3 (id verification)

7 (send REPL commands)
├── 6 (launch at checkpoint) — if REPL-injection route
└── 8 (view REPL output)
```

Items 4 and 5 are standalone bugs, no dependencies.
