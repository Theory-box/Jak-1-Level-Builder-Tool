# Actor notes (after the entity pass)
Actors that still need work, don't work, or have limits worth remembering. Compiled at the end of the
entity pass (branch `claude/entity-pass`). Each actor's DB "description" has the details for the
actor itself; this file is the overview.

---

## Not done yet (no DB record, or record still missing a feature)
- **helix-button**: needs helix-water and helix-slide-door records (rising dark eco room, Sunken).
- **helix-water / helix-dark-eco** (water look 40): rises on 'trigger, Sunken-specific, uses an alt-actor list.
- **reflector-mirror**: the eye-beam mirror between periscopes (Jungle); it sends 'stop to the accordian.
- **flutflutegg**, **gorge-start**, **exit-chamber** (+ exit-chamber-button): not added.
- **precursor-arm** (swamp-arm task): the swamp blimp's link 0; no record.
- **lrocklrg / beach-rock**: seagull flock target and a 'trigger receiver; no record.
- **allpontoons**: the warrior needs one (crashes without); no record.
- **'trigger receivers without a record**: helix-slide-door, silostep, citb-stair-plat, citb-drop-plat,
  citadelcam, beach-rock. Add `"reacts_to": ["trigger"]` when they get one (button notify list).
- **citb-drop-plat**: needs a specific UI to be intuitive.
- **Particles** (part-spawner, level -part files): planned feature, see the to-do list.

## Hidden (can't work as-is; reason in the DB description)
| Actor | Why |
|---|---|
| energylava | Its art group doesn't exist |
| citb-chains | process-hidden, draws nothing |
| powercellalt | No init-from-entity!, only spawned by the 100-cell door cutscene |
| seagull | Only spawned by a Seagull Flock |
| green-sagecage | Vanilla Citadel story: fixed Z trigger, want-levels citadel finalboss |
| evilbro / evilsis | Need an "intro" tpage group (INT.DGO tpage-1454..1457) |
| sequenceA-village1 / B / C, finalbosscam | Not placeable entities |

## Working, with limits
- **Texture source** (Level settings): shared vanilla art uses texture page 983, which only its own
  level's remap translates. The audit warns (DB `"texture_sources"`):
  - Flut Flut eyes: swamp / snow.
  - Transparent / reflective water looks (water, electric, dark eco): their own level. Mud / lava looks work anywhere.
  - Tried and failed: re-pointing shaders to the real page, extra .jsonc textures, tpage in the .gd.
    A real fix needs a custom remap in build_level (C++).
- **Liquids**: mud / tar / shallow water only wade; they need ground within the wade depth. Tar only
  hurts below world Y -0.1 m (vanilla check).
- **robotboss**: its loops (charge buzz, red buzz, blue loop) fade 80 m from its origin; vanilla fights
  within ~20 m of it. Light eco sparkle particles are cut below vanilla heights (cosmetic).
- **sage-finalboss**: uses the vanilla finalboss-movies task; the credits end the game like vanilla.
- **Caged sages** (red / blue / yellow): the rescue cutscene only plays if the actor is named
  `<colour>-sagecage-1` (hard-coded process name).
- **yakow**: herding can't finish (the pen is a nav-mesh poly flag the nav-mesh export doesn't write).
- **oracle**: trades and cells work, no speech (picks its cutscene by vanilla level name).
- **swamp-blimp**: floats away without a tether rock; tether rocks need vanilla swamp-tether tasks / cameras.
- **gondola**: rides to vanilla village3 / snow.
- **pistons**: only move when the gondola sends 'update.
- **windmill-sail**: vanilla jungle-lurkerm sets its speed; no sound fields yet.
- **villageb-ogreboss**: removed once vanilla village2-levitator is done; boulder throws follow fixed paths.
- **spike**: one controller per group; the export adds the controller itself last.
- **Klaww (ogreboss)**: if goalc was already running with an older subtype it fails with
  "Inconsistent type definition"; the build now restarts goalc when a level's types change.
- **muse**: path of 11+ points (add more if it gets stuck).
- **lightning-mole**: needs a path and a nav-mesh; chain moles with next / prev (no loop).

## Keyed paths
The game can key several values of one lump by time ('path at 0 / 1 / 2 ...), but a custom
level's .jsonc holds one res tag per lump name (build_level). Actors that read keyed paths
are edited to read named paths instead (billy, pelican, snow-ball); a path keyframe set in
Blender only changes the one tag's time.

## Custom tasks on actors (for the next actor pass)
The task pickers list the .blend's custom tasks, but no actor was checked in
game with one yet. To check with a custom task: fuel-cell, buzzer
(buzzer-info: fly index + task), crates holding a cell or a fly, the oracle /
pontoon / race-ring alternate tasks, and anything with a game-task panel. Look
for: the cell / fly spawns, collecting it closes need-resolution / counts the
fly for that task, and it stays collected after a save + reload.

## Enemy drops (for the enemies pass)
Killing an enemy drops its eco (green eco pills for most): nav-enemies and some others
can drop other things. Give them the pickup picker (what they drop / how many), like
the crate contents, where their code reads it (fact-info pickup-type / pickup-amount).

## Soft warnings (required.py soft())
Required-field warnings (the red "N⚠" counts) are for things that break the game or the
build. Soft warnings (a yellow triangle count next to them, in the panel headers, next to
Export & Compile and as audit warnings) are setups that work but make an actor do less:
- a nav-enemy with no nav-mesh linked: it idles / notices Jak but can't pathfind
- its nav-mesh: separate parts (enemies can't path between them), jump areas that don't
  join two walkable areas (enemies stop at them)
Add more per actor during the actor checks.

## Sound bank requirements (DB "sounds")
Each actor record lists the sounds it plays that aren't in the common bank (`"sounds"`,
101 actors). They come from its code (sound-play / sound specs / its particle groups'
sounds, following the helper functions its states call and its parent types, from the
game's goal_src; `tools/scan_sounds.py`) and from its art groups (animation effect sounds,
e.g. babak-roar, lurkbat-wing: most enemy sounds). Which bank holds each sound comes from
BankSFX; a sound in several banks needs any one of them. When the level loads none of
them: a soft warning "sound bank X not loaded: no ...". Rerun the scan (and
tools/sound_db.py) when actors are added. Art strings are matched against the
known sound names, so an animation / joint named like a sound can give a false one.

## Older notes from the earlier passes
- gnawer: orb vertex list + vanilla cell / camera positions.
- balloonlurker: boat-fuelcell.
- darkvine, robber: clamp values.
- green-eco-lurker: a crash was reported, not reproduced.
- plat-button: camera link.
- wall-plat: triggered mode.
- minecart: show its path in Blender.
- eco door "starts open" (needs a subtype per door type); sun-iris-door scale-factor from the Blender scale.
- lumps that should become fields; Blender 5 collision export.

## Edited actors (addons/opengoal_tools/subtypes, export/edited.py)
An actor's DB record names its default edited file (`"edited": "<file stem>"`); each file's
header says why. Child types are exported as `<level>-<stem>` (in the level's -obs.gc) or
`lt-<stem>` (Shared file: `goal_src/levels/level-tools/edited/lt-<stem>.gc`, compiled once,
listed in each using level's .gd); files without `(deftype __TYPE__` are patches (the actor
keeps its etype). Per actor, GOAL Code > Code picks the default, Vanilla, or a file of the
Custom code folder (Preferences / this .blend's folders; `;; edits: <etype>` header = which
actors it's for, `;; place: shared` = default place).

| File | What it changes |
|---|---|
| water-anim | flat water surface for floating / splashing actors (no look) |
| fireboulder | hover sound for every boulder |
| ogreboss | editable intro / fight distance / continue point, actor task, end task |
| warp-gate-switch | warp menu for custom levels |
| lightning-mole | hole at its peeper, "Appears" option, cell mode (peeper movie-pos) |
| robotboss (patch) | yellow shot / light eco at the boss's height |
| sage-finalboss | ending without vanilla positions / final door |
| dark-plant / happy-plant | own task, any link shape (vanilla froze on plants linked both ways) |
| muse | catching it gives its own task's cell |
| sage / assistant / gambler / geologist / minershort | cutscenes without the level-unloading commands |
| explorer | talks from anywhere |
| mayorgears | turns always / once / until its task is complete |
| assistant-firecanyon / assistant-lavatube-end / sage-villagec / assistant-villagec / bird-lady | own task or a cell count, no level-unloading commands, talk from anywhere |
| warrior | no crash without allpontoons |
| fisher | own task, minigame spot / camera from Blender |
| energyhub | no crash, own task |
| cavespatula | works outside darkcave |
| snow-switch / snow-fort-gate / snow-bumper / sunken-pipegame / gorge-pusher / swamp-tetherrock | own tasks instead of the vanilla ones, cameras from Blender |
| billy | own task, named paths path / pathb / pathc, no Boggy Swamp kill lists |
| pelican | named paths (path, dive, to-nest, from-nest, spit, dive-b, to-nest-b, run-away), dive camera from Blender, no fixed camera spot |
| snow-ball | named paths path / pathb, shrinks at its track's end (not below 200 m), no junction timing |
| fishermans-boat | kinematic boat: path out, pathb back (or path backwards), ride camera or the vanilla ride cutscenes (load boundaries off meanwhile), task gate, saved end |
