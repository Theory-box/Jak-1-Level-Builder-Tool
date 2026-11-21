# Audio

Jak and Daxter keeps its sounds in **sound banks**. A level only plays the sounds of the banks it loads: the
**common** bank (always loaded) plus up to **two level banks** that you pick. Music comes from a separate **music
bank** and is started by **music zones**. Point sounds such as a waterfall are **sound emitters**.

## Sound banks

Set them in **Level › Settings › Sound & Music**:

| Field | What it does |
|---|---|
| **Music Bank** | The music the level uses (a vanilla level's music, or **None**). See [Music](#music) below. |
| **Sound Bank 1** | The first level sound bank (a vanilla level's sounds, or **None**). |
| **Sound Bank 2** | The second level sound bank. |

The grey line under them counts the sounds you get: *N common + N level = N sounds*. A red line warns when
**Bank 1 and Bank 2 are the same**.

Only two level banks fit, so pick the levels whose sounds your level uses most: enemies, platforms and props from
Snowy Mountain need the `snow` bank, and so on.

### Bank warnings

The add-on checks every sound against the loaded banks:

- **Sound emitters and particle spawners** whose sound is in a bank the level doesn't load get a red ⚠ count (it
  won't play). It also counts in the ⚠ next to **Export & Compile**. Click the count to see which bank it needs.
- **Actors** whose own sounds (footsteps, attacks, machinery ...) are in a bank the level doesn't load get a yellow ⚠
  (a soft warning): the actor works but is silent, e.g. *sound bank snow not loaded: no ...*. Sounds that are in
  several banks need any one of them.
- **Level › Level Audit** lists each sound that won't play and the bank it is in.

The fix is always the same: set that bank as **Sound Bank 1** or **Sound Bank 2**, or pick a sound from a loaded bank.
See [Troubleshooting](troubleshooting.md) for the other warnings.

## Music

1. Set **Level › Settings › Sound & Music › Music Bank**.
2. Add a **music zone**: **Spawn Objects › Effects › Music zone**. Before clicking **Spawn**, set its **Bank**,
   **Flava**, **Priority** and **Radius (m)**. A gold sphere `AMBIENT_mus001` is added at the 3D cursor, in the
   level's **Sound Emitters** collection.
3. Make the zone big enough to cover the level: one large zone is the usual setup. The music plays while Jak is
   inside it.

<!-- check: does the level Music Bank alone start music, or only reset it after a death? (knowledge-base audio-system.md says both) -->

Select a zone and open **Object Settings › Music Zone** to change it:

| Field | What it does |
|---|---|
| **Bank** | The music bank this zone plays (search list). Changing it resets the flava to default. |
| **Flava** | The variant of that music, e.g. village1's `sage`, `farmer`, `dock` or snow's `snow-cave`, `snow-fort`. Only the bank's own flavas are listed; a flava that isn't in the bank is marked ⚠ and exports as default. |
| **Priority** | Wins when zones overlap (higher wins). Vanilla uses 10 for normal zones and 40 for races and bosses. Default 10. |
| **Radius (m)** | Size of the zone. Default 40. |

Use several zones with different flavas to change the music in parts of the level, e.g. a calmer variant inside a
building, with a higher priority than the zone around it.

## Sound emitters

A sound emitter plays a looping sound around a point: waterfalls, machines, wind.

1. Open **Spawn Objects › Effects › Sound emitter**.
2. Click the sound button to search the sounds (listed as `[Bank] sound`), and set **Default radius (m)**.
3. Click **Spawn**: a sphere `AMBIENT_snd001` is added at the 3D cursor, in the **Sound Emitters** collection. The
   sphere shows how far the sound reaches.

Select one and open **Object Settings › Sound Emitter** to change it:

| Field | What it does |
|---|---|
| **Sound** | The sound it plays; click to pick another. |
| **Radius (m)** | How far the sound reaches. Default 15. Changing it resizes the sphere. |

Emitters always loop. Pick a sound from **common** or from one of the level's two sound banks, or it won't play (red
⚠, see above).

Particle spawners can play a sound too; see [Actors](actors.md).

---
[← Previous](volumes-and-triggers.md) · [Guide index](README.md) · [Next →](lighting.md)
