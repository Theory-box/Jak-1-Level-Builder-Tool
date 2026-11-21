# Volumes & triggers

A **volume** is a mesh whose name starts with `VOL_`. It is never drawn and has no collision: it marks an area. What
happens in that area depends on what the volume is linked to: a camera switches, a checkpoint is set, an enemy wakes
up, water appears, a task stage closes. **Load boundaries** (`LOADBND_`) are a different object that loads and shows
levels as Jak walks between them.

Volumes and load boundaries live in the level's **Triggers** collection (⑤ in the [Outliner](images/outliner.png)).

## Make a trigger volume

1. **Spawn Objects › Triggers › Trigger volume** adds a 4 m wireframe cube `VOL_<n>` at the 3D cursor. If a camera,
   checkpoint or other linkable object was the active object, the new volume is linked to it straight away.
2. Move, scale and edit the mesh to cover the area. It must stay **convex** (no dents) with its normals facing out
   (**Mesh › Normals › Recalculate Outside**). Rotated and odd shapes are fine.
3. Link it: select the volume and open **Object Settings › Volume Links**. Shift-select a target and click
   **Link → <name>**, or use **Search target…**.

You can also start from the target: checkpoints, enemies and actors with a volume have **Add Trigger Volume**,
**Add Aggro Trigger** or **Add Volume** buttons, plus **Link → VOL_...** for a selected volume and **Search volume…**.

The volume renames itself after its links: `VOL_<target>` with one link, `VOL_<n>_<count>links` with more,
`VOL_<n>` with none. Links to deleted objects are removed on export.

### Volume Links panel

| Item | What it does |
|---|---|
| **Links (N)** | Every link of the volume, with an icon for its kind. A red *missing* line means the target was deleted or renamed. |
| behaviour drop-down | Only on enemy links: what the enemy does when Jak enters (see below). |
| magnifier | Selects and frames the target. |
| **X** | Removes this link. |
| **Link → <name>** | One button per shift-selected object that can take a link. |
| **Search target…** | Pick any target in the level by name. |
| **Clear All Links** | Removes every link of the volume. |
| **Task actions** | Close or open task stages when Jak enters (below). |

A volume with no links and no task actions exports nothing; the Level Audit warns about it.

## What a volume can be linked to

| Target | What the volume does | More |
|---|---|---|
| **Camera** (`CAMERA_`) | The camera is used while Jak is inside. With built-in cameras each link has a role: **Volume**, **Preferred** (wins when camera volumes overlap) or **Cut-out** (cuts a hole in the camera's area). | [Checkpoints & cameras](checkpoints-and-cameras.md) |
| **Checkpoint** (`CHECKPOINT_`) | Becomes the current checkpoint when Jak enters. One volume per checkpoint. | [Checkpoints & cameras](checkpoints-and-cameras.md) |
| **Nav-enemy** | Sends the enemy an event when Jak enters. An enemy can have several volumes. | [Enemies & nav-meshes](enemies-and-navmesh.md) |
| **Actor with a Volume panel** | The volume is the actor's own area: water, the swamp bat's area, an Actor Light's area, Helix dark eco ... | [Actors](actors.md) |
| **Custom type actor** | Sends `trigger` on enter and `untrigger` on exit to your own GOAL type. | [Edited actors & GOAL code](edited-actors-and-goal-code.md) |

### Enemy behaviour (aggro triggers)

Only nav-enemies (the ones that patrol and chase on a nav-mesh) react to volumes. The enemy's own panel lists them
under **Trigger Behaviour**, with **Add Aggro Trigger** to make one at the enemy. Each link picks:

| Behaviour | What the enemy does when Jak enters |
|---|---|
| **Aggro (chase player)** | Wakes up and chases Jak (default) |
| **Patrol** | Goes back to patrolling |
| **Wait for cue (freeze)** | Freezes until the next cue |

One volume can link several enemies, and an enemy can have several volumes with different behaviours (e.g. one to
start the chase, one to send it back).

### Actor volumes

Actors that read an area of their own have a **Volume** sub-panel in **Object Settings**:

- **Add Volume** makes a 4 m cube at the actor, linked to it.
- With a mesh shift-selected: **Use <mesh> as volume** turns it into a `VOL_` volume linked to the actor.
- **Link → VOL_...** and **Search volume…** link an existing volume.

Most actors only use one volume: with more, a red line says *Only the first volume is exported*.

### Task triggers

Any volume can change tasks when Jak enters it. In **Volume Links › Task actions** click **Add Task Action**, then
pick **Close** or **Open**, the **Stage** and the task. The actions run every time Jak enters. This works with or
without links. See [Tasks](tasks.md).

## Water

**Spawn Objects › Volumes** has two water objects:

- **Water volume**: an invisible water area (swim, wade).
- **Water Anim**: water with a vanilla look (its mesh and ripples) or **No look**. Pick the look before spawning.
  Floating and splashing actors (Misty's ogre isles and steps, square platforms) can link it as their water. The look
  meshes keep their vanilla size, so scale and place the volume to match.

Both add an actor; give it its area with **Add Volume** in its **Volume** panel (or link a convex mesh). Its
settings are in **Object Settings › Water Volume Settings**:

| Field | What it does |
|---|---|
| **Water surface Y (m)** | Height of the surface. Locked by default: it is kept at the **top of the linked volume**, so you just move the volume. Click the lock to type it yourself; **Sync Surface from Volume Top** then sets it once. |
| **Wade depth (m)** | How deep below the surface Jak starts wading. Default 0.5. |
| **Swim depth (m)** | How deep below the surface Jak starts swimming. Default 1.0. |
| **Liquid** | **Water (wade, swim, drown)**, **Shallow water (wade only)**, **Deep water (swim only)**, **Mud (slows)**, **Tar (sinks + hurts; only near world Y 0)**, **Lava (instant death)**, **Dark eco (instant death)**, **Electric water (hurts)**. |

Mud, tar and shallow water only let Jak wade: put ground under the surface within the wade depth or he sinks through
(vanilla mud is about 0.5 m deep). On **Water Anim** the look sets some of these (shown with a lock, *set by the
look*). Transparent looks (water, electric, dark eco) only show with the matching **Texture Remap** (see
[Geometry](geometry.md#texture-remap)); mud and lava looks work anywhere.

## Load boundaries

A load boundary tells the game to load, show or hide levels when Jak (or the camera) crosses it. This is how vanilla
streams from one level into the next without a loading screen. Use them when your .blend has several levels next to
each other, or to connect your level to a vanilla one.

1. **Spawn Objects › Level Flow › Load Boundary** adds `LOADBND_<n>` at the 3D cursor: a 4 m line.
2. Shape it in Edit Mode. An **edge or polyline** is a vertical wall (crossing it fires the commands). A **flat face**
   with **Closed Area** on is an area.
3. Select it and open **Object Settings › Load Boundary**. Set the **Forward** and **Backward** commands.

In the viewport the boundary is drawn as a wall or filled area with arrows (a viewport-only modifier, not exported).
**Forward** is crossing in the direction of the mesh normal, **Backward** the other way.

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
| **Load** | **Level 0**, **Level 1** | Loads these two levels (the game holds two at a time) |
| **Display** | **Level 0**, **Mode** | Shows a loaded level: **Display**, **Display (no wait)**, or **Off** to hide it |
| **Vis** | **Nick** | Switches to a level's visibility data (its vis nickname) |
| **Force Vis** | **Level 0** | Forces a level's visibility data to load |
| **Checkpoint** | **Continue** | Sets the checkpoint (a continue name like `my-level-start`) without any loading |

The level fields offer **(None)**, **(This level)**, the levels of this .blend and **Custom…** (type a name, e.g. a
vanilla level). Load boundaries are written into the game's shared `load-boundary-data.gc`; each level only replaces
its own entries.

## Level flow between levels

To let Jak walk from one level into another:

1. Both levels need their own name, **Level Index** and vis nickname, and a **Bounding Sphere** or checkpoints that
   cover them (see [Levels](levels.md)). Give them different **Texture Remap** settings, or **None** for one.
2. Before the border, a boundary with **Load** (this level + the next one) loads the next level.
3. At the border, boundaries with **Display** show the level ahead (and **Off** hides the one behind), and **Vis**
   switches the visibility data.
4. Give each checkpoint **Respawn Loads** so a death or a continue loads the right levels: see
   [Checkpoints & cameras](checkpoints-and-cameras.md).

Commands that run when the level itself loads go in **Level › Settings › Others › Commands**.
<!-- check: recommended boundary setup order (load / display / vis) against a tested two-level example -->

---
[← Previous](checkpoints-and-cameras.md) · [Guide index](README.md) · [Next →](audio.md)
