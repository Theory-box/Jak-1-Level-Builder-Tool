# Jak 1 Level Builder Tool

A Blender addon for building custom Jak and Daxter levels for the [OpenGOAL](https://github.com/open-goal/jak-project) engine. Place actors, triggers, cameras, enemies, platforms, and navmesh from inside Blender — then compile and launch the game with one button.

The addon source lives in [`addons/opengoal_tools/`](addons/opengoal_tools/). All written material lives in [`knowledge-base/`](knowledge-base/) and is split into `manual/` (user-facing) and `research/` (deep notes).

> Confirmed working on Blender 4.4+ and OpenGOAL v0.2.29+.

---

## Getting Started

| Doc | Description |
|---|---|
| [Getting Started](knowledge-base/manual/getting-started.md) | Install the addon, set preferences, create your first level |
| [Workflow](knowledge-base/manual/workflow.md) | Export & Build vs Play, console management, common issues |

---

## Level Content

| Doc | Description |
|---|---|
| [Entity Spawning](knowledge-base/manual/entity-spawning.md) | Place enemies, NPCs, pickups, platforms — JSONC format, DGO/game.gp, bsphere rules |
| [Audio System](knowledge-base/manual/audio-system.md) | Sound banks, music, ambient sound emitters, known bugs |
| [Camera System](knowledge-base/manual/camera-system.md) | Camera markers, trigger volumes, orbit pivots, look-at targets |
| [Player & Continues](knowledge-base/manual/player-loading.md) | Spawn points, continue points, level registration |

---

## Enemy Reference

| Doc | Enemy | Notes |
|---|---|---|
| [Babak](knowledge-base/manual/enemies/babak.md) | Babak (lurker soldier) | Always in GAME.CGO, no DGO needed |
| [Junglesnake](knowledge-base/manual/enemies/junglesnake.md) | Junglesnake | No navmesh required, safest enemy to use |

---

## Data Reference

| File | Description |
|---|---|
| [Enemy Definitions](knowledge-base/manual/data/jak1-enemy-definitions.json) | All entity types, art groups, code paths |
| [SBK Sounds](knowledge-base/manual/data/sbk_sounds.json) | All 1,048 sound effect names across 24 banks |

---

## Deeper Notes

[`knowledge-base/research/`](knowledge-base/research/) holds the source material the manual is distilled from — goal_src deep-dives, AI onboarding, future-research leads, and per-system notes. Useful when you want the full picture rather than a summary.

[`knowledge-base/archive/`](knowledge-base/archive/) holds older snapshots kept for reference (e.g. previous addon versions).

---

## External Resources

- [OpenGOAL Project](https://github.com/open-goal/jak-project)
- [Rockpool Mod (reference level)](https://github.com/dallmeyer/OG-ModBase-Rockpool)
- [OpenGOAL Discord](https://discord.gg/VZbXMHXzTv)
