# ───────────────────────────────────────────────────────────────────────
# panels/spawn.py — OpenGOAL Level Tools
#
# Spawn picker panels: search, category tabs (enemies/platforms/props/etc.), water spawn.
#
# Auto-generated from the original panels.py by the refactor split.
# Edit freely — this is no longer a generated file.
# ───────────────────────────────────────────────────────────────────────

from __future__ import annotations

import bpy
from bpy.types import Panel, Operator
from pathlib import Path
from ..data import (
    ENTITY_DEFS, ENTITY_WIKI, ENTITY_ENUM_ITEMS, ENEMY_ENUM_ITEMS, VERTEX_EXPORT_TYPES,
    PROP_ENUM_ITEMS, NPC_ENUM_ITEMS, PICKUP_ENUM_ITEMS, PLATFORM_ENUM_ITEMS,
    CRATE_ITEMS, CRATE_PICKUP_ITEMS, ALL_SFX_ITEMS, SBK_SOUNDS, LEVEL_BANKS,
    LUMP_REFERENCE, ACTOR_LINK_DEFS, LUMP_TYPE_ITEMS,
    NAV_UNSAFE_TYPES, NEEDS_PATH_TYPES, IS_PROP_TYPES, ETYPE_AG,
    _lump_ref_for_etype, _actor_link_slots, _actor_has_links,
    _actor_links, _actor_get_link, AGGRO_TRIGGER_EVENTS,
    _parse_lump_row, _LUMP_HARDCODED_KEYS,
    GLOBAL_TPAGE_GROUPS, _is_custom_type,
)
from ..collections import (
    _get_level_prop, _set_level_prop, _level_objects, _active_level_col,
    _all_level_collections, _classify_object, _col_path_for_entity,
    _recursive_col_objects, _ensure_sub_collection, _link_object_to_sub_collection,
    _COL_PATH_NAVMESHES, _COL_PATH_WAYPOINTS, _COL_PATH_EXPORT_AS,
    _COL_PATH_TRIGGERS, _COL_PATH_CAMERAS, _COL_PATH_SOUND_EMITTERS,
    _COL_PATH_SPAWNABLE_ENEMIES, _COL_PATH_GEO_SOLID,
)
from ..export import (
    _nick, _iso, _lname, _ldir, _goal_src, _level_info, _game_gp,
    _levels_dir, _entity_gc,
    _actor_uses_waypoints, _actor_uses_navmesh,
    _actor_is_platform, _actor_is_launcher, _actor_is_spawner,
    _actor_is_enemy, _actor_supports_aggro_trigger,
    _vol_links, _vols_linking_to, _classify_target,
    _vol_get_link_to, _vol_has_link_to,
    collect_cameras, collect_aggro_triggers, log,
)
from ..build import (
    _EXE, _BUILD_STATE, _PLAY_STATE, goalc_ok, kill_gk,
    _exe_root, _data_root, _data, _goalc, _gk, _user_dir,
)
from ..properties import OGLumpRow, OG_UL_LumpRows
from ..utils import (
    _is_linkable, _is_aggro_target, _vol_for_target,
    _ENEMY_CATS, _NPC_CATS, _PICKUP_CATS, _PROP_CATS,
    _INTERACTIVE_CATS, _OBSTACLE_CATS, _BUTTONDOOR_CATS, _VISUALS_CATS,
    _draw_platform_settings, _header_sep, _draw_entity_sub,
    _draw_wiki_preview, _prop_row,
    _preview_collections, _load_previews, _unload_previews,
)
from .. import model_preview as _mp
from ..audit import run_audit


class OG_PT_Spawn(Panel):
    bl_label       = "➕  Spawn Objects"
    bl_idname      = "OG_PT_spawn"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_options     = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        props = ctx.scene.og_props
        if props.tpage_limit_enabled:
            active = [g for g in (props.tpage_filter_1, props.tpage_filter_2) if g != "NONE"]
            if active:
                row = self.layout.row()
                row.label(text="🔍 Filtered: " + " + ".join(active), icon="FILTER")



class OG_PT_SpawnSearch(Panel):
    bl_label       = "Quick Search"
    bl_idname      = "OG_PT_spawn_search"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_spawn"
    bl_order       = 0

    def draw(self, ctx):
        layout = self.layout
        props  = ctx.scene.og_props

        # Search input
        row = layout.row(align=True)
        row.prop(props, "entity_search", icon="VIEWZOOM", text="")

        query = props.entity_search.strip().lower()

        if query:
            # Scrollable dropdown — Blender renders this as a floating popup list
            layout.prop(props, "entity_search_results", text="", icon="COLLAPSEMENU")

            # Spawn button — active when a real result is selected
            sel = props.entity_search_selected
            if sel and sel in ENTITY_DEFS:
                col = layout.column()
                col.scale_y = 1.4
                op = col.operator("og.spawn_entity",
                                  text=f"Spawn  {ENTITY_DEFS[sel]['label']}", icon="ADD")
                op.source_prop = "entity_search_selected"
            else:
                sub = layout.column()
                sub.enabled = False
                sub.operator("og.spawn_entity", text="Spawn", icon="ADD")
        else:
            layout.label(text="Type to search all spawnable objects…", icon="INFO")



class OG_PT_SpawnLimitSearch(Panel):
    bl_label       = "Limit Search"
    bl_idname      = "OG_PT_spawn_limit_search"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_spawn_search"
    bl_options     = {"DEFAULT_CLOSED"}

    def draw_header(self, ctx):
        props = ctx.scene.og_props
        self.layout.prop(props, "tpage_limit_enabled", text="")

    def draw(self, ctx):
        layout = self.layout
        props  = ctx.scene.og_props

        col = layout.column(align=True)
        col.enabled = props.tpage_limit_enabled

        # Two dropdowns side by side
        row = col.row(align=True)
        # Grey out slot 2 if slot 1 is NONE (nothing to pair with yet)
        row.prop(props, "tpage_filter_1", text="")
        sub = row.row(align=True)
        sub.enabled = props.tpage_filter_1 != "NONE"
        sub.prop(props, "tpage_filter_2", text="")

        # Warn if same group selected in both slots
        if (props.tpage_filter_1 != "NONE"
                and props.tpage_filter_1 == props.tpage_filter_2):
            col.label(text="Both slots are the same group", icon="ERROR")



class OG_PT_SpawnEnemies(Panel):
    bl_label       = "⚔  Enemies"
    bl_idname      = "OG_PT_spawn_enemies"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_spawn"
    bl_options     = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        layout = self.layout
        props  = ctx.scene.og_props

        # ---- Preview status (toggle is in addon preferences) ----
        _prefs = bpy.context.preferences.addons.get("opengoal_tools")
        preview_on = _prefs and _prefs.preferences.preview_models
        if preview_on:
            row = layout.row(align=True)
            row.label(text="Preview Models", icon="OUTLINER_OB_MESH")
            row.operator("og.clear_previews", text="", icon="TRASH")
            if not _mp.models_available():
                box = layout.box()
                box.label(text="No GLBs found", icon="ERROR")
                box.label(text="1. Set rip_levels: true in jak1_config.jsonc")
                box.label(text="2. Delete data/decompiler_out/jak1/")
                box.label(text="3. Re-run the extractor from scratch")
                probe = _mp.models_probe_path()
                display = ("..." + probe[-47:]) if len(probe) > 50 else probe
                box.label(text=f"Checking: {display}")

        layout.separator(factor=0.3)
        _draw_entity_sub(layout, ctx, _ENEMY_CATS, nav_inline=True, prop_name="enemy_type")



class OG_PT_SpawnPlatforms(Panel):
    bl_label       = "🟦  Platforms"
    bl_idname      = "OG_PT_spawn_platforms"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_spawn"
    bl_options     = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        layout = self.layout
        props  = ctx.scene.og_props
        scene  = ctx.scene

        # Spawn
        layout.label(text="Spawn", icon="ADD")
        layout.prop(props, "platform_type", text="")
        layout.operator("og.spawn_platform", text="Add Platform at Cursor", icon="ADD")
        layout.separator(factor=0.5)

        # Active platform settings
        sel = ctx.active_object
        is_platform_selected = (
            sel is not None
            and sel.name.startswith("ACTOR_")
            and "_wp_" not in sel.name
            and len(sel.name.split("_", 2)) >= 3
            and _actor_is_platform(sel.name.split("_", 2)[1])
        )
        if is_platform_selected:
            layout.label(text="Selected Platform Settings", icon="SETTINGS")
            _draw_platform_settings(layout, sel, scene)
            layout.separator(factor=0.5)

        # Scene platform list
        plats = sorted(
            [o for o in _level_objects(scene)
             if o.name.startswith("ACTOR_")
             and "_wp_" not in o.name
             and o.type == "EMPTY"
             and len(o.name.split("_", 2)) >= 3
             and _actor_is_platform(o.name.split("_", 2)[1])],
            key=lambda o: o.name
        )

        if not plats:
            box = layout.box()
            box.label(text="No platforms in scene", icon="INFO")
            return

        row = layout.row()
        icon = "TRIA_DOWN" if props.show_platform_list else "TRIA_RIGHT"
        row.prop(props, "show_platform_list",
                 text=f"Platforms ({len(plats)})", icon=icon, emboss=False)
        if not props.show_platform_list:
            return

        box = layout.box()
        for p in plats:
            etype = p.name.split("_", 2)[1]
            einfo = ENTITY_DEFS.get(etype, {})
            label = einfo.get("label", etype)
            is_active = (sel is not None and sel == p)
            row = box.row(align=True)
            if is_active:
                row.label(text=f"▶ {label}", icon="CUBE")
            else:
                row.label(text=label, icon="CUBE")
            row.label(text=p.name.split("_", 2)[2])
            op = row.operator("og.select_and_frame", text="", icon="VIEWZOOM")
            op.obj_name = p.name
            op = row.operator("og.delete_object", text="", icon="TRASH")
            op.obj_name = p.name



class OG_PT_SpawnProps(Panel):
    bl_label       = "📦  Interactive Objects"
    bl_idname      = "OG_PT_spawn_props"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_spawn"
    bl_options     = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        _draw_entity_sub(self.layout, ctx, _INTERACTIVE_CATS, prop_name="prop_type")



class OG_PT_SpawnObstacles(Panel):
    bl_label       = "⚠  Obstacles"
    bl_idname      = "OG_PT_spawn_obstacles"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_spawn"
    bl_options     = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        _draw_entity_sub(self.layout, ctx, _OBSTACLE_CATS, prop_name="obstacle_type")



class OG_PT_SpawnButtonsDoors(Panel):
    bl_label       = "🚪  Buttons and Doors"
    bl_idname      = "OG_PT_spawn_buttons_doors"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_spawn"
    bl_options     = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        _draw_entity_sub(self.layout, ctx, _BUTTONDOOR_CATS, prop_name="button_door_type")



class OG_PT_SpawnVisuals(Panel):
    bl_label       = "🎨  Visuals"
    bl_idname      = "OG_PT_spawn_visuals"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_spawn"
    bl_options     = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        _draw_entity_sub(self.layout, ctx, _VISUALS_CATS, prop_name="visuals_type")



class OG_PT_SpawnNPCs(Panel):
    bl_label       = "🧍  NPCs"
    bl_idname      = "OG_PT_spawn_npcs"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_spawn"
    bl_options     = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        _draw_entity_sub(self.layout, ctx, _NPC_CATS, prop_name="npc_type")



class OG_PT_SpawnPickups(Panel):
    bl_label       = "⭐  Pickups"
    bl_idname      = "OG_PT_spawn_pickups"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_spawn"
    bl_options     = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        _draw_entity_sub(self.layout, ctx, _PICKUP_CATS, prop_name="pickup_type")



class OG_PT_SpawnSounds(Panel):
    bl_label       = "🔊  Sound Emitters"
    bl_idname      = "OG_PT_spawn_sounds"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_spawn"
    bl_options     = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        layout = self.layout
        props  = ctx.scene.og_props

        col = layout.column(align=True)
        col.prop(props, "ambient_default_radius", text="Default Radius (m)")
        col.separator(factor=0.4)

        snd_display = props.sfx_sound.split("__")[0] if "__" in props.sfx_sound else props.sfx_sound
        pick_row = col.row(align=True)
        pick_row.scale_y = 1.2
        pick_row.operator("og.pick_sound", text=f"🔊  {snd_display}", icon="VIEWZOOM")

        col.separator(factor=0.4)
        row2 = col.row()
        row2.scale_y = 1.4
        row2.operator("og.add_sound_emitter", text="Add Emitter at Cursor", icon="ADD")

        emitters = [o for o in _level_objects(ctx.scene)
                    if o.name.startswith("AMBIENT_") and o.type == "EMPTY"
                    and o.get("og_sound_name")]
        if emitters:
            layout.separator(factor=0.3)
            sub = layout.box()
            sub.label(text=f"{len(emitters)} emitter(s) in scene:", icon="OUTLINER_OB_EMPTY")
            for o in emitters[:8]:
                row = sub.row(align=True)
                snd  = o.get("og_sound_name", "?")
                mode = o.get("og_sound_mode", "loop")
                icon = "PREVIEW_RANGE" if mode == "loop" else "PLAYER"
                row.label(text=f"{o.name}  →  {snd}  [{mode}]", icon=icon)
            if len(emitters) > 8:
                sub.label(text=f"… and {len(emitters) - 8} more")
        else:
            layout.label(text="No emitters placed yet", icon="INFO")



class OG_PT_SpawnMusicZones(Panel):
    bl_label       = "🎵  Music Zones"
    bl_idname      = "OG_PT_spawn_music"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_spawn"
    bl_options     = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        layout = self.layout
        props  = ctx.scene.og_props

        col = layout.column(align=True)
        col.label(text="New Zone Settings:", icon="SETTINGS")
        col.prop(props, "og_music_amb_bank",     text="Music Bank")
        col.prop(props, "og_music_amb_flava",    text="Flava")
        col.prop(props, "og_music_amb_priority", text="Priority")
        col.prop(props, "og_music_amb_radius",   text="Radius (m)")

        col.separator(factor=0.6)
        row = col.row()
        row.scale_y = 1.4
        row.operator("og.add_music_zone", text="Add Music Zone at Cursor", icon="ADD")

        # List existing music zones
        zones = [o for o in _level_objects(ctx.scene)
                 if o.name.startswith("AMBIENT_mus") and o.type == "EMPTY"
                 and o.get("og_music_bank")]
        if zones:
            layout.separator(factor=0.3)
            sub = layout.box()
            sub.label(text=f"{len(zones)} zone(s) in scene:", icon="OUTLINER_OB_EMPTY")
            for o in zones[:8]:
                row = sub.row(align=True)
                bank  = o.get("og_music_bank", "?")
                flava = o.get("og_music_flava", "default")
                pri   = o.get("og_music_priority", 10.0)
                label = f"{o.name}  →  {bank}"
                if flava and flava != "default":
                    label += f"  [{flava}]"
                label += f"  pri:{pri:.0f}"
                row.label(text=label, icon="SOUND")
            if len(zones) > 8:
                sub.label(text=f"… and {len(zones) - 8} more")
        else:
            layout.separator(factor=0.3)
            layout.label(text="No music zones placed yet", icon="INFO")
            layout.label(text="Tip: one large zone covering the", icon="BLANK1")
            layout.label(text="whole level is usually enough.",  icon="BLANK1")



class OG_PT_SpawnWater(Panel):
    bl_label       = "💧  Water Volumes"
    bl_idname      = "OG_PT_spawn_water"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_spawn"
    bl_options     = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        layout = self.layout
        col = layout.column(align=True)

        row = col.row()
        row.scale_y = 1.4
        row.operator("og.add_water_volume", text="Add Water Volume", icon="MOD_OCEAN")

        col.separator(factor=0.4)
        sub = col.row(); sub.enabled = False
        sub.label(text="Scale to cover water area (no rotation)", icon="INFO")

        # List existing water volumes
        water_meshes = [o for o in _level_objects(ctx.scene)
                        if o.type == "MESH" and o.name.startswith("WATER_")]
        if water_meshes:
            from mathutils import Vector
            layout.separator(factor=0.3)
            box = layout.box()
            box.label(text=f"{len(water_meshes)} volume(s):", icon="MESH_CUBE")
            for o in water_meshes:
                row = box.row(align=True)
                surface = float(o.get("og_water_surface", 0.0))
                bb = [o.matrix_world @ Vector(o.bound_box[i]) for i in range(8)]
                w = max(c.x for c in bb) - min(c.x for c in bb)
                d = max(c.y for c in bb) - min(c.y for c in bb)
                row.label(text=f"{o.name}  {w:.1f}×{d:.1f}m  surf={surface:.1f}m", icon="MOD_OCEAN")



class OG_PT_SpawnCustomTypes(Panel):
    """Spawn panel for user-defined GOAL types.

    Place a plain ACTOR_ empty for any custom deftype written in a GOAL code block.
    The type name must match the deftype name in obs.gc exactly.
    """
    bl_label       = "⚙  Custom Types"
    bl_idname      = "OG_PT_spawn_custom_types"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_spawn"
    bl_options     = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        layout = self.layout
        props  = ctx.scene.og_props
        col    = layout.column(align=True)

        # ── Type name input + spawn button ───────────────────────────────────
        col.label(text="GOAL deftype name:", icon="SCRIPT")
        row = col.row(align=True)
        row.prop(props, "custom_type_name", text="")
        row.scale_x = 0.9
        col.separator(factor=0.4)
        spawn_row = col.row()
        spawn_row.scale_y = 1.4
        name_val = (props.custom_type_name or "").strip()
        spawn_row.enabled = bool(name_val)
        spawn_row.operator("og.spawn_custom_type",
                           text=f"Spawn  ACTOR_{name_val}_N" if name_val else "Enter a type name first",
                           icon="ADD")

        # ── Hint box ────────────────────────────────────────────────────────
        layout.separator(factor=0.5)
        box = layout.box()
        box.label(text="How it works:", icon="INFO")
        col2 = box.column(align=True)
        col2.scale_y = 0.85
        col2.label(text="1. Enter a type name (e.g. spin-prop)")
        col2.label(text="2. Spawn the empty at the 3D cursor")
        col2.label(text="3. Select it → GOAL Code panel")
        col2.label(text="4. Create / assign a code block")
        col2.label(text="5. Write deftype + defstate + init")
        col2.label(text="6. Export & Build — type compiles")
        col2.separator(factor=0.3)
        col2.label(text="Name must be lowercase + hyphens,")
        col2.label(text="matching your deftype exactly.")

        # ── Existing custom-type actors in scene ─────────────────────────────
        custom_actors = [
            o for o in _level_objects(ctx.scene)
            if (o.name.startswith("ACTOR_")
                and o.type == "EMPTY"
                and "_wp_" not in o.name
                and len(o.name.split("_", 2)) >= 3
                and _is_custom_type(o.name.split("_", 2)[1]))
        ]
        if custom_actors:
            layout.separator(factor=0.3)
            sub = layout.column(align=True)
            sub.label(text=f"{len(custom_actors)} custom actor(s) in scene:", icon="OUTLINER_OB_EMPTY")
            for o in custom_actors[:8]:
                ref      = getattr(o, "og_goal_code_ref", None)
                has_code = ref is not None and ref.text_block is not None and ref.enabled
                icon     = "CHECKMARK" if has_code else "ERROR"
                tip      = ref.text_block.name if has_code else "no code block"
                row      = sub.row(align=True)
                row.label(text=o.name, icon=icon)
                sub2 = row.row()
                sub2.enabled = False
                sub2.label(text=f"[{tip}]")
            if len(custom_actors) > 8:
                sub.label(text=f"… and {len(custom_actors) - 8} more")




class OG_PT_SpawnLevelFlow(Panel):
    bl_label       = "🗺  Level Flow"
    bl_idname      = "OG_PT_spawn_level_flow"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_spawn"
    bl_options     = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        layout = self.layout
        props  = ctx.scene.og_props
        scene  = ctx.scene

        # ── Dropdown + Add button ─────────────────────────────────────────
        row = layout.row(align=True)
        row.prop(props, "spawn_flow_type", text="")
        if props.spawn_flow_type == "SPAWN":
            row.operator("og.spawn_player",     text="Add", icon="ADD")
        else:
            row.operator("og.spawn_checkpoint", text="Add", icon="ADD")

        # ── Object lists ──────────────────────────────────────────────────
        lv_objs     = _level_objects(scene)
        spawns      = [o for o in lv_objs if o.name.startswith("SPAWN_")
                       and o.type == "EMPTY" and not o.name.endswith("_CAM")]
        checkpoints = [o for o in lv_objs if o.name.startswith("CHECKPOINT_")
                       and o.type == "EMPTY" and not o.name.endswith("_CAM")]

        if spawns or checkpoints:
            layout.separator(factor=0.4)

        if spawns:
            row = layout.row()
            icon = "TRIA_DOWN" if props.show_spawn_list else "TRIA_RIGHT"
            row.prop(props, "show_spawn_list",
                     text=f"Player Spawns ({len(spawns)})", icon=icon, emboss=False)
            if props.show_spawn_list:
                box = layout.box()
                for o in sorted(spawns, key=lambda x: x.name):
                    row = box.row(align=True)
                    row.label(text=o.name, icon="EMPTY_ARROWS")
                    cam_obj = scene.objects.get(o.name + "_CAM")
                    if cam_obj:
                        row.label(text="📷", icon="NONE")
                    else:
                        sub = row.row()
                        sub.alert = True
                        sub.label(text="no cam", icon="NONE")
                    op = row.operator("og.select_and_frame", text="", icon="VIEWZOOM")
                    op.obj_name = o.name
                    op = row.operator("og.delete_object", text="", icon="TRASH")
                    op.obj_name = o.name

        if checkpoints:
            row = layout.row()
            icon = "TRIA_DOWN" if props.show_checkpoint_list else "TRIA_RIGHT"
            row.prop(props, "show_checkpoint_list",
                     text=f"Checkpoints ({len(checkpoints)})", icon=icon, emboss=False)
            if props.show_checkpoint_list:
                box = layout.box()
                for o in sorted(checkpoints, key=lambda x: x.name):
                    row = box.row(align=True)
                    row.label(text=o.name, icon="EMPTY_SINGLE_ARROW")
                    vol_list = _vols_linking_to(scene, o.name)
                    if vol_list:
                        row.label(text=f"📦 {vol_list[0].name}")
                    else:
                        r = float(o.get("og_checkpoint_radius", 3.0))
                        sub = row.row()
                        sub.alert = True
                        sub.label(text=f"r={r:.1f}m")
                    cam_obj = scene.objects.get(o.name + "_CAM")
                    if cam_obj:
                        row.label(text="📷", icon="NONE")
                    op = row.operator("og.select_and_frame", text="", icon="VIEWZOOM")
                    op.obj_name = o.name
                    op = row.operator("og.delete_object", text="", icon="TRASH")
                    op.obj_name = o.name

        # ── Selected spawn/checkpoint context actions ─────────────────────
        sel = ctx.active_object
        if (sel and sel.type == "EMPTY"
                and (sel.name.startswith("SPAWN_") or sel.name.startswith("CHECKPOINT_"))
                and not sel.name.endswith("_CAM")):
            is_cp = sel.name.startswith("CHECKPOINT_")
            layout.separator(factor=0.3)
            sub = layout.column(align=True)
            cam_exists = bool(scene.objects.get(sel.name + "_CAM"))
            if not cam_exists:
                sub.operator("og.spawn_cam_anchor",
                             text=f"Add Camera for {sel.name}", icon="CAMERA_DATA")
            else:
                row = sub.row()
                row.enabled = False
                row.label(text=f"{sel.name}_CAM exists ✓", icon="CHECKMARK")
            if is_cp:
                vol_list_sel = _vols_linking_to(scene, sel.name)
                if vol_list_sel:
                    vol_linked = vol_list_sel[0]
                    row = sub.row()
                    row.enabled = False
                    row.label(text=f"{vol_linked.name} linked ✓", icon="MESH_CUBE")
                    sub.operator("og.unlink_volume", text="Unlink Volume", icon="X")
                else:
                    op = sub.operator("og.spawn_volume_autolink",
                                      text="Add Trigger Volume", icon="MESH_CUBE")
                    op.target_name = sel.name
                    sub.label(text="Or use Triggers panel to link existing", icon="INFO")




class OG_OT_SearchSelectEntity(bpy.types.Operator):
    bl_idname      = "og.search_select_entity"
    bl_label       = "Select Entity"
    bl_description = "Select this entity as the spawn target"
    bl_options     = {"INTERNAL", "UNDO"}

    etype: bpy.props.StringProperty()

    def execute(self, ctx):
        ctx.scene.og_props.entity_search_selected = self.etype
        try:
            ctx.scene.og_props.entity_type = self.etype
        except Exception:
            pass
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Spawn > Quick Search  (sub-panel — always open, pinned to top)
# ---------------------------------------------------------------------------

# ─── Classes to register ───────────────────────────────────────────────────
CLASSES = (
    OG_OT_SearchSelectEntity,
    OG_PT_Spawn,
    OG_PT_SpawnLevelFlow,
    OG_PT_SpawnSearch,
    OG_PT_SpawnLimitSearch,
    OG_PT_SpawnEnemies,
    OG_PT_SpawnPlatforms,
    OG_PT_SpawnObstacles,
    OG_PT_SpawnButtonsDoors,
    OG_PT_SpawnProps,
    OG_PT_SpawnVisuals,
    OG_PT_SpawnNPCs,
    OG_PT_SpawnPickups,
    OG_PT_SpawnSounds,
    OG_PT_SpawnMusicZones,
    OG_PT_SpawnWater,
    OG_PT_SpawnCustomTypes,
)
