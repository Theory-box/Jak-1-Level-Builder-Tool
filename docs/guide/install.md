# Install

This page gets Blender, OpenGOAL and the add-on talking to each other. You only do it once.

## What you need

| | |
|---|---|
| **Blender** | 4.4 or newer. 4.4 or 4.5 is the safe choice (see below). |
| **OpenGOAL** | A working Jak 1 install of OpenGOAL: the game must already run. Any of the three kinds below works. |
| **The add-on** | The release zip `opengoal-level-tools-<version>.zip` from the [Releases page](https://github.com/Theory-box/Jak-1-Level-Builder-Tool/releases). |

Some newer Blender versions have glTF export bugs. The add-on works around them for the level export:

| Blender | Problem | What the add-on does |
|---|---|---|
| **4.4, 4.5** | None known. Recommended. | |
| **5.0** | Its glTF exporter leaves out custom properties that add-ons register. | Copies the collision settings to plain custom properties for the export, so collision works. Other add-on properties may still be missing. |
| **5.2.2** | Meshes export white when their render and active colour layers are different. | Exports only the **Active** colour layer. |

OpenGOAL comes in three kinds. The add-on detects which one you have and turns a few features on or off to match:

| Kind | What it is | How the add-on reads its version |
|---|---|---|
| **Release** | A normal jak-project release (launcher or zip) | Runs `gk --version` |
| **jak-project dev** | Your own git clone of jak-project, built yourself | The clone's git commit |
| **mod-base dev** | A clone of the modding fork (it has `engine/mods/mod-settings.gc`) | The clone's git commit |

Most of the add-on works on all three. These features depend on the kind and version:

| Feature | Release | jak-project dev | mod-base dev |
|---|---|---|---|
| Built-in cameras | v0.3.4+ | yes | yes |
| Boot straight into the spawn (`mod-settings.gc`) | no | no | yes |
| Custom tasks | no | no | yes |
| Time of day | v0.3.8+ | from commit `d04ac9d` | from commit `3a0aadf` |

For built-in cameras, boot into spawn and custom tasks the add-on also looks at the game's source code. If it finds the feature there, the feature is on, whatever the version says. When a feature isn't available, the panel that uses it shows a short line saying what it needs.

## Install the add-on

1. Download the release zip. Don't unzip it.
2. In Blender, open **Edit › Preferences › Add-ons**.
3. Click the drop-down arrow at the top right and pick **Install from Disk…**. Choose the zip.
4. Tick **OpenGOAL Level Tools** in the list to enable it.
5. In the 3D viewport, press **N** to open the sidebar. A new **OpenGOAL** tab appears.

The add-on's settings are in the same place: expand **OpenGOAL Level Tools** in **Preferences › Add-ons**.

## Point the add-on at OpenGOAL

The add-on needs two folders:

- the **executables** folder, the one with `gk` and `goalc` in it
- the **game source / data** folder, the one with `goal_src/jak1` in it. In a release this is inside a `data/` folder next to `gk`. In a dev clone it's the clone itself.

The quickest way to set both:

1. In the add-on preferences, set **OpenGOAL Root** to a folder that *contains* your install. For example, if your exe is at `…/OpenGOAL/jak1/v0.3.8/gk.exe`, pick `…/OpenGOAL/jak1/`. With a dev clone you can pick the clone itself.
2. The add-on scans that folder as soon as you pick it. You can scan again at any time with **Find Files**.
3. Two lists appear: **Executables (gk + goalc):** and **Game source / data folder:**. The ticked entry in each is the one in use. Click another entry to switch, for example to change between two OpenGOAL versions.
4. A small status box underneath shows **EXE:**, **Data:** (with "dev layout" or "release layout") and **Decompiler:**. A tick means the folder was found.

Picking folders automatically:
- **Executables:** a dev clone picked as the root uses its own build (`out/build/Release/bin`, then `RelWithDebInfo`, then `Debug`). Otherwise the highest version number wins.
- **Data:** the root itself if it is a dev clone, then the data folder of the chosen exe, then a folder with "active" in its name, then the first one found.

If the scan finds nothing, or picks the wrong thing, open **Manual path overrides (advanced)** and type the folders in yourself.

You can also set the folders per `.blend` file instead: **Developer Tools › Paths › Project Folders (this .blend)**, tick **Use this .blend's folders**. **Copy From Preferences** fills them in with the folders in use now. The folders are saved in the `.blend` and win over the preferences. This is handy when you work on several projects with different OpenGOAL installs, or after installing a newer add-on version. More in [Developer Tools](developer-tools.md).

### All preference settings

| Setting | What it does |
|---|---|
| **OpenGOAL Root** | Parent folder of your OpenGOAL install(s). Scanned for exe and data folders. |
| **Find Files** | Scans the root folder again and picks the best exe and data folder. |
| **Executables (gk + goalc):** list | The folder with `gk` and `goalc` that the add-on uses. |
| **Game source / data folder:** list | The folder with `goal_src` (or `data/goal_src`) that the add-on uses. |
| **Manual path overrides (advanced)** | Opens the fields below. A filled-in field wins over the lists above. |
| **EXE folder (override)** | Folder containing `gk` / `goalc`. |
| **Data folder (override)** | Release: the parent of `data/`. Dev build: the repository root. A box under it says whether it found a dev or release layout. |
| **Decompiler output (override)** | The `decompiler_out/jak1/` folder. Leave it blank to use `<data>/decompiler_out/jak1`. |
| **Custom code folder (edited actors)** | A folder of your own edited-actor `.gc` files. See [Edited actors & GOAL code](edited-actors-and-goal-code.md). |
| **Preview Models** | When you spawn an actor, show its game model in the viewport as a stand-in. On by default. See below. |
| **Select actors by their preview model** | Clicking or box-selecting a preview model selects its actor. Turn off to select the preview meshes themselves. On by default. |
| **Snapping skips the moved actor's preview** | While actors are selected you can't snap to their own previews (they move with them). Other actors' previews still work. Turns on Blender's snapping option *Exclude Non-Selectable*. Needs the setting above. On by default. |
| **Connect spawned actors to the selection** | When you spawn an actor, link what was selected: a curve becomes its path, a nav-mesh (or an actor that has one) becomes its nav-mesh, a `VOL_` volume becomes its volume. On by default. |
| **8-bit colours in every glTF export** | Level exports always write vertex colours as 8-bit. With this on, glTF exports you make by hand (**File › Export › glTF**) do the same. Off by default. |
| **Game database: Override** | A `.jsonc` file used instead of the bundled `jak1_game_database.jsonc`. For advanced users; see [Developer Tools](developer-tools.md). |
| **Reload Database** | Reads the database again (this reloads the add-on). Use it after changing the override. |

### Check it worked

Open the sidebar's **OpenGOAL** tab. If the **Build & Play** panel says **Missing paths — open Developer Tools**, the add-on can't find `gk`, `goalc` or `game.gp`. **Developer Tools › Paths** shows which one is missing (✓ OK or ✗ NOT FOUND) and has a **Set EXE / Data Paths** button that opens the preferences.

## Versions and Re-check Versions

**Developer Tools › Addon Settings › Versions** shows your Blender version, the OpenGOAL the add-on detected (for example "Release v0.3.8" or "mod-base dev @ 3a0aadf") and every feature from the table above with a tick, a cross or a question mark. A cross or a question mark has a line under it saying why.

- **Re-check Versions**: detect OpenGOAL again. The result is cached, so click this after you update OpenGOAL or change paths.
- **Overwrite**: if the detection is wrong for your setup, pick **Release** (and type its version in the **v** field), **jak-project dev** or **mod-base dev**. The features then follow your choice. **Detected** goes back to automatic.

## Game models for previews

Previews and the [Import](importing.md) panel use the models and textures that OpenGOAL's decompiler extracts from your copy of the game. They live in `decompiler_out/jak1/`, usually `<data>/decompiler_out/jak1/`:

- models: `.glb` files under `levels/<level>/`, for example `levels/beach/babak-lod0.glb`
- textures: PNG files under `textures/`

A normal install doesn't write the models. The decompiler has to export the levels' GLBs once. Pick one:

- **OpenGOAL launcher**: **Settings › Decompiler**, turn on **Rip levels**, then run the decompiler.
- **By hand**: set `rip_levels` to `true` in the decompiler's config file and run the decompiler.
- **Dev build (jak-project clone)**: run `task rip-levels`. `Taskfile.yml` in the clone lists all the tasks.

Textures (the PNG files) come from the `save_texture_pngs` option in the same config file.

If the models aren't there, actors still spawn and export; they just show up as empties without a model. If your `decompiler_out` is somewhere else, set **Decompiler output (override)** in the preferences.

## Updating

1. Download the new release zip.
2. Install it the same way (**Install from Disk…**) and make sure it's enabled. Restarting Blender afterwards is the safest way to load the new code.
3. **Close the GOALC window once** (the console window the add-on opened). The next build starts a fresh GOALC that knows the new code. GOALC is explained on the [Build & Play](build-and-play.md) page.

The first build after an update can be a full compile, because the add-on may have changed shared game files. From release 2026.11.20 on, updates don't break your `.blend` files; at most you might have to relink a path or a volume.

---
[← Previous](README.md) · [Guide index](README.md) · [Next →](first-level.md)
