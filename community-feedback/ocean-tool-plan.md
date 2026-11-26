# Custom ocean map tool — plan

Branch `claude/ocean`. Kuitar's notes (ToDo ordered List.md, "Custom ocean map creation tool") combined with the
research in `_claude_tmp/ocean_research.md` (game source: engine/gfx/ocean/*, ocean-tables.gc, level-info.gc).

## What the research found (answers to the notes' questions)

- **The grid is fixed.** Every map is 48 × 48 cells of 96 m (4608 m a side), drawn as 6 × 6 big squares of 768 m
  (8 × 8 cells each). The count and sizes are hard-coded, so no "squares per side" setting. Beyond the grid, a
  1440 m ring of **far** ocean in one colour.
- **start-corner** is the grid's corner (x, z). It can be anywhere, so a map far from the origin is just a corner
  far away. We can make the **centre** editable and work out the corner. Its y (height) is ignored: the engine
  puts the sea at **y = 0** every frame (another sea level needs an engine change).
- **ocean-mid-masks**: 8 bytes = 8 × 8 bits, one bit per 96 m cell of a big square. **A set bit = no ocean** there
  (inverted from what the note guessed).
- **ocean-mid-indices**: one per big square (36): which mask it uses. **-1 = no ocean at all** in it. A square
  whose cells are all ocean points at an all-zero mask (vanilla keeps one as entry 0).
- **ocean-trans-indices** and **ocean-near-indices**: finer edges. Close to the camera each 96 m cell is drawn as
  4 × 4 pieces of 24 m, and very close as 3 m quads. These tables say which 24 m pieces / 3 m quads of an edge
  cell are water (how vanilla follows Sandover's shore closely). With edges at 96 m only, they are computed
  automatically ("all water" for every ocean cell). Finer edges are an option for later (see Steps).
- **ocean-spheres**: one per big square (36): x, z = its centre, last value = its radius (768 m × √2 / 2). They
  let the game skip squares the camera can't see. Computed automatically.
- **ocean-colors**: one colour per grid **point** (49 × 49, at the cells' corners), blended across each cell.
  0x80 = full brightness.
- **The level picks a map every frame** (not once at load like moods). `:ocean 'none` hides the ocean while in the
  level; the add-on's current **None** (`#f`) leaves a neighbour level's ocean showing.
- **The waves and textures are shared** by every map (already in GAME.CGO): no per-map texture or wave shape.
- **The ocean is only a picture.** Swimming and drowning come from water volumes, as now.

## The Oceans panel

Like Moods and Tasks: an **Oceans** panel under Moods. **Add Ocean Map** makes a block (collapse, Export,
Duplicate, Delete), named from the selected level (`<level>-ocean`). **Level › Settings › Visuals › Ocean** gets the
same button as Mood / Mood Function to pick one of this .blend's oceans (and a new **Hidden** choice, see below).

### Each ocean map

**General** (top, not in a sub menu):
- **Name** (the map is `*<name>-ocean-map*`).
- **Far colour**: the ocean beyond the grid. Default: the most used vanilla ocean colour, #1F3242 (also
  Rock Village's and Lost Precursor City's far colour).
- **Template from a game ocean…**: fills the grid mesh below from village1, village2 or sunken (its water / no
  water squares and its colours), to edit from there.

**Grid** (sub menu, collapsed):
- **Grid mesh**: a mesh object the add-on makes, 48 × 48 faces of 96 m (one face per cell), in the level's Ocean
  collection (not exported as geometry), drawn at y = 0. **Make Grid Mesh** creates it; moving the object moves
  the ocean (its centre is the map's centre, so maps can be far from the origin). It can't be scaled or rotated
  (warning if it is).
- The 6 × 6 big squares are outlined in the viewport so you see what the game groups.

**Water** (sub menu, collapsed), Kuitar's mid-masks + mid-indices:
- **From**: a vanilla map, or **Own (materials)**.
- Own: like nav meshes, two materials on the grid mesh: **Ocean water** (blue) and **No water** (black,
  see-through). Assign them to faces in Edit Mode; the masks, indices (including the -1 / all-water squares),
  trans / near tables and spheres are all made from them at export. Buttons: **Fill all with water**, **Clear**,
  **Cut out selected meshes** (faces under the selected objects, seen from above, become No water: islands,
  the level's ground).

**Colour** (sub menu, collapsed):
- **From**: a vanilla map, or **Own (colour attribute)**.
- Own: an `OceanColor` colour attribute on the grid mesh's points (49 × 49), starting at the far colour. Paint it in
  Vertex Paint, or **Fill** with a colour. The game blends between points the same way.

Each part (water / colour) can come from a vanilla map while the other is your own, since the game keeps them in
separate tables.

### Export

Like moods: one file of its own, `goal_src/jak1/levels/level-tools/lt-oceans-<blend>.gc`, with every exported
ocean map (`(define *<name>-ocean-map* (new 'static 'ocean-map ...))` and its tables), registered once.
Vanilla parts point at the game's tables (no copy). The level's `:ocean` points at its map.

### Other changes

- **Ocean › Hidden** (`'none`): no ocean while in this level, even if a neighbour level has one. **None** stays
  "no ocean of its own".
- **Water volumes: Follow ocean waves** (the game's `wt08` flag): the water surface moves with the ocean's waves.

## Limits (without changing the engine)

- Sea level y = 0; grid 48 × 48 cells of 96 m; one map per level; vanilla waves and textures.
- Edges follow 96 m cells (step 5 adds finer edges if wanted).

## Steps (each tested in game before the next)

1. **Hidden** choice and **Follow ocean waves** on water volumes.
2. Oceans panel, Make Grid Mesh, water from materials (masks, indices, spheres; trans / near "all water"), Far
   colour, export file, level setting button. In game: a custom ocean shape.
3. Colours (colour attribute), vanilla parts (From a vanilla map), Template from a game ocean, Cut out selected
   meshes, the big squares' outline.
4. Warnings (scaled / rotated grid, level outside the grid, ocean with no water volume), guide (on guide-next).
5. (Optional, if wanted) finer edges: a **Fine edges** option that follows an outline at 24 m / 3 m inside edge
   cells (the trans / near tables), like vanilla's shores.

## Questions

1. Grid mesh with one face per 96 m cell (materials = water / no water, colour attribute on its points): OK?
2. Export in its own GAME.CGO file like moods (a full build when an ocean changes): OK? (The game reads the map
   every frame, so it could also go in the level's own file: level-only builds, but one copy per level using it.)
3. Finer edges (step 5): wanted, or are 96 m cells enough?
