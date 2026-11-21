# Your first level

This tutorial takes you from an empty Blender file to running around your own level in the game. It takes about 15 minutes, plus the first compile. You need a finished [install](install.md): the **Build & Play** panel must not say **Missing paths**.

You will make:
- a floor to stand on
- a checkpoint where Jak starts
- an orb, a crate, a moving platform and an enemy

All the add-on's tools are in the 3D viewport's sidebar (press **N**), on the **OpenGOAL** tab.

## 1. Create the level

1. Start a new Blender file (**File › New › General**) and delete the default cube, camera and light. You won't need them.
2. Open **OpenGOAL › Level**. In an empty file it says **No levels in this file**. Click **Add Level**.
3. Fill in the dialog:

   | Field | What to type |
   |---|---|
   | **Level Name** | A short name in lowercase, with dashes instead of spaces, at most 10 characters, for example `my-level`. It becomes the file names and the name the game uses. |
   | **Base Actor ID** | Leave it. Each level needs its own range of actor IDs; the add-on suggests a free one. |
   | **Level Index** | Leave it. A number the game uses for the level; it must not clash with another level. The add-on suggests a free one (100 or higher). |
   | **Vis Nickname** | Leave it blank; a 3-letter nickname is made from the name. It must be unique too. |
   | **Texture Remap / Sky** | The vanilla level whose sky and texture set you borrow, for example a village. You can change it later in **Level › Settings**. |

4. Click **OK**. A new collection called `my-level` appears in the Outliner, with a `my-level.Geometry` collection inside it. The level is now the *active level*: everything you spawn goes into it.

More about levels and their settings: [Levels](levels.md).

## 2. Make a floor

The level's 3D model is every mesh inside its **Geometry** collection. Meshes collide by default, so Jak can stand on them.

1. In the Outliner, click `my-level.Geometry` to make it the active collection.
2. In the viewport: **Add › Mesh › Plane**. Scale it up to about 40 × 40 m (**S**, type `20`, **Enter**: the plane starts 2 m wide). One Blender metre is one metre in the game.
3. Optional: add a few cubes as steps or walls, in the same collection.

If a mesh ends up outside Geometry, the **Build & Play** panel shows **N mesh(es) outside Geometry aren't exported** with a **Move to Geometry** button. Click it.

The floor will look plain in the game: it has no texture and no baked lighting yet. That's fine for now. See [Geometry](geometry.md) for textures and collision settings, and [Lighting](lighting.md) for baking. <!-- check: how an untextured, unbaked mesh looks in game -->

## 3. Add the start checkpoint

A checkpoint is where Jak spawns and respawns. The level's first one is called **start**, and that's where you'll launch the game.

1. Put the 3D cursor where Jak should start, a little above the floor: **Shift + right-click** on the plane.
2. Open **OpenGOAL › Spawn Objects**. Click the **Level Flow** tile, pick **Checkpoint** in the list, and click **Spawn**.
3. A small dialog asks for the **Name**. It already says `start`; click **OK**.
4. A cone-shaped empty called `CHECKPOINT_<nickname>_start` appears at the cursor, in the level's **Spawns** collection.

Every new object is placed at the 3D cursor, so you'll repeat "click to place the cursor, then **Spawn**" for each one. More about checkpoints: [Checkpoints & cameras](checkpoints-and-cameras.md).

## 4. Add an orb and a crate

1. Move the 3D cursor a few metres from the checkpoint, about 1 m above the floor.
2. In **Spawn Objects**, click the **Pickups** tile, pick **Orb (Precursor)** and click **Spawn**. You get an empty named `ACTOR_money_0`. (`money` is the game's own name for an orb.)
3. Move the cursor again, pick **Crate** in the same list and **Spawn** it. Place it so it sits on the floor.
4. With the crate selected, open **OpenGOAL › Object Settings**. Under **Actor Settings › Crate** you can pick the crate type and what's inside it.

Tip: you can also type in the search box under the list (for example `orb` or `crate`) instead of clicking tiles.

If game models are installed (see [Install](install.md#game-models-for-previews)), each actor shows its real model in the viewport.

## 5. Add a moving platform

1. Move the cursor to an open spot, about 2 m above the floor.
2. In **Spawn Objects**, click the **Platforms** tile, pick **Floating Platform** and click **Spawn**.
3. Keep the platform selected and open **Object Settings › Actor Settings › Path**. It says the platform needs at least 2 waypoints to move.
4. Click **Spawn Waypoint** twice. Each click adds a small empty (`ACTOR_plat_0_wp_00`, `…_wp_01`) at the 3D cursor; turn on **At Actor Position** to put them on the platform instead.
5. Move the two waypoints apart, for example 6 m to the side. The platform will float back and forth between them.

Paths can also be curves (**Add Curve**), and platforms have timing options. See [Paths & platforms](paths-and-platforms.md).

## 6. Add an enemy

Most walking enemies (the "nav-enemies", like the Babak lurker) need a **nav-mesh**, a mesh that tells them where they can walk. In the spawn list they show **Nav-enemy, needs navmesh and path**. That's for later: see [Enemies & nav-meshes](enemies-and-navmesh.md).

For a first test, use an enemy that stays in one place:

1. Move the cursor where you want it.
2. In **Spawn Objects**, click the **Enemies** tile, pick **Jungle Snake** and click **Spawn**.

## 7. Build and play

1. Save your `.blend` file. Turn the checkpoint (rotate it around Z) if you want Jak to face another way.
2. Open **OpenGOAL › Build & Play** and click **Export & Compile**.
   - The add-on writes the level's files and starts **GOALC**, the OpenGOAL compiler, in its own console window. Leave that window open.
   - The status bar at the bottom of Blender shows the progress. The **first** compile builds all the game's code and takes a while. Later compiles only rebuild what changed and are much faster.
   - When it's done, Blender reports **Build complete!**.
3. Set **Spawn** to `my-level-start` (your level name followed by `-start`).
4. Click **Launch Game**. The game starts and Jak appears at your checkpoint.

You can click **Launch Game** while a compile is still running: it waits and launches when the compile is done. Or turn on **Auto** next to it to launch after every compile.

## 8. Change something and try again

Move the orb, add another crate, then:
- **Export & Compile** again, then **Launch Game**, or
- **Quick Level Export** for small changes to your level's own actors and geometry. It's quicker, but doesn't update checkpoints and a few shared files.

All the buttons and options are explained in [Build & Play](build-and-play.md). If something goes wrong, check the red **⚠** number next to **Export & Compile** (it lists fields that still need filling in) and [Troubleshooting](troubleshooting.md).

---
[← Previous](install.md) · [Guide index](README.md) · [Next →](interface.md)
