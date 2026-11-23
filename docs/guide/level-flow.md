[↑ OpenGOAL Level Tools — User Guide](README.md)

# Level flow

How the player moves through your level and between levels: checkpoints say where Jak starts and respawns, load boundaries load and show levels as he walks, and hints show a line of text when he gets close. All of them are on the **Spawn Objects › Level Flow** tile.

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

### Trigger sphere or volume

A checkpoint with **Trigger** on becomes the current checkpoint when Jak reaches it. Without a volume that means coming within 3 m of the cone (the fallback sphere). For a bigger or odd-shaped area, click **Add Trigger Volume** and shape the box; it must stay convex. One volume per checkpoint. How volumes work in general is in [Volumes & triggers](volumes-and-triggers.md).

### Respawn Loads

When Jak respawns (a teleport), the game rebuilds the set of loaded levels from these two slots only. Load boundaries handle streaming while walking, not on death.

| Slot | Choices | Display mode |
|---|---|---|
| **Load Level 0** | **(This level)** (default), any level of the project, **Custom…** (type a name in **Name 0**) | **Display** (default), **Special**, **Off (load only)** |
| **Load Level 1** | **(None)** (default), any level of the project, **Custom…** (**Name 1**) | **Off (load only)** by default |

Use slot 1 for a neighbouring level that should already be there after a respawn. See [Levels](levels.md) and [Load boundaries](#load-boundaries) below.

### The respawn camera (`_CAM` anchor)

When Jak respawns, the camera starts at the checkpoint's anchor. Select the checkpoint and click **Add Camera** in Checkpoint Settings: an arrows empty `CHECKPOINT_..._CAM` is placed 6 m behind and 3 m above the checkpoint, aimed at it, and parented to it (it moves with the checkpoint). Move and rotate it as you like; the camera looks along the empty's -Z.

Without an anchor the camera starts 4 m above the checkpoint. Selecting the anchor shows **Anchor Info** (which checkpoint it belongs to). The anchor only sets where the camera starts; cameras that take over while Jak plays are on the [Cameras](cameras.md) page.

### Booting straight into the spawn

The **Spawn** dropdown in **Build & Play** (③ in the [Build & Play screenshot](images/build-play.png)) picks the checkpoint the game starts at. Normally the game boots and then Jak is teleported there.

With a **mod-base** install you can tick **Boot into spawn (mod-base)**: builds write the spawn into `engine/mods/mod-settings.gc` (`*debug-continue-point*`), so the game boots straight there. On jak-project releases and dev clones the option is shown off, with the reason. Boot modes and the retail checkpoints are in [Build & Play](build-and-play.md) and [Levels](levels.md).

## Load boundaries

A load boundary tells the game to load, show or hide levels when Jak (or the camera) crosses it. This is how vanilla streams from one level into the next without a loading screen. Use them when your .blend has several levels next to each other, or to connect your level to a vanilla one.

1. **Spawn Objects › Level Flow › Load Boundary** adds `LOADBND_<n>` at the 3D cursor: a 4 m line.
2. Shape it in Edit Mode. An **edge or polyline** is a vertical wall (crossing it fires the commands). A **flat face** with **Closed Area** on is an area.
3. Select it and open **Object Settings › Load Boundary**. Set the **Forward** and **Backward** commands.

In the viewport the boundary is drawn as a wall or filled area with arrows (a viewport-only modifier, not exported). **Forward** is crossing in the direction of the mesh normal, **Backward** the other way. Load boundaries live in the level's **Triggers** collection (⑤ in the [Outliner](images/outliner.png)).

| Field | What it does |
|---|---|
| **Closed Area** | Off: the points are a wall. On: a flat area (the first face). |
| **Player Cross** | On: fires when Jak crosses. Off: when the camera crosses. |
| **Top** / **Bottom** | Height of the wall above / below the line, in metres (default 400 / -400). Top must be above Bottom. |
| **Flip** / **Wireframe** | Viewport only: flip the drawn wall and arrows, draw it as wires. |
| **Forward (cross +normal)** / **Backward (cross -normal)** | The command for each direction (below). |
| **Custom Flags** | Advanced: extra load-boundary flag names your OpenGOAL build knows. |

Commands:

| Command | Fields | What it does |
|---|---|---|
| **(None)** | | Nothing in this direction |
| **Load** | **Level 0**, **Level 1** | Loads these two levels, each into a slot (the game holds two at a time) |
| **Display** | **Level 0**, **Mode** | Shows a loaded level: **Display**, **Display (no wait)**, or **Off** to hide it |
| **Vis** | **Nick** | Switches to a level's visibility data (its vis nickname): that level becomes the current level |
| **Force Vis** | **Level 0** | Forces a level's visibility data to load |
| **Checkpoint** | **Continue** | Sets the checkpoint (a continue name like `my-level-start`) without any loading. The field lists this .blend's checkpoints and the game's as you type; any other name can be typed too. |

The level fields offer **(None)**, **(This level)**, the levels of this .blend and **Custom…** (type a name, e.g. a vanilla level). Load boundaries are written into the game's shared `load-boundary-data.gc`; each level only replaces its own entries.

## Level flow between levels

To let Jak walk from one level into another:

1. Both levels need their own name, **Level Index** and vis nickname, and a **Bounding Sphere** or checkpoints that cover them (see [Levels](levels.md)). Give them different **Texture Remap** settings, or **None** for one.
2. Place the boundaries along the way, in this order of commands:
   1. **Load** (this level + the next one): puts the next level into a slot. Do it well before the border, so it has time to load.
   2. **Display** the next level: makes it visible.
   3. **Vis** with the next level's nickname: makes it the current level.
   4. Optional: once Jak is in the new level, **Display** with **Off** for the previous level hides it, which helps performance.
3. Set the **Backward** commands too, so walking back does the same in the other direction.
4. Give each checkpoint **Respawn Loads** so a death or a continue loads the right levels (see [Respawn Loads](#respawn-loads)).

Commands that run when the level itself loads go in **Level › Settings › Others › Commands**.

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
[← Previous](enemies-and-navmesh.md) · [Guide index](README.md) · [Next →](cameras.md)
