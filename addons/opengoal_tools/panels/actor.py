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
    ACTOR_LINK_DEFS, LUMP_TYPE_ITEMS,
    ETYPE_AG,
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
from .. import db as _db
from ..audit import run_audit


from .selected import _draw_actor_links


class OG_PT_ActorNavBehaviour(Panel):
    """Activation fields ("activation" panel) + aggro trigger volumes."""
    bl_label       = "Nav Behaviour"
    bl_idname      = "OG_PT_actor_nav_behaviour"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_actor_fields"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        return (len(parts) >= 3 and parts[0] == "ACTOR"
                and (_db.has_panel(parts[1], "activation") or _actor_supports_aggro_trigger(parts[1])))

    def draw(self, ctx):
        layout = self.layout
        sel    = ctx.active_object
        etype  = sel.name.split("_", 2)[1]
        if _db.has_panel(etype, "activation"):
            _draw_panel_fields(layout, sel, "activation")
        if not _actor_supports_aggro_trigger(etype):
            return
        layout.label(text="Trigger Behaviour", icon="MESH_CUBE")
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
        from .selected import _draw_vol_link_add
        _draw_vol_link_add(layout, sel)



class OG_PT_ActorNavMesh(Panel):
    bl_label       = "NavMesh"
    bl_idname      = "OG_PT_actor_navmesh"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_actor_fields"
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
            row.operator("og.unlink_navmesh", text="", icon="X").actor_name = sel.name
            others = [o for o in ctx.scene.objects if o is not sel and o.get("og_navmesh_link") == nm_obj.name]
            if others:
                warn = layout.column(align=True)
                warn.alert = True
                warn.label(text=f"{len(others)} other actor(s) also use this nav-mesh:", icon="ERROR")
                warn.label(text="it is built once per actor. Share it instead:")
                layout.operator("og.navmesh_share", text="Others use this actor's nav-mesh",
                                icon="LINKED").actor_name = sel.name
            try:
                nm_obj.data.calc_loop_triangles()
                tc = len(nm_obj.data.loop_triangles)
                layout.label(text=f"{tc} triangles", icon="MESH_DATA")
            except Exception:
                pass
        else:
            layout.label(text="No mesh linked", icon="ERROR")
        # Same pattern as the other links: selected meshes, then search.
        from .selected import _draw_link_search
        for m in [o for o in bpy.context.selected_objects
                  if o.type == "MESH" and o is not nm_obj and not o.name.startswith(("VOL_", "CPVOL_"))][:6]:
            op = layout.row().operator("og.link_navmesh_to", text=f"Link → {m.name}", icon="LINKED")
            op.actor_name = sel.name; op.target_name = m.name
        _draw_link_search(layout, "Search navmesh…", "og.link_navmesh_to", actor_name=sel.name)
        nav_r = float(sel.get("og_nav_radius", 6.0))
        layout.label(text=f"Fallback sphere radius: {nav_r:.1f}m", icon="SPHERE")
        if _db.can_jump(sel.name.split("_", 2)[1]):
            r = layout.row(); r.enabled = False
            r.label(text="Can jump (usable as a battlecontroller lurker)", icon="CHECKMARK")
        if _db.panel_fields(sel.name.split("_", 2)[1], "nav-mesh", visible_only=True):
            layout.separator()
            _draw_panel_fields(layout, sel, "nav-mesh")



def _bc_section(layout, idname, title, icon, closed=False):
    """A collapsible sub menu (Blender 4.1+ layout panels; a box before)."""
    if hasattr(layout, "panel"):
        header, body = layout.panel(idname, default_closed=closed)
        header.label(text=title, icon=icon)
        return body
    box = layout.box(); box.label(text=title, icon=icon)
    return box


class OG_PT_ActorBattlecontroller(Panel):
    """Battlecontroller (ambush): intro camera variant + its options."""
    bl_label       = "Battle Controller"
    bl_idname      = "OG_PT_actor_battlecontroller"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_actor_fields"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        return len(parts) >= 3 and parts[0] == "ACTOR" and _db.has_panel(parts[1], "battlecontroller")

    def draw(self, ctx):
        from .actor_fields import _draw_field
        from .selected import _draw_link_slot
        from ..export import battlecontroller as _bc
        layout = self.layout
        sel = ctx.active_object
        etype = sel.name.split("_", 2)[1]
        info = {"etype": etype, **(_db.find_actor(etype) or {})}
        fields = _db.panel_fields(etype, "battlecontroller", visible_only=True)
        by_sec = lambda s: [f for f in fields if f.get("section") == s]
        sel_actors = [o for o in ctx.selected_objects if o != sel and o.type == "EMPTY"
                      and o.name.startswith("ACTOR_") and "_wp_" not in o.name]

        def links(box, *keys):
            for k in keys:
                s = _db.link_slot(etype, k, 0)
                if s:
                    _draw_link_slot(box, sel, ctx.scene, etype, k, 0, s.get("label", k),
                                    s.get("accepts", ["any"]), s.get("required", False), sel_actors)

        body = _bc_section(layout, "og_bc_camera", "Intro camera", "CAMERA_DATA")
        if body:
            self._camera(body, ctx, sel, etype, _bc)
        body = _bc_section(layout, "og_bc_spawn", "Lurkers spawn", "OUTLINER_OB_ARMATURE")
        if body:
            for f in by_sec("spawn"):
                _draw_field(body, sel, f, info)
            links(body, "spawner-blocker-actor", "spawner-trigger-actor")
        body = _bc_section(layout, "og_bc_lurkers", "Lurker info", "COMMUNITY")
        if body:
            for i, e in enumerate(sel.og_bc_lurkers):
                b = body.box()
                r = b.row(align=True)
                r.label(text=f"[{i}] {(_db.find_actor(e.etype) or {}).get('label', e.etype)}", icon="GHOST_ENABLED")
                op = r.operator("og.bc_lurker_remove", text="", icon="X"); op.index = i
                col = b.column(align=True)
                col.prop(e, "percent"); col.prop(e, "pickup_percent")
                col.prop(e, "pickup_type"); col.prop(e, "max_pickup_count")
                if i >= _bc.MAX_LURKER_TYPES:
                    w = b.row(); w.alert = True; w.label(text="Not used (max 4 lurker types)", icon="ERROR")
            r = body.row(align=True)
            r.operator("og.bc_lurker_add", text="Add Lurker", icon="ADD")
            if len(sel.og_bc_lurkers) > 1:
                r.operator("og.bc_lurker_even", text="Split Evenly", icon="ALIGN_JUSTIFY")
            if not len(sel.og_bc_lurkers):
                h = body.row(); h.enabled = False
                h.label(text="None added: the game spawns babaks", icon="INFO")
            for w in _bc.percent_problems(sel):
                r = body.row(); r.alert = True; r.label(text=w, icon="ERROR")
            body.separator()
            for f in by_sec("lurkers"):
                _draw_field(body, sel, f, info)
        body = _bc_section(layout, "og_bc_end", "End pickup", "FUND")
        if body:
            for f in by_sec("end"):
                _draw_field(body, sel, f, info)
        body = _bc_section(layout, "og_bc_other", "Other options", "PREFERENCES", closed=True)
        if body:
            links(body, "kill-actor", "trigger-actor", "fade-actor", "alt-actor")
            for f in by_sec("other"):
                _draw_field(body, sel, f, info)

    def _camera(self, box, ctx, sel, etype, _bc):
        from .actor_fields import _draw_enum_field, _prop_row
        vf = _db.variant_field(etype)
        if vf:
            _draw_enum_field(box, sel, vf)
        var = _bc.variant(sel)
        if var.get("custom_camera"):
            ag, anim = _bc.camera(sel)
            row = box.row(align=True)
            row.label(text="Camera:")
            row.operator("og.bc_pick_camera", text=("Custom…" if sel.get("og_bc_cam") == "custom" else (ag or "Pick…")), icon="VIEWZOOM")
            if sel.get("og_bc_cam") == "custom":
                _prop_row(box, sel, "og_bc_cam_custom", "  Art group:", "")
            row = box.row(align=True)
            row.label(text="Animation:")
            row.operator("og.bc_pick_anim", text=("Custom…" if sel.get("og_bc_anim") == "custom" else (anim or "Pick…")), icon="VIEWZOOM")
            if sel.get("og_bc_anim") == "custom":
                _prop_row(box, sel, "og_bc_anim_custom", "  Animation:", "")
            hint = box.column(); hint.enabled = False; hint.scale_y = 0.8
            hint.label(text="Plays at the controller when the ambush starts", icon="INFO")
            if not (ag and anim):
                w = box.row(); w.alert = True
                w.label(text="Pick a camera and an animation", icon="ERROR")
        elif var.get("needs_citadel_camera"):
            cam = _bc.citadel_camera_object(sel)
            row = box.row(align=True)
            if cam:
                row.label(text=f"Camera position: {cam.name}", icon="MESH_CONE")
                op = row.operator("og.select_and_frame", text="", icon="VIEWZOOM"); op.obj_name = cam.name
            else:
                row.alert = True
                row.label(text=f"Needs a camera position ({_bc.CITADEL_CAM_NAME})", icon="ERROR")
            for e in [o for o in ctx.selected_objects if o.type == "EMPTY" and o is not sel
                      and not o.name.startswith("ACTOR_") and o is not cam][:4]:
                op = box.row().operator("og.bc_campos_link", text=f"Link → {e.name}", icon="LINKED")
                op.actor_name = sel.name; op.target_name = e.name
            row = box.row(align=True)
            op = row.operator("og.bc_campos_add", text="Add Camera Position", icon="PLUS"); op.actor_name = sel.name
            row.prop(ctx.scene.og_props, "waypoint_spawn_at_actor", text="At Actor Position", toggle=True)
            hint = box.column(); hint.enabled = False; hint.scale_y = 0.8
            hint.label(text="Exported as the entity 'citadelcam-1' (one per level)", icon="INFO")


class OG_PT_ActorGameTask(Panel):
    """DB "game-task" panel: the actor's game task (the .jsonc "game_task";
    cells / scout flies also write it into their eco-info) + fly number."""
    bl_label       = "Game Task"
    bl_idname      = "OG_PT_actor_game_task"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_actor_fields"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        return len(parts) >= 3 and parts[0] == "ACTOR" and _db.has_panel(parts[1], "game-task")

    def draw(self, ctx):
        layout = self.layout
        sel = ctx.active_object
        etype = sel.name.split("_", 2)[1]
        note = _db.panel_option(etype, "game-task", "description", "")
        if note:
            hint = layout.column(); hint.enabled = False; hint.scale_y = 0.8
            hint.label(text=note, icon="INFO")
        _draw_panel_fields(layout, sel, "game-task")


class OG_PT_ActorMoviePos(Panel):
    """DB "movie-pos" panel: where a power cell plays its pickup animation
    (cells; actors that give one), or where the cell jumps (last scout fly)."""
    bl_label       = "Movie Position"
    bl_idname      = "OG_PT_actor_movie_pos"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_actor_fields"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        return len(parts) >= 3 and parts[0] == "ACTOR" and _db.has_panel(parts[1], "movie-pos")

    def draw(self, ctx):
        from .selected import _draw_link_search
        layout = self.layout
        sel    = ctx.active_object
        etype  = sel.name.split("_", 2)[1]
        note = _db.panel_option(etype, "movie-pos", "description",
                                "Where the power cell plays its pickup animation (cone = facing).")
        hint = layout.column(); hint.enabled = False; hint.scale_y = 0.8
        hint.label(text=note, icon="INFO")
        ents = list(sel.og_movie_pos)
        for i, s in enumerate(ents):
            row = layout.row(align=True)
            if s.obj is None or s.obj.name not in ctx.scene.objects:
                row.alert = True
                row.label(text=f"[{i}] missing", icon="ERROR")
            else:
                row.label(text=f"[{i}] {s.obj.name}", icon="MESH_CONE")
                op = row.operator("og.select_and_frame", text="", icon="VIEWZOOM"); op.obj_name = s.obj.name
            op = row.operator("og.movie_pos_remove", text="", icon="X")
            op.actor_name = sel.name; op.index = i
        if not ents:
            r = layout.row(); r.enabled = False
            r.label(text="Not set — the game uses its default spot", icon="DOT")
        # same pattern as the other links: selected, search, then spawn
        have = {s.obj.name for s in ents if s.obj}
        for e in [o for o in ctx.selected_objects if o.type == "EMPTY" and o is not sel
                  and not o.name.startswith("ACTOR_") and "_wp_" not in o.name and o.name not in have][:6]:
            op = layout.row().operator("og.movie_pos_link", text=f"Link → {e.name}", icon="LINKED")
            op.actor_name = sel.name; op.target_name = e.name
        _draw_link_search(layout, "Search empty…", "og.movie_pos_link", actor_name=sel.name)
        row = layout.row(align=True)
        op = row.operator("og.movie_pos_add", text="Add Position", icon="PLUS"); op.actor_name = sel.name
        row.prop(ctx.scene.og_props, "waypoint_spawn_at_actor", text="At Actor Position", toggle=True)
        # movie-mask: victory animations the cell must not pick (8 toggles)
        mask = [f for f in _db.panel_fields(etype, "movie-pos", visible_only=True) if f.get("group") == "movie-mask"]
        if mask:
            layout.separator()
            layout.label(text="Victory animations not to use (movie-mask):")
            grid = layout.grid_flow(columns=4, align=True)
            for i, f in enumerate(mask):
                on = bool(sel.get(f["key"], f.get("default", False)))
                op = grid.operator("og.toggle_actor_bool_field", text=str(i + 1),
                                   icon="CHECKBOX_HLT" if on else "CHECKBOX_DEHLT", depress=on)
                op.prop_key = f["key"]


class OG_PT_ActorLinks(Panel):
    """Entity link slots — actor-to-actor references exported as alt-actor / water-actor etc."""
    bl_label       = "Entity Links"
    bl_idname      = "OG_PT_actor_links"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_actor_fields"
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
    """DB "sync" panel. Was category-driven (all Platforms)."""
    bl_label       = "Sync"
    bl_idname      = "OG_PT_actor_platform"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_actor_fields"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        return len(parts) >= 3 and parts[0] == "ACTOR" and _db.has_panel(parts[1], "sync")

    def draw(self, ctx):
        _draw_platform_settings(self.layout, ctx.active_object, ctx.scene)



class OG_PT_ActorCrate(Panel):
    bl_label       = "Crate"
    bl_idname      = "OG_PT_actor_crate"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_actor_fields"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        return len(parts) >= 3 and parts[0] == "ACTOR" and _db.has_panel(parts[1], "crate")

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
        elif ct == "iron" and pickup != "buzzer":
            warn = box.box()
            warn.alert = True
            warn.label(text="Iron only holds a scout fly (the game makes it wood)", icon="ERROR")

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
        if sel.get("og_fop_fade"):
            _prop_row(box2, sel, "og_crate_fade_time", "Fade time (s):", 0.0)



class OG_PT_ActorLauncher(Panel):
    bl_label       = "Launcher Settings"
    bl_idname      = "OG_PT_actor_launcher"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_actor_fields"
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

        # ── Destination: actors whose DB fields have og_launcher_dest ─────────
        _keys = {f.get("key") for f in _db.inherited_fields(etype)}
        if "og_launcher_mode" in _keys:
            boxm = layout.box()
            boxm.label(text="Camera on Launch", icon="VIEW_CAMERA")
            mf = next(f for f in _db.inherited_fields(etype) if f.get("key") == "og_launcher_mode")
            cur = sel.get("og_launcher_mode", mf.get("default"))
            colm = boxm.column(align=True)
            for c in mf.get("choices", []):
                op = colm.operator("og.set_actor_enum_field", text=c["label"],
                                   icon="RADIOBUT_ON" if cur == c["value"] else "RADIOBUT_OFF")
                op.prop_key = "og_launcher_mode"; op.value = c["value"]
        if "og_launcher_dest" in _keys:
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
    bl_parent_id   = "OG_PT_actor_fields"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        return len(parts) >= 3 and parts[0] == "ACTOR" and _db.has_panel(parts[1], "eco-door")

    def draw(self, ctx):
        layout = self.layout
        sel    = ctx.active_object

        # ── Open condition hint ───────────────────────────────────────────────
        # (module-level import of _actor_get_link at the top of this file is used)
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
    bl_parent_id   = "OG_PT_actor_fields"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        return len(parts) >= 3 and parts[0] == "ACTOR" and _db.has_panel(parts[1], "water")

    def draw(self, ctx):
        layout = self.layout
        sel    = ctx.active_object
        box = layout.box()
        box.label(text="Water Volume", icon="MOD_OCEAN")
        box.label(text="Shape the linked VOL_ mesh to cover the water.", icon="INFO")
        # The "water" panel's fields (PanelTypes water + actor overrides).
        from .actor_fields import _draw_field
        etype = sel.name.split("_", 2)[1]
        info = {"etype": etype, **(_db.find_actor(etype) or {})}
        for f in _db.panel_fields(etype, "water", visible_only=True):
            _draw_field(box, sel, f, info)
        op = box.operator("og.sync_water_from_object",
                          text="Sync Surface from Volume Top", icon="OBJECT_ORIGIN")
        op.actor_name = sel.name


class OG_PT_ActorLauncherDoor(Panel):
    bl_label       = "Launcher Door Settings"
    bl_idname      = "OG_PT_actor_launcherdoor"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_actor_fields"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        return len(parts) >= 3 and parts[0] == "ACTOR" and _db.has_panel(parts[1], "launcherdoor")

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
    bl_parent_id   = "OG_PT_actor_fields"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        return len(parts) >= 3 and parts[0] == "ACTOR" and _db.has_panel(parts[1], "sun-iris-door")

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
    bl_parent_id   = "OG_PT_actor_fields"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        return len(parts) >= 3 and parts[0] == "ACTOR" and _db.has_panel(parts[1], "caveelevator")

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
    bl_parent_id   = "OG_PT_actor_fields"
    bl_options     = {"DEFAULT_CLOSED"}

    _TYPES = {"oracle", "pontoon"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        return len(parts) >= 3 and parts[0] == "ACTOR" and _db.has_panel(parts[1], "task-gated")

    def draw(self, ctx):
        layout = self.layout
        sel    = ctx.active_object
        etype  = sel.name.split("_", 2)[1]

        box = layout.box()
        if etype == "oracle":
            box.label(text="Second Orb Task (alt-task)", icon="SPHERE")
            sub = box.row(); sub.enabled = False
            sub.label(text="Set if oracle requires 2 orbs", icon="INFO")
        else:
            box.label(text="Sink Condition Task (alt-task)", icon="FORCE_FORCE")
            sub = box.row(); sub.enabled = False
            sub.label(text="Pontoon sinks when this task is complete", icon="INFO")

        # same searchable task picker as the Game Task panel (+ Custom)
        from .actor_fields import _draw_task_field
        field = next((f for f in _db.panel_fields(etype, "custom-fields") if f.get("key") == "og_alt_task"),
                     {"key": "og_alt_task", "label": "Task", "type": "task", "default": "none"})
        _draw_task_field(box, sel, field)



class OG_PT_ActorVisibility(Panel):
    bl_label       = "Visibility"
    bl_idname      = "OG_PT_actor_visibility"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_actor_fields"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        if len(parts) < 3 or parts[0] != "ACTOR": return False
        return _db.has_panel(parts[1], "visibility")

    def draw(self, ctx):
        _draw_panel_fields(self.layout, ctx.active_object, "visibility")



def _draw_panel_fields(layout, sel, pid):
    """Draw one DB panel's visible fields (labels/defaults/notes from the DB)."""
    from .actor_fields import _draw_field
    etype = sel.name.split("_", 2)[1]
    info = {"etype": etype, **(_db.find_actor(etype) or {})}
    for f in _db.panel_fields(etype, pid, visible_only=True):
        _draw_field(layout, sel, f, info)


class OG_PT_ActorScale(Panel):
    """DB "scale" panel: shows what the empty's Blender scale exports as."""
    bl_label       = "Scale"
    bl_idname      = "OG_PT_actor_scale"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_actor_fields"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        return len(parts) >= 3 and parts[0] == "ACTOR" and _db.panel_exports(parts[1], "scale")

    def draw(self, ctx):
        sel = ctx.active_object
        etype = sel.name.split("_", 2)[1]
        layout = self.layout
        # top-down so several axes can be dragged/edited together
        col = layout.column(align=True)
        for i, ax in enumerate("XYZ"):
            col.prop(sel, "scale", index=i, text=ax)
        lump = _db.scale_lump(etype, sel.matrix_world.to_scale())
        col = layout.column(); col.scale_y = 0.85
        if lump:
            col.label(text=f"Exports scale [{lump[1]:g}, {lump[2]:g}, {lump[3]:g}, 1]", icon="CHECKMARK")
        else:
            col.label(text="Scale 1: not exported", icon="DOT")
        if _db.panel_option(etype, "scale", "always", False):
            col.label(text="Always exported for this actor", icon="INFO")
        s = sel.matrix_world.to_scale()
        if _db.panel_option(etype, "scale", "uniform", False) and (abs(s.x - s.y) > 1e-4 or abs(s.x - s.z) > 1e-4):
            w = col.row(); w.alert = True
            w.label(text="This actor reads one value: only X is used", icon="ERROR")


class OG_PT_ActorFactOptions(Panel):
    """DB "fact-options" panel: the 'options' lump bits the actor's code reads
    (fact-h.gc). Options marked "highlight" for this actor come first."""
    bl_label       = "Options"
    bl_idname      = "OG_PT_actor_fact_options"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_actor_fields"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name: return False
        parts = sel.name.split("_", 2)
        return (len(parts) >= 3 and parts[0] == "ACTOR"
                and _db.panel_exports(parts[1], "fact-options"))

    def draw(self, ctx):
        from .actor_fields import _draw_field
        sel = ctx.active_object
        etype = sel.name.split("_", 2)[1]
        info = {"etype": etype, **(_db.find_actor(etype) or {})}
        flds = _db.panel_fields(etype, "fact-options", visible_only=True)
        top = [f for f in flds if f.get("highlight")]
        rest = [f for f in flds if not f.get("highlight")]
        if top:
            box = self.layout.box()
            box.label(text="For this actor", icon="SOLO_ON")
            for f in top:
                _draw_field(box, sel, f, info)
        if rest:
            col = self.layout.column()
            if top:
                col.label(text="Other options")
            for f in rest:
                _draw_field(col, sel, f, info)
        # Everything else stays reachable, collapsed (actors can use options
        # in less obvious ways, e.g. through the pickups they spawn).
        shown = {f.get("key") for f in flds}
        hidden = [f for f in _db.panel_fields(etype, "fact-options") if f.get("key") not in shown]
        if hidden:
            props = ctx.scene.og_props
            box = self.layout.box()
            box.prop(props, "show_all_fact_options",
                     icon="TRIA_DOWN" if props.show_all_fact_options else "TRIA_RIGHT", emboss=False,
                     text=f"All options ({len(hidden)} more)")
            if props.show_all_fact_options:
                for f in hidden:
                    _draw_field(box, sel, f, info)


class OG_UL_PathKnots(bpy.types.UIList):
    """Manual knot list (path-k): index + editable value per row."""

    def draw_item(self, ctx, layout, data, item, icon, active_data,
                  active_propname, index):
        row = layout.row(align=True)
        row.label(text=f"{index}")
        row.prop(item, "value", text="", emboss=True)


def draw_knot_editor(layout, owner, lump_name, actor_name, path_index, auto_knots,
                     manual_attr, list_attr, index_attr, open_attr):
    """Collapsed-by-default knot (path-k) box. Automatic unless the user
    switches to a manual list; presets fill the list, Fit follows point
    count changes, the export resizes on its own if they differ."""
    if not auto_knots:
        return
    from ..export import path_modes as _pm
    manual = getattr(owner, manual_attr)
    coll = getattr(owner, list_attr)
    box = layout.box()
    hdr = box.row(align=True)
    is_open = getattr(owner, open_attr)
    hdr.prop(owner, open_attr, text="", emboss=False, icon="TRIA_DOWN" if is_open else "TRIA_RIGHT")
    hdr.label(text=f"Knots ({lump_name}-k): {'Manual' if manual else 'Automatic'} · {len(auto_knots)} values",
              icon="IPO_BEZIER")
    if not is_open:
        if manual and len(coll) != len(auto_knots):
            w = box.row(); w.alert = True
            w.label(text=f"Manual list has {len(coll)}, path needs {len(auto_knots)}", icon="ERROR")
        return

    def _op(row, preset, text, icon="NONE"):
        op = row.operator("og.path_knots_preset", text=text, icon=icon)
        op.actor_name = actor_name; op.path_index = path_index; op.preset = preset

    if not manual:
        _op(box.row(), "AUTO", "Edit Knots Manually", "GREASEPENCIL")
        return
    row = box.row(align=True)
    _op(row, "CLAMPED", "Clamped")
    _op(row, "UNIFORM", "Uniform")
    _op(row, "AUTO", "Automatic")
    box.template_list("OG_UL_PathKnots", f"knots{path_index}", owner, list_attr, owner, index_attr,
                      rows=4, maxrows=8)
    _vals, note = _pm.manual_knots(auto_knots, [k.value for k in coll])
    if len(coll) != len(auto_knots):
        w = box.row(align=True); w.alert = True
        w.label(text=f"Points changed: list {len(coll)}, needs {len(auto_knots)}", icon="ERROR")
        _op(w, "FIT", "Fit")
    elif note:
        w = box.row(); w.alert = True
        w.label(text=note, icon="ERROR")
    box.prop(owner, manual_attr, text="Manual knots (off = automatic)", toggle=True)


class OG_UL_WaypointSources(bpy.types.UIList):
    """List of waypoint source entries for an actor. Each entry points to
    either an EMPTY (legacy _wp_NN style, single point) or a CURVE (each
    control point becomes one waypoint at export). The list's order is the
    export order. Rendered with a vertical sidebar of frame/delete/move
    buttons in OG_PT_ActorWaypoints."""

    def draw_item(self, ctx, layout, data, item, icon, active_data,
                  active_propname, index):
        obj = item.obj
        if obj is None:
            # Source was cleared — show a placeholder so the user can re-pick.
            row = layout.row(align=True)
            row.alert = True
            row.label(text="(empty slot — pick a source)", icon="ERROR")
            row.prop(item, "obj", text="")
            return

        if obj.name not in ctx.scene.objects:
            # Pointer survived but the object was deleted. Surface it as
            # an error row; X button in the sidebar removes the entry.
            row = layout.row(align=True)
            row.alert = True
            row.label(text=f"{obj.name} — DELETED", icon="ERROR")
            return

        row = layout.row(align=True)
        if obj.type == "CURVE":
            n = _count_curve_points(obj)
            row.label(text=obj.name, icon="CURVE_DATA")
            sub = row.row(align=True)
            sub.alignment = "RIGHT"
            sub.active = False
            sub.label(text=f"{n} pt{'s' if n != 1 else ''}")
        elif obj.type == "EMPTY":
            row.label(text=obj.name, icon="EMPTY_AXIS")
        else:
            row.label(text=obj.name, icon="QUESTION")


def _draw_path_add(layout, sel, scene, coll, path_index=-1):
    """Ways to add to a path, same pattern as actor links: one Link button
    per shift-selected curve not yet in it, a search over every curve, then
    Spawn Waypoint with its at-actor-position toggle on one line."""
    from .selected import _draw_link_search
    have = {s.obj.name for s in coll if s.obj}
    for c in [o for o in bpy.context.selected_objects if o.type == "CURVE" and o.name not in have][:6]:
        op = layout.row().operator("og.waypoint_source_link_curve", text=f"Link → {c.name}", icon="CURVE_DATA")
        op.actor_name = sel.name; op.path_index = path_index; op.target_name = c.name
    _draw_link_search(layout, "Search curve…", "og.waypoint_source_link_curve",
                      actor_name=sel.name, path_index=path_index)
    row = layout.row(align=True)
    op = row.operator("og.add_waypoint", text="Spawn Waypoint", icon="PLUS")
    op.enemy_name = sel.name; op.path_index = path_index
    row.prop(scene.og_props, "waypoint_spawn_at_actor", text="At Actor Position", toggle=True)


def _count_curve_points(curve_obj) -> int:
    """Total spline-point count across every spline in a curve.
    Bezier splines use bezier_points; poly/NURBS use points."""
    n = 0
    for spline in curve_obj.data.splines:
        if spline.bezier_points:
            n += len(spline.bezier_points)
        else:
            n += len(spline.points)
    return n


class OG_PT_ActorWaypoints(Panel):
    bl_label       = "Path"
    bl_idname      = "OG_PT_actor_waypoints"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_actor_fields"
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

        sources = sel.og_waypoint_sources
        legacy_wps = self._discover_legacy_wps(sel, scene)
        n_sources = len(sources)

        # Total point count for the header — sum across the list, expanding
        # curves to their spline-point counts.
        if n_sources > 0:
            total_pts = sum(
                (_count_curve_points(s.obj) if s.obj and s.obj.type == "CURVE"
                 else (1 if s.obj and s.obj.type == "EMPTY" else 0))
                for s in sources
            )
            header_text = f"Path  ({total_pts} point{'s' if total_pts != 1 else ''})"
        else:
            n_legacy = len(legacy_wps)
            header_text = f"Path  ({n_legacy} legacy waypoint{'s' if n_legacy != 1 else ''})"

        layout.label(text=header_text, icon="ANIM")

        # If the new collection is empty and legacy _wp_NN empties exist,
        # offer a one-click migration. Skips Path B which stays on the
        # legacy system for now.
        if n_sources == 0 and legacy_wps:
            box = layout.box()
            box.label(text=f"Found {len(legacy_wps)} legacy waypoint empties",
                      icon="INFO")
            op = box.operator("og.waypoint_source_migrate",
                              text="Migrate to reorderable list",
                              icon="FILE_REFRESH")
            op.actor_name = sel.name

        # List + sidebar (the new UI).
        list_row = layout.row()
        list_row.template_list(
            "OG_UL_WaypointSources", "",
            sel, "og_waypoint_sources",
            sel, "og_waypoint_sources_index",
            rows=4,
        )
        sidebar = list_row.column(align=True)
        sidebar.operator("og.waypoint_source_frame", text="", icon="VIEWZOOM")
        sidebar.operator("og.waypoint_source_remove", text="", icon="X")
        sidebar.separator()
        sidebar.operator("og.waypoint_source_move",
                         text="", icon="TRIA_UP").direction = "UP"
        sidebar.operator("og.waypoint_source_move",
                         text="", icon="TRIA_DOWN").direction = "DOWN"

        # Link a curve (selected / searched), or spawn an empty waypoint.
        _draw_path_add(layout, sel, scene, sources)

        # Path mode (export/path_modes.py). Linear-only actors (path-control —
        # they ignore path-k) only get the straight-line choices.
        from ..export import path_modes as _pm
        linear_only = _db.path_linear_only(etype)
        mode_box = layout.box()
        if linear_only:
            mode_box.label(text="Path Mode (this actor only moves in straight lines):", icon="IPO_LINEAR")
            mrow = mode_box.row(align=True)
            for m in ("AUTO", "LINEAR", "LINEAR_LOOP"):
                mrow.prop_enum(sel, "og_path_mode", m)
        else:
            mode_box.prop(sel, "og_path_mode", text="Path Mode")
        try:
            _pts, _knots, _eff, _warn = _pm.build(
                _pm.gather_sources(sel), sel.og_path_mode, linear_only=linear_only)
            info = mode_box.column(); info.scale_y = 0.8
            label = _pm.MODE_LABELS.get(_eff, _eff)
            if sel.og_path_mode == "AUTO":
                label = f"Automatic → {label}"
            info.label(text=f"{label}: {len(_pts)} points"
                            + (f", {len(_knots)} knots (path-k)" if _knots else ""),
                       icon="IPO_BEZIER" if _knots else "IPO_LINEAR")
            if _warn:
                w = info.row(); w.alert = True
                w.label(text=_warn, icon="ERROR")
            draw_knot_editor(mode_box, sel, (sel.og_path_lump or "path").strip(), sel.name, -1, _knots,
                             "og_path_knots_manual", "og_path_knots", "og_path_knots_index",
                             "og_path_knots_open")
        except Exception:
            pass

        # Validation hints. Path panel options: "required" (errors without a
        # path), "min-points" (e.g. plat-button / sync platforms need 2).
        min_pts = int(_db.panel_option(etype, "path", "min-points", 1) or 1)
        if einfo.get("needs_path") or min_pts > 1:
            pt_count = sum(
                (_count_curve_points(s.obj) if s.obj and s.obj.type == "CURVE"
                 else (1 if s.obj and s.obj.type == "EMPTY" else 0))
                for s in sources
            ) if n_sources else len(legacy_wps)
            if pt_count < min_pts:
                if einfo.get("needs_path"):
                    layout.label(text=f"⚠ Needs ≥ {min_pts} waypoint{'s' if min_pts > 1 else ''} or will crash",
                                 icon="ERROR")
                else:
                    layout.label(text=f"Add ≥ {min_pts} waypoints to make it move", icon="INFO")

        # ── Extra paths (pathb, patha..pathh, pathspawn, custom) ─────────────
        self._draw_extra_paths(layout, sel, scene, etype, einfo, linear_only)

    def _draw_extra_paths(self, layout, sel, scene, etype, einfo, linear_only):
        from ..export import path_modes as _pm
        layout.separator(factor=0.5)
        hdr = layout.row(align=True)
        hdr.label(text="Lump:")
        hdr.prop(sel, "og_path_lump", text="")
        hdr.label(text="Keyframe:")
        hdr.prop(sel, "og_path_keyframe", text="")
        has_b = any(p.name == "pathb" for p in sel.og_extra_paths)
        # Path panel options: "paths" (lump names Add Path offers) or "multi-path".
        names_db = _db.path_names(etype)
        multi = bool(_db.panel_option(etype, "path", "multi-path", False) or len(names_db) > 1)

        for i, xp in enumerate(sel.og_extra_paths):
            box = layout.box()
            row = box.row(align=True)
            row.prop(xp, "expanded", text="", emboss=False,
                     icon="TRIA_DOWN" if xp.expanded else "TRIA_RIGHT")
            row.prop(xp, "name", text="")
            row.prop(xp, "keyframe", text="@")
            n_src = len(xp.sources)
            row.label(text=f"{n_src} source{'s' if n_src != 1 else ''}")
            op = row.operator("og.remove_extra_path", text="", icon="X")
            op.actor_name = sel.name; op.path_index = i
            if not xp.expanded:
                continue
            lrow = box.row()
            lrow.template_list("OG_UL_WaypointSources", f"xp{i}", xp, "sources", xp, "sources_index", rows=3)
            side = lrow.column(align=True)
            side.operator("og.waypoint_source_frame", text="", icon="VIEWZOOM").path_index = i
            side.operator("og.waypoint_source_remove", text="", icon="X").path_index = i
            side.separator()
            op = side.operator("og.waypoint_source_move", text="", icon="TRIA_UP"); op.direction = "UP"; op.path_index = i
            op = side.operator("og.waypoint_source_move", text="", icon="TRIA_DOWN"); op.direction = "DOWN"; op.path_index = i
            _draw_path_add(box, sel, scene, xp.sources, i)
            mrow = box.row(align=True)
            if linear_only:
                for m in ("AUTO", "LINEAR", "LINEAR_LOOP"):
                    mrow.prop_enum(xp, "mode", m)
            else:
                mrow.prop(xp, "mode", text="")
            try:
                pts, knots, eff, warn = _pm.build(_pm.gather_from(xp.sources), xp.mode,
                                                  linear_only=linear_only)
                info = box.column(); info.scale_y = 0.8
                lab = _pm.MODE_LABELS.get(eff, eff)
                if xp.mode == "AUTO":
                    lab = f"Automatic → {lab}"
                info.label(text=f"{lab}: {len(pts)} points" + (f", {len(knots)} knots ({xp.name}-k)" if knots else ""),
                           icon="IPO_BEZIER" if knots else "IPO_LINEAR")
                if warn:
                    w = info.row(); w.alert = True; w.label(text=warn, icon="ERROR")
                draw_knot_editor(box, xp, xp.name.strip() or "path", sel.name, i, knots,
                                 "knots_manual", "knots", "knots_index", "knots_open")
            except Exception:
                pass

        names = [p.name for p in sel.og_extra_paths] + [sel.og_path_lump]
        dup = sorted({n for n in names if names.count(n) > 1})
        if dup:
            w = layout.row(); w.alert = True
            w.label(text=f"Same name twice ({', '.join(dup)}): only the first exports", icon="ERROR")
        # Extra paths only for actors the DB marks multi-path ("paths" list
        # or "multi_path": true); existing ones always stay visible.
        if multi:
            wanted = [n for n in names_db
                      if n != sel.og_path_lump and not any(p.name == n for p in sel.og_extra_paths)]
            add = layout.row()
            op = add.operator("og.add_extra_path",
                              text=f"Add Path ({wanted[0]})" if wanted else "Add Path", icon="ADD")
            op.actor_name = sel.name
        if einfo.get("needs_pathb") and not has_b:
            layout.label(text="⚠ swamp-bat crashes without a 'pathb' path", icon="ERROR")

    def _discover_legacy_wps(self, actor_obj, scene):
        """Return the list of legacy <actor>_wp_NN empty objects in name order.
        Used to show the migration button and as the fallback path count."""
        prefix = actor_obj.name + "_wp_"
        return sorted(
            [o for o in _level_objects(scene)
             if o.name.startswith(prefix) and o.type == "EMPTY"
             and o.name[len(prefix):].isdigit()],     # not extra-path empties
            key=lambda o: o.name
        )



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
    bl_order       = 30
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



# ─── Actor Settings sub-panel order ────────────────────────────────────────
# Top: what is specific to the actor; going down: more general, the bottom
# being general and less used (Kuitar). Custom fields are drawn by the parent
# panel itself, so they always come first. Any sub-panel not listed here
# counts as actor-specific and goes above Sync — new bespoke panels need no
# entry; only add a new *general* panel to this list.
_GENERAL_PANEL_ORDER = (
    "OG_PT_actor_platform",        # Sync
    "OG_PT_actor_waypoints",       # Path
    "OG_PT_actor_navmesh",
    "OG_PT_actor_nav_behaviour",   # Activation + Trigger Behaviour
    "OG_PT_actor_game_task",       # Game Task
    "OG_PT_actor_movie_pos",       # Movie Position (power cell)
    "OG_PT_actor_fact_options",    # Options
    "OG_PT_actor_links",           # Entity Links
    "OG_PT_actor_visibility",
    "OG_PT_actor_scale",
)


def _actor_panel_rank(cls) -> int:
    idn = getattr(cls, "bl_idname", "")
    if idn in _GENERAL_PANEL_ORDER:
        return 100 + _GENERAL_PANEL_ORDER.index(idn)
    return 10   # actor-specific


# ─── Classes to register ───────────────────────────────────────────────────
_ACTOR_SUBPANELS = (
    OG_PT_ActorBattlecontroller,
    OG_PT_ActorNavBehaviour,
    OG_PT_ActorGameTask,
    OG_PT_ActorMoviePos,
    OG_PT_ActorNavMesh,
    OG_PT_ActorLinks,
    OG_PT_ActorPlatform,
    OG_PT_ActorLauncher,
    OG_PT_ActorCrate,
    OG_PT_ActorWaterVol,
    OG_PT_ActorEcoDoor,
    OG_PT_ActorLauncherDoor,
    OG_PT_ActorSunIrisDoor,
    OG_PT_ActorCaveElevator,
    OG_PT_ActorTaskGated,
    OG_PT_ActorVisibility,
    OG_PT_ActorWaypoints,
    OG_PT_ActorScale,
    OG_PT_ActorFactOptions,
)
for _c in _ACTOR_SUBPANELS:
    _c.bl_order = _actor_panel_rank(_c)

# Sub-panels show in registration order, so register them sorted by rank.
CLASSES = (
    OG_UL_PathKnots,
    OG_UL_WaypointSources,
    *sorted(_ACTOR_SUBPANELS, key=_actor_panel_rank),   # stable: ties keep listed order
    OG_PT_ActorGoalCode,
)
