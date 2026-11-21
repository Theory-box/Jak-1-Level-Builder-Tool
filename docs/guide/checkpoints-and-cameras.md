# Checkpoints & cameras

Checkpoints say where Jak starts and respawns. Cameras replace the normal follow camera in parts of your level. Hints show a line of text when Jak gets close. All three are under **Spawn Objects** (**Level Flow** and **Cameras** tiles).

## Checkpoints (continue points)

A checkpoint is a cone empty named `CHECKPOINT_<level>_<name>`. In game it is a *continue point* called `<level>-<name>`: where Jak spawns when the level starts, when he dies, or when the game loads a save there.

### Add one

1. Put the 3D cursor where Jak should stand.
2. **Spawn Objects › Level Flow › Checkpoint › Spawn**. A dialog asks for a **Name** (blank = the next free one).
3. Rotate the cone around Z to set the way Jak faces.

The level's first checkpoint is called **start**: that's where Build & Play spawns. The next ones are **cp1**, **cp2** ... Names use a–z, 0–9 and `-`, and must be unique in the level.

### Checkpoint Settings

Select the checkpoint and open **Object Settings › Checkpoint Settings**.

| Option | What it does |
|---|---|
| **Name** | The checkpoint name (continue point `<level>-<name>`). Changing it renames the object, its `_CAM` anchor and the volume links. **start** is where Build & Play spawns |
| Camera anchor | **✓ ..._CAM** with select / delete buttons, or **⚠ No camera anchor** and **Add Camera** (see below) |
| **Trigger** | Off: a plain continue point, chosen by load boundaries, death or code. On: an invisible trigger makes this the current checkpoint when Jak walks into it |
| Trigger volume | With Trigger on and no volume: **⚠ No trigger volume (fallback r=3.0m)** — Jak must come within 3 m. **Add Trigger Volume** adds a linked box, or link an existing `VOL_` mesh (**Link → VOL_...** / **Search volume…**). A linked volume also turns the trigger on |
| **Respawn Loads** | The levels kept loaded when Jak respawns here (see below) |
| **Vis Nickname** | Vis nick set on respawn (blank = this level's nickname). Also used for music / menu context |
| **Advanced › Continue Flags** | Toggles for the vanilla continue-flags (hover each for what it does). Most are for vanilla sequences: Warp, Demo, Intro, Sage Intro, Title, Game Start ... |
| **Advanced › Load Commands** | Commands run when Jak respawns here |

#### Respawn Loads

When Jak respawns (a teleport), the game rebuilds the set of loaded levels from these two slots only. Load boundaries handle streaming while walking, not on death.

| Slot | Choices | Display mode |
|---|---|---|
| **Load Level 0** | **(This level)** (default), any level of the project, **Custom…** (type a name in **Name 0**) | **Display** (default), **Special**, **Off (load only)** |
| **Load Level 1** | **(None)** (default), any level of the project, **Custom…** (**Name 1**) | **Off (load only)** by default |

Use slot 1 for a neighbouring level that should already be there after a respawn. See [Levels](levels.md) and [Volumes & triggers](volumes-and-triggers.md) for load boundaries.

### The respawn camera (`_CAM` anchor)

When Jak respawns, the camera starts at the checkpoint's anchor. Select the checkpoint and click **Add Camera** in Checkpoint Settings: an arrows empty `CHECKPOINT_..._CAM` is placed 6 m behind and 3 m above the checkpoint, aimed at it, and parented to it (it moves with the checkpoint). Move and rotate it as you like; the camera looks along the empty's -Z.

Without an anchor the camera starts 4 m above the checkpoint. Selecting the anchor shows **Anchor Info** (which checkpoint it belongs to).

### Booting straight into the spawn

The **Spawn** dropdown in **Build & Play** (③ in the [Build & Play screenshot](images/build-play.png)) picks the checkpoint the game starts at. Normally the game boots and then Jak is teleported there.

With a **mod-base** install you can tick **Boot into spawn (mod-base)**: builds write the spawn into `engine/mods/mod-settings.gc` (`*debug-continue-point*`), so the game boots straight there. On jak-project releases and dev clones the option is shown off, with the reason. Boot modes and the retail checkpoints are in [Build & Play](build-and-play.md) and [Levels](levels.md).

## Cameras

A camera is a Blender camera named `CAMERA_0`, `CAMERA_1` ... It does nothing until a trigger volume is linked to it: while Jak is inside the volume, the game uses this camera.

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

### Built-in vs legacy cameras

Newer OpenGOAL versions (v0.3.4 and later) have built-in camera entities in the level file; older ones only have the add-on's legacy camera actors. The top of Camera Settings tells you which one you're using: **Built-in camera entity** or **Legacy camera actors**.

**Developer Tools › Addon Settings › Build Settings › Camera system**:

| Choice | What it does |
|---|---|
| **Auto** (default) | Built-in cameras when this OpenGOAL supports them, else legacy |
| **Built-in** | The level `.jsonc` "cameras": preferred / cut-out volumes, flags, path cameras (OpenGOAL v0.3.4+) |
| **Legacy** | camera-marker + camera-trigger actors; works on any OpenGOAL version |

Below it the add-on says whether your OpenGOAL supports built-in cameras and what it exports as. Legacy cameras don't have **Tilt**, the orbit angles, flags, **Path** mode or volume roles.

### Camera Settings

**Mode**

| Mode | What it does | Needs |
|---|---|---|
| **Fixed** (default) | Stays where the camera object is, aimed by its rotation (or a Look-At target) | — |
| **Side-Scroll** | Keeps the offset from the anchor empty to the camera, moving with Jak | **Add Anchor**: a `CAMERA_N_ALIGN` empty at the spot Jak is expected to be |
| **Orbit** | Circles around the pivot, staying on the far side from Jak | **Add Pivot**: a `CAMERA_N_PIVOT` empty at the orbit's centre |
| **Follow** | The normal gameplay camera with custom leash lengths. The camera object only marks the region | — |
| **Path** | Rides along the camera's path at the point closest to Jak (built-in only) | A **Path** with 4+ points (waypoints or a curve; see [Paths & platforms](paths-and-platforms.md)) |

A Side-Scroll or Orbit camera without its anchor / pivot, or a Path camera without enough points, exports as Fixed (the build log says so).

**Fields**

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

**Look-At**: **Add Look-At Target** adds a `CAMERA_N_LOOKAT` empty at the 3D cursor. The camera then ignores its own rotation and aims at the target. **Clear Look-At** removes the link. Without a target, a camera that was never rotated shows **⚠ Camera has no rotation!**

**Volumes**: the trigger volumes of this camera. You can link several. With built-in cameras each volume has a role:

| Role | Meaning |
|---|---|
| **Volume** | The camera is used while Jak is inside |
| **Preferred** | Wins when several camera volumes overlap |
| **Cut-out** | The camera is NOT used while Jak is inside (cuts a hole in its volume) |

Volumes must be closed, convex meshes. More on volumes in [Volumes & triggers](volumes-and-triggers.md).

Enemies can also move the camera when they attack (Attack camera fields, see [Enemies & nav-meshes](enemies-and-navmesh.md)), and a Battle Controller can play an intro camera.

## Hints

A hint is a sphere empty `AMBIENT_hint001` ... that shows a text at the top of the screen when the camera gets close, once per save.

1. **Spawn Objects › Level Flow › Hint › Spawn** (at the 3D cursor).
2. In **Object Settings › Hint**, type the **Text** and set the **Radius** (default 10 m; the sphere's size follows it).

| Option | What it does |
|---|---|
| **Text** | Shown at the top of the screen (once per save). Can use game text names (see [Tasks](tasks.md)) |
| **Voice line** | Optional: a vanilla voice line played instead of the text (search button lists them with speaker and words). Needs the game's Hints option on |
| **Radius** | Shown when the camera is this close |
| **Commands** | **Add Command**, then pick a command and a **Task**. "If ..." commands are checks (a failed one skips the hint): **If task hidden**, **If task known**, **If task done**, **If at need-introduction** ... "Close ..." commands close one of the task's stages when the hint shows (**Close need-hint** shows the task in the menu) |

A hint with no text isn't exported. Its text goes into the level's game text with the task names.

---
[← Previous](enemies-and-navmesh.md) · [Guide index](README.md) · [Next →](volumes-and-triggers.md)
