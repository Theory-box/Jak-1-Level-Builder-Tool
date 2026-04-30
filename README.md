# Jak 1 Level Builder Tool

A Blender addon for building custom Jak and Daxter levels for the [OpenGOAL](https://github.com/open-goal/jak-project) engine. Place actors, triggers, cameras, enemies, platforms, water volumes, navmesh, sound emitters, music zones, and lighting from inside Blender — then compile and launch the game with one button.

The addon source lives in [`addons/opengoal_tools/`](addons/opengoal_tools/). All written material lives in [`knowledge-base/`](knowledge-base/), split into `manual/` (user-facing) and `research/` (deep notes).

> **Versions:** Addon 2026.4.30 · Blender 4.4+ · OpenGOAL v0.2.29+

---

## Getting Started

| Doc | Description |
|---|---|
| [Getting Started](knowledge-base/manual/getting-started.md) | Install the addon, set preferences, create your first level |
| [Workflow](knowledge-base/manual/workflow.md) | Export & Build vs Play, console management, GOALC nREPL |
| [Known Issues](knowledge-base/manual/known-issues.md) | Current bugs, limitations, and workarounds |

---

## Manual — Polished Guides

| Doc | Description |
|---|---|
| [Entity Spawning](knowledge-base/manual/entity-spawning.md) | Place enemies, NPCs, pickups, platforms — JSONC format, DGO/game.gp, bsphere rules |
| [Audio System](knowledge-base/manual/audio-system.md) | Sound banks, music, ambient sound emitters, known bugs |
| [Camera System](knowledge-base/manual/camera-system.md) | Camera markers, trigger volumes, orbit pivots, look-at targets |
| [Player & Continues](knowledge-base/manual/player-loading.md) | Spawn points, continue points, level registration |

### Enemy Reference

| Doc | Enemy | Notes |
|---|---|---|
| [Babak](knowledge-base/manual/enemies/babak.md) | Babak (lurker soldier) | Always in GAME.CGO, no DGO needed |
| [Junglesnake](knowledge-base/manual/enemies/junglesnake.md) | Junglesnake | No navmesh required, safest enemy to use |

> The database ships with **156 actor types** across 9 categories (Enemies, Bosses, NPCs, Pickups, Platforms, Props, Objects, Debug, Hidden). Babak and Junglesnake have polished writeups — the rest are documented in the database itself ([`jak1_game_database.jsonc`](addons/opengoal_tools/jak1_game_database.jsonc)) and the per-system research notes below.

---

## Research Notes — Deeper Coverage

The addon has UI for many systems that don't yet have polished manual entries. The notes below in [`knowledge-base/research/`](knowledge-base/research/) are the authoritative source for these — researched directly from `goal_src/jak1/`.

| Topic | Notes |
|---|---|
| [Triggers](knowledge-base/research/opengoal/trigger-system.md) | Volume-based events, aggro triggers, custom vol-trigger types |
| [NavMesh](knowledge-base/research/opengoal/navmesh-system.md) | Nav-mesh requirements, nav-enemy gotchas, sphere workaround |
| [Lighting & Mood](knowledge-base/research/opengoal/lighting-system.md) | Per-level mood, time-of-day, vertex-color light bake |
| [Water Volumes](knowledge-base/research/opengoal/water-system.md) | Wade/swim/surface heights, water vol export |
| [Platforms](knowledge-base/research/opengoal/platform-system.md) | plat / plat-eco / orbit / flip / square / launcher behaviour |
| [Doors](knowledge-base/research/opengoal/door-system.md) | iris-door, sun-iris, eco-door, side/round/launcher variants |
| [GOAL Code Injection](knowledge-base/research/opengoal/goal-code-system.md) | Per-actor `obs.gc` code blocks, runtime hooks, examples |
| [Lump System](knowledge-base/research/opengoal/lump-system.md) | Custom lumps, hardcoded keys, type encoding |
| [Texture Pages](knowledge-base/research/opengoal/tpage-system.md) | tpage groups, heap budget, 11 MB kheap limit |
| [Texture Browser](knowledge-base/research/opengoal/texture-browser.md) | Browsing and assigning game textures |
| [Level Flow & Transitions](knowledge-base/research/opengoal/level-transitions.md) | Multi-level setups, vis files, load boundaries |
| [Particle Effects](knowledge-base/research/opengoal/particle-effects-system.md) | Effects system, entity-actor effect lookup |
| [nREPL & Startup](knowledge-base/research/opengoal/nrepl-and-startup.md) | GOALC connection, build pipeline internals |

Other research material in [`knowledge-base/research/opengoal/`](knowledge-base/research/opengoal/) covers known bugs, future research leads, upstream fixes to watch, AI onboarding, and per-enemy activation rules.

---

## Data Reference

| File | Description |
|---|---|
| [Game Database](addons/opengoal_tools/jak1_game_database.jsonc) | Canonical source: 156 actors, 21 levels, 20 sound banks, lump schemas, PAT enums, fields[] schemas |
| [Enemy Definitions (snapshot)](knowledge-base/manual/data/jak1-enemy-definitions.json) | Static snapshot of entity types, art groups, code paths |
| [SBK Sounds](knowledge-base/manual/data/sbk_sounds.json) | 1,038 sound effect names across 20 banks |

---

## Archive

[`knowledge-base/archive/`](knowledge-base/archive/) holds older snapshots kept for reference — e.g. previous addon versions.

---

## External Resources

- [OpenGOAL Project](https://github.com/open-goal/jak-project)
- [Rockpool Mod (reference level)](https://github.com/dallmeyer/OG-ModBase-Rockpool)
- [OpenGOAL Discord](https://discord.gg/VZbXMHXzTv)
