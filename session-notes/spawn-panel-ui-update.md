# Spawn Panel UI Update

**Branch:** `feature/spawn-panel-ui-update`
**Status:** Planning — design locked, not yet implemented.

---

## Goal

Replace the current Spawn Objects panel (1 parent + 14 sub-panels, ~720 lines in
`panels/spawn.py`) with a single unified picker: search bar, sort dropdown,
static multi-select category grid, scrollable list of spawnable objects,
dynamic settings area, spawn button. Same spawn capabilities, dramatically
flatter navigation.

---

## Final design (agreed)

Single panel, top to bottom:

1. **Search input** — the native UIList filter (`self.filter_name`, real-time per keystroke). Expanded by default so it reads as a search bar at the top of the list.
2. **Sort dropdown** — Alphabetical (default) · Category · Art Group · Tpage Group · Favorites first.
3. **Category grid** — 14 static tiles in a `grid_flow`, multi-select toggles. Empty selection ≡ all selected ≡ "show everything."
4. **Scrollable object list** — `UIList`. Each row: star (favorite toggle) · category icon · label. Selection highlights one row.
5. **Dynamic settings area** — appears only when an item is selected. Shows the wiki description (text only, no images) and any pre-spawn fields that item needs (deftype name for Custom Type, sound + radius for Sound Emitter, etc.).
6. **Spawn button** — disabled until an item is selected; spawns at 3D cursor.

Favorites stored per-file (scene CollectionProperty). Wiki images deferred (legal uncertainty); description text only.

---

## Categories — the 14

DB-backed (filter `ENTITY_DEFS` by `info["cat"]`):

| # | Tile | Source `cat` values |
|---|------|--------------------|
| 1 | Enemies | `Enemies`, `Bosses` |
| 2 | Platforms | `Platforms` |
| 3 | Interactive Objects | `Interactive Objects`, `Debug` |
| 4 | Obstacles | `Obstacles` |
| 5 | Buttons and Doors | `Buttons and Doors` |
| 6 | Visuals | `Visuals` |
| 7 | NPCs | `NPCs` |
| 8 | Pickups | `Pickups` |

Synthetic (not in `ENTITY_DEFS` — built from special spawn operators):

| # | Tile | Items |
|---|------|-------|
| 9  | Audio | Sound Emitter · Music Zone |
| 10 | Volumes | Water Volume |
| 11 | Level Flow | Player Spawn · Checkpoint |
| 12 | Cameras | Camera Anchor *(needs target selection)* |
| 13 | Custom Types | Custom Type *(needs deftype name)* |
| 14 | Favorites | *(virtual — filters list to scene-prop favorites set)* |

---

## New data model

### `SpawnItem` — unified spawnable abstraction

New file: `addons/opengoal_tools/spawn_items.py`

```python
@dataclass(frozen=True)
class SpawnItem:
    spawn_id: str          # 'entity:babak' or 'special:music_zone'
    label: str             # 'Babak warrior'
    category: str          # one of the 14 tile names
    art_group: str | None  # for sort
    tpage_group: str | None
    description: str       # from ENTITY_WIKI or hand-authored for specials
    operator: str          # e.g. 'og.spawn_entity'
    op_props: dict         # e.g. {'source_prop': 'entity_type'} for og.spawn_entity
    pre_spawn_fields: list # ids of fields the dynamic settings area should render
    needs_target_sel: bool # True for Camera anchor
    icon: str              # Blender icon name for the row
```

`build_spawn_index()` returns a list of `SpawnItem` covering:
- Every entry in `ENTITY_DEFS` → one `SpawnItem` per entity, category mapped
  from the DB `cat` value using the table above
- Hard-coded `SpawnItem`s for the synthetic categories

The index is built once at addon register.

### Pre-spawn field registry

A small map of field-id → draw function. The dynamic settings area iterates
the selected `SpawnItem.pre_spawn_fields` and calls the corresponding draw
function. Fields needed:

- `nav_radius` — for nav-unsafe enemies (existing `nav_radius` prop)
- `crate_type` — for crates (existing `crate_type` prop)
- `sound` + `radius` — for sound emitters (existing `sfx_sound`, `ambient_default_radius`)
- `music_bank` + `flava` + `priority` + `radius` — for music zones (existing `og_music_amb_*`)
- `custom_name` — for custom types (existing `custom_type_name`)
- `target_context` — for cameras (read-only; shows selected spawn/checkpoint name or warning)

Existing prop names reused where possible to keep operator wiring untouched.

---

## New scene properties

Added to `OGProperties` in `properties.py`:

```python
# Active categories (multi-select). One BoolProperty per category tile.
cat_enemies_active:     BoolProperty(default=False)
cat_platforms_active:   BoolProperty(default=False)
cat_interactive_active: BoolProperty(default=False)
# ... one per tile, 14 total
cat_favorites_active:   BoolProperty(default=False)

# Sort mode
spawn_sort_mode: EnumProperty(items=[
    ('ALPHA', 'Alphabetical', ''),
    ('CATEGORY', 'Category', ''),
    ('ARTGROUP', 'Art Group', ''),
    ('TPAGEGROUP', 'Tpage Group', ''),
    ('FAVORITES', 'Favorites first', ''),
], default='ALPHA')

# UIList backing collection — populated once at register, NOT rebuilt
spawn_list_items: CollectionProperty(type=OGSpawnListRow)
spawn_list_index: IntProperty(default=-1)  # which row is highlighted

# Favorites (per-file)
spawn_favorites: CollectionProperty(type=OGSpawnFavoriteRow)
# OGSpawnFavoriteRow has a single StringProperty: spawn_id
```

`entity_search` (existing) is reused as the search query input.

### Helper functions

```python
def get_active_categories(props) -> set[str]: ...
def is_favorited(scene, spawn_id) -> bool: ...
def toggle_favorite(scene, spawn_id) -> None: ...
```

No `rebuild_spawn_list` needed. `spawn_list_items` is populated **once** at addon
register from `build_spawn_index()` and never re-touched. All filtering and
sorting happens inside `OG_UL_SpawnableItems.filter_items`:

```python
def filter_items(self, context, data, propname):
    items = getattr(data, propname)
    props = context.scene.og_props
    active_cats = get_active_categories(props)
    filter_text = self.filter_name.lower()  # ← native, real-time

    flt_flags = []
    for item in items:
        ok = True
        if active_cats and item.category not in active_cats:
            ok = False
        if filter_text and filter_text not in item.label.lower():
            ok = False
        flt_flags.append(self.bitflag_filter_item if ok else 0)

    # flt_neworder for sort mode
    flt_neworder = sort_by(items, props.spawn_sort_mode)
    return flt_flags, flt_neworder
```

---

## UI components

### `OG_PT_Spawn` (rewritten)

Single panel. No sub-panels. Draws:

```
draw():
  draw_search_row()      # entity_search + sort dropdown
  draw_category_grid()   # 14 tiles in grid_flow(columns=4)
  draw_object_list()     # template_list with OG_UL_SpawnableItems
  draw_dynamic_settings()# only if selected_item is not None
  draw_spawn_button()    # one big operator, disabled unless ready
```

### `OG_UL_SpawnableItems` (new UIList)

Custom `UIList` class. `draw_item`:

```
star_icon = SOLO_ON / SOLO_OFF based on is_favorited
[star] [cat_icon] [label]
```

Star is an operator button (`og.toggle_spawn_favorite`) that flips the
favorite state without changing the list selection.

### Category tiles

Each tile is a property toggle (`layout.prop(props, f"cat_{name}_active", toggle=True)`)
inside a `grid_flow(row_major=True, columns=4, even_columns=True, even_rows=True)`.
`depress=True` styling comes for free from the BoolProperty toggle.

The Favorites tile uses a different icon (`BOOKMARKS` or `SOLO_ON`) to read as user-managed vs. static.

### Dynamic settings area

```python
def draw_dynamic_settings(layout, item):
    box = layout.box()
    if item.description:
        col = box.column()
        col.scale_y = 0.85
        # wrap description across rows
    for field_id in item.pre_spawn_fields:
        FIELD_DRAWERS[field_id](box, ctx, item)
```

`FIELD_DRAWERS` is a dict of field-id → draw function. Camera's `target_context`
field is what currently lives in `_draw_entity_sub`'s navmesh inline section,
generalized.

---

## Unified spawn operator

`og.spawn_selected` (new) dispatches based on the selected `SpawnItem`:

```python
class OG_OT_SpawnSelected(Operator):
    bl_idname = "og.spawn_selected"

    def execute(self, ctx):
        item = current_spawn_item(ctx)
        if item is None:
            return {'CANCELLED'}
        # Validate pre-spawn fields (e.g. custom_type_name not empty)
        if not validate_pre_spawn(ctx, item):
            self.report({'ERROR'}, 'Missing required field')
            return {'CANCELLED'}
        # Set any backing props the target operator needs
        apply_op_props(ctx, item)
        # Invoke the underlying operator
        getattr(bpy.ops, item.operator.replace('og.', 'og.'))(...)
        return {'FINISHED'}
```

For `og.spawn_entity` items, this means setting `entity_type` first
(reuses the existing operator unchanged).

---

## Implementation phases

Each phase ends in a testable state. Commit at the end of each.

### Phase 1 — Data layer (no UI changes yet)
- [ ] Create `spawn_items.py` with `SpawnItem` dataclass and `build_spawn_index()`.
- [ ] Verify the index is well-formed (count, no dups, all categories represented) via a one-off print.
- [ ] Add `OGSpawnListRow` and `OGSpawnFavoriteRow` PropertyGroup classes in `properties.py`.
- [ ] Register them and add the new scene properties (`cat_*_active`, `spawn_sort_mode`, `spawn_list_items`, `spawn_list_index`, `spawn_favorites`).
- [ ] Populate `spawn_list_items` once at register from `build_spawn_index()`.
- [ ] Add `get_active_categories()`, `is_favorited()`, `toggle_favorite()` helpers.
- [ ] Old panel still works. Nothing visible has changed.

### Phase 2 — UIList with native filter and sort
- [ ] Add `OG_UL_SpawnableItems` class in `panels/spawn.py` (or split to `panels/spawn_list.py`).
- [ ] Set `use_filter_show = True` so the filter input is expanded by default.
- [ ] Implement `filter_items` to combine `self.filter_name` (real-time search) + category booleans + sort mode.
- [ ] Add a temporary debug panel that just shows the UIList — verify filter + sort behaviors before wiring it into the real panel.

### Phase 3 — Unified spawn operator
- [ ] Add `OG_OT_SpawnSelected` and `OG_OT_ToggleSpawnFavorite`.
- [ ] Spawn dispatcher routes to existing operators (`og.spawn_entity`, `og.spawn_player`, `og.spawn_checkpoint`, `og.spawn_cam_anchor`, `og.add_water_volume`, `og.add_music_zone`, `og.add_sound_emitter`, `og.spawn_custom_type`, `og.spawn_platform`).
- [ ] Pre-spawn validation for items with `pre_spawn_fields` (e.g. Custom Type needs a name).
- [ ] Test each item type spawns correctly via the debug panel.

### Phase 4 — Tile grid + dynamic settings + spawn button
- [ ] Build category grid as a panel section.
- [ ] Build `draw_dynamic_settings()` with the `FIELD_DRAWERS` registry. Port the per-field draw code from `_draw_entity_sub` and the special-panel forms (Sound Emitter, Music Zone, Custom Type).
- [ ] Build spawn button. Disabled state messaging when no item selected, when validation fails, or when context is missing (Camera anchor with no target).
- [ ] All assembled in the new `OG_PT_Spawn` draw method.

### Phase 5 — Cutover
- [ ] Remove old sub-panel classes from `panels/spawn.py`:
  `OG_PT_SpawnSearch`, `OG_PT_SpawnLimitSearch`, `OG_PT_SpawnEnemies`,
  `OG_PT_SpawnPlatforms`, `OG_PT_SpawnProps`, `OG_PT_SpawnObstacles`,
  `OG_PT_SpawnButtonsDoors`, `OG_PT_SpawnVisuals`, `OG_PT_SpawnNPCs`,
  `OG_PT_SpawnPickups`, `OG_PT_SpawnSounds`, `OG_PT_SpawnMusicZones`,
  `OG_PT_SpawnWater`, `OG_PT_SpawnCustomTypes`, `OG_PT_SpawnLevelFlow`.
- [ ] Update `CLASSES` registration tuple.
- [ ] Remove Limit Search properties (`tpage_limit_enabled`, `tpage_filter_1`, `tpage_filter_2`) and the `_make_filtered_enum` wrapper if nothing else uses them.
- [ ] Keep `_draw_entity_sub` if anything else uses it; otherwise delete.
- [ ] Smoke test: every category spawns its things, favorites persist across save/load, sort modes all work.

### Phase 6 — Polish
- [ ] Empty state when filters produce zero matches.
- [ ] Empty state for Favorites tile when no favorites set.
- [ ] Per-tile entity counts? (`Enemies (42)`) — TBD, may be too noisy.
- [ ] Showing-X-of-Y count above the list.
- [ ] Verify Preview Models toggle (currently inside Enemies sub-panel) — move to addon prefs or top of the new panel.

---

## Code being removed

| File | What |
|------|------|
| `panels/spawn.py` | 14 of 16 panel classes (everything except `OG_PT_Spawn` itself and the search-select operator) |
| `properties.py` | `tpage_limit_enabled`, `tpage_filter_1`, `tpage_filter_2`, `show_platform_list`, `show_spawn_list`, `show_checkpoint_list` (replaced by selection state) |
| `data.py` | `_build_tpage_filter_items`, `TPAGE_FILTER_ITEMS`, `_tpage_filter_passes`, `_make_filtered_enum` (if Limit Search filter is fully replaced by tpage sort) |
| `utils.py` | `_draw_entity_sub` (logic moves into `FIELD_DRAWERS` + `draw_dynamic_settings`) |

Existing per-category enum items (`ENEMY_ENUM_ITEMS`, `PROP_ENUM_ITEMS`, etc.)
can stay — they're still used by the underlying spawn operators which read
from the scene properties.

---

## Risks / unknowns

1. **UIList rebuild performance.** Total spawnable count is probably ~200. UIList filter callbacks run on every redraw; pre-filtering into `spawn_list_items` instead of using Blender's filter callback should keep this fast. If it does drag, we can throttle the rebuild.

2. **Search input mechanism.** Original concern (StringProperty `update` fires on focus-loss, not per keystroke) was misdirected — Blender's `UIList` has a built-in filter input that updates `self.filter_name` per keystroke and re-runs `filter_items` on each character. The fix is to use the native UIList filter instead of a separate StringProperty: set `use_filter_show = True` on the UIList class so the filter section is expanded by default, looking like a search bar attached to the list. This also removes the need for manual `rebuild_spawn_list` — `filter_items` combines `self.filter_name` + our category booleans + sort mode on each redraw.

3. **Camera context-driven spawn.** Currently `og.spawn_cam_anchor` reads from the selected object's name. The new flow needs the selected scene object preserved through the dispatcher. Should be fine since `bpy.ops` invocations preserve the active object, but worth verifying.

4. **`_draw_entity_sub`'s navmesh-link inline UI.** Actor-management UI that hitchhiked into the picker. The same controls already exist in `panels/selected.py` (lines 166-191) and `panels/actor.py` (lines 187-207), so nothing needs to move — the plan just deletes the duplicate when `_draw_entity_sub` goes.

5. **`OG_PT_SpawnEnemies` Preview Models toggle UI.** Currently lives only in the Enemies sub-panel. In the unified design either (a) move to addon prefs, or (b) show in dynamic settings when an enemy with previewable model is selected. Lean toward (a) — it's a per-user preference not a per-spawn one.

---

## Open small decisions

- **Tile column count.** 14 tiles → 4×4 with 2 empty (denser) or 3×5 with 1 empty (taller). Decide visually in Phase 4.
- **First-item auto-select.** When filters change and selection becomes invalid, auto-select the new top item or clear selection? Lean toward clear — selection should be explicit.
- **Double-click to spawn from list.** Nice-to-have. Defer.
- **Keyboard navigation.** Inherits whatever `UIList` supports. Don't customize.
