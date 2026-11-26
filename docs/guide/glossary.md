[↑ OpenGOAL Level Tools — User Guide](README.md)

# Glossary

Short definitions of the words OpenGOAL modding and this guide use, in alphabetical order.

---

**-obs.gc** — The GOAL code file the add-on writes for each level, `goal_src/jak1/levels/<level>/<level>-obs.gc`.
It holds the code of the level's triggers and edited actors and is compiled with the level. "obs" is the game's own
name for a level's object code (`village-obs.gc` ...).

**Actor / entity** — Something placed in a level that the game runs: an enemy, a platform, a crate, an NPC. In the
game's files it's an *entity* (a record with a type, a position and lumps); when the level loads, each
entity-actor starts a process that does the work. In Blender each actor is an empty named `ACTOR_<etype>_<name>`.
See [Actors](actors.md).

**Actor id (aid)** — The number that identifies an actor in the game. The add-on numbers a level's actors from its
**Base Actor ID** (**Level › Settings › Others**, default 10000), so each level needs its own range. The current
nav-mesh system finds each actor's nav-mesh by its id.

**Ambient** — A non-actor entity: sound emitters, music zones, hints (`AMBIENT_` empties). See [Audio](audio.md).

**Art group** — An actor's model, skeleton and animations, in a file named `<name>-ag.go`. A level must load the art
group of every actor it uses; the add-on adds them to the level's .gd for you.

**Base Actor ID** — See *Actor id*.

**bsphere** — Bounding sphere: a centre and radius around something. A level's bsphere (**Level › Settings › Others**)
tells the game where the level is; without one the add-on computes it from the checkpoints. Entities have one too.

**Checkpoint** — A `CHECKPOINT_` empty: a place the player can start or respawn. Each one exports as a
continue point. The one named `start` is where **Build & Play** spawns you. See
[Level flow](level-flow.md).

**Continue point** — The game's name for a checkpoint, written into `level-info.gc` as `<level>-<name>` (for example
`my-level-start`). It also says which levels must be loaded when you respawn there.

**custom_assets** — The folder `custom_assets/jak1/levels/<level>/` in your OpenGOAL data folder, where the add-on
writes each level's `.jsonc`, `.glb` and `.gd`.

**custom-nav** — The other nav-mesh system (from The Forgotten Lands): each level's nav-meshes in `<level>-nav.gc`,
picked by a `custom-nav` lump. See [Developer Tools](developer-tools.md).

**Custom lump** — A lump you add by hand in **Object Settings › Custom Lumps**, for settings the add-on has no field
for. See [Actors](actors.md).

**Death plane** — The height below which Jak dies from falling (**Level › Settings › Gameplay › Death Plane (m)**).

**Decompiler / decompiler_out** — The OpenGOAL tool that unpacks the original game. Its output folder
`decompiler_out/jak1/` holds the game's models (GLB), textures (PNG) and entity files the **Import** tab reads.

**DGO / .gd** — A DGO is the archive the game loads for a level (all its code, art groups and textures). The `.gd`
file lists what goes into it; the add-on writes one per level, named after its vis nickname (`<nick>.gd`).

**Edited actor** — A vanilla actor whose code the add-on changes so it works in a custom level (for example an NPC
that used a hard-coded task or position). See [Edited actors & GOAL code](edited-actors-and-goal-code.md).

**Entity** — See *Actor / entity*.

**etype** — Entity type: the GOAL type name of an actor, such as `babak`, `plat-eco` or `crate`. It's the middle part
of an actor's object name.

**game.gd / GAME.CGO** — The files the game always loads. Code and art groups in them don't need to be in your
level's `.gd` (Developer Tools › **Ignore game.gd files**).

**game.gp** — The build script in `goal_src/jak1/game.gp` that tells GOALC what to build. The add-on adds an entry
for each of your levels.

**gk** — The game executable (the OpenGOAL runtime).

**GLB** — The binary glTF file of a level's geometry and collision (`<level>.glb`), and the format of the game models
the decompiler exports.

**GOAL** — The Lisp-like programming language Jak and Daxter is written in. Files end in `.gc`.

**GOALC / REPL / (mi)** — GOALC is the GOAL compiler (`goalc`). It runs in its own console window with a REPL, a
prompt you can type GOAL into. `(mi)` ("make ISO") builds everything that changed; **Export & Compile** sends it for
you over GOALC's network REPL (nREPL). The first `(mi)` after GOALC starts compiles all the game code.

**Jsonc** — JSON with comments. A level's `<level>.jsonc` lists its actors, ambients, cameras and art groups.

**Level index** — A unique number for each level in `level-info.gc` (**Level › Settings › Level Index**, 100 and up).
Two levels with the same index clash.

**level-info.gc** — The game file with every level's definition (name, nickname, mood, music ...) and its continue
points. The add-on adds your levels to it.

**Listener / (lt)** — The link between GOALC and the running game. `(lt)` connects them; then GOALC can send commands,
like the spawn, to the game.

**Load boundary** — A line or area (`LOADBND_` mesh) that loads, shows or hides levels when Jak crosses it. Vanilla
levels have their own in `load-boundary-data.gc`. See [Volumes & triggers](volumes-and-triggers.md).

**Lump** — One setting stored on an entity: a key (like `path`, `eco-info`, `vis-dist`) and a typed value. The add-on's
fields write lumps for you. The value types are:

| Type | Holds |
|---|---|
| `float`, `int32`, `uint32` | Plain numbers (one or more) |
| `meters`, `degrees` | A distance or an angle (converted to game units: 4096 per metre) |
| `enum-int32`, `enum-uint32` | A named game value |
| `vector`, `vector4m`, `vector3m` | Points (positions in metres) |
| `vector-vol` | The planes of a volume |
| `movie-pos` | A position and angle for a cutscene |
| `water-height` | Water level, wade / swim heights and water flags |
| `eco-info`, `cell-info`, `buzzer-info` | What a crate or pickup holds (eco, orbs, a power cell, a scout fly) |
| `symbol`, `string`, `type` | A GOAL symbol, a text, a type name |
| `plain-text` | Raw JSON written as typed |

**mod-base** — OpenGOAL's modding base, a fork of the OpenGOAL repository made for mods. Some features (booting
straight into your spawn, custom tasks) need it. See [Developer Tools](developer-tools.md).

**Mood** — A level's lighting, fog, sun and sky settings over the day (**Level › Settings › Visuals**). Each vanilla
level has one; a custom level picks one, or uses one of its own. See [Moods](moods.md).

**Nav-mesh / nav-enemy** — A nav-mesh is a low-poly mesh of where enemies can walk (and jump). A nav-enemy is an enemy
that uses one to chase and patrol (babak, lurker crab ...). Without a nav-mesh a nav-enemy only idles. See
[Enemies & nav-meshes](enemies-and-navmesh.md).

**nREPL** — See *GOALC*.

**PAT** — Surface attributes: what a collision face is (material such as stone or grass, mode such as ground or wall,
and events such as deadly). On nav-mesh faces the PAT marks jump and special areas (the **NAV Walk / NAV Jump /
NAV Special** materials). See [Geometry](geometry.md).

**Path** — The points an actor follows (a moving platform, a patrolling enemy), drawn as a curve or waypoints and stored
in the `path` lump (`pathb` ... for more). See [Paths & platforms](paths-and-platforms.md).

**Process** — A running piece of game code, such as an actor's behaviour. Most actors are a *process-drawable*: a
process with a model.

**Retail / Debug mode** — How the game starts. Debug mode has the debug menus and the listener; retail mode runs like
the released game. See [Build & Play](build-and-play.md).

**Sound bank** — A set of sounds a level loads. A level loads `common` plus up to two banks; a sound from another bank
stays silent. See [Audio](audio.md).

**Task / game-task** — A goal the game tracks: each power cell and scout fly belongs to one (`game-task` values such as
`jungle-eggtop`). Actors that give a cell need a task. The add-on can also make custom tasks. See [Tasks](tasks.md).

**Time of day** — The game's day cycle. The add-on bakes lighting for its 8 times of day into the vertex colours. See
[Lighting](lighting.md).

**tpage** — Texture page: a group of textures the game loads together. Every actor brings the tpages of the vanilla
level it comes from, and the memory for them is small, so mix enemies from at most one or two vanilla levels (see
[Troubleshooting](troubleshooting.md)).

**Vis nickname** — A level's short (3-letter) name, used for its DGO / `.gd` file and in load commands. Set it in
**Level › Settings › Vis Nickname** or leave it blank to derive it from the name. Two levels can't share one.

**vis-dist** — A lump: how far away an actor is still drawn / active, in metres.

**Volume (VOL_)** — A mesh named `VOL_...` that marks an area: a trigger, water, a camera's area, a checkpoint trigger.
See [Volumes & triggers](volumes-and-triggers.md).

---

[← Previous](troubleshooting.md) · [Guide index](README.md) · [Next →](actor-list.md)
