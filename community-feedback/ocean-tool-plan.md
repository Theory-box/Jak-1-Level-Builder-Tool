# Custom ocean map tool — plan

Branch `claude/ocean`. Based on the to-do list's section ("driven by its position / size and materials; each
section has a way to select the level of detail for how precise you want to be") and the research in
`_claude_tmp/ocean_research.md` (game source: engine/gfx/ocean/*, ocean-tables.gc, level-info.gc, water.gc).

## What the research found

1. **The ocean is only a picture.** It is a flat, endless water surface drawn every frame. It has no collision, and
   swimming, wading, drowning and the underwater camera all come from **water volumes** (`water-vol`), as now.
2. **One fixed grid per map.** A map covers a square of 48 × 48 cells of 96 m (4608 m a side). Its only placement
   setting is the square's corner (x, z). Beyond the square, a 1440 m ring of "far" ocean in one colour.
3. **Detail comes from the camera, not the map.** The game picks how finely to draw by camera distance: 768 m tiles
   far away, 24 m pieces within ~136 m, 3 m quads with real wave heights within ~34 m (only when the camera is
   near the sea). The map can't ask for more or less detail in an area.
4. **What the map does say: where there is ocean**, at three precisions: per 96 m cell, per 24 m piece, and per 3 m
   square (that's how vanilla cuts the ocean around Sandover's beach and docks). Plus **colours**: one per 96 m
   grid point (2548 of them), blended between points, and the far colour.
5. **Sea level is always y = 0.** The engine overwrites the map's height every frame (vanilla: 0, or a few fixed
   exceptions). Another sea level needs an engine change.
6. **Textures and waves are shared by every map** (one global wave animation, textures already in GAME.CGO), so a
   custom level can use them as they are. No per-map texture or wave shape without engine changes.
7. **How a level picks it:** `level-info :ocean`. The game checks it every frame (not once at load like moods), so a
   custom map can live in the level's own code (no full build). `'none` hides the ocean while the camera is in
   the level; `#f` (what the add-on's **None** writes today) leaves a neighbour level's ocean showing.
8. **Cost is bounded:** masks only remove work, so a custom map can't cost more than the full vanilla sunken map.
   About 25 KB per map.

## Proposal

### Ocean objects

A new **Ocean** object type (Spawn Objects › Level Flow, or its own entry): a flat mesh (a plane, or any outline
seen from above) in the level's **Ocean** collection, not exported as geometry. Each one:

| Setting | What it does |
|---|---|
| **Mode** | **Ocean** (adds water) or **Cut out** (removes it: islands, a lake that should be dry, under a building). Cut-outs win over oceans. |
| **Precision** | Your "level of detail" note: how exactly its outline is followed. **Coarse (96 m cells)**, **Medium (24 m)**, **Fine (3 m)**. Coarse is cheapest to store; Fine follows a shoreline closely (like vanilla's beaches). Edges are rounded to that size. |
| **Colour** | From its **material** (base colour) by default, or its own colour, with a **Brightness**. Colours blend between neighbouring areas like vanilla's. |

The meshes' outlines are seen from above (their height doesn't matter: the sea is at y = 0, see the limit below).

### Level settings (Level › Settings › Visuals › Ocean)

- **Ocean**: None, **Hidden** (new: `'none`, also hides a neighbour level's ocean), Village 1, Village 2, Sunken,
  **This level's ocean** (generated from the Ocean objects), Custom.
- With **This level's ocean**: **Far colour**, and the grid's **Position**: automatic (centred on the Ocean objects)
  or set by hand. A warning if the objects don't fit in the 4608 m square.

### Preview in Blender

The ocean as the game will draw it, shown in the viewport (drawn like the race-ring circles, not objects): the
covered cells at each precision and the square's outline. Recomputed only when an Ocean object changes
(performance first).

### Export

`(define *<level>-ocean-map* (new 'static 'ocean-map ...))` in the level's own code: the masks and indices
computed from the objects' outlines (rasterised at 3 m, then grouped into 24 m and 96 m like vanilla's data, shared
entries de-duplicated), the colours sampled at each 96 m point, the cull spheres. `:ocean` points at it.

### Swimming

The ocean doesn't make Jak swim. Two helpers:
- **Water volumes: Follow ocean waves** (the game's `wt08` flag, not offered today): the water surface moves with
  the waves.
- **Make Water Volume from Ocean** (button on an Ocean object): a water volume covering it at sea level.

## Limits (without changing the engine)

- Sea level is y = 0. (An engine patch could add a per-level height later.)
- One map per level, 4608 m square plus the far ring.
- Same waves and textures as vanilla; colours and far colour only.

## Steps (each tested in game before the next)

1. **Hidden** option (`'none`) and **Follow ocean waves** on water volumes (small, useful at once).
2. Ocean objects (mode, precision, colour) + the map export with full cells only (Coarse), level setting
   **This level's ocean**. In game: a custom ocean shape.
3. Medium and Fine precision (24 m / 3 m outlines), cut-outs.
4. Colours from materials, far colour, automatic / manual position, the viewport preview, warnings.
5. Make Water Volume from Ocean, guide (on guide-next).

## Questions

1. Your updated to-do notes for the ocean aren't on GitHub yet (the file still has the two lines above). Could you
   push them? I'll fold them into this plan.
2. **Level of detail** — is it what I took it to be (how exactly the outline is followed), or something else?
3. Sea level fixed at y = 0: fine for now, or should a per-level sea height (an engine change) be part of this?
4. **Cut out** mode and **Make Water Volume from Ocean**: wanted?
