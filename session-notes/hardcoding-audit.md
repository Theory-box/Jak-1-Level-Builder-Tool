# Hardcoding Audit — path to a fully DB-driven exporter

Branch: `feature/schema-driven-export`

Goal of this doc: list every place the addon special-cases a specific actor in
code, so each can be **approved individually** before migration. For each item:
how it is hardcoded, what that blocks (changing behaviour from the DB, or
copying the same feature onto another actor), and a concrete data-driven fix.

## The two facts that frame everything

1. **UI is already data-driven.** Per-actor settings are Blender id-properties
   (`o["og_..."]`) drawn by the generic `OG_PT_ActorFields` panel, whose `poll`
   falls through to `inherited_fields(etype)` for any actor that has a `fields[]`
   schema. Adding a field in the DB makes it editable with no code — this is why
   the green eco vent worked. So UI is *not* the bottleneck for most actors.

2. **Export is the bottleneck.** `emit_schema_lumps` (export/schema_emit.py)
   already understands these lump shapes:
   - scalar `[type, value]`
   - multi-slot array `[type, s0, s1, ...]` (two+ fields → same lump `key`, each
     with a `slot`)
   - bitfield `[type, acc]` (via `lump_bit`)
   - modifiers: `scale` (×N), `format` (`"(... {value})"`), `symbol_literal`
     (bare `'value`), `value_if_true` (const-on-bool)
   - `write_if`: always / if_true / if_nonzero / if_nonneg / if_positive /
     if_non_empty / if_not_none / if_not_default
   - computed: `eco-info-picker` (the encoder we just added)

   Anything that fits the list above is a **pure migration** (delete the code
   branch, add `fields[]` + `schema_export: true` to the DB entry, done). Only
   things that need *computation* (geometry, linked-object lookups, link-derived
   bits, fixed multi-element constants) need a new reusable encoder first.

Everything hardcoded falls into one of seven categories (A–G). Each item has an
ID so you can approve them piecemeal (e.g. "do A1–A8, B1, skip B3 for now").

---

## Category A — Direct migration (schema already supports; no new code)

Each of these is a per-actor branch in `export/actors.py::collect_actors` that
reads `o.get("og_...")` and writes one or two lumps. In every case the shape is
already expressible in `fields[]`.

- **How it's hardcoded:** logic lives in an `if etype == "X":` branch in Python.
- **What it blocks (all of them):** you cannot change the lump/units/default from
  the DB, and you cannot give the same behaviour to another actor without editing
  Python — the branch only fires for its one etype.
- **Fix pattern:** move to `fields[]` on the DB entry + `schema_export: true`,
  then delete the branch. Column "Encoder" shows the schema feature used.

| ID | Actor(s) | Lump(s) | Encoder used by the fix |
|----|----------|---------|--------------------------|
| A1 | dark-crystal | `mode` int32 (underwater) | bool → `value_if_true: 1`, `write_if: if_true` |
| A2 | plat-flip | `sync-percent` float; `delay` [down,up] | scalar `if_nonzero`; 2-field slot array |
| A3 | sun-iris-door | `proximity` uint32; `timeout` float | bool→uint32 `if_true`; scalar `if_positive` |
| A4 | basebutton | `timeout` float | scalar `if_positive` |
| A5 | launcherdoor | `continue-name` string | scalar string `if_non_empty` |
| A6 | orb-cache-top | `orb-cache-count` int32 | scalar, default 20 |
| A7 | whirlpool | `speed` [base,var] | 2-field slot array |
| A8 | ropebridge | `art-name` symbol | scalar `symbol` |
| A9 | orbit-plat | `scale` float; `timeout` float | scalars `if_not_default` |
| A10 | square-platform | `distance` [down,up] (×4096) | 2-field slot array + `scale: 4096` |
| A11 | caveflamepots | `shove` meters; `cycle-speed` [period,phase,pause] | scalar + 3-field slot array |
| A12 | shover | `shove` meters; `rotoffset` degrees | scalar; scalar `if_nonzero` |
| A13 | lavaballoon / darkecobarrel | `speed` meters | scalar, **per-actor default** (3.0 / 15.0) lives in each DB entry |
| A14 | windturbine | `particle-select` uint32 | bool→uint32 `if_true` |
| A15 | caveelevator | `mode` uint32; `rotoffset` degrees | scalars `if_nonzero` |
| A16 | mis-bone-bridge | `animation-select` uint32 | scalar `if_nonzero` |
| A17 | breakaway-left/mid/right | `height-info` [h1,h2] | 2-field slot array, write-if-any-nonzero |
| A18 | sunkenfisha | `count` uint32 | scalar `if_not_default` |
| A19 | sharkey | `scale`;`delay`;`distance` m;`speed` m | scalars (`scale` if_not_default) |
| A20 | oracle / pontoon | `alt-task` enum-uint32 | enum + `format: "(game-task {value})"` + `if_not_none` |
| A21 | (all Enemies/Bosses) | `idle-distance` meters (def 80) | scalar on the enemy base class (inherited) |
| A22 | (needs_notice_dist actors) | `notice-dist` meters (def -1) | scalar; gated today by a data.py flag → see C5 |
| A23 | (spawners) | `num-lurkers` int32 | scalar `if_nonneg`; gate is D2 |

Notes:
- A13's two defaults are handled naturally — each actor's own `fields[]` sets its
  own default, so no per-type code is needed.
- A21/A22/A23 attach to a *group* of actors. Put the field on the shared parent
  (`fields[]` are inherited down the parent chain), so it's authored once and all
  members get it. Their category/flag gates are Category C/D below.

**Effort:** small each; mechanical. **Risk:** low — `emit_schema_lumps` is
covered by `test_schema_emit.py`; add one expected-output case per actor and the
test proves the schema reproduces the old branch before deleting it.

---

## Category B — Needs one small reusable encoder first, then DB opt-in

These can't be a plain field→lump; they need computation. The point (per your
goal) is that once the encoder exists, **any** actor opts in through the DB — no
per-actor code, exactly like `eco-info-picker`.

### B1 — Constant structured lump (`const-lump`)
- **Where:** `fuel-cell` → `["cell-info", "(game-task none)"]`; `buzzer` →
  `["buzzer-info", "(game-task none)", 1]`; `money` → `["eco-info",
  "(pickup-type money)", 1]` (both the ACTOR_ path and the vertex-instanced path,
  ~line 212 and ~line 859).
- **How hardcoded:** fixed arrays written directly in two `if etype ==` chains.
- **Blocks:** these pickups' contents can't be tweaked from the DB, and a new
  "always drops a fuel cell" actor needs code.
- **Fix:** add a tiny `const` lump type that emits `field.const` verbatim, e.g.
  `"lump": {"key":"eco-info","type":"const","const":["cell-info","(game-task none)"]}`.
  (`money` can alternatively reuse the existing `eco-info-picker` with default
  `money`.) fuel-cell's separate `options` bool is Category A.
- **Effort:** small. **Risk:** low.

### B2 — Bitfield with a link-derived bit (`eco-door` family)
- **Where:** `eco-door/jng-iris-door/sidedoor/rounddoor` `flags` bitfield +
  `perm-status`.
- **How hardcoded:** auto-close/one-way are plain bits, **but** bit `ecdf00` is
  auto-set when a `state-actor` link exists, and `starts_open` writes a second
  lump. The link-coupling is real logic.
- **Blocks:** auto-close/one-way could already be `lump_bit` fields; only the
  "lock until linked button is pressed" bit needs code. Another door type can't
  reuse the locking behaviour without copying the branch.
- **Fix:** migrate the plain bits to `lump_bit` fields (Category-A-like), and add
  a small convention for the computed bit, e.g. `"lump_bit": {"key":"flags",
  "bit_value":1, "set_if_link":"state-actor"}`. `starts_open` → a
  `value_if_true` scalar field for `perm-status`.
- **Effort:** medium. **Risk:** medium (link lookup lives in the emitter's caller;
  pass link presence in like we passed `choice_tables`).

### B3 — Geometry-derived lumps (`water-vol`)
- **Where:** `water-vol` `water-height` (5 floats) + `vol` (6 planes from the
  empty's world scale).
- **How hardcoded:** the plane box is computed from `o.scale` and object position.
- **Blocks:** no other actor can get an activation volume without this exact code;
  the box math isn't reusable.
- **Fix:** a named computed encoder (`type: "vol-box"`) that reads object
  scale/position and emits the 6 planes; `water-height` becomes a 5-slot array of
  fields. Any future volume actor then sets `type: "vol-box"` in the DB.
- **Effort:** medium–large (geometry, needs the object handle passed to the
  encoder). **Risk:** medium — validate exported planes against a known-good level.

### B4 — Linked-object vector (`launcher` alt-vector)
- **Where:** `launcher` `alt-vector` = destination object location (coord-swapped)
  with `w` = fly-time frames. (`object_ref` fields are explicitly skipped by the
  emitter today and handled in code.)
- **How hardcoded:** reads another object's transform + a paired time field.
- **Blocks:** any "teleport/launch to target" actor needs bespoke code.
- **Fix:** a computed `target-vector` encoder: resolve the `object_ref` field to a
  location, coord-swap, take `w` from a paired field. Reusable by any actor that
  declares it.
- **Effort:** medium. **Risk:** medium.

---

## Category C — Per-entity behaviour flags that live in `data.py`, not the DB

`export/actors.py` and `predicates.py` branch on flags read from
`data.py::ENTITY_DEFS` (the pre-migration Python source): `nav_safe`,
`needs_path`, `needs_pathb`, `is_prop`, `needs_sync`, `needs_notice_dist`,
`requires_navmesh`, `ai_type`, and `cat` (drives `_actor_is_enemy` /
`_actor_is_platform`). The derived sets `NAV_UNSAFE_TYPES`, `NEEDS_PATH_TYPES`,
`NEEDS_PATHB_TYPES`, `IS_PROP_TYPES` are built from these at import time.

- **How hardcoded:** the flags are data, but the data is in a **Python module**,
  so behaviour is "semi-hardcoded" — the jsonc DB is not the source of truth.
- **Blocks:** to make an actor nav-unsafe, path-driven, a prop, a platform, etc.,
  you edit `data.py`, not the DB. This directly contradicts the restructuring
  goal: you can't flip these per-actor traits from the database.
- **Fix:** move these keys into each actor's jsonc DB entry (many already carry
  `cat`), expose them via `db.py` accessors, and derive the type-sets from the DB
  instead of `ENTITY_DEFS`. Pure data migration; the branching code keeps working
  once its inputs come from the DB.
- **Items:** C1 nav_safe · C2 needs_path/needs_pathb · C3 is_prop · C4 cat
  (enemy/platform/bosses) · C5 needs_sync / needs_notice_dist / requires_navmesh /
  ai_type.
- **Effort:** medium (data move + one accessor swap). **Risk:** low-medium — diff
  the derived sets before/after to prove they're identical.

---

## Category D — Literal hardcoded type sets (no data backing at all)

- **Where:** `export/predicates.py`
  - D1 `_LAUNCHER_TYPES = {"launcher", "springbox"}` → `_actor_is_launcher`
  - D2 `_SPAWNER_TYPES = {"swamp-bat","yeti","villa-starfish","swamp-rat-nest"}`
    → `_actor_is_spawner`
- **How hardcoded:** literal sets in code.
- **Blocks:** making a new actor a launcher (spring-height lump) or a lurker
  spawner (num-lurkers lump) requires editing this file — the DB can't express it.
- **Fix:** replace with DB flags on the entries (`"is_launcher": true`,
  `"spawns_lurkers": true`) read via `db.py`; the predicate becomes a DB lookup.
  Pairs with A23 (num-lurkers) and the launcher lumps.
- **Effort:** small. **Risk:** low.

---

## Category E — Bespoke UI panels + the exclusion allow-lists

- **Where:** `panels/actor_fields.py` `DEDICATED_FIELD_UI_ETYPES` (crate, launcher,
  springbox, the door family, water-vol, launcherdoor, sun-iris-door,
  caveelevator, oracle, pontoon, the sync-box plats) and their matching
  `OG_PT_Actor*` panels in `panels/actor.py` / `panels/selected.py`; also the
  transitional allow-list `GENERIC_PANEL_ETYPES`.
- **How hardcoded:** each of these actors has a handwritten panel, and its etype
  is listed so the generic panel yields to it.
- **Blocks:** nothing functional, but it's duplicate UI that must be kept in sync,
  and a migrated actor keeps a redundant bespoke panel unless it's removed.
- **Fix:** as each actor moves to `fields[]` (Categories A/B), delete its bespoke
  panel and its `DEDICATED_FIELD_UI_ETYPES` entry so the generic panel takes over.
  Once nothing is left, `GENERIC_PANEL_ETYPES` can go too and `poll` reduces to
  "has `inherited_fields`?".
- **Effort:** small per actor (delete code). **Risk:** low — visual check the
  generic panel renders the same controls.
- **Note:** crate keeps custom logic (wood+buzzer interlock, amount stepper).
  That interlock is UI-only sugar; export is already schema-driven for crate.

---

## Category F — Spawn-time default props hardcoded per actor

- **Where:** `operators/spawn.py` (~218–251: crate, orb-cache-top, sunkenfisha,
  lavaballoon/darkecobarrel defaults), `spawn_items.py` (~267), `utils.py` (~203).
- **How hardcoded:** when an actor is spawned, initial `og_...` values are set in
  Python by etype.
- **Blocks:** changing a spawn default, or giving a new actor sensible defaults,
  needs code — even though the DB `fields[]` already declare those same defaults.
- **Fix:** on spawn, iterate `inherited_fields(etype)` and seed each `og_...` from
  its DB `default`. One generic loop replaces all the per-actor assignments.
- **Effort:** small. **Risk:** low — the panel already reads the same defaults, so
  behaviour matches.

---

## Category G — Abstract-type export remap

- **Where:** `export/actors.py` ~line 190: `if etype == "eco-door": etype =
  "jng-iris-door"` (abstract type remapped to a concrete subclass at export).
- **How hardcoded:** a one-off etype swap in the exporter.
- **Blocks:** any other abstract/alias actor needs the same code edit.
- **Fix:** a DB field on the entry, e.g. `"export_as": "jng-iris-door"`, honoured
  generically by the exporter.
- **Effort:** small. **Risk:** low.

---

## Suggested ordering (for approval)

1. **D1/D2 + C** — move trait flags/sets into the DB. Unblocks A21/A22/A23 and
   makes "is this a launcher/spawner/enemy/prop" a DB question.
2. **Category A** — batch-migrate the simple actors (biggest count, lowest risk).
   Each: add `fields[]`, add a `test_schema_emit` case, delete the branch.
3. **B1** (const-lump) then **G** (export_as) — tiny encoders, clear wins.
4. **B4 / B3 / B2** — the genuinely computed encoders, in rising difficulty.
5. **E / F** — cleanup that follows each migration (delete bespoke panel, unify
   spawn defaults).

Nothing here changes exported output on its own — every step is "reproduce the
current bytes from the DB, prove equality in `test_schema_emit`, then delete the
branch." Approve items individually and I'll implement them the same way we did
`eco-info-picker`: change, test, push to this branch.
