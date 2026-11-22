"""A small ? in the header of the main tabs and the larger feature panels:
opens that part of the user guide (docs/guide on GitHub) in the browser.

attach(classes) adds it before registration, as draw_header_preset (the right
side of the header), so no panel gets an extra line."""
from __future__ import annotations

import bpy
from bpy.props import StringProperty

GUIDE_URL = "https://github.com/Theory-box/Jak-1-Level-Builder-Tool/blob/main/docs/guide/"

# panel bl_idname -> (page, heading anchor or "")
GUIDE = {
    # the main tabs
    "OG_PT_build_play": ("build-and-play", ""),
    "OG_PT_level": ("levels", ""),
    "OG_PT_spawn": ("actors", "spawning-an-actor"),
    "OG_PT_object_controls": ("object-controls", ""),
    "OG_PT_selected_object": ("actors", "actor-settings"),
    "OG_PT_lighting": ("lighting", "light-baking"),
    "OG_PT_tasks": ("tasks", ""),
    "OG_PT_import": ("importing", ""),
    "OG_PT_dev_tools": ("developer-tools", ""),
    # larger features
    "OG_PT_level_settings": ("levels", "settings"),
    "OG_PT_level_audit": ("troubleshooting", "level-audit"),
    "OG_PT_actor_fields": ("actors", "actor-settings"),
    "OG_PT_actor_links": ("actors", "entity-links"),
    "OG_PT_actor_waypoints": ("paths-and-platforms", ""),
    "OG_PT_actor_navmesh": ("enemies-and-navmesh", "nav-meshes"),
    "OG_PT_navmesh_info": ("enemies-and-navmesh", "nav-meshes"),
    "OG_PT_selected_navmesh_tag": ("enemies-and-navmesh", "nav-meshes"),
    "OG_PT_actor_nav_behaviour": ("enemies-and-navmesh", "nav-behaviour-waking-up-and-aggro"),
    "OG_PT_actor_battlecontroller": ("enemies-and-navmesh", "battle-controller-ambushes"),
    "OG_PT_actor_platform": ("paths-and-platforms", "platforms"),
    "OG_PT_actor_movie_pos": ("actors", "movie-position"),
    "OG_PT_selected_lumps": ("actors", "custom-lumps"),
    "OG_PT_actor_goal_code": ("edited-actors-and-goal-code", "goal-code-blocks"),
    "OG_PT_camera_settings": ("cameras", "camera-settings"),
    "OG_PT_checkpoint_settings": ("level-flow", "checkpoints-continue-points"),
    "OG_PT_load_boundary_settings": ("level-flow", "load-boundaries"),
    "OG_PT_hint_volume": ("level-flow", "hints"),
    "OG_PT_volume_links": ("volumes-and-triggers", "what-a-volume-can-be-linked-to"),
    "OG_PT_actor_water_vol": ("volumes-and-triggers", "water"),
    "OG_PT_ambient_emitter": ("audio", "sound-emitters"),
    "OG_PT_music_zone": ("audio", "music"),
    "OG_PT_selected_collision": ("geometry", "the-collision-panel"),
    "OG_PT_vertex_colors": ("lighting", "vertex-colors-tools"),
    "OG_PT_uv_tools": ("object-controls", "uv-tools"),
    "OG_PT_texturing": ("geometry", "textures"),
}


def url(page, anchor=""):
    return f"{GUIDE_URL}{page}.md" + (f"#{anchor}" if anchor else "")


class OG_OT_OpenGuide(bpy.types.Operator):
    """Open this part of the user guide in the browser"""
    bl_idname = "og.open_guide"
    bl_label = "Open Guide"

    page: StringProperty()
    anchor: StringProperty()

    @classmethod
    def description(cls, ctx, props):
        return f"Open the user guide: {props.page.replace('-', ' ')}" + (
            f" › {props.anchor.replace('-', ' ')}" if props.anchor else "")

    def execute(self, ctx):
        bpy.ops.wm.url_open(url=url(self.page, self.anchor))
        return {"FINISHED"}


def _header_button(page, anchor, old=None):
    def draw_header_preset(self, ctx):
        if old is not None:
            old(self, ctx)
        op = self.layout.operator("og.open_guide", text="", icon="QUESTION", emboss=False)
        op.page, op.anchor = page, anchor
    return draw_header_preset


def attach(classes):
    """Give the GUIDE panels their ? (call before the classes are registered)."""
    for c in classes:
        if not (isinstance(c, type) and issubclass(c, bpy.types.Panel)):
            continue
        g = GUIDE.get(getattr(c, "bl_idname", ""))
        if g is None or getattr(c, "_og_guide", False):
            continue
        c.draw_header_preset = _header_button(*g, old=c.__dict__.get("draw_header_preset"))
        c._og_guide = True


CLASSES = (OG_OT_OpenGuide,)
