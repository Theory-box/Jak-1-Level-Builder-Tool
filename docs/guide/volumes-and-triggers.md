# Volumes & triggers

A **volume** is a mesh whose name starts with `VOL_`. It is never drawn and has no collision: it marks an area. What
happens in that area depends on what the volume is linked to: a camera switches, a checkpoint is set, an enemy wakes
up, water appears, a task stage closes. **Load boundaries** (`LOADBND_`) are a different object that loads and shows
levels as Jak walks between them: see [Level flow](level-flow.md#load-boundaries).

Volumes live in the level's **Triggers** collection (⑤ in the [Outliner](images/outliner.png)).

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
| **Camera** (`CAMERA_`) | The camera is used while Jak is inside. With built-in cameras each link has a role: **Volume**, **Preferred** (wins when camera volumes overlap) or **Cut-out** (cuts a hole in the camera's area). | [Cameras](cameras.md#volumes) |
| **Checkpoint** (`CHECKPOINT_`) | Becomes the current checkpoint when Jak enters. One volume per checkpoint. | [Level flow](level-flow.md#trigger-sphere-or-volume) |
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

---
[← Previous](cameras.md) · [Guide index](README.md) · [Next →](audio.md)
