# Paths & platforms

Many actors follow a **path**: patrolling enemies, floating platforms, flying lurkers, button platforms, race rings. A path is a list of points. You build it from **waypoint empties**, **curves**, or both. When you export, it is written as the actor's `path` lump, plus a `path-k` lump for smooth curves.

Actors that need a path say so when you spawn them ("needs a path") and show a red ⚠ count until they have one. The [Actor list](actor-list.md) marks them with **path**.

## Giving an actor a path

1. Select the actor and open **OpenGOAL › Object Settings › Actor Settings › Path** (④ in the [Actor screenshot](images/actor.png)).
2. Add points in one of these ways:
   - **Spawn Waypoint**: adds an empty at the 3D cursor. With **At Actor Position** on, it goes at the actor instead. The actor stays selected, so you can move the cursor and click again.
   - **Add Curve**: adds a new curve linked to the path (see [Add Curve](#add-curve)).
   - **Link → <curve>**: links a curve you have shift-selected (one button per selected curve, up to 6).
   - **Search curve…**: links any curve in the scene by name.
3. Move the waypoints, or edit the curve, until the path is where you want it.

You can also select a curve first and then spawn the actor. With the preference **Connect spawned actors to the selection** on, the curve becomes its path straight away ([Actors](actors.md#connecting-to-the-selection)).

Waypoints are named `ACTOR_<etype>_<n>_wp_00`, `_wp_01` ... and go in the level's **Waypoints** collection. With preview models on, each waypoint shows a see-through ghost of the actor, so you can see where it will stand.

### The path list

The list shows every **source** of the path in order: an empty is one point, and a curve gives all of its control points. The header shows the total point count. Export goes through the list from top to bottom.

| Button (right of the list) | What it does |
|---|---|
| Magnifier | Selects and frames the highlighted source. |
| **Edit** (pencil) | Selects the source. A curve goes straight into Edit Mode. |
| X | Removes the source from the path (the object stays in the scene). |
| Up / down arrows | Change the order. |

A source that was deleted shows in red ("DELETED"). Remove it with X.

## Add Curve

**Add Curve** adds a new curve at the 3D cursor (or at the actor with **At Actor Position** on), links it to this path, and puts it in the level's **Paths** collection. It is named `PATH_<actor>_<lump>`, for example `PATH_plat_0_path`. Change its options right after in Blender's **Adjust Last Operation** panel (bottom left of the viewport):

| Option | What it does |
|---|---|
| **Curve Type** | **NURBS** (smooth, like the game's smooth paths), **Poly** (straight lines between points), **Bézier** (curve with handles). |
| **Curve Shape** | **Circle**, **Straight Line**, **Single Point**, **Half Circle**. |
| **Number of Points** | For shapes where the count can change (for example a NURBS line, 4 at least). |
| **Cyclic** | Closed loop. On by default for circles. |
| **Endpoints** | NURBS only: the curve starts and ends exactly on its first / last point. |
| **Diameter** / **Length** | Size of a circle / half circle, or length of a line. |
| **Rotation** | 0, 0, 0 = flat on the XY plane. |
| **Position** | Where the curve goes. |

A NURBS curve with fewer than 4 points warns that Blender keeps its Order U lower. Set it to 4 once the curve has 4 or more points.

Curves you make yourself work just as well. Link them with **Link →** or **Search curve…**. The level's **Sort & Clean** also moves every curve a path uses into the Paths collection ([Levels](levels.md)).

## Path Mode

The **Path Mode** box under the list decides how the points are turned into the game's path. A line under it shows the result, for example "Automatic → Smooth Clamped: 6 points, 10 knots (path-k)", and a red line if something doesn't fit.

| Mode | Result |
|---|---|
| **Automatic** (default) | Picked from the sources: waypoints or several sources = Linear. One Poly curve = Linear (Looped if cyclic). One NURBS curve = Smooth, or Smooth Clamped with Endpoints (Looped if cyclic). One Bézier curve = Bezier (Looped if cyclic). |
| **Linear** | Straight lines through every point (no `path-k`). |
| **Linear (Looped)** | Linear, plus the first point again at the end. |
| **Smooth** | A smooth curve that doesn't quite reach the first and last points. Needs 4+ points. |
| **Smooth (Looped)** | A smooth closed loop. |
| **Smooth Clamped** | Smooth, starting and ending exactly on the end points. Needs 4+ points. |
| **Smooth Clamped (Looped)** | Smooth Clamped, plus the first point again. |
| **Bezier (Sharp Corners)** | One Bézier curve: passes through every anchor, the handles shape each segment, sharp corners allowed. |
| **Bezier (Looped)** | Bezier with a closing segment back to the first anchor. |

**Linear-only actors**: some actors only move in straight lines between points, because their code ignores `path-k`. For them the box reads "Path Mode (this actor only moves in straight lines)" and offers only **Automatic**, **Linear** and **Linear (Looped)**.

**Knots**: smooth modes show a collapsed **Knots (path-k)** box. Knots are worked out automatically. **Edit Knots Manually** gives you the list, with presets **Clamped**, **Uniform** and **Automatic**. If you change the point count later, **Fit** resizes the list. Most levels never need this.

## More than one path

Under the path, **Lump** is the lump name the main path exports to (normally `path`). **Keyframe** is an optional lump keyframe (blank = default).

Some actors read more than one path. The swamp bat needs `path` and `pathb`, and the battle controller uses `patha` ... `pathh` and `pathspawn`. These actors get **Add Path** (for example "Add Path (pathb)"). Each extra path has its own box with a name, **@** keyframe, its own list, Spawn Waypoint / Add Curve, and its own mode. X removes it, along with its add-on-made waypoints. Two paths with the same name are flagged: only the first exports.

## Sharing one path

If several actors use the same curve, the Path panel warns "N other actor(s) also use this path: it is exported once per actor". Click **Make other connected actors use this as path-actor**. The other actors then read this actor's path through their **path-actor** link instead of carrying their own copy, so it is exported only once. You can offset them in time with **Sync** (phase). Actors that have extra paths are skipped, because path-actor would replace all their paths.

You can also set this by hand: every actor with a Path panel has the link slot **path-actor** ("Use the path of ...") under [Entity Links](actors.md#entity-links).

## Sync

Platforms and other actors that travel along a path on a timer have **Actor Settings › Sync**:

| Field | What it does |
|---|---|
| **Period (s)** | How long one trip along the path takes. Default 4. |
| **Phase (0-1)** | Where in the trip the actor starts. Give several platforms on one path different phases to space them out. |
| **Ease out** / **Ease in** | How smoothly it speeds up and slows down at the ends. Default 0.15, minimum 0.001 (at 0 the game divides by zero and the platform stops). |
| **Reset to Defaults** | Puts all four back. |

The panel says "✓ N points — will move" once the path has at least 2 points. Without them the platform just sits still ("Add ≥2 waypoints to enable movement").

By default a platform goes to the end of its path and back (0 → 1 → 0 each period). Turn on **Wrap phase** in **Actor Settings › Options** to make it go round in one direction instead, which suits looped paths.

Some actors use Sync for something else, such as a timer. In that case the panel's description says what it does on that actor.

### Distribute along the path

Floating platforms (`plat` and the platforms based on it) have two more options in Sync:

| Option | What it does |
|---|---|
| **Place platform on path** | Keeps the platform empty where the game first puts it on its path (from its phase), so what you see in Blender is where it starts. |
| **Distribute along the path** | Exports this platform several times on the same path, evenly spread in time. |
| **Platforms** | How many in total, this one included (2-32). The panel lists the phases. |

The copies share every other setting and the path. They are exported as `<name>-1`, `<name>-2` ... With **Place platform on path** on too, wire ghosts show where the copies start.

## Platforms

Platforms are in the **Platforms** tile of [Spawn Objects](actors.md#spawning-an-actor). A few common ones:

- **Floating Platform** (`plat`): moves along its path using **Sync**. It needs at least 2 points to move.
- **Eco Platform** (`plat-eco`): a floating platform that wakes up when Jak brings blue eco. **Entity Links** has **next-actor** / **prev-actor** slots, so a chain of them wakes up together. Use **Chain N selected by name (prev / next)** to link a row in one click.
- **Button Platform** (`plat-button`): a platform with a button that moves along its path. It requires a path with at least 2 points.
- **Orbit Platform** (`orbit-plat`): needs a partner orbit-plat in **alt-actor** (both linked to each other). Standing on one makes the other circle around it, only where its nav-mesh allows, so give both a nav-mesh. **Orbit timeout (s)** resets them.
- **Launcher** (`launcher`) and other launchers: **Actor Settings › Launcher Settings** has **Launch Height** (-1 = the art's default), **Camera on Launch**, an optional **Launch Destination** empty (**Add Destination Empty at Cursor** or **Link →**; not set = Jak goes straight up), and **Fly Time** (only needed with a destination).

See the [Actor list](actor-list.md#platforms) for all of them.

### Drop Platforms grid

**Drop Platforms (citadel)** (`citb-drop-plat`) spawns a grid of coloured platforms when it gets a `'trigger`. Link it from a button or a trigger volume. **Actor Settings › Platforms**:

| Option | What it does |
|---|---|
| **Count X** / **Count Z** | Grid size. The platforms sit 4 m apart, centred on the actor, along its X and Y axes. |
| **Random** / **Custom** | Random: every slot gets a random colour, or stays empty, each time. Custom: set each platform yourself. |
| Grid buttons (Custom) | A top view. Click a slot to change it: None, Red, Green, Blue, Yellow, Plain. |
| **Set all to** | Fills every slot with one type. |
| **Click does** | The arrow cycles types on click. A colour "paints" that colour on click. |
| **Show preview** | Shows the platforms in the viewport. |

## Race rings

A **Race Ring** (`race-ring`) with a path becomes a **chain of rings**, one per path point, in path order. Jump through the first to start. Each ring must be reached in time or the chain resets. The Path panel then shows a box instead of Path Mode:

- **Point Tilt** of a curve point adds yaw (turns that ring).
- **Point Radius** of a curve point multiplies that ring's time.
- The rings are linked next / prev. The last ring gets the movie position.
- A red line names any ring that would face edge-on in the game (three points in a straight line). Bend the path a little.

Without a path, it exports as that one ring. **Show preview** draws a circle at every ring.

## Distribute Along Curve

**OpenGOAL › Object Controls › Distribute Along Curve** puts the selected objects (any objects, such as orbs or crates) along a curve, in name order. It is different from [Sync's distribute](#distribute-along-the-path): this one moves real objects. See [Distribute Along Curve](object-controls.md#distribute-along-curve) on the Object Controls page for how to use it and its options.

---
[← Previous](actors.md) · [Guide index](README.md) · [Next →](enemies-and-navmesh.md)
