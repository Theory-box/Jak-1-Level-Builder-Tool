# Direct Questions — Pre-Fix Answers

> **Purpose of this document.** This is a **temporary planning doc**, not a finished change-log. Each section below is a proposed fix or implementation plan for an open item from `Direct Questions.md`, written before any code is touched. The goal is to let humans approve, reject, or modify the approach — and to let other AI sessions pick up the work without re-deriving everything — *before* edits land in the addon.
>
> Once a section is approved and implemented, the corresponding open item in `Direct Questions.md` should get a `Claude:` reply summarising what shipped, the human marks it `[SOLVED]`, and the section here can be dropped or archived.
>
> **For reviewers:** confidence levels are noted at the bottom of each section. Anything below ~80% means there's a real chance the proposed fix is wrong or incomplete and should be tested live before committing.

---

## Table of Contents
- [Fix 1 — Better auto-detect of dev env](#fix-1--better-auto-detect-of-dev-env)
- [Fix 2 — Object rotation isn't correctly exported](#fix-2--object-rotation-isnt-correctly-exported)
- [Fix 3 — Green eco vent not working](#fix-3--green-eco-vent-not-working)
- [Fix 4 — Next/Prev actor lump issues](#fix-4--nextprev-actor-lump-issues)
- [Fix 5 & 6 — balance-plat / mis-bone-bridge crashes](#fix-5--6--balance-plat--mis-bone-bridge-crashes)
- [Feature 1 — Make preview mesh "useable"](#feature-1--make-preview-mesh-useable)

---

## Fix 1 — Better auto-detect of dev env

### Why Kui's setup fails
Kui's dev clone:
- Main path: `MainRepoFolder` (has `goal_src/jak1`)
- Binary at: `MainRepoFolder/out/build/Release/bin/`
- Data path: `MainRepoFolder` (same as main)
- Decompiler at: `MainRepoFolder/decompiler_out/jak1/`

`_scan_for_installs` (`build.py:118-153`) has two issues that combine to defeat dev-layout auto-detection:

1. **The root itself is never tested.** `_walk` iterates `path.iterdir()` for the supplied root, so the root path is never directly checked for `gk + goalc` or `goal_src/jak1`. With `og_root_path = MainRepoFolder`, the scanner walks children (`goal_src`, `data`, `out`, `decompiler_out`, …) looking for matches that are actually one level higher.
2. **`out` is in `skip_dirs`.** Even if the root were checked, the dev-layout binary lives at `out/build/Release/bin/`. `out` being skipped means that subtree never gets walked.

### Proposed change — `build.py:_scan_for_installs`
- Pre-check the root before recursing: if `<root>/gk{ext}` and `<root>/goalc{ext}` both exist → add `root` to `exe_folders`. If `<root>/goal_src/jak1/` or `<root>/data/goal_src/jak1/` exists → add `root` to `data_folders`.
- Remove `"out"` from `skip_dirs`. With `max_depth=4`, the dev-layout path (`out/build/Release/bin/`, depth 4) is reachable; release-layout `out/jak1/iso/` has no `gk`/`goalc` and no `goal_src/jak1`, so no false positives.
- Once the root is recognised as a data folder, the existing `_decompiler_path()` already auto-derives `<root>/decompiler_out/jak1/` correctly — no further change needed for that path.

### UX detail
With the root recognised as the data folder, the picker will show one entry whose `_rel(d)` is `.` (root relative to itself). Either render that as the literal `"."` or special-case to `"(root)"` in the draw method.

### Confidence
~90%. Recursion logic and skip-dir analysis are clear from the source. Only outstanding uncertainty is whether any release distribution puts something `gk`-shaped under `out/` that would now be mis-detected — none of the documented release layouts do, but worth a smoke test against a downloaded release before merging.

---

## Fix 2 — Object rotation isn't correctly exported

### Current code — `export/actors.py:89-99`
```python
_R  = mathutils.Matrix(((1,0,0),(0,0,1),(0,-1,0)))
_m3 = o.matrix_world.to_3x3()
_gq = (_R @ _m3 @ _R.transposed()).to_quaternion()
aqx = round(-_gq.x, 6)
aqy = round(-_gq.y, 6)
aqz = round(-_gq.z, 6)
aqw = round( _gq.w, 6)
```
Output: `[aqx, aqy, aqz, aqw]`. Comment claims "the engine reads quaternions as the conjugate (negate xyz)".

### Math check on Kui's example
Blender quat: `(W=0.932, X=0.067, Y=0.025, Z=-0.355)`

`R = [[1,0,0],[0,0,1],[0,-1,0]]` is the basis change Blender→game (sends `(x,y,z)` → `(x, z, -y)`). For an orthogonal `R`, the similarity transform `R M R^T` produces a rotation matrix whose quaternion has the same scalar and a vector part that's `R` applied to the original vector part. So:

- `_gq.w = 0.932`
- `_gq.x = 0.067`         (was bl.x)
- `_gq.y = -0.355`        (was bl.z)
- `_gq.z = -0.025`        (was -bl.y)

After current negation: `[-0.067, 0.355, 0.025, 0.932]` — matches Kui's "buggy" output exactly.
Without negation: `[0.067, -0.355, -0.025, 0.932]` — matches Kui's "correct" output exactly.

### Smoking gun — the spawn path already documents this exact bug
`export/scene.py:440-453` (spawn / checkpoint quaternion export):
> Remap: `game_rot = R_remap @ bl_rot @ R_remap^T`
> Maps Blender Z-rotation → game Y-rotation (yaw). **No conjugate —** the similarity transform already produces the correct orientation.
> **(The previous conjugate was erroneously borrowed from the camera system; it inverted facing for all non-0°/180° angles.)**

The spawn path was fixed by removing the negation. The same bug exists in `actors.py` and was not propagated.

### Proposed change — `export/actors.py:96-99`
Drop the four minus signs:
```python
aqx = round(_gq.x, 6)
aqy = round(_gq.y, 6)
aqz = round(_gq.z, 6)
aqw = round(_gq.w, 6)
```

### Out-of-scope but related
`export/scene.py:281-284` has the same `-x, -y, -z, w` pattern in the camera-marker export, applied to a quaternion built from a hand-constructed look-at basis `[right, up, gl]`. It's almost certainly the same bug — but the input is a reconstructed orientation matrix rather than the user's empty rotation, so the symptoms differ (flipped roll axis, mirrored aim). Worth flagging as a follow-up; not part of Kui's question and shouldn't ship in the same patch without a separate camera test.

### Confidence
~98%. The math is unambiguous and the spawn-path comment is a smoking gun. Only thing not done is round-trip testing through goalc and a live game launch.

---

## Fix 3 — Green eco vent not working

### Why Kui's database edit failed
Database `lumps` entries only **declare** that a lump field exists for manual editing — they don't write a default value. The actual lump emission for special-case pickups happens in `export/actors.py:101-133`, in a cascade of `if etype == "X":` blocks.

The database entry for `ecovent` already has a TODO comment at `jak1_game_database.jsonc:5683-5684`:
```
// Eco Vent Green needs a special case in lumps because there's no actor for it
// It needs an eco-info with the pickup type set to eco-green and amount to 1
```
So the previous author flagged this exact gap; it was never finished.

### Comparison to other eco vents
- `eco-yellow`, `eco-red`, `eco-blue` use distinct etypes — engine-side logic ties etype to pickup type. No lump needed.
- `ecovent` (green) is the generic vent class; needs an explicit `eco-info` lump to pick the colour. That's why it's in the same actor block as the "needs special case" comment.

### Proposed change — extend the existing cascade
`export/actors.py`, after the `elif etype == "money":` block at line 132:
```python
elif etype == "ecovent":
    lump["eco-info"] = ["eco-info", "(pickup-type eco-green)", 1]
```
That produces:
```json
"eco-info": ["eco-info", "(pickup-type eco-green)", 1]
```
which is exactly the format Kui described. Pattern matches `money`, `crate`, `fuel-cell`, `buzzer` lines above it.

Also remove the TODO comment in `jak1_game_database.jsonc:5683-5684` when this lands.

### Database-edit guidance — for Kui's "future reference" follow-up
For pickups whose lump value is **fixed** (not user-editable, like a green vent always dispensing eco-green): special-case in the python export cascade above, do **not** add a `lumps` entry to the database for that key — that would create an editable UI field the user has to fill in every time, defeating the point of a fixed-value vent.

For pickups whose lump value is **user-editable** (like crates, where pickup type and amount are choosable): both pieces are needed — a `lumps` entry (declares the lump exists) and a `fields` entry (drives the UI and links the field to the lump key via `lump.key` + `lump.type`). The crate entry around line 5470 is the working template.

Green vents fall into the first bucket, so no database edit is needed beyond removing the TODO comment.

### Optional follow-up — data-driven defaults (out of scope)
Cleaner long-term: extend the database schema with a `default_lumps` array and have `export/actors.py` apply it generically before the special-case cascade. Then `ecovent` would be:
```json
"default_lumps": [
  ["eco-info", ["eco-info", "(pickup-type eco-green)", 1]]
]
```
and `fuel-cell`/`buzzer`/`money` could move out of the python cascade into this declarative form. Refactor for later, not part of this fix.

### Confidence
~95%. Lump format matches the `money` and `crate` formats verbatim. The TODO comment confirms intent. Only thing not done is launching the game to confirm a green vent actually dispenses green eco — but the lump shape is identical to working pickup paths, so failure would be surprising.

---

## Fix 4 — Next/Prev actor lump issues

### Root cause
`prev-actor` and `next-actor` are declared in the database for three actors with `type: "structure"`:
- `balance-plat` — `jak1_game_database.jsonc:5931-5940`
- `warp-gate` — `jak1_game_database.jsonc:6750-6759`
- `basebutton` — `jak1_game_database.jsonc:9217-9226` (also has `link_slots`)

But `"structure"` is **not** in `LumpTypes` (`jak1_game_database.jsonc:3432-3528`). Valid types are: `float`, `meters`, `degrees`, `int32`, `uint32`, `enum-int32`, `enum-uint32`, `vector4m`, `vector3m`, `vector-vol`, `vector`, `movie-pos`, `water-height`, `eco-info`, `cell-info`, `buzzer-info`, `symbol`, `string`, `type`. When Kui clicks "Use This" on a `structure`-typed reference, `OG_OT_UseLumpRef.execute` (`panels/tools.py:373`) sets `row.ltype = "structure"`, which Blender's enum validation rejects → the traceback Kui posted.

### What the addon already does correctly
There's an established **link system** for actor-to-actor references — see `link_slots` on `basebutton` (`jak1_game_database.jsonc:9249-9268`). It:
- Surfaces a UI control for picking another actor by name
- Validates against an `accepts: [...]` whitelist
- Emits the lump at export as `["string", "name1", "name2", ...]` via `_build_actor_link_lumps` (`data.py:548-580`)

`knowledge-base/opengoal/lump-system.md:235-238` confirms this is the canonical mechanism for prev-actor/next-actor:
> JSONC: referenced via `entity-actor-lookup` — set by actor reference system, not direct lump

So `balance-plat` and `warp-gate` are **missing their `link_slots` definitions** — they were declared as manual lump rows when they should be link-system actors.

### Proposed change — two-part edit in `jak1_game_database.jsonc`

**Part 1 — add `link_slots` to `balance-plat`.** After the closing of its `lumps` array (around line 5941), add:
```json
"link_slots": [
  {
    "lump_key": "next-actor",
    "slot": 0,
    "label": "Next balance platform",
    "accepts": ["balance-plat"],
    "required": false
  },
  {
    "lump_key": "prev-actor",
    "slot": 0,
    "label": "Previous balance platform",
    "accepts": ["balance-plat"],
    "required": false
  }
],
```

**Part 2 — add `link_slots` to `warp-gate`.** Same structure, with `accepts: ["warp-gate"]` and labels mentioning warp gates.

**Part 3 — remove the broken manual lump entries.** For `balance-plat` (5931-5940) and `warp-gate` (6750-6759), delete the `next-actor` and `prev-actor` entries from the `lumps` array. They're redundant once `link_slots` is in place, and they're the source of the broken `structure`-type reference. `distance` (balance-plat) and `timeout` (warp-gate) stay — those are real numeric lumps.

### About the format Kui expected
Kui wrote that the export should be a bare string:
```json
"prev-actor": "test1_balance-plat_0001"
```
but the link system emits the list form:
```json
"prev-actor": ["string", "test1_balance-plat_0001"]
```
which is what `basebutton` chains use today and what the addon will produce for `balance-plat` once `link_slots` is added.

Two possibilities:
1. **The list form is correct.** Naughty Dog's res-lump JSON format wraps every typed value as `[type, ...payload]`, and the GOAL `entity-actor-lookup` reads the string from index 1. `basebutton` chains have shipped working with this form, which is strong evidence.
2. **`balance-plat` actually reads bare-string.** Possible if `swamp-obs.o` uses a different res-lump accessor than `basebutton`. To confirm, would need to inspect `swamp-obs.gc` for how it calls `res-lump-struct` or `res-lump-data` on the `prev-actor` key.

**Recommendation:** ship the link_slots fix (matches the working basebutton pattern), and if balance-plat still doesn't link correctly at runtime, the next debug step is to check `swamp-obs.gc` for the actual lookup form and either patch the JSON converter or the database schema to emit bare-string for those keys specifically.

### About Kui's "custom type" feature ask
Kui asked whether a freeform lump type should exist. The current `string` type already accepts any value. What Kui actually wants is a way to emit a **bare-string** lump (no `["string", ...]` wrapper). That's a small addition to `_parse_lump_row` (`data.py:593-664`) — e.g. a `raw-string` ltype that returns the value alone instead of the typed list. Out of scope for the immediate fix; flag for the same follow-up as the format-question above.

### Confidence
- Root cause analysis: ~99%. Traceback is unambiguous, `structure` type is plainly missing from `LumpTypes`.
- Link-slots fix: ~85%. Pattern matches basebutton exactly. Small uncertainty about what `accepts:` should list — the original game might chain `balance-plat` with non-`balance-plat` types — but that's recoverable by editing the array later.
- Format expectation: ~60%. List form matches basebutton precedent but there's a real chance Kui has GOAL-side evidence for bare-string that I haven't seen.

---

## Fix 5 & 6 — balance-plat / mis-bone-bridge crashes

### Two questions, similar symptoms — strong hint they share a cause
Both report `STATUS_STACK_BUFFER_OVERRUN` (`0xC0000409`) on level load. Both backtraces show the unwinder losing context (`"Backtrace was too long. Exception might have happened outside GOAL code"`) and falling into raw stack data — the repeating `0x657361422d646f4d` chunks in the rip column decode to `"Mod-Base"`, which is stack content being mis-read as instruction pointers, not real return addresses. That pattern is consistent with corrupted state during a load step (bad type registration, bad return value, mismatched function signature).

### What's different about these two actors
Both share a shape no other addon-spawnable actor has:
- `o_only: true` shared obstacle module — `swamp-obs.o` / `misty-obs.o`
- These are **multi-type** code modules: `swamp-obs.gc` defines balance-plat, tar-plat, swamp-rock, swamp-spike, swampgate, swamp-rat-nest, etc., each referencing the others' types within the file. `misty-obs.gc` is the same shape for misty obstacles.

`needed_code` (`export/levels.py:64-87`) injects the single referenced `.o` into the custom DGO. For `o_only` types it writes `(o, None, None)` so the .o is added to the .gd file but no `goal-src` line is added to `game.gp` — the comment at line 67-68 says "vanilla game.gp already has their goal-src lines."

That assumption holds only if the .o is self-contained. For an obstacle module that references sibling types defined in its OWN file, that's fine. For a module that references types defined in sibling .o files (e.g. `kermit.o`, `swamp-bat.o`), the injected .o has unresolved external references when linked alone. Vanilla SWA.DGO works because `swa.gd` lists every swamp `.o` in the same package; references resolve internally. A custom DGO that lists only `swamp-obs.o` may drop external references that aren't in the link set.

### Specific actors and their docs status

**balance-plat**
- `knowledge-base/opengoal/platform-system.md:609-616` (test 2026-04-09): "Designed as a linked chain of platforms that communicate — standalone one never receives `'grow`. Physics exist in code but require a chain partner to function. **Not fixable from addon side — game design limitation**." That test reported a non-functional but loaded actor — no crash. Kui's report is a newer, harder failure than what's documented.
- `knowledge-base/opengoal/entity-spawning.md:692` (source-verified April 2026): reads `distance` (meters, default 5m) and `scale-factor` (float, default 1.0). No mention of prev/next-actor being required at spawn time.
- The `prev-actor`/`next-actor` lumps in the database are part of Fix 4's `structure`-type bug. Kui worked around it by manually editing the export, which likely produced a malformed lump payload — that on its own could trigger a crash if the engine dereferences it during init.

**mis-bone-bridge**
- Listed at `entity-spawning.md:671` as added/spawnable. No "broken" notes anywhere.
- Database entry (`jak1_game_database.jsonc:8260-8297`) declares `animation-select` (uint32, valid values 1, 2, 3, 7) with field default `0` and `write_if: if_nonzero`. So unless the user types a value, the lump is omitted. The description claims "Default 0 (no particles)" but the valid-values list doesn't include 0. If the engine reads `animation-select` as a particle group index and indexes into a bounded array using 0, that's a plausible early crash.

### Proposed plan — three independent diagnostics, run in order

**Step 1 — fix the prev/next-actor lumps for balance-plat (Fix 4).**
Add `link_slots` to `balance-plat` and remove the broken `structure`-typed manual entries. After that, do **not** edit the exported JSON manually — let the addon emit the canonical `["string", "name"]` form via the link system. If the crash was caused by malformed manual JSON, this resolves it.

**Step 2 — try mis-bone-bridge with `animation-select` set to 1.**
In Blender: set the `og_bone_bridge_anim` field to 1, export, build, run. If it loads without crashing, change the default in the database (`jak1_game_database.jsonc:8289`) from `0` to `1` and switch `write_if` to `"always"`. If it still crashes, animation-select isn't the cause and we move to step 3.

**Step 3 — investigate sibling .o dependencies.**
This is where it gets speculative without a debug build. Two ways to probe:
- **Check the link output.** When the custom DGO is built, examine the goalc output for unresolved-symbol or undefined-type warnings. If `swamp-obs.o` complains about types in `kermit.o`/`swamp-bat.o`/etc. being missing, we have confirmation.
- **Try inlining sibling modules manually.** Edit the generated `.gd` file by hand: add `"kermit.o"`, `"swamp-bat.o"`, `"swamp-rat.o"`, `"flutflut.o"`, etc. to the file list (the same set vanilla `swa.gd` ships with — minus the geometry .go). Rebuild. If the crash disappears, the addon needs an "include sibling .o files for multi-type obstacle modules" rule.

If step 3 confirms the dependency hypothesis, the fix is to extend `needed_code` (`export/levels.py:64-87`) with a per-module dependency map — when injecting `swamp-obs.o`, also inject the swamp companion .o files. The same for `misty-obs.o`. The map can live in `jak1_game_database.jsonc` under a new `code_module_companions` section so it's data-driven.

### What to actually tell Kui
1. The platform doc's prior-tested verdict on balance-plat was "loads but doesn't function" — Kui's crash is a regression or a new failure mode, not the previously documented limitation.
2. Run step 1 first — fix the prev-actor/next-actor format the proper way (link_slots) and stop editing the JSON manually. That alone may resolve the balance-plat crash.
3. Run step 2 in parallel for mis-bone-bridge.
4. If either crash survives step 1/2, step 3 is the real-debug path — would need Kui to either share goalc compile output, or do a manual `.gd` edit to test the dependency hypothesis.
5. Even once balance-plat loads cleanly, `platform-system.md:609-616` still warns that without a chain partner it stays in the wrong collide list and Jak passes through it. The crash and the standalone-non-functional issue are separate problems; fixing one doesn't fix the other.

### Confidence
- Step 1 fix → addressing the malformed-lump cause: ~60%.
- Step 2 fix → animation-select=0 being invalid: ~40%. Plausible but the database description claims 0 is valid, and source-verification didn't flag it.
- Step 3 hypothesis → sibling .o dependency: ~55%. Strong by elimination (both crashes share the o_only-multi-type-module shape) but unconfirmed without runtime/compile output.
- Overall: this item needs interactive debugging. The doc is intentionally a diagnostic ladder rather than a one-line fix.

---

## Feature 1 — Make preview mesh "useable"

### Current state — `model_preview.py`
Two preview-mesh paths, both lock selection:
- Actor preview at line 257: `mesh_obj.hide_select = True   # non-selectable — move the ACTOR empty instead`
- Waypoint preview at line 379: `mesh_obj.hide_select = True`

`_PREVIEW_PROP = "og_preview_mesh"` and `_WAYPOINT_PREVIEW_PROP = "og_waypoint_preview_mesh"` mark the meshes; `_is_any_preview(obj)` (line 384) returns True for either.

The lock is intentional ("move the ACTOR empty instead") — Kui wants the inverse: clickable preview that auto-redirects the active selection to the parent empty so the actor's settings panel appears.

### Three problems to solve, exactly as Kui listed them
1. **Selectability.** The `hide_select = True` lines need to come off.
2. **Click → parent.** When the user clicks a preview mesh, the actor empty (parent) becomes the selected/active object — not the mesh. Same for shift-click and box-select.
3. **Panel reflects the actor.** This is a free consequence of #2: panels read `bpy.context.active_object`, so once the parent is active, the actor settings panel renders.

### Proposed implementation

**Part 1 — preference toggle.**
Add to `properties.py:OGPreferences`, near `preview_models` at line 84:
```python
preview_click_through: BoolProperty(
    name="Click-through preview meshes",
    description="Clicking a preview mesh selects its actor empty instead (so the actor's panel opens). Disable to select the mesh directly.",
    default=True,
)
```

**Part 2 — drop the `hide_select` lock.**
In `model_preview.py`, change lines 257 and 379 from `True` to `False`. Add a comment noting click-through redirects selection to the parent when the preference is on.

**Part 3 — selection redirector via msgbus.**
Subscribe to active-object changes via `bpy.msgbus`. When the new active is a preview mesh, swap to its parent.

```python
# In model_preview.py, near module bottom

_msgbus_owner = object()  # any unique sentinel

def _on_active_changed():
    ctx = bpy.context
    prefs = ctx.preferences.addons.get("opengoal_tools")
    if not prefs or not getattr(prefs.preferences, "preview_click_through", True):
        return
    if ctx.mode != "OBJECT":
        return
    obj = ctx.view_layer.objects.active
    if obj is None or not _is_any_preview(obj):
        return
    parent = obj.parent
    if parent is None or parent.hide_get():
        return
    obj.select_set(False)
    parent.select_set(True)
    ctx.view_layer.objects.active = parent

def register_selection_msgbus():
    bpy.msgbus.subscribe_rna(
        key=(bpy.types.LayerObjects, "active"),
        owner=_msgbus_owner,
        args=(),
        notify=_on_active_changed,
        options={"PERSISTENT"},
    )

def unregister_selection_msgbus():
    bpy.msgbus.clear_by_owner(_msgbus_owner)
```

Wire those into `__init__.py`'s `register()` / `unregister()` paired with the existing addon registration. msgbus subscriptions don't survive `Load Factory Settings` or file load; add a `@bpy.app.handlers.persistent` `load_post` handler that re-calls `register_selection_msgbus`.

**Part 4 — box-select / shift-click multi-select (out of scope for now).**
The msgbus path handles single-click. For box-select (B) or shift-click that picks several objects at once, the active-object change fires once at the end of the operator, so the callback only sees the final active object. Adequate for Kui's listed requirements (select-mesh → see-actor-panel) but not for "select 3 meshes → select 3 parents." A separate `depsgraph_update_post` pass that scans `selected_objects` for previews and swaps each one to its parent would cover that case. Flag as a follow-up if Kui wants box-select to feel right.

### Caveats
- **Outliner / search popup.** Clicking a preview mesh in the Outliner triggers the same active-change event, so the redirect works there too. Same for the Search ⌘F popup.
- **Edit mode.** The `ctx.mode == "OBJECT"` guard prevents the redirect from yanking the user out of edit mode if they Tab into a preview mesh.

### Confidence
~80%. The `hide_select` toggle and msgbus redirect are well-trodden Blender patterns and integrate cleanly with the existing preview-mesh tagging system. Box-select multi-redirect is the only piece I'd want to validate live before committing to a particular implementation.
