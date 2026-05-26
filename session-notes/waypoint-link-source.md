# Waypoint Link Source

**Branch:** `feature/waypoint-link-source`

---

## Goal

When an actor that uses waypoints is selected, allow the user to build the
actor's path from a mixed list of **empties** (existing `_wp_NN` pattern) and
**curves** (new — each spline point becomes one waypoint at export). The list
is reorderable. A "ping-pong" toggle exports the path forward then backward
so the actor walks A→B→C→B→A→... instead of looping back to start.

---

## Final design

### Data model (per actor empty)

```python
class OGWaypointSource(PropertyGroup):
    obj: PointerProperty(type=bpy.types.Object)  # EMPTY or CURVE
```

On `bpy.types.Object`:
- `og_waypoint_sources: CollectionProperty(type=OGWaypointSource)`
- `og_waypoint_sources_index: IntProperty(default=0)`
- `og_waypoint_pingpong: BoolProperty(default=False)`

### UI — replaces the current Waypoints sub-panel content

A standard Blender UIList with a vertical sidebar on the right:

```
┌────────────────────────────────┬───┐
│ ⊕ ACTOR_babak_0_wp_00          │ 🔍│  (frame)
│ ⊕ ACTOR_babak_0_wp_01          │ X │  (delete)
│ 𝓒 patrol-curve     12 pts      │ ─ │
│ ⊕ ACTOR_babak_0_wp_02          │ ↑ │  (move up)
│                                │ ↓ │  (move down)
└────────────────────────────────┴───┘
[ + Spawn Waypoint  ] [ 🔗 Link Curve ]   [ ☐ Ping-pong ]
```

Each row shows source-type icon (`EMPTY_AXIS` or `CURVE_DATA`), the object
name, and for curves the spline-point count.

### Export

Replace the current `o.name + "_wp_"` name-grep in `export/actors.py` with
iteration over `og_waypoint_sources`:

```python
def _collect_waypoints(actor_obj):
    if actor_obj.og_waypoint_sources:
        points = []
        for src in actor_obj.og_waypoint_sources:
            if src.obj is None:
                continue
            if src.obj.type == 'EMPTY':
                points.append(world_pos(src.obj))
            elif src.obj.type == 'CURVE':
                for spline in src.obj.data.splines:
                    for cp in spline.bezier_points or spline.points:
                        points.append(world_pos_from_local(src.obj, cp.co))
        if actor_obj.og_waypoint_pingpong and len(points) > 2:
            points = points + list(reversed(points))[1:-1]
        return points
    # Backwards compat: fall back to legacy name-based discovery
    return [world_pos(o) for o in legacy_wp_objects(actor_obj)]
```

### Ping-pong math

A 4-point forward path `[A, B, C, D]` becomes `[A, B, C, D, C, B]` so the
engine's modulo walk produces `A→B→C→D→C→B→A→B→...` — true ping-pong with
no duplicated points at the turn.

For paths of length ≤2, ping-pong is a no-op since a 2-point path already
oscillates under normal looping.

### Backwards compat

Existing levels have `_wp_NN` empties but no `og_waypoint_sources` collection.
Strategy: export falls back to legacy name-grep when the collection is empty.
The Waypoints sub-panel offers a one-click "Migrate to new list" button when
it detects legacy empties on the active actor — populates the collection
from them in name order. Migration is opt-in; nothing breaks if the user
never migrates.

### Out of scope (for this branch)

- **Path B** (swamp-bat's `_wpb_` second path) stays on the legacy name-grep
  system. Path B only matters for swamp-bat; refactoring it is busywork.
- **Loop / cycle-mode toggle** for non-ping-pong behavior. Most patrol
  enemies already loop by default per their hardcoded GOAL code. Adding a
  generic toggle would require engine investigation.

---

## Phases

| # | Scope | Files touched |
|---|-------|---------------|
| 1 | Data: `OGWaypointSource`, Object props, register | `properties.py`, `__init__.py` |
| 2 | UIList + reorder/delete/frame operators | `panels/actor.py`, `operators/spawn.py` (or new file) |
| 3 | Link Curve + Ping-pong toggle UI, Migrate button | `panels/actor.py`, `operators/spawn.py` |
| 4 | Export integration — replace `_wp_` name-grep with collection iteration | `export/actors.py` |
| 5 | Backwards-compat fallback in export + Migrate operator | `export/actors.py`, `operators/spawn.py` |
| 6 | Polish, error states, edge cases | various |

Estimated: 2-3 sessions of focused work.
