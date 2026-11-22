[↑ OpenGOAL Level Tools — User Guide](README.md)

# Enemies & nav-meshes

Enemies are actors like any other (see [Actors](actors.md)): spawn them from **Spawn Objects › Enemies**. This page covers what is special about them: nav-meshes, waking up and aggro, drops, ambushes and bosses.

## Two kinds of enemies

The database sorts every enemy under a parent type, and the parent decides which panels it gets:

| Kind | Examples | Moves with | Panels |
|---|---|---|---|
| **Nav-enemy** (parent `nav-enemy`) | babak, hopper, lurker crab, kermit, snow bunny, swamp rat, ram boss | a **nav-mesh** (where it may walk) + a **path** (its patrol) | NavMesh, Nav Behaviour (with Trigger Behaviour), Drop, Path |
| **Process-drawable enemy** | bully, puffer, flying lurker, mother spider, swamp bat, junglesnake | its own code: a path, or nothing at all | Path (when it uses one), sometimes activation fields; nav-mesh only for some, no aggro triggers |

The [Actor list](actor-list.md) marks every enemy that needs a nav-mesh (**nav-mesh**) or a path (**path**). When you pick a nav-enemy in Spawn Objects, it says **Nav-enemy, needs navmesh and path** above the Spawn button.

A nav-enemy without a nav-mesh still works: it idles and notices Jak, but it can't chase him. You get a grey (soft) warning **no nav-mesh: it idles / notices Jak but can't pathfind** (see the ⚠ counts, ② in the [actor screenshot](images/actor.png)). Paths are explained in [Paths & platforms](paths-and-platforms.md).

## Nav-meshes

A nav-mesh is a simple, flat-ish mesh that covers the floor a nav-enemy may walk on. The game reads it as triangles: enemies find their way from triangle to triangle across shared edges. You don't see it in game.

### Make one

**From your level's floor (quickest)**

1. Select a mesh of your level (a floor or a whole area).
2. Open **Object Settings › NavMesh**. In the **Make a nav-mesh from faces** box, set **Max slope** and **Height** if you like.
3. Click **From All Faces**. Or go into Edit Mode, select the faces you want and click **From Selected Faces**.
4. A new mesh `NAVMESH_<name>_nav` appears in the level's NavMeshes collection. Faces steeper than **Max slope** (walls) are left out, the faces are merged, triangulated and raised a little.
5. Change the settings in Blender's **Adjust Last Operation** panel (bottom left) to see the result update. It shows **Result: N triangles** and turns red above 255.

| Option | Default | What it does |
|---|---|---|
| **Max slope** | 45° | Faces steeper than this are left out (walls) |
| **Height** | 0.03 m | Raised this much above the faces so they don't overlap |
| **Decimate** | 1.0 | Simplify the result (1 = keep every triangle). Only in Adjust Last Operation |
| **Reduce to the limit** | on | Simplify the result to the game's 255 triangles if it has more |

**By hand**

Model a low-poly mesh over the walkable floor, then select it and click **Mark as NavMesh** in **Object Settings › NavMesh** (the NavMesh Tag box). This adds the `NAVMESH_` prefix, moves it to the NavMeshes collection and gives it the nav materials. **Unmark as NavMesh** undoes it (the mesh goes back to Geometry / Solid).

Linking any mesh to an enemy (below) also turns it into a nav-mesh.

### Link it to enemies

Select the enemy and open **Object Settings › Actor Settings › NavMesh**:

- Shift-select the nav-mesh too and click **Link → NAVMESH_...**, or
- click **Search navmesh…** and pick one (meshes that aren't nav-meshes yet are marked so; linking one makes it a nav-mesh).

The panel then shows **✓ NAVMESH_...** with an **X** to unlink, a bin to unlink and delete the mesh (it asks first and
says how many other actors use it), and its triangle count.

### Share one mesh between several enemies

Many enemies can stand on the same nav-mesh. If you link the same mesh to several enemies, the NavMesh panel warns that the mesh *is built once per actor*. Click **Make other connected actors use this as nav-mesh-actor**: the other enemies lose their direct link and get a `nav-mesh-actor` link to this one instead, so the mesh is exported once.

### Jump faces (NAV materials)

Every nav-mesh gets three materials. In Edit Mode, assign faces to them:

| Material | Colour | Meaning in game |
|---|---|---|
| **NAV Walk** | blue | Normal walkable floor |
| **NAV Jump** | teal | A gap: nav-enemies jump across these triangles. Be aware that not all nav-enemies can jump and might crash when trying. |
| **NAV Special** | green | Special area: the lurker shark's water area, the yakow pen |

The colours match the game's own nav-mesh viewer. In **Object Settings › Navmesh Info**, the **Jump faces** box has **Add Nav Materials** (when a slot is missing) and a button that switches the mesh between a plain wire and coloured, see-through faces.

A jump area should touch walkable floor on both sides, otherwise enemies stop at it.

### Nav-spheres

Nav-spheres are round areas the mesh's enemies steer around (a pillar, a tree). Open the **Nav-Spheres (N)** sub-menu (in Navmesh Info, and in the enemy's NavMesh panel):

- **New** adds a sphere empty `NAVSPHERE_...` at the 3D cursor.
- **Add Empty** uses an existing empty.
- The radius is the empty's display size × its scale (shown as **r ... m**). **X** removes it from the list (the empty stays); the bin also deletes the empty.

None by default.

### Limits and warnings

Select the nav-mesh and open **Object Settings › Navmesh Info**. It lists the enemies that use it, the triangle count and any problems.

Errors (red; also counted on the enemies that use it):

| Message | Fix |
|---|---|
| **N triangles: the game allows 255 at most** | Click **Reduce to 255 Triangles** (keeps jump / special faces), or decimate it yourself |
| **N vertices: the game allows 255 at most** | Simplify the mesh |
| **N triangle(s) with no area or standing up (skipped)** | Delete or fix those faces |
| **N edge(s) shared by 3+ triangles (only 2 are joined)** | Make the mesh manifold: one edge, at most two faces |
| **only jump (gap) triangles: needs walkable ones** | Put some faces back on NAV Walk |

Triangles that face down are flipped for you on export.

Soft warnings (they work, but enemies can't use all of the mesh):

| Message | Meaning |
|---|---|
| **N separate parts: enemies can't path from one to another** | Islands no edge joins. Fine on purpose, otherwise join them |
| **N jump area(s) not joining two walkable areas: enemies stop at them** | A dead-end jump: a NAV Jump area must lie between two walkable areas |

### Fields in the enemy's NavMesh panel

| Field | Default | What it does |
|---|---|---|
| **Nav-mesh snap height (m)** | -1 | How far above / below the nav-mesh the actor can be and still find its place on it. -1 = the actor's own default (10 m for most enemies) |
| **Max nav-mesh users** | 32 | How many actors can use this actor's nav-mesh at once (actors linking it with nav-mesh-actor, spawned enemies) |

Some enemies also show **Can jump (usable as a battlecontroller lurker)**, and a few have a **Move speed (x)** field.

### Nav-mesh system

**Developer Tools › Addon Settings › Build Settings › Nav-mesh system** decides how meshes are written:

| Choice | How it works |
|---|---|
| **Current (entity.gc)** (default) | Each linked actor gets its mesh by actor id in the game's `entity.gc`, rebuilt every export |
| **custom-nav (TFL)** | The Forgotten Lands' way: each level's meshes go in `goal_src/levels/<level>/<level>-nav.gc`, loaded with the level; actors pick one with a `custom-nav` lump, and `entity.gc` gets a fixed hook once |

You don't need to change it. custom-nav keeps each level's meshes in its own file and writes each mesh once.

## Nav Behaviour: waking up and aggro

**Object Settings › Actor Settings › Nav Behaviour** holds the activation fields and, for nav-enemies, the aggro triggers.

| Field | Default | What it does |
|---|---|---|
| **Idle distance (m)** | 80 | Jak must be closer than this for the enemy to leave idle |
| **Notice height (m)** | 1000 | Jak is only noticed / chased while he is lower than the enemy's height + this (nav-enemies) |
| **Notice depth (m)** | 1000 | The below-the-enemy counterpart; no vanilla code uses it yet |
| **Attack camera range (m)** | -1 (off) | When this enemy attacks Jak within this range, Jak looks at it and the camera uses the two fields below |
| **Attack camera height (m)** | 0 | While attacked, the camera rises to at least this height |
| **Attack camera distance (m)** | 0 | While attacked, the camera pulls back to at least this distance |

### Aggro triggers (Trigger Behaviour)

A trigger volume can tell nav-enemies what to do when Jak walks into it, for example wake a whole group at once.

1. Select the enemy, open **Nav Behaviour** and click **Add Aggro Trigger**. A box volume appears at the enemy (red-orange), already linked.
2. Move and scale it over the area Jak should enter. It must stay a closed, convex mesh.
3. Pick the behaviour in the dropdown next to the volume's name.

To use an existing volume, shift-select it and click **Link → VOL_...**, or use **Search volume…**. One volume can trigger many enemies, and one enemy can have many volumes, each with its own behaviour. The volume's own panel (**Volume Links**) shows the same dropdown per enemy; see [Volumes & triggers](volumes-and-triggers.md).

| Behaviour | What the enemy does |
|---|---|
| **Aggro (chase player)** (default) | Wakes up and starts chasing Jak |
| **Patrol** | Returns to its patrol |
| **Wait for cue (freeze)** | Freezes until the next cue |

Process-drawable enemies don't react to these, so they don't get this section.

## Enemy drops

Enemies that drop something when they die have a **Drop** box in Actor Settings:

| Field | What it does |
|---|---|
| **Change Drop** | Off: the vanilla drop (random green eco pills) |
| **Drop** | Nothing, Green Eco Pills (Random), Green Eco Pills, Orbs, Green / Blue / Red / Yellow Eco |
| **Amount** | 1–99. For random green eco pills: extra pills on top of the random 3 to 5 |

A nav-enemy can also carry a power cell: **Options › Has power cell**, with the cell's task in its **Game Task** panel (see [Tasks](tasks.md)).

## Battle Controller (ambushes)

**Battle Controller (Ambush)** (Spawn Objects › Enemies) is the lurker ambush from Misty Island, Boggy Swamp and the Citadel. When Jak comes within 30 m it spawns lurkers along its spawn paths until enough have been beaten.

Paths (in its **Path** panel):

- The main **path** (required: the game crashes without it) is the lurkers' patrol.
- **patha** to **pathh** are spawn paths (at least one, max 8): a lurker spawns at the first point and jumps along the rest.
- **pathspawn**: one lurker is placed on each point at the start.

Give it a nav-mesh too, so the lurkers can walk.

Settings, in **Object Settings › Actor Settings › Battle Controller**:

| Section | Options |
|---|---|
| **Intro camera** | **Intro camera**: Basic (no intro camera), Misty / Swamp / Citadel ambush camera, Custom camera. Custom: pick a **Camera** art group and an **Animation**. Citadel: needs a camera position (**Add Camera Position**, **At Actor Position**); it is exported as the entity `citadelcam-1` (one per level) |
| **Lurkers spawn** | **Max alive at once** (12), **Total to beat** (35; very high, e.g. 1000, means the spawn blockers must be destroyed instead), **Time between spawns (s)** (0.1); links to spawn path blockers and spawn path actors |
| **Lurker info** | **Add Lurker** (enemies that can jump, max 4). Each: **Spawn chance**, **Special eco chance**, **Special eco**, **Max special eco**. **Split Evenly** sets the chances to add up to 1.0. None added: the game spawns babaks. Then **Normal drop** and **Normal drop amount** |
| **End pickup** | **Spawn a pickup at the end** (on) and **End pickup** (Power Cell by default: it uses the **Game Task**, and plays at the **Movie Position** if set) |
| **Other options** | Links: turned off while the ambush is on, triggered when it starts, faded out when it is over, triggered when it is completed (open doors ...). **Spawn lurkers before Jak arrives** |

The lurkers' code and art are added to the level for you. Variants other than Basic write a small battlecontroller type into the level's code.

## Bosses

Klaww (**ogreboss**), the **Plant Boss** and the **Precursor Robot Boss** are under Spawn Objects › Enemies (marked **boss** in the [Actor list](actor-list.md)). Klaww and the robot boss are edited actors: they are exported as level subtypes so they work in a custom level. See [Edited actors & GOAL code](edited-actors-and-goal-code.md) and each actor's description in Object Settings.

---
[← Previous](paths-and-platforms.md) · [Guide index](README.md) · [Next →](level-flow.md)
