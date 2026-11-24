# Custom mood creation tool — plan

Branch `claude/mood-tool`. Based on Kuitar's notes (ToDo ordered List.md) and the research in
`_claude_tmp/mood_research.md` (game source: engine/gfx/mood/mood-h.gc, mood-tables.gc, mood.gc, time-of-day.gc, level.gc).

## What the research changed or added to the notes

1. **Where the code goes (the big one).** The game looks up a level's `:mood` and `:mood-func` when the level *starts*
   loading, and calls the mood function while it is still loading. Code in the level's own files would not exist yet
   (crash) or point at freed memory on later loads. So custom moods and mood functions must be compiled into
   **GAME.CGO** (always loaded), the way the add-on already ships its shared `lt-*` files. They still get their own
   files (one per mood, one per mood function), so only those recompile — but a change means GAME.CGO is rebuilt
   (a "full" build, a bit slower than a level-only one). There is no way around this that keeps the mood correct
   while the level loads.
2. **The time of day setup belongs to the mood in the game.** Which vertex colour palettes are used at which hour is an
   *interp table* stored on the mood (three of them: fog, palettes + lights, sky + sun). Kuitar's notes put it in the
   mood function, which is the right place for the user (the function decides which slots are times and which are
   effects), so: **the mood function owns the timeline**, and its generated code points the mood at the function's
   own tables each frame (one pointer write, no cost). A mood used with a vanilla function keeps its own tables.
3. **interp-table explained.** 24 rows, one per hour: which two of the 8 slots are mixed and how much (morph start → end
   over the hour). The default one peaks at sunrise 7:00, morning 9, noon 12, afternoon 15, sunset 18, twilight 19,
   evening 23, green sun 4:00. We build these from the timeline (per slot: on / off + its hour); a raw 24-row editor is
   not needed (kept as an "advanced: custom" option at most).
4. **Slots are shared by three things.** Slot N is at once the geometry's bake layer N (`_SUNRISE` … `_GREENSUN`), lights
   table entry N, and fog / sun entry N. An effect slot (e.g. lamps on slot 5) adds its bake layer on top of the time
   of day — so the bake layer for an effect slot should hold only that effect's light. The Light Baking › Time of day
   list will name a slot by what the level's mood function uses it for (e.g. "5 — Flicker (lamps)").
5. **Light kits 1-7.** Some NPCs (bird lady, warrior …) light themselves with kit 3 / 4 of the mood. A custom mood fills
   kits 1-7 from the main light (like the vanilla `make-light-kit`), or they'd be black.
6. **16 bytes of effect state per mood.** Effects need some (flicker 4, pulse 2, lightning 1, caustics 1, lava 18!). The
   add-on assigns them and refuses combinations that don't fit (lava glow on its own, basically).
7. **Bugs found in the current Fog override** (Level › Settings › Visuals): `fog_min` isn't scaled to 0-255 (so the fog
   is total at the far distance), the tooltips describe density backwards (the game uses visibility), and it fights the
   mood's own fog every frame. A custom mood's fog table replaces it properly. Proposal: fix the scaling + wording now,
   keep it for vanilla moods, and say in its panel that a custom mood is the better way.

## The tab

A new **Moods** sidebar tab (like Tasks): a short description, then two sub-panels.

### Mood Functions

Description at the top, **+** to add. Each function is a collapsible block (like tasks) with **Export** checkbox,
**Duplicate**, **Delete**:
- **Name** (default `update-mood-<active level>`; the add-on keeps names unique).
- **Template**: vanilla functions (default, village1, misty, firecanyon, village2, swamp, sunken, rolling, snow …) and
  this file's functions. A template fills the timeline and the effects it can reproduce. Effects tied to vanilla
  places / tasks (village1 houses, misty warehouse, citadel shield, eggtop tasks) are left out or turned into options.
- **Time of day** (collapsible, 8 rows): per slot on / off and its hour. Off slots are free for effects. Presets: all 8
  (default), village1 (slot 5 free), 2 slots (misty), 3 slots (firecanyon), 4 slots (rolling), **fixed slot** (no time
  of day, like caves).
- **Effects**: a checkbox per effect, its settings below when ticked, each picking the slot(s) it uses (only free
  slots offered):
  - **Flicker** (fires / lamps): slots (1-4), base, strength, speed.
  - **Pulse** (slow glow): slot, base, strength, always on / night only, phase.
  - **Lightning + thunder**: palette slots, sky slots, count, quiet. Needs a sky with flash textures (village2 / rolling sky)
    and the thunder sound.
  - **Lava glow**: 4 slots, glow colour (the vanilla one is fixed orange; ours can expose it).
  - **Caustics** (underwater shimmer): 4 slots, speed.
  - **Actor driven slots**: slot N follows actors that use the game's palette fade controls (cave crystals …).
  - **Fog by camera pitch** (swamp): fog colour / clearness when looking up.
  - **Lock time** (new): the mood always uses the given hour (the rest of the game's clock goes on).
  - New ideas (tell me which you want): **Triggered slot** (an actor / volume turns a slot on, fading — switchable
    lights), **Light zones** (near an empty, Jak uses light kit N: lit interiors), **Time speed** (this level's hours go
    faster / slower), **Fog breathing** (fog distance slowly changes).

### Moods

Same blocks (Export / Duplicate / Delete, collapsible), with **Name** (default `*<level>-mood*`) and **Template**:
- **Match level lighting** checkbox: pick a level; it says whether it found the time of day suns / worlds
  (Light Baking › Time of day). **Strength** (default 1.0). At export, per slot: lights direction = the sun's
  direction, light colour = sun colour × energy, ambient = world colour × strength, shadow from the direction (the
  game's 65° clamp), sun colour; optionally fog colour from the world. Those fields grey out with "Driven by level
  lights". Built at every export, so changing the suns / worlds updates the mood.
- **Fog table / Lights table / Sun table**: each **From** a vanilla level or a mood of this file, or **Custom**
  (collapsible, per slot with an on / off checkbox — off slots export empty entries like the vanilla caves):
  - fog: colour, start / end (m), clearness at start / end (0-255, 255 = clear), erase colour (behind the sky);
  - lights: direction (or from an empty), light colour, particle colour (auto), ambient; shadow is computed;
  - sun: sun colour, env colour (shiny surfaces / water reflections).
- **Stars** (85 default; 0 = none; needs > 45 and a sky).
- **Hour tables**: follow the mood function's timeline (default), or a preset.

### Level settings

**Level › Settings › Visuals › Mood** and **Mood function** also list this file's moods / functions.

## Export

- One file per mood and per function in `goal_src/jak1/levels/level-tools/moods/` (`lt-mood-<name>.gc`,
  `lt-mood-func-<name>.gc`), listed in GAME.CGO and game.gp (only the ticked / used ones, only rewritten when changed).
- Mood: `(define *<name>* (new 'global 'mood-context))` + static tables + light kits. Function: a generated
  `update-mood-<name>` (fog, sky, palette / quick, the effects, light kits, `update-mood-itimes`).
- Vanilla tables / interp tables for templates and "From": extracted once from mood-tables.gc into the database.

## Steps (each tested in game before the next)

1. Database: the vanilla tables, hour tables and functions (as templates). Fog override fixes.
2. Moods tab, mood function blocks (timeline + no effects), mood blocks (tables From / Custom), export into GAME.CGO,
   level settings lists. In game: a custom mood + function on a test level.
3. Match level lighting.
4. Effects one by one; Light Baking slot names.
5. Templates from vanilla, guide (on guide-next).

## Questions

1. GAME.CGO is the only safe place (see 1). OK that mood changes need the full build?
2. Timeline in the mood function (generated code points the mood at it) — OK, or would you rather it lived on the mood?
3. Which new effects do you want (Lock time is in; Triggered slot, Light zones, Time speed, Fog breathing)?
4. Fog override: fix + keep for vanilla moods (proposed), or remove once custom moods exist?
