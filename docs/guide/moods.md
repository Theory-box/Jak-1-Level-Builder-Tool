[↑ OpenGOAL Level Tools — User Guide](README.md)

# Moods

A level's **mood** is its light outside the baked vertex colours: the fog, the sun light on actors (Jak, enemies,
crates ...), the sun and sky colours, and which baked time of day layer shows at each hour. Every vanilla level
has one. The **Moods** panel (OpenGOAL tab, under Light Baking) lets you make your own moods, and your own **mood
functions**: the code that runs the mood every frame and adds effects (flickering fires, pulsing lights,
lightning, lava glow, switchable lights ...).

A level picks its mood and mood function in **Level › Settings › Visuals** (see [Levels](levels.md)). The
buttons next to **Mood** and **Mood Function** pick one of this .blend's.

Moods and mood functions are built into the game itself (GAME.CGO), because the game looks a level's mood up
before the level has loaded. So changing them means a full build, a bit slower than a level-only one.

## Slots

A mood has **8 slots** (0 Sunrise … 7 Green Sun). Slot N is at once:
- the geometry's baked layer N (`_SUNRISE` … `_GREENSUN`, see [Lighting › Time of day](lighting.md#time-of-day)),
- the N-th entry of the mood's fog, lights and sun tables.

The **timeline** uses some slots for the time of day. The others are free for **effects**: bake only a lamp's
light into a free slot, and an effect turns that layer up and down in game (flicker, pulse, a switch ...).
Light Baking › Time of day names each slot by what the level uses it for (for example "5 Twilight: Pulse").

## Moods

**Add Mood** makes a mood named after the active level (`*<level>-mood*`), starting from Sandover's tables.
Each mood is a block with **Export**, **Duplicate** and **Delete** buttons:

| Setting | What it does |
|---|---|
| **Name** | The mood is `*<name>*` in the game. It can't be a vanilla mood's name. |
| **Template from a game mood…** | Fills the tables, hour tables and stars from one of the game's 25 moods. |
| **Match level lighting** | Builds the lights and sun tables from a level's Light Baking suns and worlds (below). |
| **Time of day** | The timeline: per slot **On** and its **Hour** (when it is at full strength). Presets: **All 8** (the game's default hours), **7** (Twilight free, like Sandover), **2** (day / night, slots 2-7 free), **3**, **4**, **Fixed slot** (one slot all day, like the caves). Then **Fog / Lights / Sky hours**: built from the timeline, or one of the game's hour tables. |
| **Fog** | Per slot: **Fog colour**, **Start** / **End** (m), **Clear at start** / **Clear at end** (0-255, 255 = no fog), **Erase colour** (behind everything, where no sky is drawn). |
| **Lights** | Per slot: **Direction** (to the light: X / Y / Z values, or drag the sphere), **Light colour** (1.0 = normal, up to about 2), **Ambient**, **Particles: auto** (particle colour from the lights) or a colour. |
| **Sun** | Per slot: **Sun colour** (the sun sprite and halo) and **Env colour** (shiny surfaces, water reflections). |
| **Stars** | Stars at night (0 = none; they need more than 45 and a sky). |

Each table (**Fog**, **Lights**, **Sun**) can also come **From** a vanilla level or another mood of this file,
instead of **Custom**. A slot turned off writes an empty entry, like the vanilla caves' unused slots.

### Match level lighting

Tick it to light actors like your baked level. At every build, per slot:
- the light direction and colour come from that time's sun (the first sun, by name, in its light collection,
  colour × strength × **Strength**), and the sun colour too;
- the ambient comes from that time's world colour × strength × **Strength**;
- **Fog colour** (optional): the fog colour is the world's colour too.

Pick the **Level** (empty: the active level). Lines under it say which slots have no sun or world: those keep
the values set by hand. The matched fields are greyed out and the table rows say "driven by level lights".

**Curve:** if your baked colours went through a curve (Light Baking's curve, or an Effects After Bake curve),
pick the same one here: **Light Baking's curve**, or a preset / your saved curves / **Custom**, with a factor.
The actor light then goes through it the same way, so dark times look the same on actors as on the geometry.
Times of day with **Ignore curve** on in Light Baking skip Light Baking's curve here too.

## Mood functions

**Add Mood Function** makes `update-mood-<level>`. It mixes the mood's tables by the hour, then runs its effects.

| Setting | What it does |
|---|---|
| **Name** | The function is `update-mood-<name>` in the game. |
| **Template from a game function…** | Replaces the effects with the ones a game function uses (18 of them: village1's lamps, the swamp's storm and fog, Precursor Basin's night lights, the caves' crystals ...). Parts tied to vanilla places or tasks are left out. |
| **Time** | **Normal**, **Lock time** (while Jak is in the level the game's clock stays at **Hour**: sun, moon and sky too; it goes on from there when he leaves), **Time speed** (while Jak is in the level the clock runs **Speed** times faster or slower). |
| **Add Effect** | Adds an effect (below). Each has its own block with how it works and what it is for. |

A warning shows when two effects use the same slot. **Level › Settings › Visuals** warns when the level's mood
uses a slot for time of day that its function also uses for an effect.

### Effects

| Effect | What it does | Settings |
|---|---|---|
| **Flicker** | The slots stay at Base; now and then one flares up, like the game's fires. Torches, lamps, campfires. | First slot, Slots (1-4), Base, Strength, Speed |
| **Pulse** | The slot goes up and down around Base. Glowing plants, beacons, slow neon. | Slot, Base, Up / down, Period (s), Phase |
| **Lightning + thunder** | Now and then a flash: the sky slots switch to their flash textures, the palette slots light up (their lights entries light actors too), then thunder. Needs a sky with flash textures. | Distant, Flash slots, Sky slot, First palette slot |
| **Lava glow** | A flickering coloured light from below on actors, and 4 slots cross-fading at random. | Colour, Strength, Speed, Cross-fade 4 slots |
| **Caustics** | 4 slots take turns, fading one into the next: light rippling under water. | First slot, Speed |
| **Triggered slot** | The slot follows the actors that switch it: **Light switch**, **Cave Crystal** (below). | Slot |
| **Fog by camera pitch** | Looking up, the fog moves toward a colour and clears, like Boggy Swamp. | Colour, Colour amount, Clearing |
| **Fog breathing** | The fog start / end slowly go in and out. | Nearest, Farthest, Period, Shape |

**Active hours** (every effect): the effect only runs from **Start** to **End** (game hours, over midnight if End
is earlier), fading in and out over **Fade** hours. Defaults 19 to 7, 1 hour: a night-only effect.

A slot's strength is kept between 0 and 2.

## Switchable lights

1. Bake the switchable light (a lamp, a crystal's glow ...) alone into a free slot: put only those lights in that
   time's light collection (Light Baking › Time of day).
2. Give the level's mood function a **Triggered slot** effect on that slot.
3. Place what switches it:
   - **Light switch** (Spawn Objects › Effects): **Slot**, **On strength**, **Fade on / off (s)**, **Starts on**,
     **Saved** (stays on after reloading). `'trigger` switches it (a button's notify list, a Camera animation …),
     `'untrigger` / `'off` turn it off, `'on` on. A linked volume turns it on while Jak is inside (or switches
     it each time he enters), and a **Trigger actor** dying switches it once.
   - **Cave Crystal**: lit when hit, for its **Light time**. **Slot**: its place in the next-actor chain + 1
     (vanilla) or any slot. Also **Glow strength**, **Fade out**, **Lit by 'trigger**, **No sage hints**,
     **Glow colour** (X: back to white), **Self glow strength** (above 1 it glows extra bright),
     **Darken far actors** (every actor of the level stays dark unless near a lit crystal: **Dark level**,
     **Reach full / end**) and linked **Actor Lights** turned on while it is lit.

With several switches or crystals on one slot, the lit one nearest the camera wins. **Level › Settings ›
Visuals** shows a red warning when a Light switch or crystal's slot isn't a Triggered slot of the level's
function: it won't light.

An **Actor Light** can follow an effect too: its **Follow effect** field makes it as strong as that slot every
frame, so it flickers, pulses or switches with the baked light (see [Lighting › Actor Light](lighting.md#actor-light)).

## The old Fog override

**Override Mood Fog** (Level › Settings › Visuals) is replaced by custom moods. In its place, **Edit Mood**
opens the level's custom mood here, and **Make a Custom Mood** copies the level's current mood (same look) and
uses it. A file that used the override shows **Convert to a Custom Mood**: the override's fog goes into every
slot of a custom mood, with the same look, and the override is turned off.
