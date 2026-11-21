# Geometry

The level's ground, walls and scenery are ordinary Blender meshes in the level's **Geometry** collection. On export
they become one file, the level GLB, which OpenGOAL's level builder turns into the drawn level and its collision.

## The Geometry collection

Every level has a **Geometry** collection (`<level>.Geometry`, ② in the [Outliner](images/outliner.png)). The
add-on makes it with the level, and it is the only place level meshes are exported from:

- Every mesh in **Geometry** and in any collection inside it is exported, selectable or not, visible or not, even
  with rendering turned off (handy for invisible walls).
- A sub-collection ticked in **Level › Collections › Disable Export** is left out, with everything in it.
- Meshes elsewhere in the level are **not** exported. **Build & Play** shows a red box
  *N mesh(es) outside Geometry aren't exported* with a **Move to Geometry** button that moves them into
  **Geometry › Solid**. **Level › Collections › Sort & Clean** does the same for the whole level.
- Helper meshes are never level geometry, wherever they are: `VOL_` volumes, `NAVMESH_` nav-meshes, `LOADBND_` load
  boundaries, water and checkpoint volumes, meshes parented to an actor, and **Export As** meshes (below).

### Sub-collections

**Solid** is where new and sorted meshes go. You can add more collections inside **Geometry** to keep things tidy.
The names don't change anything: the export treats every collection in Geometry the same way, and the
**Collision** panel (below) decides whether a mesh is drawn, collides, or both. A common setup:

| Collection | Holds | How to set it up |
|---|---|---|
| **Solid** | meshes that are drawn and collide | nothing to do (the default) |
| **Collision Only** | invisible walls, simplified floors | tick **Invisible** on the meshes (or their material) |
| **Visual Only** | decoration Jak walks through | tick **Apply Collision Properties** and **ignore** |
| **Reference** | blockouts, imported reference models | tick it in **Disable Export** so it isn't exported |

## The Collision panel

Select a mesh and open **OpenGOAL › Object Settings › Collision**. It sets how the mesh
collides and whether it is drawn. The same settings are on materials, at the top of **Properties › Material ›
Custom Properties**, so you can give a whole material (e.g. all your ice) one surface.

| Option | What it does |
|---|---|
| **Apply Collision Properties** | Use the settings below for this mesh. Off: plain ground. |
| **ignore** | No collision at all: Jak and the camera go through it. |
| **Mode** | **ground** (default), **wall** (Jak slides off) or **obstacle**. |
| **Material** | The surface Jak walks on: its footstep sounds and effects. `stone` (default), `ice`, `quicksand`, `waterbottom`, `tar`, `sand`, `wood`, `grass`, `pcmetal`, `snow`, `deepsnow`, `hotcoals`, `lava`, `crwood`, `gravel`, `dirt`, `metal`, `straw`, `tube`, `swamp`, `stopproj`, `rotate`, `neutral`. |
| **Event** | What touching it does: `none`, `deadly`, `endlessfall`, `burn`, `deadlyup`, `burnup`, `melt`. |
| **No-Edge** | Jak can't grab its edges. |
| **No-Entity** | Actors (enemies, pickups ...) don't collide with it. |
| **No-LOS** | Doesn't block line of sight (enemies see through it). |
| **No-Camera** | The camera goes through it. |
| **Invisible** | Not drawn, but still collides. |
| **Use Custom Bone Weights**, **Copy Eye Draws**, **Copy Mod Draws** | glTF options of the level builder, for meshes that use them. <!-- check: what these do for level geometry --> |

Some collision is set for the whole level in **Level › Settings › Gameplay**: **Automatic Wall Angle** (faces
steeper than this are walls, default 45°) and **Double Sided Collision**. See [Levels](levels.md#gameplay).

The **NavMesh** sub-panel below Collision is for enemy nav-meshes: see [Enemies & nav-meshes](enemies-and-navmesh.md).

## Textures

Give your meshes materials with an **Image Texture** node, as usual in Blender. The level builder takes the images
from the GLB and makes the level's own texture pages.

To use the game's own textures, open **Import › Game Textures** with a mesh selected: pick a group, click **Load**,
click a texture, then **Apply to Selected** (in Edit Mode: **Apply to Selected Faces**). It makes an `og_<texture>`
material. The textures must have been extracted by the decompiler first. See [Importing](importing.md).

### Texture Remap

Some things in the game are drawn with generic textures that each vanilla level remaps to its own: Flut Flut's eyes,
water, dark eco pools, dying enemies. **Level › Settings › Visuals › Texture Remap** picks the vanilla level whose
remap table (and texture pages) your level borrows. When an actor needs a certain one, the Level Audit warns:
*... only show with the texture source ...*. Use **None** for a level that is loaded at the same time as another
custom level: two loaded levels sharing a remap crash.

### Texture page limits

Each level has a fixed amount of memory (about 10 MB) for its geometry and its texture pages. Enemies and many
objects bring the texture page of their home level (shown in brackets in the Spawn list, e.g. *(Beach)*); the
Village and Training ones are always loaded and cost nothing. Each extra page is around 2 MB, so a level that mixes
actors from more than about two other levels can crash while loading or show missing textures. Keep the actors of a
level to one or two home levels where you can. <!-- check: no add-on warning for this; numbers from knowledge-base/research/opengoal/tpage-heap-research.md -->

## Export As

**Object Settings › Export As** turns a plain mesh into many actors: every vertex of the mesh (after modifiers)
becomes one actor of the type you pick, e.g. a row of orbs along a curve. Type in the search field and click a type
(pickups and props). The panel shows how many actors the mesh makes; **X** clears it. The mesh is moved to the
level's **Export As** collection and is not exported as geometry. Use Array, Subdivision or Curve modifiers to place
the points without touching the mesh itself.

## Level GLB size

**Build & Play › GLB Export Settings** opens the glTF exporter of the Geometry collection (**Properties ›
Collection › Exporters**). The add-on sets what the build needs on every export (GLB, Y up, custom properties, apply
modifiers, all objects); the rest, such as **Draco** mesh compression, is yours to change there.

To keep the file small, the export writes vertex colours as 8-bit (the game only keeps 8 bits anyway) and leaves out
the plain colour layer when all 8 times of day are baked. It looks the same in game. The add-on preference **8-bit
colours in every glTF export** does the same for glTF files you export by hand. For even smaller files, lower
**Color Depth** in Light Baking: see [Lighting](lighting.md).

---
[← Previous](levels.md) · [Guide index](README.md) · [Next →](actors.md)
