# Research: Schema-Driven Actor Export (DB as single source of truth)

**Status:** research only — no code changes proposed yet. Branch: `research/db-driven-export`.

## Problem (from Kuitar)

Completing the lump database does **not** by itself fix the steam-cap class of bug. Setting `sync` on a steam-cap had no effect because the *exporter* decides per-actor whether to emit `sync` — via hardcoded logic, gated on the actor having waypoints. The data was fine; the export gate dropped it.

The desired contract:

> Any actor that has a setting/lump turned on with a value should export that lump — period. The addon should look at the actor and its declared fields, not at a hardcoded allow-list. An advanced user should be able to add a brand-new actor entry to the database file and have the addon (UI **and** export) work with it, with zero code edits.

That is an **architecture** change in the export layer, not a data fix.

## Current architecture (three layers, DB owns ~one)

1. **UI** — partly data-driven. `panels/actor_fields.py` reads a `fields[]` schema from the DB and auto-draws controls, but only for the ~20 etypes listed in `GENERIC_PANEL_ETYPES`. Everything else uses bespoke panels.
2. **Property defaults** — ad-hoc. `og_*` custom props are seeded in operators (`spawn.py`, etc.), not derived from the schema.
3. **Export** — fully hardcoded. `export/actors.py` emits each lump from a dedicated `if einfo.get("needs_X")` / `if etype == "..."` block. The `fields[]` schema's `lump` sub-object is explicitly labelled "informational" — nothing emits from it.

So the schema *describes* lumps the export never reads. That gap is the whole problem.

## Two concrete symptoms

- **Gated emit.** `sync` is written only inside `if path_pts:` — no waypoints, no emit, even when the field is set. A custom or pathless actor (steam-cap) silently loses it.
- **Allow-list emit.** `sync-percent` is emitted only by `if etype == "plat-flip"`. A new actor that should use it can't, without editing `export/actors.py`.

## Target: schema-driven export

Make the exporter loop over each actor's `fields[]` / `lumps[]` schema, read the bound `og_*` property, and emit the declared lump according to a `write_if` rule — the same schema the panel already consumes for UI. Remove the per-actor allow-lists and gates for the simple cases.

A field entry already carries what's needed:
```
{ "key": "og_sync_phase", "label": "...", "type": "float",
  "default": 0.0, "lump": { "key": "sync", "type": "float" },
  "write_if": "if_nonzero" }
```
Export pseudo-logic:
```
for field in actor.fields:
    val = obj.get(field.key, field.default)
    if should_write(val, field.write_if):
        lump[field.lump.key] = encode(field.lump.type, val)
```

### What this fixes
- Set field + value → lump exported, for **every** actor, no gate.
- New DB actor with `fields[]` → UI and export both work with no code edit.

## The honest boundary: value lumps vs computed lumps

Not every lump is "read a prop, write a value." Some are **computed from scene state** and will always need code:

| Class | Examples | How to handle declaratively |
|---|---|---|
| Value lump | `percent`, `sync`, `notice-dist`, `scale`, `timeout`, `delay`, `mode` | Pure schema (`field → lump`, `write_if`). Most lumps by count. |
| Waypoint-derived | `path`, `path-k`, `pathb` | Field `type: "waypoints"` → a named **emitter** in a small registry. |
| Link lump | `alt-actor`, `state-actor`, `water-actor`, `next/prev-actor` | Already structured (`link_slots`); keep, but emit generically. |
| Geometry-derived | `bsphere`, `trans`, volume bounds | Engine/exporter intrinsic; not user data. |
| Bitfield pack | `options` (e.g. `wrap-phase`) | Field group → `bitfield` emitter with bit map in schema. |

So the realistic target is a **hybrid**: schema drives value lumps directly (the long tail), and a **small fixed set of named emitters** (`waypoints`, `links`, `bitfield`) handles computed lumps. Crucially, those emitters are *referenced from the schema by name*, so a custom actor can say `"emit": "waypoints"` and reuse the path emitter without new code. New code is only needed to add an entirely new *kind* of computation, which is rare.

This directly answers Kuitar: yes, this is fixable, and custom actors work for the common (value-lump) case immediately; the computed cases work as long as the actor reuses an existing emitter kind.

## `write_if` vocabulary (to define)

`always` · `if_true` · `if_nonzero` · `if_set` (prop present at all) · `if_not_default`. The hardcoded gates today implicitly use these; e.g. `sync-percent` is `if_nonzero`, `notice-dist` is `always` with a default. The waypoint gate becomes a property of the `waypoints` emitter, not a blanket condition on `sync`.

## Property registration (third layer)

For true no-code custom actors, the `og_*` props must also come from the schema. Options to research:
- **Convention + `obj.get(key, default)`** (current style) — works without registration, but no typed UI widgets / tooltips for unregistered props.
- **Dynamic registration** from `fields[]` at addon load — cleaner UI, more work, needs care with Blender's registration lifecycle.

Leaning toward deriving registration from `fields[]` so UI, defaults, and export all read one schema.

## Migration plan (staged, low-risk)

1. Add schema-driven export *alongside* the hardcoded blocks; emit only for actors flagged migrated. No behaviour change for others.
2. Migrate value-lump actors first (steam-cap, orbit-plat, whirlpool, the `sync` cluster). Retire each hardcoded block as its actor moves, to avoid double-emit / drift. **`plat-flip` is already double-tracked** (field system + hardcoded `sync-percent`) — convert it early and delete the hardcoded handler.
3. Introduce the `waypoints` / `links` / `bitfield` emitters; migrate path/link/option actors.
4. Decouple the `sync` waypoint gate → move it into the `waypoints` emitter so set-sync always emits.
5. Make `fields[]` the default UI driver for *all* actors (not just `GENERIC_PANEL_ETYPES`); keep bespoke panels only where genuinely custom.
6. Wire the lump extractor (`tools/extract_lumps_from_goal.py`) into `build_database.py` as a validation/diff step so the DB can't silently drift from the source again.

## Risks / open questions

- Double-emit during migration → mitigate with the per-actor migrated flag and deleting handlers as you go.
- Encoding parity: the schema-driven encoder must match the existing `_parse_lump_row` type handling exactly (`float`, `meters`, `vector4m`, `eco-info`, etc.) — reuse it, don't re-implement.
- How much of `options`/bitfield logic to expose to custom-actor authors vs keep internal.
- Should `link_slots` fold into `fields[]` (one schema) or stay separate? (Leaning: keep separate; they have distinct UI/semantics, but emit generically.)
- Property registration approach (above).

## Suggested next steps (when we move past research)

1. Lock the `write_if` vocabulary and the `lump`/`emit` schema shape.
2. Prototype schema-driven emit for one value-lump actor end-to-end (steam-cap), behind a migrated flag.
3. Build the validation diff into the DB build.
