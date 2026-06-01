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

═══════════════════════════════════════════════════════════════════════════
# UPDATE — parent-field inheritance foundation + Step D decision
═══════════════════════════════════════════════════════════════════════════
- db.py: added `inherited_fields(etype)` (parent fields root-first, actor overrides
  by `key`; const fields always kept) and `schema_export_enabled(etype)` (actor OR
  any ancestor flagged). Mirrors the existing inherited_links/inherited_lumps.
- export/actors.py hook now uses `schema_export_enabled` + `inherited_fields`
  instead of the raw actor record. Validated ZERO behaviour change today: no Parent
  carries fields[] or schema_export, so inherited == own for all 34 (0 mismatches).
  This unlocks per-family schema (flag a parent → whole family inherits).
- Step D DECISION: enemy idle-distance / vis-dist STAY as the small code rule
  (the `if _actor_is_enemy(etype)` / `if is_enemy` blocks at ~L549 / ~L574). Reason:
  they are CATEGORY-WIDE engine defaults (every enemy/boss), not per-actor value
  config, AND the two lumps use DIFFERENT enemy tests — idle-distance uses the
  `_actor_is_enemy(etype)` helper, vis-dist uses `cat in (Enemies,Bosses)`. A single
  parent flag can't faithfully reproduce both sets, so forcing them into schema
  risks regressing some enemies. Keep as code; revisit only if the two tests are
  unified. (Foundation above is still the right call for genuine per-family fields.)

# REMAINING TO BE "DONE" (current best list)
  B  launcher (spring-height -> schema meters/if_not_default; alt-vector stays code),
     launcherdoor (continue-name BARE string -> add field flag "bare":true to engine,
     or keep code), crate (crate-type bare + eco-info pickup map -> stays code).
  C  doors flags hybrid: add a tiny code emitter that ORs bit 1 (ecdf00) when a
     state-actor link exists, and migrate auto-close(4)/one-way(8)/perm-status(64)
     to schema bits on eco-door/jng-iris-door/sidedoor/rounddoor.
  E  UI: panels/actor_fields.py drop GENERIC_PANEL_ETYPES, drive panel from
     inherited_fields(etype) for ALL actors; properties.py register og_* from the
     union of all fields[] (so custom DB actors get a UI + auto-registered props).
  CLEANUP  once B/C land, delete the now-dead hardcoded VALUE branches (190..705)
     for migrated etypes, keeping ONLY computed emitters (path/pathb/path-k,
     nav-mesh-sphere, water-vol, launcher alt-vector, crate, checkpoint, vertex-export,
     enemy idle/vis). Safe because schema already overrides those keys.
  F  wire tools/extract_lumps_from_goal.py as a diff/validation step in build_database.py.

═══════════════════════════════════════════════════════════════════════════
# ⚠ COURSE CORRECTION — an existing fields[] schema already exists
═══════════════════════════════════════════════════════════════════════════
DISCOVERY: the DB ALREADY had a rich `fields[]` schema for 37 actors (authored
in prior commits, e.g. "Update jak1_game_database.jsonc"). It is consumed by the
UI panel (panels/actor_fields.py L302), NOT by export — export was hardcoded.
Its convention is RICHER than the one I invented this session:
  - enum fields: "type":"enum" with "choices":[{value,label,lump_value}] — the
    emitted lump value is the selected choice's `lump_value` (int), not the string.
  - object_ref + "pairs_with": e.g. launcher og_launcher_dest (object_ref) pairs
    with og_launcher_fly_time -> alt-vector (resolved from the object's location).
  - write_if vocabulary: always, if_true, if_nonzero, if_not_default, if_nonneg
    (>=0), if_positive (>0), if_non_empty (str), if_not_none (!= "none"),
    if_any_nonzero (any slot != 0), if_object_found (referenced object exists).

MY ERROR: I authored a PARALLEL convention (different write_if words, no enum
lump_value, no object_ref) and bulk-INJECTED `fields[]`+`schema_export` onto ~34
actors — creating DUPLICATE `fields` keys on 25 of them (the originals won the
parse) and, with the now-authoritative hook, running MY engine against the
ORIGINAL rich fields it cannot interpret -> would mis-export or crash flagged actors.

FIX APPLIED: reverted the DB to commit 5754318 (post-merge, post-dedupe). The DB
is now CLEAN — 0 duplicate keys, 0 schema_export, existing 37-actor schema intact,
export back to the safe hardcoded path. The engine/hook/inherited_fields code
remains in place but DORMANT (nothing is flagged, so the hook never fires).

CORRECTED PLAN (unify export onto the EXISTING schema — do NOT reinvent it):
  1. Upgrade export/schema_emit.py to the existing convention:
       - enum: map selected choice -> its lump_value.
       - full write_if vocabulary above.
       - object_ref/pairs_with: treat as computed (resolver needs the Blender
         scene) — either add a resolver hook or leave those specific lumps to the
         existing computed code. (alt-vector stays computed regardless.)
  2. For EACH of the 37 existing-fields actors, validate engine output == the
     current hardcoded export output (same /tmp harness), reading the actor's
     OWN existing fields[] (no new fields authored).
  3. Only after an actor validates, add `schema_export:true` to it (single key,
     no new fields[]). Hook is already authoritative + inheritance-aware.
  4. Keep computed emitters as code (path/water/launcher-alt-vector/crate/checkpoint/
     nav/enemy idle+vis).
  5. Then UI/property-reg already consume the same fields[] -> custom actors get
     UI + export from one schema.
OPEN QUESTION FOR USER: confirm we unify on the existing fields[] convention
(recommended), and whether object_ref/pairs_with lumps should get a schema
resolver or stay as code. Do not author parallel fields[] again.

═══════════════════════════════════════════════════════════════════════════
# UPDATE — engine rebuilt to the EXISTING convention (unify, validated)
═══════════════════════════════════════════════════════════════════════════
- export/schema_emit.py REWRITTEN to consume the DB's real fields[] convention
  (the one the UI panel already uses). Now supports: enum choices (inline with
  lump_value -> emit the int; named-table/no-lump_value -> emit the value string),
  lump.format "(game-task {value})", symbol_literal (bare 'value), lump_bit
  bitfields (key/type/bit_value, OR-accumulated), value_if_true, lump.slot arrays,
  lump.scale, default_per_etype (needs etype), and the full write_if vocabulary
  (always|None, if_true, if_nonzero, if_nonneg, if_positive, if_non_empty,
  if_not_none, if_not_default, if_any_nonzero[group]). SKIPS computed lumps:
  field type object_ref, and lump type eco-info-picker (and default_from inputs).
- export/actors.py hook now passes etype=etype to the engine (for default_per_etype).
- export/test_schema_emit.py rewritten: loads the REAL DB fields[] and asserts the
  engine output == current hardcoded export output for 15 cases covering EVERY
  convention feature (launcher enum+lump_value, oracle named-choice+format, crate
  symbol_literal + eco-info-picker skip, eco-door lump_bit, fuel-cell value_if_true,
  breakaway if_any_nonzero, lavaballoon/darkecobarrel default_per_etype,
  square-platform lump.scale, sharkey if_not_default). ALL 15 PASS.
- Engine/hook are still DORMANT (0 schema_export in DB) -> export unchanged/safe.

## NEXT (flip phase — do per-actor, validated)
  For each of the 37 existing-fields actors, confirm engine output == hardcoded
  for representative inputs (sample of 15 features already covered; spot-check the
  rest), THEN add `schema_export:true` (single key — NO new fields). Computed/hybrid
  stays code: crate eco-info (eco-info-picker), launcher alt-vector (object_ref),
  doors flags ecdf00 LINK bit (so doors: migrate the bits the schema covers but the
  ecdf00 link-OR must be added back as a post-schema code step, OR keep doors fully
  code), water-vol (default_from + vol geometry), enemy idle/vis, path/nav/checkpoint.
  Then author NEW fields[] (IN THIS CONVENTION) for the sync cluster (plat/plat-eco/
  side-to-side-plat/steam-cap: sync slots + options wrap lump_bit + plat-eco notice-dist)
  and pickups (money/buzzer eco-info) which have NO existing fields.

═══════════════════════════════════════════════════════════════════════════
# UPDATE — flip phase: 32 existing-fields actors now schema_export
═══════════════════════════════════════════════════════════════════════════
- Added `schema_export:true` (single key, no new fields) to 32 of the 37
  existing-fields actors. DB verified: 0 duplicate keys, each has schema_export +
  its original fields[]. Engine smoke-tested on all (default + maximal inputs):
  no crashes, well-formed lumps.
- KEPT AS CODE (not flipped): eco-door, jng-iris-door, sidedoor, rounddoor
  (flags has the ecdf00 LINK bit — schema would drop it), and water-vol
  (default_from mesh geometry + vol planes).
- HYBRID flips (schema emits its keys; computed keys stay from code, not in
  _protected so preserved): crate (schema crate-type / code eco-info), launcher
  (schema mode+spring-height / code alt-vector).
- ADDITIVE flips to VERIFY at test time (schema emits a lump the OLD hardcoded
  export did NOT): launcher `mode`, pontoonten `alt-task`. These are intended
  (fields[] was authored more complete than export) but are new emissions.
- money/buzzer/fuel-cell eco-info are CONSTANTS emitted by code (no fields) and
  stay code-driven; fuel-cell's `options` is schema (flipped).

═══════════════════════════════════════════════════════════════════════════
# UPDATE — sync cluster authored + flipped (flip phase complete: 36 actors)
═══════════════════════════════════════════════════════════════════════════
- Authored NEW fields[] (in the existing convention) + schema_export for the 4
  needs_sync actors that had none: plat, plat-eco, side-to-side-plat, steam-cap.
  Fields: og_sync_period/phase/ease_out/ease_in -> sync slots 0-3 (float, always),
  og_sync_wrap -> options lump_bit bit_value 8 (if_true); plat-eco also
  og_notice_dist -> notice-dist (meters, always, default -1.0). Validated vs
  hardcoded (0 failures). DB: 0 duplicate keys, 36 schema_export actors total.
- This makes sync emit UNCONDITIONALLY (the original pathless-platform bug) for
  the whole cluster, not just steam-cap — the schema overrides the path-gated
  hardcoded sync; the computed `path` lump is untouched.
- money/buzzer eco-info stay CODE (constants, no fields). 

## FLIP PHASE DONE. Remaining to finish the restructure:
  E (UI unify): panels/actor_fields.py likely has a GENERIC_PANEL_ETYPES allow-list
    — drop it so ALL actors render their fields[] (via db.inherited_fields), and
    register og_* props from the schema union, so custom DB actors get UI for free.
    (Sync cluster currently shows via the needs_sync UI box, separate from fields.)
  CLEANUP: delete the now-dead hardcoded VALUE branches for the 36 (schema already
    overrides them). Keep computed emitters: crate eco-info, launcher alt-vector,
    doors flags, water-vol, path/pathb/path-k, nav-mesh, checkpoint, enemy idle/vis,
    money/buzzer/fuel-cell eco-info constants. LOW VALUE / cosmetic — fine to defer
    until after a Blender smoke test.
  F: extract_lumps_from_goal.py diff step in build_database.py.

═══════════════════════════════════════════════════════════════════════════
# UPDATE — Step E (UI unify): generic panel now covers all fields-actors
═══════════════════════════════════════════════════════════════════════════
- panels/actor_fields.py: poll() no longer limited to GENERIC_PANEL_ETYPES. It now
  shows for: (allow-list) OR (has inherited_fields AND etype NOT in
  DEDICATED_FIELD_UI_ETYPES). draw() uses db.inherited_fields(etype).
- DEDICATED_FIELD_UI_ETYPES (new frozenset) = actors whose field UI comes from a
  dedicated OG_PT_Actor* panel or the utils.py sync box: crate, launcher, springbox,
  eco-door, jng-iris-door, sidedoor, rounddoor, water-vol, launcherdoor,
  sun-iris-door, caveelevator, oracle, pontoon, plat, plat-eco, side-to-side-plat,
  steam-cap. (If a new dedicated field panel is added later, add it here.)
- VERIFIED safe: among existing actors only `pontoonten` newly shows the generic
  panel (it had fields but no UI); no allow-list∩dedicated overlap, so no double UI.
  Custom DB-only actors with fields[] now get a UI automatically. NEEDS a Blender
  glance to confirm no panel doubles (logic verified; can't run Blender here).
- Property registration NOT needed: fields render as dynamic ID-properties
  (row.prop(obj,'["key"]') / enum+bool via operators reading obj.get(key,default)).
- REMAINING Step E sub-task (Blender-side): at actor spawn, initialise og_* ID-props
  from fields[] resolved defaults so float/int/string fields on CUSTOM actors render
  before first edit (enum/bool already tolerate unset; all existing actors already
  init their props at spawn, so this only affects brand-new custom float/int actors).
  Hook point: the actor-create/spawn operator (operators/actors.py, operators/spawn.py)
  — loop fields[], set o[f["key"]] = resolved default (use db.inherited_fields + the
  same default_per_etype/default_from logic).
