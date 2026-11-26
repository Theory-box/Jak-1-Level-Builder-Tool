[↑ OpenGOAL Level Tools — User Guide](README.md)

# Oceans

The ocean is the water drawn around a level out to the horizon, like Sandover's sea. A level picks one in
**Level › Settings › Visuals › Ocean** (see [Levels](levels.md)): one of the game's, none, or one you make in the
**Oceans** panel (OpenGOAL tab, under Moods).

The ocean is only a picture: it has no collision, and Jak can't swim in it. For swimming, add **Water Volumes**
where the sea is (see [Volumes & triggers](volumes-and-triggers.md)); their **Follow ocean waves** option makes the
water surface move with the ocean's waves.

## How the game's ocean works

- An ocean map is a fixed grid of **48 × 48 cells of 96 m** (4608 m a side), grouped in **6 × 6 squares of 768 m**.
  Around it, out to the horizon, the **far** ocean in one colour.
- The sea is always at **height 0** (Blender Z = 0).
- Each cell has ocean or not, and the colour is set at each grid point, blended across the cells.
- How finely the water and its waves are drawn depends only on how close the camera is.
- The waves and textures are the same for every ocean.

## Level › Settings › Visuals › Ocean

| Choice | What it does |
|---|---|
| **None** | No ocean of its own. A neighbour level's ocean still shows while it is loaded. |
| **Village 1**, **Village 2**, **Sunken** | The game's oceans (Sandover's, Rock Village's, Lost Precursor City's). |
| **Custom** | Type an ocean map's name. The button next to **Ocean** picks one of this file's ocean maps. |
| **Hidden** | No ocean while the camera is in this level, not even a neighbour level's. |

Warnings under it (grey unless said):
- **The ocean is only a picture: add a Water Volume for swimming** — the level has an ocean but no water volume.
- **'…' reaches past the ocean grid** — part of the level is outside the 4608 m square: only far ocean there.
- Red: **No ocean map of this file has that name** / **… isn't exported** — the level's ocean map is missing.

They can be ignored in **Developer Tools › Warning Settings**.

## The Oceans panel

**Add Ocean Map** adds a map named after the active level (it is `*<name>-ocean-map*` in the game). Each map is a
block with **Export**, **Duplicate** (copies its grid mesh too) and **Delete**:

| Setting | What it does |
|---|---|
| **Name** | The map's name. |
| **Template from a game ocean…** | Fills the grid mesh from village1, village2 or sunken: its water / no water cells, colours and far colour. The grid stays where it is. |
| **Far colour** | The ocean beyond the grid. Default #1F3242, the game's most used ocean colour. |
| **Loaded** | **Always loaded**: in the game's code (like moods), one copy for every level; a change means a full build. **With its levels**: in the code of each level that uses it; level-only builds. |

**Grid** (sub-menu):
- **Make Grid Mesh** makes the grid: 48 × 48 faces of 96 m at Z = 0, centred on the 3D cursor, in the level's
  Ocean collection (not exported as geometry). Move it to move the ocean (oceans far from the origin are fine).
  It can't be scaled or rotated. The 768 m squares are outlined in light blue in the viewport.

**Water** (sub-menu): **Own** (from the grid mesh) or one of the game's maps.
- Faces with the **OG Ocean Water** material have ocean; faces with **OG Ocean No Water** (black, see-through)
  don't.
- **All Water** / **Clear**: every cell. In Edit Mode on the grid, **Selected: Water** / **Selected: No Water** set
  the selected faces.
- **Cut Out Under Selected Objects** (Object Mode): cells under the selected objects (their bounding boxes, seen
  from above) get no water: islands, the level's ground.

**Colour** (sub-menu): **Own** or one of the game's maps.
- Own: the grid mesh's **OceanColor** colour attribute, one colour per grid point (paint it in Vertex Paint;
  Material Preview shows it). 128 is full brightness, as in the game. **Fill with the Far Colour** resets it.

Water and colour can each come from a game map while the other is your own.
