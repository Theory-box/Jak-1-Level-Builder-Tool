# OpenGOAL Level Tools

**Build custom Jak and Daxter levels in Blender, then compile and play them with one button.**

OpenGOAL Level Tools is a Blender add-on for making custom levels for *Jak and Daxter: The Precursor
Legacy* on the [OpenGOAL](https://github.com/open-goal/jak-project) engine. Model your level, place
the game's actors from a searchable list, set them up with plain fields instead of raw data, bake the
lighting, and press **Build & Play**: the add-on writes every game file, compiles the level and
starts the game at your checkpoint.

<!-- screenshot: a level in Blender with the OpenGOAL sidebar open, and the same level in game -->

**[⬇ Download the latest release](https://github.com/Theory-box/Jak-1-Level-Builder-Tool/releases/latest)** ·
[OpenGOAL Discord](https://discord.gg/VZbXMHXzTv)

---

## What it does

### Place the whole game's cast
- **258 spawnable actors** from the original game: enemies and bosses, NPCs, pickups, platforms,
  doors and buttons, obstacles, props, particles. Search them by name or category, keep favourites,
  pick variants (crate types, bridge looks, sage cages…).
- **Model previews** of every actor in the viewport (from your own game files), so you see what you
  place.
- **Settings as fields**, not raw lumps: each actor shows only what its game code reads, with
  defaults, limits and explanations. Raw custom lumps stay available for anything else.
- **Links between actors** (buttons → doors, enemies → nav-meshes, paths shared between actors…)
  picked from the selection or a search, with warnings when something required is missing.
- **65 edited actors**: vanilla actors that relied on hard-coded tasks, positions or cameras (Keira,
  the sages, the oracle, the pipe game, the gondola, Klaww…) work in custom levels, set up from
  Blender. Bring your own GOAL code too: per level or shared between levels.
- **Actor Light**: areas that light (or darken) Jak, Daxter and chosen actors, with time of day
  hours, fades and triggers.

### Paths, platforms and enemies
- Waypoints or Blender curves as **paths** (linear, smooth, Bézier), extra paths, sync timing for
  moving platforms, distribute platforms along a curve, race rings.
- **Nav-meshes** made from your faces, with jump areas, nav-spheres and automatic reduction to the
  game's limits; enemy activation and aggro trigger volumes.

### Level setup
- Several levels per .blend; level settings (mood, sky, fog, death plane, sound and music banks,
  orb count), checkpoints and continue points, **cameras** with trigger volumes, hints, music zones,
  sound emitters, water volumes, load boundaries between levels.
- **Custom tasks**: your own power cells and scout flies with their game text.
- **Project settings**: the checkpoints New Game, retail boot and Quit to menu go to, and the Discord
  status of your mod.

### Lighting
- **Vertex lighting bake** with Cycles, fast on large levels (meshes baked together), with light
  curves, blur and emission.
- **Time of day**: a bake per time of day with its own lights, world and animation frame.
- **Color Quantisation preview**: see the game's 8192-colour palette in Blender and fix the colours
  it would spoil; smaller level files (8-bit colours, Color Depth).
- **Vertex Colors tools**: copy lighting onto grass and props, effects (curves, colour, alpha, blur)
  that run after every bake.

### Build, play, check
- **Build & Play**: export, compile and launch in one click; quick re-export; boot in debug, with the
  debugger attached, or in retail mode.
- **Warnings while you work**: red counts for what would crash or break, yellow for what works but
  does less, a full **Level Audit**, and explanations for each.
- **Import**: the game's own 3D models and textures, and existing levels' GOAL files (.jsonc and
  game files) back into Blender.
- Works with the official OpenGOAL release, a jak-project dev build or the
  [mod-base](https://github.com/OpenGOAL-Mods/OG-Mod-Base); features that need a newer version tell
  you so.

---

## Requirements

| | |
|---|---|
| Blender | 4.4 or newer (tested up to 5.3) |
| OpenGOAL | Jak 1 on OpenGOAL: an official release (v0.3.4+ for the built-in cameras, v0.3.8+ for time of day), a jak-project dev build, or the mod-base (needed for custom tasks) |
| Game files | your own extracted Jak 1 (OpenGOAL's extractor) for previews and textures |

## Install

1. Download `opengoal-level-tools-<version>.zip` from the [latest release](https://github.com/Theory-box/Jak-1-Level-Builder-Tool/releases/latest).
2. Blender → **Edit › Preferences › Add-ons › Install…** → pick the zip → enable **OpenGOAL Level Tools**.
3. In the add-on's preferences, point it at your OpenGOAL install (or its folder for auto-detection).
4. Open the **OpenGOAL** tab in the 3D viewport's sidebar (N) and create a level in **Level › Level Manager**.

Updating: install the new zip the same way, then restart GOALC once.

---

## Documentation

A new user guide is being written (basics first, then every feature in detail); links will be added
here when it's published. Until then:
- the release notes on the [Releases page](https://github.com/Theory-box/Jak-1-Level-Builder-Tool/releases) describe each feature;
- every field and button in the add-on has a tooltip, and the **?** buttons and warning counts explain themselves;
- deeper technical notes (how the game systems work) are in [`knowledge-base/research/`](knowledge-base/research/).

Questions and feedback: the [OpenGOAL Discord](https://discord.gg/VZbXMHXzTv).

---

## For contributors

- Add-on source: [`addons/opengoal_tools/`](addons/opengoal_tools/). Game data (actors, fields,
  panels, levels, sounds) lives in one database file,
  [`jak1_game_database.jsonc`](addons/opengoal_tools/jak1_game_database.jsonc).
- Planned work: [`community-feedback/ToDo ordered List.md`](community-feedback/ToDo%20ordered%20List.md).

**Made by** [Theory-box](https://github.com/Theory-box) and [Kuitar5](https://github.com/Kuitar5).
