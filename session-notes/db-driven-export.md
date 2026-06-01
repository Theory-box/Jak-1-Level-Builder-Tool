# Session notes: schema-driven actor export (DB as single source of truth)

**Branch:** `research/db-driven-export`  ·  **Stage:** research only (no code changes)

## Why
Completing the lump DB doesn't fix the steam-cap class of bug: the exporter
decides per-actor, via hardcoded `if einfo.get("needs_X")` / `if etype == ...`
blocks (and a waypoint gate on `sync`), whether to emit a lump. Set-but-not-
emitted is an export-layer problem, not a data problem. Goal: any actor with a
field set + value emits it, including custom actors added only to the DB jsonc,
with no code edits.

## Artifacts
- `refactoring/research/schema-driven-export.md` — full design research.
- `knowledge-base/research/opengoal/actor-lump-master.md` (on main) — source of
  truth for what each actor actually reads; the gap list that motivates this.
- `tools/extract_lumps_from_goal.py` (on main) — regenerates the master ref;
  intended to also become a build-time DB validator.

## Open questions (see research doc)
write_if vocabulary; emitter registry for computed lumps (path/links/bitfield);
property registration from schema; whether link_slots folds into fields[].

## Next
Lock schema shape + write_if; prototype schema-driven emit for steam-cap behind
a migrated flag; wire extractor diff into build_database.py.

## Progress — feature/schema-driven-export
- `export/schema_emit.py` — schema-driven emit engine (pure, no Blender). Builds
  lump dict from an actor's `fields[]` (write_if rules, slot arrays, value_if_true).
- `export/test_schema_emit.py` — standalone tests; output matches hardcoded shapes
  for plat-flip (sync-percent/delay), steam-cap (sync/percent), dark-crystal (mode).
- `export/actors.py` — gated hook: actors flagged `schema_export:true` in the DB
  emit their fields[] lumps via the engine. Additive + inert until a flag is set,
  so existing export is unchanged. Needs in-Blender verification before relying on it.

## Blockers / decisions needed before wiring the steam-cap pilot
- BASE BRANCH: main's steam-cap has only `percent` (no sync/needs_sync). The sync
  fields/props live on `platform-fixes`. Need to decide the restructure base
  (branch off platform-fixes, or merge it) before adding steam-cap fields[].
- DB hygiene: eco-blue/eco-red/eco-yellow each have 2 near-identical Actor records
  (dedupe). steam-cap/windmill-one also appear in a second catalog array.

## Pilot landed — steam-cap is the first schema-driven actor
- Merged `platform-fixes` (brings steam-cap sync + og_sync_* props).
- Deduped eco-blue/red/yellow (kept canonical collectables.o records).
- steam-cap: added `fields[]` (4 sync slots → og_sync_*, + og_steam_percent) and
  `schema_export: true`; removed the dead `links:{need_sync}` key.
- Verified end-to-end (DB schema → emit engine): a pathless steam-cap with sync
  set now emits `sync` AND `percent` — the original bug, fixed by architecture
  rather than by un-gating one hardcoded branch.
- NEEDS IN-BLENDER VERIFICATION before relying on it (no Blender in this env).

## Next
- In-Blender test of the steam-cap export.
- Add a UI field for og_steam_percent (add steam-cap to the generic field panel),
  or confirm the existing sync box + a percent field render without duplication.
- Then migrate the rest of the sync cluster, retiring hardcoded branches as we go.

═══════════════════════════════════════════════════════════════════════════
# HANDOFF — full current state (read this first if you are a fresh instance)
═══════════════════════════════════════════════════════════════════════════
Branch: feature/schema-driven-export. Everything below is on it. main is clean.
Goal of restructure: the game DB is the single source of truth. An actor (incl.
a custom one added ONLY to the DB) exports its value-lumps purely from its
declared `fields[]` schema — no per-actor code, no hardcoded allow-lists/gates.

## WHAT IS DONE
1. Emit engine — addons/opengoal_tools/export/schema_emit.py (PURE, no bpy).
   `emit_schema_lumps(get, fields) -> {lump_key: ["type", ...] }`.
   `get` is the object's prop getter (obj.get). Validated to reproduce EVERY
   hardcoded branch category exactly. Features:
     - slot arrays:      lump.slot=N        -> ["type", v0, v1, ...] (sync, delay, cycle-speed, distance, speed, height-info, eco-info)
     - bitfield OR:      lump.bit=N  OR  (value_if_true on a uint32/int32 scalar) -> OR-accumulated (flags, options/wrap, perm-status, proximity, particle-select)
     - scale:            field.scale=F      -> multiply numeric by F (square-platform x4096)
     - const:            field.const=V      -> emit constant, ignore prop (fuel-cell/buzzer/money eco-info)
     - format:           field.format="(game-task {})" -> str template on the value (alt-task)
     - value_if_true:    bool prop true -> use this value
     - encoders via lump.type: float/meters/degrees/int32/uint32/symbol/enum-uint32/cell-info/buzzer-info/eco-info/vector...
     - write_if:         always | if_true | if_nonzero | if_set | if_not_default
   Tests: export/test_schema_emit.py (run: python3 export/test_schema_emit.py). PASSES.
2. Hook — export/actors.py line ~745 (`emit_schema_lumps(`), after the custom-
   lump-rows loop and after all hardcoded value branches (190..~705).
   CURRENT MODE = ADDITIVE: `if _lk not in lump: lump[_lk]=_lv` — so for the 34
   migrated actors the HARDCODED branch still wins and schema is a no-op (zero
   behavior change). For a CUSTOM actor (no hardcoded branch) the hook adds all
   its schema lumps -> the core goal (custom actors export code-free) ALREADY WORKS.
3. DB migration — 34 actors now have `fields[]` + `schema_export:true`:
   basebutton, breakaway-left/mid/right, buzzer, caveelevator, caveflamepots,
   dark-crystal, darkecobarrel, fuel-cell, lavaballoon, mis-bone-bridge, money,
   oracle, orb-cache-top, orbit-plat, plat, plat-eco, plat-flip, ropebridge,
   sharkey, shover, side-to-side-plat, springbox, square-platform, steam-cap,
   sun-iris-door, sunkenfisha, swamp-bat, swamp-rat-nest, villa-starfish,
   whirlpool, windturbine, yeti.
   Every spec was validated against its expected hardcoded output (0 failures)
   BEFORE injection. DB re-parses valid; 152 unique actors.
4. Merge + dedupe done (platform-fixes merged; eco-blue/red/yellow deduped).

## EXACT NEXT STEPS (in order)
STEP A — Retire the hardcoded value branches for the 34 migrated actors so the
  schema actually DRIVES export (right now it is redundant).
   - Two ways: (i) delete each hardcoded value branch in export/actors.py for the
     migrated etypes (lines ~190..705 inventory below), leaving ONLY the computed
     emitters; or (ii) lower-risk: flip the hook to schema-WINS (change
     `if _lk not in lump:` to always-set) so schema is authoritative while the
     dead hardcoded branches are deleted in a later cosmetic pass. Recommend (ii)
     first (behaviour-identical, schema validated equal), then delete dead code.
   - DO NOT touch the computed emitters (keep as code): path / pathb / path-k
     (waypoints), nav-mesh-sphere, water-vol (water-height+vol from mesh bounds),
     launcher alt-vector (from dest actor pos), crate crate-type+eco-info (pickup
     map), checkpoint has-volume/cull-radius/vol/radius, vertex-export money/buzzer.
STEP B — Migrate the remaining VALUE actors not yet done:
   - launcherdoor: continue-name is a BARE string (lump value = the string, not
     ["string",v]). Engine has no bare mode yet — add field flag "bare":true
     (emit value directly) OR keep hardcoded. continue-name + spring-height(launcher).
   - launcher: spring-height is schema-able (meters, if_not_default default -1.0);
     alt-vector stays computed. So launcher is HYBRID.
   - crate: hybrid (crate-type bare + eco-info computed from pickup) -> keep code.
STEP C — Hybrid: doors flags. eco-door/jng-iris-door/sidedoor/rounddoor `flags`
   bitfield = ecdf00(1, set when a state-actor LINK exists) | auto-close(4) |
   one-way(8); plus perm-status(64) if starts-open. auto-close/one-way/perm-status
   ARE schema-able (bits 4/8 + value_if_true 64). ecdf00 depends on a link ->
   needs a tiny code emitter that ORs bit 1 when link present, then schema ORs the rest.
STEP D — Enemy CATEGORY defaults (NOT per-actor): idle-distance (meters, all
   enemies, default 80) and vis-dist (meters, all enemies, default 200, only if
   not already set). Handle by adding these fields to the ENEMY PARENT and teaching
   the hook to inherit parent `fields[]`, OR keep as the small `if is_enemy:` code block.
STEP E — UI + property registration (so custom DB actors get a panel too):
   - panels/actor_fields.py: drop the GENERIC_PANEL_ETYPES allow-list; drive the
     panel from `_db.find_actor(etype).get("fields",[])` for ALL actors.
   - properties.py: derive og_* PropertyGroup registration from the union of all
     fields[] across the DB (so a new field key auto-registers). Respect type
     (float/int32->Int, bool->Bool, symbol/string->String/enum).
STEP F — Wire tools/extract_lumps_from_goal.py as a validation/diff step in
   refactoring/build_database.py (warn when DB fields[] diverge from source lumps).

## SCHEMA FIELD FORMAT (authoritative — copy this shape)
  { "key": "og_whirl_speed", "type": "float", "default": 0.3,
    "lump": { "key": "speed", "type": "float", "slot": 0 }, "write_if": "always" }
  Optional on field: "scale", "const", "format", "value_if_true", "min", "max", "label".
  Optional in lump: "slot" (array index), "bit" (OR constant into uint32).
  const field shape: { "const": 1, "lump": { "key":"eco-info","type":"eco-info","slot":1 } }

## VALIDATION WITHOUT BLENDER (this is how everything was checked)
  cp .../export/schema_emit.py /tmp/ ; from /tmp import emit_schema_lumps; feed a
  fake getter `g=lambda d:(lambda k,dflt=None:d.get(k,dflt))` plus the actor's
  fields[] and assert the dict equals the expected hardcoded lump shape. The
  per-actor expected shapes are the hardcoded branches in export/actors.py.

## HARDCODED BRANCH INVENTORY (export/actors.py, approx lines, pre-removal)
  190 eco-door flags(hybrid) | 212 fuel-cell eco-info+options | 218 buzzer eco-info
  220 crate(computed) | 240 money eco-info | 257 nav-mesh-sphere(computed)
  274/284/327/337/360 path/pathb/path-k(computed) | 306 sync+wrap | 369 notice-dist
  375 dark-crystal mode | 381 plat-flip sync-percent | 390 doors flags(hybrid)
  415 sun-iris-door proximity/timeout | 426 basebutton timeout | 463 water-vol(computed)
  501 launcherdoor continue-name(bare) | 513 spring-height | 518 launcher alt-vector(computed)
  537 num-lurkers | 550 idle-distance(enemy cat) | 567 water-vol | 575 vis-dist(enemy cat)
  580 plat-flip delay | 587 orb-cache-count | 594 whirlpool speed | 601 ropebridge art-name
  607 orbit-plat scale/timeout | 617 square-platform distance x4096 | 625 caveflamepots
  635 shover | 644 lavaballoon/darkecobarrel speed | 651 windturbine | 657 caveelevator
  667 mis-bone-bridge | 674 breakaway height-info | 682 sunkenfisha | 689 sharkey
  702 oracle/pontoon alt-task | ~796 checkpoint(computed) | ~853/869 vertex-export(computed)

## ENVIRONMENT GOTCHAS
  - bpy shadow: NEVER run python3 from inside addons/opengoal_tools/ (its
    collections.py shadows stdlib). Run from /tmp or /home/claude.
  - DB is JSONC (comments) -> cannot json.dump round-trip; edit as TEXT. To strip
    for parsing: re.sub(r'/\*.*?\*/','',t,flags=re.S) then re.sub(r'(?m)//.*$','',t).
  - Injection lesson: a "block already has fields" guard must scan ONLY the current
    record (until its closing `},`), NOT a fixed N-line window (a neighbour's freshly
    injected field will false-trigger and silently skip the actor).
  - VertexExportTypes / ObjectTypes arrays (~L15200+) also list etypes (steam-cap,
    eco-*, etc.) — these are CONFIG, not Actor duplicates. Inject/dedupe only inside
    the Actors[] top-level array range.
  - pontoon is NOT in the DB Actors (it is on the "placeable types missing from DB"
    list); its spec exists in migrate_fields.py but cannot inject. ~105 source-only
    placeable types remain un-added (scope decision still open).

## FILE MAP
  engine        addons/opengoal_tools/export/schema_emit.py
  engine tests  addons/opengoal_tools/export/test_schema_emit.py
  hook          addons/opengoal_tools/export/actors.py  (~L745; branches L190-705)
  DB            addons/opengoal_tools/jak1_game_database.jsonc  (Actors[] array)
  field UI      addons/opengoal_tools/panels/actor_fields.py  (GENERIC_PANEL_ETYPES)
  prop reg      addons/opengoal_tools/properties.py
  master ref    knowledge-base/research/opengoal/actor-lump-master.md  (on main)
  extractor     tools/extract_lumps_from_goal.py  (on main)
  design doc    refactoring/research/schema-driven-export.md
  OG source     (sandbox only) /home/claude/jak-project/goal_src/jak1
  migrate script(sandbox only, not in repo) /home/claude/migrate_fields.py

## CONSTRAINT FROM USER
  Do the WHOLE restructure before any in-Blender testing. No test cycles requested
  until complete. (I cannot run Blender here; all checks are Python/engine-level.)

═══════════════════════════════════════════════════════════════════════════
# UPDATE — Step A (partial): schema hook is now AUTHORITATIVE
═══════════════════════════════════════════════════════════════════════════
- export/actors.py hook (~L751) changed from additive (`if _lk not in lump`) to
  authoritative: schema OVERRIDES the legacy hardcoded value lumps, but YIELDS to
  `_protected_keys` = computed entity-link lumps + user custom lump rows.
  Wiring: `_protected_keys = set(link_lumps.keys())` after links; `.add(key)` in
  the custom-row loop; hook guard is `if _lk not in _protected_keys`.
- Effect: for the 34 schema_export actors the DB is now the real driver. Output is
  validated-identical to the old hardcoded path EXCEPT the intended bug fix —
  legacy `sync` was gated behind `if path_pts:` (L311), so pathless platforms
  (plat/plat-eco/side-to-side-plat/steam-cap) silently lost `sync`; schema now
  emits it unconditionally. Computed `path` lump (L337) is NOT in schema and is
  preserved untouched.
- The hardcoded value branches still RUN then get overwritten — dead-but-harmless
  compute. Wholesale deletion of those branches is deferred until ALL value actors
  are migrated (avoids partial-migration interleaving hazard; some branches like
  spring-height serve both a migrated etype `springbox` and a not-yet-migrated
  `launcher`). Delete only after B/C/D below land.
- Remaining: B launcher/launcherdoor/crate (hybrid/bare/computed) · C doors flags
  ecdf00 link-bit · D enemy idle-distance/vis-dist via parent-field inheritance ·
  E schema-driven UI panel + property registration · F extractor diff in build.
