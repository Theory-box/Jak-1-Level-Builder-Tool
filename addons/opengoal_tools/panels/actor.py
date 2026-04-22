# ───────────────────────────────────────────────────────────────────────
# panels/actor.py — OpenGOAL Level Tools
#
# Bespoke per-actor sub-panels (for actors whose UI isn't fully data-driven).
# Simple pure-field actors go through OG_PT_ActorFields in actor_fields.py instead.
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
    _draw_platform_settings, _header_sep, _draw_entity_sub,
    _draw_wiki_preview, _prop_row,
    _preview_collections, _load_previews, _unload_previews,
)
from .. import model_preview as _mp
from ..audit import run_audit


class OG_PT_ActorActivation(Panel):
    bl_label       = "Activation"
    bl_idname      = "OG_PT_actor_activation"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        return len(parts) >= 3 and parts[0] == "ACTOR" and _actor_is_enemy(parts[1])

    def draw(self, ctx):
        layout = self.layout
        sel    = ctx.active_object
        _prop_row(layout, sel, "og_idle_distance", "Idle Distance (m):", 80.0)
        sub = layout.row(); sub.enabled = False
        sub.label(text="Player must be closer than this to wake the enemy", icon="INFO")



class OG_PT_ActorTriggerBehaviour(Panel):
    bl_label       = "Trigger Behaviour"
    bl_idname      = "OG_PT_actor_trigger_behaviour"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        return len(parts) >= 3 and parts[0] == "ACTOR" and _actor_supports_aggro_trigger(parts[1])

    def draw(self, ctx):
        layout = self.layout
        sel    = ctx.active_object
        scene  = ctx.scene
        linked_vols = _vols_linking_to(scene, sel.name)
        if linked_vols:
            for v in linked_vols:
                entry = _vol_get_link_to(v, sel.name)
                if not entry: continue
                row = layout.row(align=True)
                row.label(text=f"✓ {v.name}", icon="MESH_CUBE")
                row.prop(entry, "behaviour", text="")
                op = row.operator("og.select_and_frame", text="", icon="VIEWZOOM")
                op.obj_name = v.name
                op = row.operator("og.remove_vol_link", text="", icon="X")
                op.vol_name = v.name; op.target_name = sel.name
        else:
            sub = layout.row(); sub.enabled = False
            sub.label(text="No trigger volumes linked", icon="INFO")
        op = layout.operator("og.spawn_aggro_trigger", text="Add Aggro Trigger", icon="ADD")
        op.target_name = sel.name



class OG_PT_ActorNavMesh(Panel):
    bl_label       = "NavMesh"
    bl_idname      = "OG_PT_actor_navmesh"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        return len(parts) >= 3 and parts[0] == "ACTOR" and _actor_uses_navmesh(parts[1])

    def draw(self, ctx):
        layout = self.layout
        sel    = ctx.active_object
        nm_name = sel.get("og_navmesh_link", "")
        nm_obj  = bpy.data.objects.get(nm_name) if nm_name else None
        if nm_obj:
            row = layout.row(align=True)
            row.label(text=f"✓ {nm_obj.name}", icon="CHECKMARK")
            row.operator("og.unlink_navmesh", text="", icon="X")
            try:
                nm_obj.data.calc_loop_triangles()
                tc = len(nm_obj.data.loop_triangles)
                layout.label(text=f"{tc} triangles", icon="MESH_DATA")
            except Exception:
                pass
        else:
            layout.label(text="No mesh linked", icon="ERROR")
            sel_meshes = [o for o in bpy.context.selected_objects if o.type == "MESH"]
            if sel_meshes:
                layout.label(text=f"Will link to: {sel_meshes[0].name}", icon="INFO")
                layout.operator("og.link_navmesh", text="Link NavMesh", icon="LINKED")
            else:
                layout.label(text="Shift-select a mesh to link", icon="INFO")
        nav_r = float(sel.get("og_nav_radius", 6.0))
        layout.label(text=f"Fallback sphere radius: {nav_r:.1f}m", icon="SPHERE")



class OG_PT_ActorLinks(Panel):
    """Entity link slots — actor-to-actor references exported as alt-actor / water-actor etc."""
    bl_label       = "Entity Links"
    bl_idname      = "OG_PT_actor_links"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name:
            return False
        parts = sel.name.split("_", 2)
        return (len(parts) >= 3
                and parts[0] == "ACTOR"
                and _actor_has_links(parts[1]))

    def draw(self, ctx):
        sel   = ctx.active_object
        etype = sel.name.split("_", 2)[1]
        _draw_actor_links(self.layout, sel, ctx.scene, etype)



class OG_PT_ActorPlatform(Panel):
    bl_label       = "Platform Settings"
    bl_idname      = "OG_PT_actor_platform"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        return len(parts) >= 3 and parts[0] == "ACTOR" and _actor_is_platform(parts[1])

    def draw(self, ctx):
        _draw_platform_settings(self.layout, ctx.active_object, ctx.scene)



class OG_PT_ActorCrate(Panel):
    bl_label       = "Crate"
    bl_idname      = "OG_PT_actor_crate"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        return len(parts) >= 3 and parts[0] == "ACTOR" and parts[1] == "crate"

    def draw(self, ctx):
        layout = self.layout
        sel    = ctx.active_object
        ct     = sel.get("og_crate_type",          "steel")
        pickup = sel.get("og_crate_pickup",         "money")

        # ── Crate Type ───────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Crate Type", icon="PACKAGE")
        col = box.column(align=True)
        for (val, label, _, _, _) in CRATE_ITEMS:
            sub = col.row(align=True)
            # Wood is greyed out when a scout fly is inside
            sub.enabled = not (val == "wood" and pickup == "buzzer")
            icon = "RADIOBUT_ON" if ct == val else "RADIOBUT_OFF"
            op = sub.operator("og.set_crate_type", text=label, icon=icon)
            op.crate_type = val

        # Scout fly + wood warning
        if pickup == "buzzer" and ct == "wood":
            warn = box.box()
            warn.alert = True
            warn.label(text="Scout Fly needs Iron/Steel!", icon="ERROR")

        # ── Contents ─────────────────────────────────────────────────────
        box2 = layout.box()
        box2.label(text="Contents", icon="GHOST_ENABLED")
        col2 = box2.column(align=True)
        for (uid, label, _, ico, _) in CRATE_PICKUP_ITEMS:
            sub = col2.row(align=True)
            btn_icon = "RADIOBUT_ON" if pickup == uid else "RADIOBUT_OFF"
            op = sub.operator("og.set_crate_pickup", text=label, icon=btn_icon)
            op.pickup_id = uid

        # ── Amount input (only for orbs) ──────────────────────────────────
        _supports_multi = {uid: sm for (uid, _, _, _, sm) in CRATE_PICKUP_ITEMS}
        if _supports_multi.get(pickup, False):
            _prop_row(box2, sel, "og_crate_pickup_amount", "Amount (1–5):", 1)
        elif pickup == "buzzer":
            box2.label(text="Amount: 1  (fixed)", icon="INFO")



class OG_PT_ActorLauncher(Panel):
    bl_label       = "Launcher Settings"
    bl_idname      = "OG_PT_actor_launcher"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        return len(parts) >= 3 and parts[0] == "ACTOR" and _actor_is_launcher(parts[1])

    def draw(self, ctx):
        layout = self.layout
        sel    = ctx.active_object
        etype  = sel.name.split("_", 2)[1]

        # ── Spring Height ─────────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Launch Height", icon="TRIA_UP")
        _prop_row(box, sel, "og_spring_height", "Height (m, -1=default):", -1.0)
        height = float(sel.get("og_spring_height", -1.0))
        if height >= 0:
            op2 = box.operator("og.nudge_float_prop", text="Reset to Default", icon="LOOP_BACK")
            op2.prop_name = "og_spring_height"; op2.delta = -9999.0; op2.val_min = -1.0
        else:
            sub = box.row(); sub.enabled = False
            sub.label(text="Uses art default (~40m). Set above to override.", icon="INFO")

        # ── Springbox has no destination, launcher does ───────────────────────
        if etype == "launcher":
            box2 = layout.box()
            box2.label(text="Launch Destination (optional)", icon="EMPTY_AXIS")
            dest_name = sel.get("og_launcher_dest", "")
            dest_obj  = bpy.data.objects.get(dest_name) if dest_name else None

            sel_dests = [
                o for o in ctx.selected_objects
                if o != sel and o.type == "EMPTY" and o.name.startswith("DEST_")
            ]

            if dest_obj:
                row2 = box2.row(align=True)
                row2.label(text=f"✓ {dest_obj.name}", icon="CHECKMARK")
                op = row2.operator("og.select_and_frame", text="", icon="VIEWZOOM")
                op.obj_name = dest_obj.name
                op = row2.operator("og.clear_launcher_dest", text="", icon="X")
                op.launcher_name = sel.name
            elif dest_name:
                row2 = box2.row(); row2.alert = True
                row2.label(text=f"⚠ missing: {dest_name}", icon="ERROR")
                op = row2.operator("og.clear_launcher_dest", text="", icon="X")
                op.launcher_name = sel.name
            else:
                sub = box2.row(); sub.enabled = False
                sub.label(text="Not set — Jak launches straight up", icon="INFO")

            if len(sel_dests) == 1:
                op = box2.operator("og.set_launcher_dest", text=f"Link → {sel_dests[0].name}", icon="LINKED")
                op.launcher_name = sel.name
                op.dest_name = sel_dests[0].name
            else:
                op = box2.operator("og.add_launcher_dest", text="Add Destination Empty at Cursor", icon="ADD")
                op.launcher_name = sel.name

            # Fly time
            box3 = layout.box()
            box3.label(text="Fly Time (optional)", icon="TIME")
            fly_time = float(sel.get("og_launcher_fly_time", -1.0))
            _prop_row(box3, sel, "og_launcher_fly_time", "Fly Time (s, -1=default):", -1.0)
            if fly_time >= 0:
                op2 = box3.operator("og.nudge_float_prop", text="Reset to Default", icon="LOOP_BACK")
                op2.prop_name = "og_launcher_fly_time"; op2.delta = -9999.0; op2.val_min = -1.0
            else:
                sub = box3.row(); sub.enabled = False
                sub.label(text="Only needed when Destination is set.", icon="INFO")



class OG_PT_ActorEcoDoor(Panel):
    bl_label       = "Eco Door Settings"
    bl_idname      = "OG_PT_actor_eco_door"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        ECO_DOOR_TYPES = {"eco-door", "jng-iris-door", "sidedoor", "rounddoor"}
        return len(parts) >= 3 and parts[0] == "ACTOR" and parts[1] in ECO_DOOR_TYPES

    def draw(self, ctx):
        layout = self.layout
        sel    = ctx.active_object

        # ── Open condition hint ───────────────────────────────────────────────
        from opengoal_tools.data import _actor_get_link
        has_state_actor = bool(_actor_get_link(sel, "state-actor", 0))
        hint = layout.box()
        if has_state_actor:
            hint.label(text="Button-controlled door", icon="LINKED")
            col = hint.column(align=True)
            col.enabled = False
            col.label(text="• Locked until linked button is pressed")
            col.label(text="• Opens when Jak walks close with blue eco")
            col.label(text="• Tip: enable One Way to skip blue eco requirement")
        else:
            hint.label(text="Opens when Jak is nearby AND one of:", icon="INFO")
            col = hint.column(align=True)
            col.enabled = False
            col.label(text="• Jak has blue eco")
            col.label(text="• Starts Open is enabled")
            col.label(text="• One-way flag + Jak on exit side")
            col.label(text="• Link a button via Actor Links → state-actor")

        # ── Behaviour flags ───────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Door Behaviour", icon="SETTINGS")

        auto_close  = bool(sel.get("og_door_auto_close",  False))
        one_way     = bool(sel.get("og_door_one_way",     False))
        starts_open = bool(sel.get("og_door_starts_open", False))

        row = box.row()
        icon = "CHECKBOX_HLT" if auto_close else "CHECKBOX_DEHLT"
        row.operator("og.toggle_door_flag", text="Auto Close",   icon=icon).flag = "auto_close"

        row2 = box.row()
        icon2 = "CHECKBOX_HLT" if one_way else "CHECKBOX_DEHLT"
        row2.operator("og.toggle_door_flag", text="One Way",     icon=icon2).flag = "one_way"

        row3 = box.row()
        icon3 = "CHECKBOX_HLT" if starts_open else "CHECKBOX_DEHLT"
        row3.operator("og.toggle_door_flag", text="Starts Open", icon=icon3).flag = "starts_open"

        sub = box.row(); sub.enabled = False
        if starts_open:
            sub.label(text="Door spawns already open (perm-complete set)", icon="CHECKMARK")
        elif auto_close and one_way:
            sub.label(text="Closes after Jak passes, one direction only", icon="INFO")
        elif auto_close:
            sub.label(text="Closes automatically after Jak passes", icon="INFO")
        elif one_way:
            sub.label(text="Can only be opened from one side", icon="INFO")
        else:
            sub.label(text="Default: needs blue eco or button link", icon="INFO")



class OG_PT_ActorWaterVol(Panel):
    bl_label       = "Water Volume Settings"
    bl_idname      = "OG_PT_actor_water_vol"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        return len(parts) >= 3 and parts[0] == "ACTOR" and parts[1] == "water-vol"

    def draw(self, ctx):
        layout = self.layout
        sel    = ctx.active_object

        # Scale warning — empties default to scale 1 = 2m box, must be scaled up
        sx, sy = abs(sel.scale.x), abs(sel.scale.y)
        if sx < 2.0 or sy < 2.0:
            warn = layout.box()
            warn.label(text="⚠  Scale empty to cover water area!", icon="ERROR")
            warn.label(text=f"Current: {sx*2:.1f}m × {sy*2:.1f}m  (Scale X/Y in 3D view)")

        # Surface height
        box = layout.box()
        box.label(text="Water Heights (world Y)", icon="MOD_OCEAN")

        water_y  = float(sel.get("og_water_surface", 0.0))
        wade_y   = float(sel.get("og_water_wade",    water_y - 0.5))
        swim_y   = float(sel.get("og_water_swim",    water_y - 1.0))
        bottom_y = float(sel.get("og_water_bottom",  water_y - 5.0))

        col = box.column(align=True)
        _prop_row(col, sel, "og_water_surface", "Surface Y:",  water_y)
        _prop_row(col, sel, "og_water_wade",    "Wade Y:",     wade_y)
        _prop_row(col, sel, "og_water_swim",    "Swim Y:",     swim_y)
        _prop_row(col, sel, "og_water_bottom",  "Bottom Y:",   bottom_y)

        # Show computed depths relative to surface so user can sanity-check
        sub = box.column(align=True)
        sub.enabled = False
        sub.label(text=f"  Wade at: {water_y - wade_y:.2f}m below surface", icon="INFO")
        sub.label(text=f"  Swim at: {water_y - swim_y:.2f}m below surface")
        sub.label(text=f"  Kill floor: {water_y - bottom_y:.2f}m below surface")

        op = box.operator("og.sync_water_from_object", text="Sync Surface from Object Y", icon="OBJECT_ORIGIN")
        op.actor_name = sel.name



class OG_PT_ActorLauncherDoor(Panel):
    bl_label       = "Launcher Door Settings"
    bl_idname      = "OG_PT_actor_launcherdoor"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        return len(parts) >= 3 and parts[0] == "ACTOR" and parts[1] == "launcherdoor"

    def draw(self, ctx):
        layout = self.layout
        sel    = ctx.active_object
        scene  = ctx.scene

        box = layout.box()
        box.label(text="Continue Point", icon="FORWARD")

        cp_name = sel.get("og_continue_name", "")

        level_name = str(_get_level_prop(scene, "og_level_name", "")).strip().lower().replace(" ", "-")
        cps = sorted([
            o for o in _level_objects(scene)
            if o.name.startswith("CHECKPOINT_") and o.type == "EMPTY" and not o.name.endswith("_CAM")
        ], key=lambda o: o.name)
        spawns = sorted([
            o for o in _level_objects(scene)
            if o.name.startswith("SPAWN_") and o.type == "EMPTY" and not o.name.endswith("_CAM")
        ], key=lambda o: o.name)

        all_cps = [(o, f"{level_name}-{o.name[11:]}") for o in cps] + \
                  [(o, f"{level_name}-{o.name[6:]}") for o in spawns]

        if cp_name:
            row = box.row(align=True)
            row.label(text=f"✓ {cp_name}", icon="CHECKMARK")
            op = row.operator("og.clear_door_cp", text="", icon="X")
            op.actor_name = sel.name
        else:
            sub = box.row(); sub.enabled = False
            sub.label(text="Not set — door won't set a continue point", icon="INFO")

        if all_cps:
            box.label(text="Set from scene checkpoints/spawns:")
            col = box.column(align=True)
            for (cp_obj, name) in all_cps:
                row2 = col.row(align=True)
                is_active = (name == cp_name)
                icon = "CHECKMARK" if is_active else "DOT"
                op = row2.operator("og.set_door_cp", text=name, icon=icon)
                op.actor_name = sel.name
                op.cp_name = name
        else:
            sub = box.row(); sub.enabled = False
            sub.label(text="No checkpoints in scene — add a CHECKPOINT_ empty", icon="INFO")



class OG_PT_ActorSunIrisDoor(Panel):
    bl_label       = "Iris Door Settings"
    bl_idname      = "OG_PT_actor_sun_iris_door"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        return len(parts) >= 3 and parts[0] == "ACTOR" and parts[1] == "sun-iris-door"

    def draw(self, ctx):
        layout = self.layout
        sel    = ctx.active_object

        # ── Open method ───────────────────────────────────────────────────────
        hint = layout.box()
        hint.label(text="Opens when it receives a 'trigger event", icon="INFO")
        sub = hint.row(); sub.enabled = False
        sub.label(text="Use a Trigger Volume or basebutton linked to this door")

        # ── Proximity toggle ──────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Proximity", icon="DRIVER_DISTANCE")
        proximity = bool(sel.get("og_door_proximity", False))
        row = box.row()
        icon = "CHECKBOX_HLT" if proximity else "CHECKBOX_DEHLT"
        row.operator("og.toggle_door_flag", text="Open by Proximity", icon=icon).flag = "proximity"
        sub2 = box.row(); sub2.enabled = False
        if proximity:
            sub2.label(text="Also opens when Jak walks close", icon="CHECKMARK")
        else:
            sub2.label(text="Event-triggered only (default)", icon="INFO")

        # ── Timeout ───────────────────────────────────────────────────────────
        box2 = layout.box()
        box2.label(text="Auto-Close Timeout", icon="TIME")
        timeout = float(sel.get("og_door_timeout", 0.0))
        _prop_row(box2, sel, "og_door_timeout", "Timeout (s, 0=stays open):", 0.0)
        if timeout > 0.0:
            op_r = box2.operator("og.nudge_float_prop", text="Reset (no timeout)", icon="LOOP_BACK")
            op_r.prop_name = "og_door_timeout"; op_r.delta = -999.0; op_r.val_min = 0.0



class OG_PT_ActorCaveElevator(Panel):
    bl_label       = "Cave Elevator Settings"
    bl_idname      = "OG_PT_actor_cave_elevator"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        return len(parts) >= 3 and parts[0] == "ACTOR" and parts[1] == "caveelevator"

    def draw(self, ctx):
        layout = self.layout
        sel    = ctx.active_object
        mode   = int(sel.get("og_elevator_mode", 0))

        box = layout.box()
        box.label(text="Mode", icon="SETTINGS")
        col = box.column(align=True)
        for (val, label) in [(0, "Mode 0 (default)"), (1, "Mode 1 (alternate)")]:
            row = col.row()
            icon = "RADIOBUT_ON" if mode == val else "RADIOBUT_OFF"
            op = row.operator("og.set_elevator_mode", text=label, icon=icon)
            op.mode_val = val

        box2 = layout.box()
        box2.label(text="Rotation Offset", icon="CON_ROTLIKE")
        _prop_row(box2, sel, "og_elevator_rot", "Rotation (°):", 0.0)



class OG_PT_ActorTaskGated(Panel):
    bl_label       = "Task Settings"
    bl_idname      = "OG_PT_actor_task_gated"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    _TYPES = {"oracle", "pontoon"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        return len(parts) >= 3 and parts[0] == "ACTOR" and parts[1] in cls._TYPES

    def draw(self, ctx):
        layout = self.layout
        sel    = ctx.active_object
        etype  = sel.name.split("_", 2)[1]
        cur    = sel.get("og_alt_task", "none")

        box = layout.box()
        if etype == "oracle":
            box.label(text="Second Orb Task (alt-task)", icon="SPHERE")
            sub = box.row(); sub.enabled = False
            sub.label(text="Set if oracle requires 2 orbs", icon="INFO")
        else:
            box.label(text="Sink Condition Task (alt-task)", icon="FORCE_FORCE")
            sub = box.row(); sub.enabled = False
            sub.label(text="Pontoon sinks when this task is complete", icon="INFO")

        col = box.column(align=True)
        for (val, label) in _GAME_TASKS_COMMON:
            row = col.row()
            icon = "RADIOBUT_ON" if cur == val else "RADIOBUT_OFF"
            op = row.operator("og.set_alt_task", text=label, icon=icon)
            op.task_name = val



class OG_PT_ActorVisibility(Panel):
    bl_label       = "Visibility"
    bl_idname      = "OG_PT_actor_visibility"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        if len(parts) < 3 or parts[0] != "ACTOR": return False
        return _actor_is_enemy(parts[1])

    def draw(self, ctx):
        layout = self.layout
        sel    = ctx.active_object

        box = layout.box()
        box.label(text="Vis Distance", icon="HIDE_OFF")
        _prop_row(box, sel, "og_vis_dist", "Distance (m):", 200.0)
        sub = box.row(); sub.enabled = False
        sub.label(text="Default 200m. Reduce for distant background enemies.", icon="INFO")



class OG_PT_ActorWaypoints(Panel):
    bl_label       = "Waypoints"
    bl_idname      = "OG_PT_actor_waypoints"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        return (len(parts) >= 3 and parts[0] == "ACTOR"
                and _actor_uses_waypoints(parts[1]))

    def draw(self, ctx):
        layout = self.layout
        sel    = ctx.active_object
        scene  = ctx.scene
        parts  = sel.name.split("_", 2)
        etype  = parts[1]
        einfo  = ENTITY_DEFS.get(etype, {})

        prefix = sel.name + "_wp_"
        wps = sorted(
            [o for o in _level_objects(scene) if o.name.startswith(prefix) and o.type == "EMPTY"],
            key=lambda o: o.name
        )
        layout.label(text=f"Path  ({len(wps)} point{'s' if len(wps) != 1 else ''})", icon="ANIM")
        if wps:
            col = layout.column(align=True)
            for wp in wps:
                row = col.row(align=True)
                row.label(text=wp.name, icon="EMPTY_AXIS")
                op = row.operator("og.select_and_frame", text="", icon="VIEWZOOM"); op.obj_name = wp.name
                op = row.operator("og.delete_waypoint",  text="", icon="X");        op.wp_name  = wp.name
        row = layout.row(align=True)
        row.operator("og.add_waypoint", text="Spawn Waypoint", icon="PLUS").enemy_name = sel.name
        row.prop(ctx.scene.og_props, "waypoint_spawn_at_actor", text="Spawn at Position", toggle=False)
        if einfo.get("needs_path") and len(wps) < 1:
            layout.label(text="⚠ Needs ≥ 1 waypoint or will crash", icon="ERROR")

        if einfo.get("needs_pathb"):
            layout.separator(factor=0.5)
            prefixb = sel.name + "_wpb_"
            wpsb = sorted(
                [o for o in _level_objects(scene) if o.name.startswith(prefixb) and o.type == "EMPTY"],
                key=lambda o: o.name
            )
            layout.label(text=f"Path B  ({len(wpsb)} points)", icon="ANIM")
            if wpsb:
                col2 = layout.column(align=True)
                for wp in wpsb:
                    row = col2.row(align=True)
                    row.label(text=wp.name, icon="EMPTY_AXIS")
                    op = row.operator("og.select_and_frame", text="", icon="VIEWZOOM"); op.obj_name = wp.name
                    op = row.operator("og.delete_waypoint",  text="", icon="X");        op.wp_name  = wp.name
            row2 = layout.row(align=True)
            op2b = row2.operator("og.add_waypoint", text="Spawn Path B Waypoint", icon="PLUS")
            op2b.enemy_name = sel.name; op2b.pathb_mode = True
            row2.prop(ctx.scene.og_props, "waypoint_spawn_at_actor", text="Spawn at Position", toggle=False)
            if len(wpsb) < 1:
                layout.label(text="⚠ swamp-bat crashes without Path B", icon="ERROR")



class OG_PT_ActorGoalCode(Panel):
    """Per-actor custom GOAL code injection.

    Shown for any ACTOR_ empty (not waypoints).
    Links a Blender text block to the actor; the block is appended verbatim
    to *-obs.gc on export after the addon's own generated types.
    Multiple actors can share the same text block — it is emitted only once.
    """
    bl_label       = "GOAL Code"
    bl_idname      = "OG_PT_actor_goal_code"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or sel.type != "EMPTY" or "_wp_" in sel.name or "_wpb_" in sel.name:
            return False
        parts = sel.name.split("_", 2)
        return len(parts) >= 3 and parts[0] == "ACTOR"

    def draw_header(self, ctx):
        """Show a small indicator dot when a code block is active + enabled."""
        sel = ctx.active_object
        if sel and hasattr(sel, "og_goal_code_ref"):
            ref = sel.og_goal_code_ref
            if ref.text_block and ref.enabled:
                self.layout.label(text="", icon="RADIOBUT_ON")

    def draw(self, ctx):
        layout = self.layout
        sel    = ctx.active_object
        ref    = sel.og_goal_code_ref

        if ref.text_block is None:
            # ── No block assigned ───────────────────────────────────────────
            col = layout.column(align=True)
            col.label(text="No GOAL code block assigned", icon="INFO")
            col.separator(factor=0.5)
            col.operator("og.create_goal_code_block",
                         text="Create boilerplate block",
                         icon="FILE_NEW")
            col.separator(factor=0.5)
            col.label(text="Or assign an existing text block:", icon="BLANK1")
            col.prop(ref, "text_block", text="")
        else:
            # ── Block assigned ──────────────────────────────────────────────
            txt = ref.text_block

            # Header row: enabled toggle + block name picker + disconnect X
            row = layout.row(align=True)
            row.prop(ref, "enabled", text="")
            row.prop(ref, "text_block", text="")
            row.operator("og.clear_goal_code_block", text="", icon="X")

            layout.separator(factor=0.3)

            # Status line: line count + will/won't inject
            line_count = len(txt.lines)
            if ref.enabled:
                status_icon = "CHECKMARK"
                status_text = f"{line_count} lines — will inject on export"
            else:
                status_icon = "PAUSE"
                status_text = f"{line_count} lines — disabled (won't export)"

            row2 = layout.row()
            row2.enabled = False
            row2.label(text=status_text, icon=status_icon)

            layout.separator(factor=0.3)

            # Action buttons: new block (replaces) + open in editor
            row3 = layout.row(align=True)
            row3.operator("og.create_goal_code_block",
                          text="New block (replace)",
                          icon="FILE_NEW")
            row3.operator("og.open_goal_code_in_editor",
                          text="Open in Editor",
                          icon="TEXT")

            # Shared-block warning: list other actors using the same text block
            users = [o for o in ctx.scene.objects
                     if (o.type == "EMPTY"
                         and hasattr(o, "og_goal_code_ref")
                         and o.og_goal_code_ref.text_block is txt
                         and o != sel)]
            if users:
                box = layout.box()
                box.label(text=f"Shared with {len(users)} other actor(s):", icon="LINKED")
                for u in users[:4]:
                    box.label(text=f"  {u.name}", icon="BLANK1")
                if len(users) > 4:
                    box.label(text=f"  … and {len(users) - 4} more", icon="BLANK1")
                note = box.row()
                note.enabled = False
                note.label(text="Shared blocks are emitted once in obs.gc")



# ─── Classes to register ───────────────────────────────────────────────────
CLASSES = (
    OG_PT_ActorActivation,
    OG_PT_ActorTriggerBehaviour,
    OG_PT_ActorNavMesh,
    OG_PT_ActorLinks,
    OG_PT_ActorPlatform,
    OG_PT_ActorCrate,
    OG_PT_ActorLauncher,
    OG_PT_ActorEcoDoor,
    OG_PT_ActorWaterVol,
    OG_PT_ActorLauncherDoor,
    OG_PT_ActorSunIrisDoor,
    OG_PT_ActorCaveElevator,
    OG_PT_ActorTaskGated,
    OG_PT_ActorVisibility,
    OG_PT_ActorWaypoints,
    OG_PT_ActorGoalCode,
)
