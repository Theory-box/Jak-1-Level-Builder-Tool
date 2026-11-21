# User documentation rewrite — plan (waiting for Kuitar)

Current state: README.md + knowledge-base/manual/ (written for addon 2026.5.12, out of date: wrong
panels, old workflows, 156 actors / 9 categories). knowledge-base/research/ are developer notes.

## Layout
New folder `docs/guide/`, every page linked from its index and with prev / next links. Root README.md
becomes a short intro (what it is, requirements, install link, "Start here" link to the guide).
The old knowledge-base/manual/ moves to knowledge-base/archive/ (research/ stays as developer notes).

### Part 1 — Basics (read in order)
1. `install.md` — Blender version, OpenGOAL (release / dev clone / mod-base), installing the zip,
   Preferences paths, Re-check Versions, extracting game models / textures for previews, updating.
2. `first-level.md` — step-by-step: create a level, add a ground mesh to Geometry, a checkpoint,
   a few actors (orb, crate, platform with a path, an enemy), Build & Play, walking around.
3. `interface.md` — tour of the sidebar tabs (Build & Play, Level, Spawn Objects, Object Controls,
   Object Settings, Light Baking, Tasks, Import, Developer Tools), the level's collections, object
   naming (ACTOR_ / VOL_ / CHECKPOINT_ ...), the ⚠ warning counts and the Level Audit.
4. `build-and-play.md` — Export & Compile vs Build & Play vs Quick Export, boot modes, launching at a
   checkpoint, GOALC / the game window, the log, what a full compile is, common build errors.

### Part 2 — Features (one page per area, any order)
- `levels.md` — Level Manager (several levels per file, rename, delete), Settings (name, index, vis
  nick, mood, sky / textures, fog, death plane, orb count), Collections + Disable Export, Project
  Settings (retail / New Game / Quit checkpoints, Discord status), export filter.
- `geometry.md` — Geometry sub-collections (Solid / Collision Only / Visual Only / Reference), collision
  settings, textures (Game Textures, texture pages / limits), Export As collection, GLB size.
- `actors.md` — Spawn Objects (search, categories, favourites, variants), the actor empty and its
  preview, Actor Settings (generic fields), Entity Links, Options, Visibility, Movie Position, Game
  Task, Custom Lumps + Lump Reference, Export As, Convert Entities, Set to Floor, Export Selected
  Definitions.
- `paths-and-platforms.md` — waypoints, Add Curve, path modes (linear / smooth / Bézier), extra
  paths, Sync (period / phase / ease), Distribute Along Curve, place on path, race rings.
- `enemies-and-navmesh.md` — nav-meshes (Make Nav-Mesh, jump / special faces, nav-spheres, Reduce,
  sharing), Nav Behaviour (activation, aggro triggers), drops, battle controller.
- `checkpoints-and-cameras.md` — checkpoints / continue points, the start spawn, camera types and
  modes, camera volumes, hints.
- `volumes-and-triggers.md` — VOL_ meshes and Volume Links, water volumes, trigger volumes, load
  boundaries and level flow.
- `audio.md` — sound banks, music bank / zones / flava, sound emitters, bank warnings.
- `lighting.md` — Light Baking (bake, options, combine, domain, curve, blur), time of day (lights,
  worlds, frames, emit per time), Color Quantisation + fixes, Color Depth, Vertex Colors tools
  (copy lighting / alpha, effects, delete, float to byte), Actor Light.
- `tasks.md` — Tasks tab: custom tasks, power cells / scout flies, game text, task-gated actors.
- `edited-actors-and-goal-code.md` — edited actors (DB / custom code folder, obs vs shared),
  GOAL Code blocks, custom types, Export As.
- `importing.md` — Game 3D Models, Game Textures, From GOAL Files (.jsonc / game files).
- `developer-tools.md` — paths, versions + override, database override, custom code folder,
  reload, logs.

### Part 3 — Reference
- `troubleshooting.md` — every warning explained (red / yellow ⚠), crashes and their usual causes,
  FAQ (replaces known-issues.md).
- `glossary.md` — actor / etype / lump / DGO / tpage / mood / time of day / nav-enemy ...
- `actor-list.md` — generated from the database: every spawnable actor per category with its
  one-line description (regenerated each release by a small script).

## Style
- Short task-first pages: "what it is", "how to", then "all the options" tables.
- UI names in **bold** exactly as in the addon; paths written as Tab › Panel › Field.
- Screenshots: I can't take them (no screen capture on this PC), so pages get `<!-- screenshot: ... -->`
  markers where one would help; Kuitar / TheoryBox can add images later in docs/guide/images/.
- Facts checked against the current code (not the old manual).
