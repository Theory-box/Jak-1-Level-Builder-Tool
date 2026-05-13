# OpenGOAL Tools — Manual

User-facing documentation for the **OpenGOAL Tools** Blender addon — a toolkit for creating custom Jak and Daxter levels using the [OpenGOAL](https://github.com/open-goal/jak-project) engine.

> **Versions:** Addon 2026.4.30 · Blender 4.4+ · OpenGOAL v0.2.29+
>
> For deep technical notes (triggers, navmesh, lighting, water, GOAL code injection, etc.), see [`../research/`](../research/).

---

## Getting Started

| Doc | Description |
|---|---|
| [Getting Started](getting-started.md) | Install the addon, set preferences, create your first level |
| [Workflow](workflow.md) | Export & Build vs Play, console management, GOALC nREPL |
| [Known Issues](known-issues.md) | Current bugs, limitations, and workarounds |

---

## Level Content

| Doc | Description |
|---|---|
| [Entity Spawning](entity-spawning.md) | Place enemies, NPCs, pickups, platforms — JSONC format, DGO/game.gp, bsphere rules |
| [Audio System](audio-system.md) | Sound banks, music, ambient sound emitters, known bugs |
| [Camera System](camera-system.md) | Camera markers, trigger volumes, orbit pivots, look-at targets |
| [Player & Continues](player-loading.md) | Spawn points, continue points, level registration |

---

## Enemy Reference

| Doc | Enemy | Notes |
|---|---|---|
| [Babak](enemies/babak.md) | Babak (lurker soldier) | Always in GAME.CGO, no DGO needed |
| [Junglesnake](enemies/junglesnake.md) | Junglesnake | No navmesh required, safest enemy to use |

The database ships with 156 actor types total. Babak and Junglesnake have polished writeups; the rest are documented in [`jak1_game_database.jsonc`](../../addons/opengoal_tools/jak1_game_database.jsonc) and the [research notes](../research/opengoal/).

---

## Data Reference

| File | Description |
|---|---|
| [Enemy Definitions (snapshot)](data/jak1-enemy-definitions.json) | Static snapshot of entity types, art groups, code paths |
| [SBK Sounds](data/sbk_sounds.json) | 1,038 sound effect names across 20 banks |

The canonical source for all game data is [`addons/opengoal_tools/jak1_game_database.jsonc`](../../addons/opengoal_tools/jak1_game_database.jsonc) — actors, levels, sound banks, lump schemas, PAT enums, and per-actor field schemas live there.

---

## External Resources

- [OpenGOAL Project](https://github.com/open-goal/jak-project)
- [Rockpool Mod (reference level)](https://github.com/dallmeyer/OG-ModBase-Rockpool)
- [OpenGOAL Discord](https://discord.gg/VZbXMHXzTv)
