# ───────────────────────────────────────────────────────────────────────
# panels/tools.py — OpenGOAL Level Tools
#
# Geometry + build-tool panels: vertex export, waypoints, collision, build-and-play, dev tools + their operators.
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


class OG_PT_VertexExport(Panel):
    bl_label       = "Export As"
    bl_idname      = "OG_PT_vertex_export"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        o = ctx.active_object
        return (
            o is not None
            and o.type == "MESH"
            and not o.name.startswith(("ACTOR_", "VOL_", "NAVMESH_", "CPVOL_"))
            and not o.get("og_navmesh")
        )

    def draw(self, ctx):
        layout = self.layout
        o      = ctx.active_object

        assigned = str(o.get("og_vertex_export_etype", "")).strip()
        search   = str(o.get("og_vertex_export_search", "")).strip()

        # ── Current assignment ────────────────────────────────────────────
        if assigned and assigned in VERTEX_EXPORT_TYPES:
            info = VERTEX_EXPORT_TYPES[assigned]
            box  = layout.box()
            row  = box.row(align=True)
            row.label(text=f"{info['label']}  [{info.get('cat','')}]", icon="CHECKMARK")
            row.operator("og.clear_vertex_export", text="", icon="X")
            # Use evaluated mesh so the preview count reflects modifiers
            try:
                depsgraph = ctx.evaluated_depsgraph_get()
                o_eval    = o.evaluated_get(depsgraph)
                vcount    = len(o_eval.to_mesh().vertices)
                o_eval.to_mesh_clear()
            except Exception:
                vcount = len(o.data.vertices)
            box.label(text=f"{vcount} vert{'ex' if vcount == 1 else 'ices'} → {vcount} actor{'s' if vcount != 1 else ''} (post-modifiers)", icon="INFO")
        else:
            layout.label(text="No entity assigned", icon="INFO")

        layout.separator(factor=0.3)

        # ── Search bar ────────────────────────────────────────────────────
        row = layout.row(align=True)
        # Use a temporary scene prop for the search string (Object props
        # can't drive Blender search fields directly without a UIList).
        row.prop(ctx.scene.og_props, "entity_search", icon="VIEWZOOM", text="")

        query = ctx.scene.og_props.entity_search.strip().lower()

        if query:
            matches = [
                (etype, info)
                for etype, info in VERTEX_EXPORT_TYPES.items()
                if query in info["label"].lower() or query in etype.lower()
            ]
            matches.sort(key=lambda x: x[1]["label"].lower())

            if matches:
                box = layout.box()
                for etype, info in matches[:20]:
                    cat    = info.get("cat", "")
                    label  = info["label"]
                    is_sel = (etype == assigned)
                    row2   = box.row(align=True)
                    op = row2.operator(
                        "og.assign_vertex_export",
                        text=f"{'▶ ' if is_sel else ''}{label}  [{cat}]",
                        emboss=is_sel,
                    )
                    op.etype = etype
                if len(matches) > 20:
                    layout.label(text=f"… {len(matches) - 20} more", icon="INFO")
            else:
                layout.label(text="No results", icon="QUESTION")
        else:
            layout.label(text="Search to assign an entity type", icon="INFO")



class OG_PT_Waypoints(Panel):
    bl_label       = "〰  Waypoints"
    bl_idname      = "OG_PT_waypoints"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or not sel.name.startswith("ACTOR_") or "_wp_" in sel.name:
            return False
        parts = sel.name.split("_", 2)
        if len(parts) < 3:
            return False
        return _actor_uses_waypoints(parts[1])

    def draw(self, ctx):
        layout = self.layout
        sel    = ctx.active_object
        etype  = sel.name.split("_", 2)[1]
        einfo  = ENTITY_DEFS.get(etype, {})

        prefix = sel.name + "_wp_"
        wps = sorted(
            [o for o in bpy.data.objects if o.name.startswith(prefix) and o.type == "EMPTY"],
            key=lambda o: o.name
        )

        layout.label(text=f"Path  ({len(wps)} point{'s' if len(wps) != 1 else ''})", icon="ANIM")

        if wps:
            col = layout.column(align=True)
            for wp in wps:
                row = col.row(align=True)
                row.label(text=wp.name, icon="EMPTY_AXIS")
                op = row.operator("og.delete_waypoint", text="", icon="X")
                op.wp_name = wp.name
        else:
            layout.label(text="No waypoints yet", icon="INFO")

        row = layout.row(align=True)
        row.operator("og.add_waypoint", text="Spawn Waypoint", icon="PLUS").enemy_name = sel.name
        row.prop(ctx.scene.og_props, "waypoint_spawn_at_actor", text="Spawn at Position", toggle=False)

        if einfo.get("needs_path") and len(wps) < 1:
            layout.label(text="⚠ Needs ≥ 1 waypoint or will crash", icon="ERROR")

        if einfo.get("needs_pathb"):
            _header_sep(layout)
            prefixb = sel.name + "_wpb_"
            wpsb = sorted(
                [o for o in bpy.data.objects if o.name.startswith(prefixb) and o.type == "EMPTY"],
                key=lambda o: o.name
            )
            layout.label(text=f"Path B — slave bats  ({len(wpsb)} points)", icon="ANIM")
            if wpsb:
                col2 = layout.column(align=True)
                for wp in wpsb:
                    row = col2.row(align=True)
                    row.label(text=wp.name, icon="EMPTY_AXIS")
                    op2 = row.operator("og.delete_waypoint", text="", icon="X")
                    op2.wp_name = wp.name
            else:
                layout.label(text="No Path B waypoints yet", icon="INFO")

            row3 = layout.row(align=True)
            op3 = row3.operator("og.add_waypoint", text="Spawn Path B Waypoint", icon="PLUS")
            op3.enemy_name = sel.name; op3.pathb_mode = True
            row3.prop(ctx.scene.og_props, "waypoint_spawn_at_actor", text="Spawn at Position", toggle=False)

            if len(wpsb) < 1:
                layout.label(text="⚠ swamp-bat crashes without Path B", icon="ERROR")



class OG_PT_BuildPlay(Panel):
    bl_label       = "▶  Build & Play"
    bl_idname      = "OG_PT_build_play"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"

    def draw(self, ctx):
        layout = self.layout
        gk_ok  = _gk().exists()
        gc_ok  = _goalc().exists()
        gp_ok  = _game_gp().exists()

        if not (gk_ok and gc_ok and gp_ok):
            box = layout.box()
            box.label(text="Missing paths — open Developer Tools", icon="ERROR")
            layout.separator(factor=0.3)

        col = layout.column(align=True)
        col.scale_y = 1.8
        col.operator("og.export_build",  text="⚙  Export & Compile",        icon="EXPORT")
        col.scale_y = 1.4
        col.operator("og.geo_rebuild",   text="🔄  Quick Geo Rebuild",       icon="FILE_REFRESH")
        col.scale_y = 1.8
        col.operator("og.play",          text="▶  Launch Game (Debug)",      icon="PLAY")



class OG_OT_ReloadAddon(Operator):
    """Hot-reload the OpenGOAL addon from disk — clears all Python module caches.
    Use this after updating the .py file instead of restarting Blender."""
    bl_idname = "og.reload_addon"
    bl_label  = "Reload Addon"
    bl_description = "Reload the OpenGOAL addon from disk without restarting Blender"

    def execute(self, ctx):
        import importlib, sys
        # Find our module name in sys.modules
        mod_name = None
        for name, mod in list(sys.modules.items()):
            if hasattr(mod, "__file__") and mod.__file__ and "opengoal_tools" in mod.__file__:
                mod_name = name
                break
        if mod_name is None:
            self.report({"ERROR"}, "Could not find opengoal_tools in sys.modules")
            return {"CANCELLED"}
        try:
            # Unregister current version
            unregister()
            # Force reload from disk — bypasses all caches
            mod = sys.modules[mod_name]
            importlib.reload(mod)
            # Re-register the freshly loaded version
            mod.register()
            self.report({"INFO"}, f"Reloaded {mod_name} from disk ✓")
        except Exception as e:
            self.report({"ERROR"}, f"Reload failed: {e}")
            return {"CANCELLED"}
        return {"FINISHED"}



class OG_PT_DevTools(Panel):
    bl_label       = "🔧  Developer Tools"
    bl_idname      = "OG_PT_dev_tools"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_options     = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        layout = self.layout

        # ── Reload / Clean ───────────────────────────────────────────────────
        row = layout.row()
        row.scale_y = 1.4
        row.operator("og.clean_level_files",  text="🗑  Clean Files",  icon="TRASH")
        layout.separator(factor=0.5)

        # Paths
        layout.label(text="Paths", icon="PREFERENCES")
        box = layout.box()
        gk_ok = _gk().exists()
        gc_ok = _goalc().exists()
        gp_ok = _game_gp().exists()
        box.label(text=f"gk{_EXE}:    {'✓ OK' if gk_ok else '✗ NOT FOUND'}", icon="CHECKMARK" if gk_ok else "ERROR")
        box.label(text=f"goalc{_EXE}: {'✓ OK' if gc_ok else '✗ NOT FOUND'}", icon="CHECKMARK" if gc_ok else "ERROR")
        box.label(text=f"game.gp:   {'✓ OK' if gp_ok else '✗ NOT FOUND'}", icon="CHECKMARK" if gp_ok else "ERROR")
        box.operator("preferences.addon_show", text="Set EXE / Data Paths", icon="PREFERENCES").module = __name__

        layout.separator()

        # Quick Open — nested here
        layout.label(text="Quick Open", icon="FILE_FOLDER")
        name = _lname(ctx)
        self._quick_open(layout, name)

    def _btn(self, layout, label, icon, path, is_file=False):
        p = Path(path) if path else None
        row = layout.row(align=True)
        row.enabled = bool(path)
        if is_file:
            op = row.operator("og.open_file",   text=label, icon=icon)
            op.filepath = str(p) if p else ""
        else:
            op = row.operator("og.open_folder", text=label, icon=icon)
            op.folder = str(p) if p else ""
        if p and not p.exists():
            row.label(text="", icon="ERROR")

    def _quick_open(self, layout, name):
        col = layout.column(align=True)
        self._btn(col, "goal_src/",    "FILE_FOLDER", str(_goal_src()) if _goal_src().parent.exists() else "")
        self._btn(col, "game.gp",      "FILE_SCRIPT", str(_game_gp()), is_file=True)
        self._btn(col, "level-info.gc","FILE_SCRIPT", str(_level_info()), is_file=True)
        self._btn(col, "entity.gc",    "FILE_SCRIPT", str(_entity_gc()), is_file=True)

        if name:
            layout.separator(factor=0.3)
            ldir       = _ldir(name)
            goal_level = _goal_src() / "levels" / name
            col2 = layout.column(align=True)
            self._btn(col2, f"{name}/",           "FILE_FOLDER", str(ldir))
            self._btn(col2, f"{name}.jsonc",      "FILE_TEXT",   str(ldir / f"{name}.jsonc"), is_file=True)
            self._btn(col2, f"{name}.glb",        "FILE_3D",     str(ldir / f"{name}.glb"),   is_file=True)
            self._btn(col2, f"{_nick(name)}.gd",  "FILE_SCRIPT", str(ldir / f"{_nick(name)}.gd"), is_file=True)
            self._btn(col2, f"{name}-obs.gc",     "FILE_SCRIPT", str(goal_level / f"{name}-obs.gc"), is_file=True)

        layout.separator(factor=0.3)
        col3 = layout.column(align=True)
        self._btn(col3, "custom_assets/", "FILE_FOLDER", str(_data() / "custom_assets" / "jak1" / "levels"))
        self._btn(col3, "Game logs",      "SCRIPT",      str(_data() / "log"))
        self._btn(col3, "startup.gc",     "FILE_SCRIPT", str(_user_dir() / "startup.gc"), is_file=True)



class OG_PT_Collision(Panel):
    bl_label       = "Collision"
    bl_idname      = "OG_PT_collision"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx): return ctx.active_object is not None

    def draw(self, ctx):
        layout = self.layout
        ob     = ctx.active_object

        # Actor info summary
        if ob.name.startswith("ACTOR_") and "_wp_" not in ob.name:
            parts = ob.name.split("_", 2)
            if len(parts) >= 3:
                etype = parts[1]
                einfo = ENTITY_DEFS.get(etype, {})
                box = layout.box()
                box.label(text=f"{etype}", icon="OBJECT_DATA")
                box.label(text=f"AI: {einfo.get('ai_type', '?')}")
                nm = ob.get("og_navmesh_link", "")
                if nm:
                    box.label(text=f"NavMesh: {nm}", icon="LINKED")
                elif einfo.get("ai_type") == "nav-enemy":
                    box.label(text="No navmesh linked!", icon="ERROR")
                layout.separator(factor=0.3)

        layout.prop(ob, "set_invisible")
        layout.prop(ob, "enable_custom_weights")
        layout.prop(ob, "copy_eye_draws")
        layout.prop(ob, "copy_mod_draws")
        layout.prop(ob, "set_collision")
        if ob.set_collision:
            col = layout.column()
            col.prop(ob, "ignore")
            col.prop(ob, "collide_mode")
            col.prop(ob, "collide_material")
            col.prop(ob, "collide_event")
            r = col.row(align=True)
            r.prop(ob, "noedge");  r.prop(ob, "noentity")
            r2 = col.row(align=True)
            r2.prop(ob, "nolineofsight"); r2.prop(ob, "nocamera")




class OG_OT_UseLumpRef(bpy.types.Operator):
    """Add a new lump row pre-filled with this reference entry's key and type."""
    bl_idname  = "og.use_lump_ref"
    bl_label   = "Use This"
    bl_options = {"REGISTER", "UNDO"}

    lump_key:   bpy.props.StringProperty()
    lump_ltype: bpy.props.StringProperty()

    def execute(self, ctx):
        obj = ctx.active_object
        if obj is None:
            self.report({"ERROR"}, "No active object"); return {"CANCELLED"}
        row = obj.og_lump_rows.add()
        row.key   = self.lump_key
        row.ltype = self.lump_ltype
        obj.og_lump_rows_index = len(obj.og_lump_rows) - 1
        return {"FINISHED"}


def _draw_lump_ref_section(layout, title, entries, icon="DOT"):
    """Draw a collapsible read-only reference section."""
    if not entries:
        return
    box = layout.box()
    box.label(text=title, icon=icon)
    col = box.column(align=True)
    for key, ltype, desc in entries:
        row = col.row(align=True)
        row.label(text=key, icon="KEYFRAME")
        sub = row.row(align=True)
        sub.enabled = False
        sub.label(text=ltype)
        op = row.operator("og.use_lump_ref", text="", icon="ADD")
        op.lump_key   = key
        op.lump_ltype = ltype
        # Description as a greyed-out label on the next line
        desc_row = col.row()
        desc_row.enabled = False
        desc_row.label(text=f"  {desc}")
        col.separator(factor=0.3)

class OG_OT_AssignVertexExport(bpy.types.Operator):
    bl_idname      = "og.assign_vertex_export"
    bl_label       = "Assign Entity"
    bl_description = "Set this entity type as the vertex-export target for this mesh"
    bl_options     = {"UNDO"}

    etype: bpy.props.StringProperty()

    def execute(self, ctx):
        o = ctx.active_object
        if o:
            o["og_vertex_export_etype"]  = self.etype
            o["og_vertex_export_search"] = ""
            ctx.scene.og_props.entity_search = ""   # clear the shared search bar
            # Move into the Export As sub-collection so it stays organised
            _link_object_to_sub_collection(ctx.scene, o, *_COL_PATH_EXPORT_AS)
        return {"FINISHED"}


# Selected Object sub-panels  (mesh context, collapsible)
# ---------------------------------------------------------------------------

class OG_OT_ClearVertexExport(bpy.types.Operator):
    bl_idname      = "og.clear_vertex_export"
    bl_label       = "Clear Export As"
    bl_description = "Remove the vertex-export entity assignment from this mesh"
    bl_options     = {"UNDO"}

    def execute(self, ctx):
        o = ctx.active_object
        if o:
            o["og_vertex_export_etype"]  = ""
            o["og_vertex_export_search"] = ""
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Selected Object > Export As  (sub-panel — only on plain MESH objects)
# ---------------------------------------------------------------------------

# ─── Classes to register ───────────────────────────────────────────────────
CLASSES = (
    OG_OT_ClearVertexExport,
    OG_OT_AssignVertexExport,
    OG_OT_UseLumpRef,
    OG_PT_VertexExport,
    OG_PT_Waypoints,
    OG_PT_BuildPlay,
    OG_OT_ReloadAddon,
    OG_PT_DevTools,
    OG_PT_Collision,
)
