# Cameras

Cameras replace the normal follow camera in parts of your level: a fixed view of a room, a side-scrolling stretch, a camera that orbits a tower. Some actors also play short camera shots of their own (*pov-cameras*, below). Cameras are on the **Spawn Objects › Cameras** tile.

The camera Jak starts with after a respawn is set on the checkpoint instead: see [The respawn camera](level-flow.md#the-respawn-camera-_cam-anchor).

## Camera objects

A camera is a Blender camera named `CAMERA_0`, `CAMERA_1` ... It's switched on by other actors (see [Cameras used by actors](#cameras-used-by-actors)) or by a trigger volume linked to it: while Jak is inside the volume, the game uses this camera.

### Add one

1. Pick where it goes with **Spawn Objects › Cameras › Camera › Spawn at**:

   | Spawn at | Where the camera goes |
   |---|---|
   | **3D cursor (aligned view)** (default) | At the 3D cursor, facing the way the viewport looks |
   | **3D cursor (default view)** | At the 3D cursor, rotation 0, 0, 0 |
   | **Viewport view** | Where the viewport looks from: the camera sees what the viewport shows |

2. Click **Spawn**. Look through it with Numpad 0.
3. Select it and open **Object Settings › Camera Settings**. At the bottom, under **Volumes**, click **Add Volume** (or link a selected `VOL_` mesh). Without one it says **No volume — the camera never activates**.
4. Aim it: rotate the camera, or add a **Look-At** target.

The Blender camera shows the game's field of view (FOV), so Numpad 0 gives you a close preview.

## Built-in vs legacy cameras

Newer OpenGOAL versions (v0.3.4 and later) have built-in camera entities in the level file; older ones only have the add-on's legacy camera actors. The top of Camera Settings tells you which one you're using: **Built-in camera entity** or **Legacy camera actors**.

**Developer Tools › Addon Settings › Build Settings › Camera system**:

| Choice | What it does |
|---|---|
| **Auto** (default) | Built-in cameras when this OpenGOAL supports them, else legacy |
| **Built-in** | The level `.jsonc` "cameras": preferred / cut-out volumes, flags, path cameras (OpenGOAL v0.3.4+) |
| **Legacy** | camera-marker + camera-trigger actors; works on any OpenGOAL version |

Below it the add-on says whether your OpenGOAL supports built-in cameras and what it exports as. Legacy cameras don't have **Tilt**, the orbit angles, flags, **Path** mode or volume roles.

## Camera Settings

### Mode

| Mode | What it does | Needs |
|---|---|---|
| **Fixed** (default) | Stays where the camera object is, aimed by its rotation (or a Look-At target) | — |
| **Side-Scroll** | Keeps the offset from the anchor empty to the camera, moving with Jak | **Add Anchor**: a `CAMERA_N_ALIGN` empty at the spot Jak is expected to be |
| **Orbit** | Circles around the pivot, staying on the far side from Jak | **Add Pivot**: a `CAMERA_N_PIVOT` empty at the orbit's centre |
| **Follow** | The normal gameplay camera with custom leash lengths. The camera object only marks the region | — |
| **Path** | Rides along the camera's path at the point closest to Jak (built-in only) | A **Path** with 4+ points (waypoints or a curve; see [Paths & platforms](paths-and-platforms.md)) |

A Side-Scroll or Orbit camera without its anchor / pivot, or a Path camera without enough points, exports as Fixed (the build log says so).

### Fields

| Field | Modes | Default | What it does |
|---|---|---|---|
| **Blend time (s)** | all | 1.0 | How long the switch to this camera blends |
| **FOV (degrees, 0 = default 64)** | all | 0 | Field of view; also drives the Blender camera's lens |
| **Tilt / roll (degrees, 0 = default)** | all (built-in) | 0 | Rolls the camera |
| **Max angle (degrees, 0 = none)** | Orbit (built-in) | 0 | How far the orbit may swing from its rest angle |
| **Focal pull (degrees)** | Orbit (built-in) | 0 | FOV the orbit camera blends towards as Jak moves (0 = off) |
| **Min length (m)** / **Max length (m)** | Follow | 5 / 12.5 | Leash lengths. Max must be above 0 |
| **Min height (m)** / **Max height (m)** | Follow | 1 / 3 | Camera heights |
| **Cliff height (m)** | Follow | 40 | How far the camera peeks down over ledges |
| **Follow distance (m)** | Path (built-in) | 0 | Stay this far along the path from the point closest to Jak |

**Flags (N on)** (built-in only): a list of the game's camera options, sorted into **For this mode** and **Other**, each with a short description. For example **Behind Jak**, **Collide** and **Line of sight** for Follow; **Same side**, **Drag** for Orbit; **Keep own rotation** for Path. Leave the ones marked "Runtime" or "no effect found" off.

### Look-At

**Add Look-At Target** adds a `CAMERA_N_LOOKAT` empty at the 3D cursor. The camera then ignores its own rotation and aims at the target. **Clear Look-At** removes the link. Without a target, a camera that was never rotated shows **⚠ Camera has no rotation!**

### Volumes

The trigger volumes of this camera. You can link several. With built-in cameras each volume has a role:

| Role | Meaning |
|---|---|
| **Volume** | The camera is used while Jak is inside |
| **Preferred** | Wins when several camera volumes overlap |
| **Cut-out** | The camera is NOT used while Jak is inside (cuts a hole in its volume) |

Volumes must be closed, convex meshes. More on volumes in [Volumes & triggers](volumes-and-triggers.md).

## Cameras used by actors

Some actors switch to one of your `CAMERA_` objects for a moment (a ride, a minigame, a cell being shown). Pick the camera in the actor's **Actor Settings** field, for example **Ride camera** (fisherman's boat, exit chamber), **Minigame camera** (fisher), **Dive camera** / **Second dive camera** / **Spit camera** (pelican), **Rock camera** / **Arm camera** (swamp tether rock), **Camera** per button (pipe game), **Shot camera** (periscope, yakow). Such a camera doesn't need a volume: the actor switches to it by name (the build log still warns that it has no trigger volume). Enemies can also move the camera when they attack (Attack camera fields, see [Enemies & nav-meshes](enemies-and-navmesh.md)).

## Pov-cameras (animated camera shots)

In Jak 1 a **pov-camera** is a small game process that plays a *camera animation*: a camera move animated by the original developers and stored in an art group, such as `junglecam`, `mistycam` or `sunkencam`. While it plays, the game camera follows the animation, which gives the short cutscene-like shots of the vanilla game (an ambush starting, the beam reaching the next tower, the yakows being penned). The shot is played from a point in the level; when the animation ends, the normal camera comes back.

These animations were made for the vanilla levels, so they move the same way wherever you play them. Place the shot's origin so the view lands on something useful, and test it in game.

In this add-on these actors play pov-camera shots:

| Actor | Setting (**Actor Settings**) | Shot | Played from |
|---|---|---|---|
| Battle Controller (Ambush) | **Intro camera** section: **Basic (no intro camera)** (default), **Misty ambush camera**, **Swamp ambush camera**, **Citadel ambush camera**, **Custom camera** | Plays when the ambush starts | The controller; the citadel one from its camera position |
| Periscope | **Beam shot**: **Vanilla shot: tower1** ... **tower5**, **Vanilla shot: beamcam** (or **None (Jak is free at once)** / **Linked camera**) | Plays once the periscope is on target | **Shot origin (empty)**; none: the periscope |
| Yakow | **Pen shot**: **Vanilla camera animation** (default), **Linked camera** or **None** | Plays once the whole herd is penned | **Shot origin (empty)**; none: the farmer (its alt-actor) |
| Klaww (Ogre Boss) | No setting: plays its vanilla intro shot | When the fight's intro starts | The boss |

The art group a shot needs is added to the level by the export.

### Set up a battle controller intro camera

1. Select the battle controller and open its **Intro camera** section.
2. Pick a variant:
   - **Misty / Swamp / Citadel ambush camera**: the vanilla ambush shot of that level, played at the controller.
   - **Citadel ambush camera** also needs a camera position: click **Add Camera Position** (at the 3D cursor, or at the actor with **At Actor Position** on), or shift-select an empty and click **Link → <name>**. Until then a red line says **Needs a camera position (citadelcam-1)**; without it the game crashes. It is exported as the entity `citadelcam-1`, so a level can have only one.
   - **Custom camera**: next to **Camera:** click **Pick…** and choose a camera art group (the list shows how many animations each has), then next to **Animation:** pick one of its animations. **Custom…** lets you type an **Art group** or **Animation** name. Until both are set a red line says **Pick a camera and an animation**. The shot plays at the controller when the ambush starts.
3. Controllers with the same setup share one generated type in the level's code, so several ambushes with the same shot cost nothing extra.

### Set up a periscope or yakow shot

1. Pick the vanilla shot in **Beam shot** (periscope) or set **Pen shot** to **Vanilla camera animation** (yakow).
2. Optional: add an empty where the shot should play from and pick it in **Shot origin (empty)**.

For your own camera instead of the animation, choose **Linked camera** and pick a `CAMERA_` in **Shot camera** (the yakow also has **Shot time (s)**, default 4).

A custom pov-camera actor, to play any camera animation from a trigger, may come in a later version.

---
[← Previous](level-flow.md) · [Guide index](README.md) · [Next →](volumes-and-triggers.md)
