# Backward-compatibility code (to clean up later)

During development old `.blend` files and older database formats are **not**
supported on purpose (Kuitar, 2026-10-08): breaking changes are fine, and new
compatibility code is only added when a break would really hurt, after asking.

The shims below were added before that rule. Each is marked in the code with a
`# COMPAT:` comment so they're easy to find (`grep -rn "COMPAT:" addons/`).
They can all be removed once nobody has files from before the
`claude/actor-list` branch.

| Where | What it keeps working | Remove with |
| --- | --- | --- |
| `db.py` `code_files()` | Old actor `"code"` objects (`{"o", "o_only"}`, `{"in_game_cgo"}`) and a separate `"extra_code"` list in override databases | the dict / `extra_code` branches |
| `db.py` `_record_panels()` | Older override databases with the pre-panel keys: `"fields"`, `"panel"`, `needs_path` / `needs_pathb` / `path_linear_only` / `paths`, `needs_sync`, `link_slots`, `requires_navmesh` / `nav_safe`, `need_vol`, `is_launcher`, `is_water`, Enemies-category activation/visibility, `spawns_lurkers`, `needs_notice_dist` | everything after `if "panels" in rec: return ...` |
| `db.py` `legacy_keys()` / `prop_getter()` + PanelTypes `"legacy_key"` (fact-options wrap-phase, skip-jump-anim) | Props saved as `og_sync_wrap` / `og_cell_skip_jump` still export | both functions (use `o.get` again), the two `"legacy_key"` lines in the DB |
| `__init__.py` `_migrate_legacy_props()` (load_post) | Copies `og_sync_wrap` / `og_cell_skip_jump` to the new keys, and the old scale fields (`og_scale_x/y/z/w`, `og_orbit_scale`, `og_shark_scale`) onto the empty's scale | the handler and its register / unregister lines |
| `db.py` `trait_fields()` + empty `"TraitFields": {}` in the DB | Override databases that still fill TraitFields | the function, `_TRAIT_PREDICATES`, the export loop over traits in `export/actors.py`, the DB section |
| `export/test_schema_emit.py` `_fields()` | Dev test reading old DBs with `"fields"` | the fallback line |

Not compatibility code, but related: the `"export": false` / pinned overrides
written during the parenting step (pickup-spawner, swampgate,
warp-gate-switch, citb-bunny, citb-exit-plat, muse, lightning-mole, ecovent)
keep those actors' exports unchanged; review them in the per-actor pass.
