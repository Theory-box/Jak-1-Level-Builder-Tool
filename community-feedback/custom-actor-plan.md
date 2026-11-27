# Custom art group / actor / camera — plan

Branch `claude/custom-actors`. Based on Kuitar's notes (ToDo ordered List.md, "Custom art group/actor/camera
implementation"), the official guide (https://opengoal.dev/docs/developing/custom_levels/custom_actors) and the
research in `_claude_tmp/custom_actor_research.md` (OpenGOAL's build-actor source, the game code, upstream issues).

## What the research found

### How OpenGOAL builds a custom actor
1. A `.glb` in `custom_assets/jak1/models/custom_levels/<name>.glb` (the file name is the art group's name).
2. `(build-actor "<name>" ...)` in `goal_src/jak1/game.gp` makes `<name>-ag.go`: the skeleton (`<name>-lod0-jg`),
   a placeholder model entry (`-lod0-mg`), the animations (`-<action>-ja`, from slot 2, in the glb's order) and,
   with `:gen-mesh #t`, collision meshes. Newer versions also take `:framerate`, `:texture-bucket`,
   `:master-art-group`, `:joint-channel` (v0.3.2+).
3. The model itself (mesh + its textures, embedded PNGs: no tpages) goes into the level's FR3 when the level's
   `.jsonc` lists it in `custom_models` (or into the common FR3 from `custom_assets/jak1/models/common/`, to be
   seen in every level). The level's `.gd` lists `<name>-ag.go`.
4. GOAL code: `(def-actor <name> :bounds ... :art (...) :joints (...))` makes the skeleton group and the
   animation constants; a `deftype` (a `process-drawable`, or a child of `plat` / `nav-enemy` ...) with
   `init-from-entity!`, states and collision. Without code the actor still shows, playing its first animation
   (the game's `viewer-process`).

### Blender side (what the export must respect)
- glb, +Y up, 1 unit = 1 m. One armature, root bone first; only bones may be animated (an animated armature or
  mesh object crashes the build). Every mesh skinned, every vertex weighted, **3 bones per vertex** at most.
- Each action = one animation, named after the action; 60 frames per second unless `:framerate` (v0.3.2+).
- Limits: about **100 bones**, 2 MB per art group, **255 vertices per collision mesh** (the build crashes above).
- Collision meshes come from objects with collision custom properties (the OpenGOAL Blender plugin's), exported
  with **Custom Properties** on.

### The bone / vertex group problem (Kuitar's note)
Found in OpenGOAL's source: PR #4371 (merged 2026-07-31, in **v0.3.6** and later, so also our v0.3.8 and the
current v0.3.9) changed one line of the shared glTF code (`joints + 2` → `joints + 1`) for the decompiler's export,
but build-actor still needs `+ 2`. Result: **every vertex follows the bone before its own** (the first bone's
vertices follow the root). Skeleton and animations are fine. v0.3.5 and older are correct. Nobody has reported
it upstream yet. Options:
- the add-on shifts the bone indices in the exported glb by one on v0.3.6+ (the add-on already knows the
  install's version), removed once upstream is fixed (to be tested: the last bone's index then points one past
  the end, which the tool doesn't seem to check);
- report it upstream (with the one-line fix) — **I'd only do that with your OK**, it's posting publicly;
- or wait for the fix.

### Custom cameras
A camera animation is an art group with a bone named `camera`: the view looks down its -Z (Y up), its X scale
sets the FOV (scale 1 = about 72.7°). Animations named `<group>-<anim>`. Our Camera animation actor and the pov
picker already accept a custom group, so a custom camera only needs the art group.

## Step 1 results (in game, mod-base v4.1.4 = OpenGOAL v0.3.8, Blender 4.4)

Test models built by script (`_claude_tmp/ca/`), added to a test level by hand, checked with queries and the
game's own screenshot (`pc-screen-shot`, saved in `%APPDATA%/OpenGOAL/jak1/screenshots`):
- **Pipeline works:** glb in `custom_levels`, `(build-actor ...)`, `custom_models`, `<name>-ag.go` in the `.gd`;
  without code the actor shows (viewer-process) playing its first animation. A model with no armature works too.
- **The bone shift is real** (each vertex follows the bone before its own). **Fix that works**, done on the
  exported glb only (`_claude_tmp/ca/glb_fix.py`): add one joint at the end of the skin, a child of its last
  joint, with still animation channels in every animation, then +1 on every vertex's bone indices. Without that
  end joint (or without its channels) the last bone's vertices end up in the sky. On by default for v0.3.6+,
  with a setting to turn it off (Kuitar).
- **Several skinned meshes break** (only the last one is placed right), with or without the fix — another
  upstream problem. Workaround: the export joins the actor's meshes into one (a temporary copy). Checked: one
  joined mesh + the fix = every part on its bone.
- **Animations:** bone rotation and translation keys both work; actions are resampled to 60 fps (a 60-frame
  action at 24 fps = 150 game frames); bones without keys in an action stay still.
- **Colours:** without a texture, the material colour is ignored (default texture); vertex colours (COLOR_0)
  are used. The add-on should export the active colour attribute and say so.
- **Collision:** `set_invisible` hides a collision-only mesh, `set_collision` + `ignore` keeps a visible mesh out
  of the collision (the add-on's level collision properties). Whether the collide mesh works needs actor code
  (step 3).
- Custom camera bone: left for step 4 (camera template).

## Step 2 results

- Development install: **OpenGOAL v0.3.5** (official release, before PR #4371), `test-v0.3.5`; newer versions
  are checked once upstream fixes the bone shift (Kuitar). Meshes are never joined (several meshes are needed for
  collision on different bones).
- In game on v0.3.5, through the add-on (OpenGOAL Actors tab, Place in Level, level build): one actor with a
  single skinned mesh and one with three separate skinned meshes both show every cube on its bone; the bone fix
  stays off (Auto, release < 0.3.6).

## Step 3 results (Basic actor, in game on v0.3.5)

- Generated code in the level's `-obs.gc`: `deftype <name>` (process-drawable), `def-actor` (bounds, the exported
  animations), an idle state looping the first animation, an optional play state on 'trigger (one animation,
  then back to idle), collision: none / the Collision meshes (`:gen-mesh`, one prim per mesh) / a sphere.
- Checked in game: both actors run their idle state; 'trigger switches to the play state; Jak stands on the
  collision box (mesh) and on the sphere. Collision is one-sided: a box with inward faces lets Jak through (the
  panel now notes it: Recalculate Outside).
- Guide note (Kuitar's setup): on an OpenGOAL release, custom level actors only show with the game's
  "all actors" option on.

## Step 4 results (Camera animation, in game on v0.3.5 and mod-base v0.3.8)

- **Make Camera Rig**: an armature with a still `root` bone and a `camera` bone under it, and a Blender camera
  (in `<name>.Camera`, not exported) that copies the bone's location / rotation, its focal length driven by the
  bone's X scale. **Set FOV** sets and keys that scale (`sx = 0.73603 / tan(fov / 2)`).
- The `camera` bone must not be the first bone: the game's first skin joint is a matrix joint, whose scale it
  never fills (FOV read as 180°, a black screen). Hence the root bone and a red check.
- No mesh needed: the export adds a 1 mm triangle on the camera bone (a skin is needed for the joints).
- The pov picker lists the custom cameras; the level defines `def-actor` + `*og-pov-<name>-sg*`, bundles
  `<name>-ag.go` and lists it in custom_models (not in an actor's art groups: those must be the game's).
- Checked in game: the camera sat exactly where the bone was (8 m out, 3 m up), looked where the rig camera
  looked, FOV 50° read back as 50°.

## Proposal

### Its own sidebar tab
Blender handles this fine: a second tab, **OpenGOAL Actors**, next to **OpenGOAL** in the 3D view's sidebar
(panels just use another category). Everything for custom actors lives there.

### Collections
**Add Custom Actor** makes a **Custom Actors** collection (not part of any level, never exported as level
geometry) with one sub collection per actor: `<name>` › **Model** (meshes + armature), **Collision**
(optional, simple meshes), **Camera** (camera template). The tab's top picks the active custom actor, like the
level picker.

### Panels (OpenGOAL Actors tab)
- **Custom Actors**: the list, Add / Duplicate / Delete, **Export This / All** (writes the glb + game.gp entry; a
  level build also does it for the actors it uses).
- **Settings**: **Name** (the art group, `<name>-ag`), **Template** (below), **Bounds** (auto from the model,
  editable; too small and it vanishes early), **Loaded**: with the levels that place it, or everywhere (common).
- **Art group**: the armature, **Animations** (from its actions: include / order / which is idle, frame rate),
  texture bucket. Checks shown as warnings: bones over 100, vertices with more than 3 weights (button: limit to
  3), unweighted vertices, unskinned meshes, animated objects, the 2 MB size, the bone shift above.
- **Collision** (optional): from the Collision collection's meshes: mode / material / event per mesh, the
  255-vertex check (a Decimate button), or simple spheres on bones.
- **Template settings** (per template, below).
- **GOAL code**: the generated code, and your own on top (a text block, like actors' GOAL Code).

### Templates (Kuitar's list)
| Template | What it makes |
|---|---|
| **Art group** | Only the art group (glb + build-actor + skeleton description), for use from your own code or other actors. |
| **Basic actor** | A `process-drawable` with an idle state playing an animation, optional collision; options: animation on 'trigger, loop / once, hide / show. |
| **Platform** | A `plat` child with your model and collision: it gets the add-on's platform settings (path, sync, ...) like the vanilla platforms. |
| **Camera animation** | The art group of a camera animation (a `camera` bone, FOV from its scale): pickable in the Camera animation actor and the actors' camera choices. A Blender camera follows the bone for previewing. |
| **Nav enemy** | A `nav-enemy` child: its `nav-enemy-info` (speeds, notice / attack distances ...) set in Blender, and which animation is idle / walk / run / notice / attack / hit / die. |

### In levels
Custom actors show in **Spawn Objects** (their own tile, **Custom Actors**) and are placed like any actor. A
level build adds what they need: `custom_models`, `<name>-ag.go` in the `.gd`, the `build-actor` line, and the
actor's code (shared `lt-` file like the edited actors, so several levels reuse it).

## Steps (each tested in game before the next)
1. **Research checks in game** (no UI yet): build a small skinned, animated glb by hand on v0.3.8, confirm the
   bone shift and test the index fix; static model, animation, collision mesh; a custom camera bone.
2. The **OpenGOAL Actors** tab, collections, **Art group** template, glb export with the checks and the bone fix,
   build-actor / `custom_models` / `.gd` wiring, a Custom Actors tile in Spawn Objects. In game: a custom model
   placed in a level, animated.
3. **Basic actor** template (GOAL code, states, collision).
4. **Camera animation** template (+ Blender preview, pov picker).
5. **Platform** template.
6. **Nav enemy** template.
7. Guide (on guide-next).

## Questions
1. The tab: **OpenGOAL Actors** next to OpenGOAL — OK? (another name?)
2. The bone shift on v0.3.6+: fix it in the add-on's export (until upstream fixes it), wait, or both? And may I
   report it upstream (an issue on open-goal/jak-project with the cause and the one-line fix)?
3. Which template after the art group: Basic actor first as above, or another order?
4. Custom actors in the same .blend as the levels (own collection) — or should they be able to live in separate
   .blends (one per actor) and be used from a level's .blend?
