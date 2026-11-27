"""OpenGOAL Actors tab: custom actors (your own art groups: model, skeleton, animations).

Each custom actor is a collection under "Custom Actors" (not part of any level) with a Model
collection (meshes + their armature) and a Collision collection (simple meshes, optional). The
export (export/actors_export.py) writes custom_assets/jak1/models/custom_levels/<name>.glb and a
(build-actor "<name>") line in game.gp; a level that places it (an ACTOR_<name>_ empty) gets it in
its custom_models and its <name>-ag.go in the .gd. Templates: Art group (no code: the game's
viewer process shows it playing its first animation), Basic actor (generated code), Camera
animation (a 'camera' bone: pickable in the pov-camera choices, pov.py; a level that plays it
loads it like a placed one).

OpenGOAL v0.3.6+ binds each vertex to the bone before its own (PR #4371): the export counters it
on the exported file (Bone index fix, Build Settings).
"""
from __future__ import annotations

import re

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty,
                       PointerProperty, StringProperty)

ROOT_COL = "Custom Actors"
MAX_BONES = 100
TEMPLATES = [("art_group", "Art group", "Only the art group (model, skeleton, animations): no code. In a level "
                                        "it plays its first animation"),
             ("basic", "Basic actor", "An actor with code: plays its idle animation, an animation when triggered, "
                                      "collision from the Collision meshes or a sphere"),
             ("camera", "Camera animation", "A camera art group: a bone named 'camera' (its animations are the "
                                            "shots). Played by a Camera animation actor or an actor's camera choice")]
CAM_BONE = "camera"
FOV_K = 14.941477 / 20.3          # the game's FOV from the camera joint's x scale: 2 atan(FOV_K / sx)
ORIGINS = [("MODEL", "Model's position", "The model mesh's origin (the first mesh of the Model collection)"),
           ("ARMATURE", "Armature's position", "The armature's origin"),
           ("CENTER", "Collection's center of mass", "The middle of all the model's vertices"),
           ("WORLD", "Blender origin", "The scene's origin (0, 0, 0)")]
COLLISIONS = [("none", "None", "Jak goes through it"),
              ("mesh", "Collision meshes", "The meshes of its Collision collection (255 vertices each at most)"),
              ("sphere", "Sphere", "A sphere around the actor")]
BONE_FIX = [("AUTO", "Auto", "On, except on OpenGOAL releases older than 0.3.6 (which don't have the problem)"),
            ("ON", "Always", "Always counter the bone shift"),
            ("OFF", "Never", "Never (an OpenGOAL with the upstream fix)")]


def clean(s):
    return re.sub(r"[^a-z0-9-]+", "-", s.strip().lower()).strip("-")


def _armature_poll(self, ob):
    return ob.type == "ARMATURE"


class OGCustomActorAnim(bpy.types.PropertyGroup):
    action: PointerProperty(type=bpy.types.Action, name="Action")
    include: BoolProperty(name="Export", default=True)


def _anim_items(self, ctx):
    out = [("NONE", "None", "Nothing happens on 'trigger")]
    out += [(x.action.name, x.action.name, "Played once on 'trigger, then back to the idle")
            for x in self.anims if x.include and x.action]
    _ANIM_ITEMS[:] = [(a, b, c, i) for i, (a, b, c) in enumerate(out)]
    return _ANIM_ITEMS


_ANIM_ITEMS: list = []


class OGCustomActor(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="", description="The art group is <name>-ag; placed actors are etype <name>")
    template: EnumProperty(name="Template", items=TEMPLATES, default="art_group")
    collection: PointerProperty(type=bpy.types.Collection, name="Collection")
    armature: PointerProperty(type=bpy.types.Object, name="Armature", poll=_armature_poll,
                              description="The skeleton (none: one fixed joint)")
    anims: CollectionProperty(type=OGCustomActorAnim)
    anim_index: IntProperty()
    origin: EnumProperty(name="Export origin", items=ORIGINS, default="MODEL",
                         description="The point of the model that is the actor's position in game")
    bounds_auto: BoolProperty(name="Auto", default=True, description="From the model's size")
    bounds: FloatProperty(name="Bounds (m)", default=5.0, min=0.1, unit="LENGTH",
                          description="Radius of the sphere around the actor: too small and it disappears early")
    # Basic actor
    collision: EnumProperty(name="Collision", items=COLLISIONS, default="none")
    sphere_radius: FloatProperty(name="Radius (m)", default=1.0, min=0.05, unit="LENGTH")
    sphere_height: FloatProperty(name="Height (m)", default=1.0, unit="LENGTH", description="Height of the sphere's centre")
    rideable: BoolProperty(name="Jak can ride it", default=True,
                           description="Jak moves with it when standing on it (when it moves)")
    coll_joints: StringProperty(default="", options={"HIDDEN"},
                                description="Written by the export: each collision mesh's joint, in build-actor's order")
    trigger_anim: EnumProperty(name="On 'trigger", items=_anim_items,
                               description="Animation played once when another actor sends it 'trigger "
                                           "(a button's notify list ...), then back to the idle")


class OGCustomActorSettings(bpy.types.PropertyGroup):
    bone_fix: EnumProperty(name="Bone index fix", items=BONE_FIX, default="AUTO",
                           description="OpenGOAL 0.3.6+ binds each vertex to the bone before its own: the export "
                                       "adds an end joint and shifts the bone indices by one to counter it")


# ── collections / objects ──────────────────────────────────────────────────

def root_collection(scene, create=False):
    c = bpy.data.collections.get(ROOT_COL)
    if c is None and create:
        c = bpy.data.collections.new(ROOT_COL)
        c["skip_export"] = True
        scene.collection.children.link(c)
    return c


def sub(a, kind, create=False):
    """The actor's Model / Collision collection."""
    if a.collection is None:
        return None
    name = f"{a.collection.name}.{kind}"
    c = next((x for x in a.collection.children if x.name == name), None)
    if c is None and create:
        c = bpy.data.collections.new(name)
        a.collection.children.link(c)
    return c


def model_objects(a):
    c = sub(a, "Model")
    return list(c.all_objects) if c is not None else []


def collision_objects(a):
    c = sub(a, "Collision")
    return [o for o in c.all_objects if o.type == "MESH"] if c is not None else []


def collision_bone(o):
    """The armature bone a collision mesh follows ('' = the whole actor)."""
    b = getattr(o, "og_ca_bone", "")
    if b:
        return b
    if o.parent_type == "BONE" and o.parent_bone:
        return o.parent_bone
    return ""


def compatible_actions(arm):
    """Actions animating this armature's bones (by their bone names)."""
    if arm is None:
        return []
    bones = {b.name for b in arm.data.bones}
    out = []
    for act in bpy.data.actions:
        paths = [fc.data_path for fc in getattr(act, "fcurves", ())]
        if any(p.startswith('pose.bones["') and p.split('"')[1] in bones for p in paths):
            out.append(act)
    return out


def sync_anims(a):
    """Add the armature's new actions to the list (kept in their order), drop missing ones."""
    acts = compatible_actions(a.armature)
    for i in range(len(a.anims) - 1, -1, -1):
        if a.anims[i].action not in acts:
            a.anims.remove(i)
    have = {x.action for x in a.anims}
    for act in acts:
        if act not in have:
            a.anims.add().action = act


def fov_to_scale(deg):
    import math
    return FOV_K / math.tan(math.radians(max(1.0, min(170.0, deg))) / 2)


def scale_to_fov(sx):
    import math
    return math.degrees(2 * math.atan(FOV_K / max(1e-4, sx)))


def camera_bone(a):
    """The armature's pose bone named 'camera' (Camera animation template), or None."""
    arm = a.armature
    return arm.pose.bones.get(CAM_BONE) if arm is not None and arm.pose else None


def _meshes(a):
    return sorted((o for o in model_objects(a) if o.type == "MESH"), key=lambda o: o.name)


def origin_point(a):
    """World point that becomes the actor's position (Export origin)."""
    from mathutils import Vector
    meshes = _meshes(a)
    if a.origin == "ARMATURE" and a.armature is not None:
        return a.armature.matrix_world.translation.copy()
    if a.origin == "CENTER" and meshes:
        s, n = Vector(), 0
        for o in meshes:
            for v in o.data.vertices:
                s += o.matrix_world @ v.co
                n += 1
        return s / max(1, n)
    if a.origin in ("MODEL", "ARMATURE") and meshes:
        return meshes[0].matrix_world.translation.copy()
    if a.origin != "WORLD" and a.armature is not None:          # no mesh (a camera): the armature
        return a.armature.matrix_world.translation.copy()
    return Vector()


def auto_bounds(a):
    """Radius (m) of a sphere at the actor's origin holding every model vertex."""
    from mathutils import Vector
    p = origin_point(a)
    r = 0.0
    for o in model_objects(a):
        if o.type == "MESH":
            for c in o.bound_box:
                r = max(r, (o.matrix_world @ Vector(c) - p).length)
    return round(r * 1.1 + 0.5, 1)


def bounds(a):
    return auto_bounds(a) if a.bounds_auto else a.bounds


# ── checks ─────────────────────────────────────────────────────────────────

def bone_fix_on(scene) -> bool:
    mode = scene.og_ca_settings.bone_fix
    if mode != "AUTO":
        return mode == "ON"
    from .versions import game_info
    g = game_info()
    v = g.get("version")
    if g.get("kind") == "release" and v:
        try:
            return tuple(int(x) for x in v.split(".")[:3]) >= (0, 3, 6)
        except ValueError:
            return True
    return True                                   # mod-base / dev build / unknown: assume a recent OpenGOAL


def checks(scene, a):
    """[(text, red)] for the actor."""
    out = []
    if not clean(a.name):
        out.append(("needs a name", True))
    meshes = [o for o in model_objects(a) if o.type == "MESH"]
    arm = a.armature
    if a.template == "camera":
        if arm is None or CAM_BONE not in arm.data.bones:
            out.append(("needs an armature with a bone named 'camera' (Make Camera Rig)", True))
        elif arm.data.bones[CAM_BONE].parent is None:
            out.append(("the 'camera' bone needs a parent bone: the game reads no FOV on the first one "
                        "(Repair Camera Rig)", True))
        elif not [x for x in a.anims if x.include]:
            out.append(("no animation: each exported action is a camera shot", True))
    elif not meshes:
        out.append(("no mesh in its Model collection", True))
    if arm is not None:
        n = len(arm.data.bones)
        if n > MAX_BONES:
            out.append((f"{n} bones: the game allows about {MAX_BONES}", True))
        skinned = [o for o in meshes if any(m.type == "ARMATURE" and m.object == arm for m in o.modifiers)]
        if len(skinned) < len(meshes):
            out.append((f"{len(meshes) - len(skinned)} mesh(es) not skinned to the armature (Armature modifier)", True))
        if len(skinned) > 1 and bone_fix_on(scene):
            out.append((f"{len(skinned)} skinned meshes: OpenGOAL 0.3.6+ places only one of them right "
                        "(upstream bug; an older OpenGOAL works)", False))
        many = unweighted = 0
        for o in skinned:
            names = {g.index: g.name for g in o.vertex_groups}
            bones = set(arm.data.bones.keys())
            for v in o.data.vertices:
                w = [g for g in v.groups if g.weight > 0 and names.get(g.group) in bones]
                if not w:
                    unweighted += 1
                elif len(w) > 3:
                    many += 1
        if unweighted:
            out.append((f"{unweighted} vertex(es) without a bone weight", True))
        if many:
            out.append((f"{many} vertex(es) with more than 3 bone weights (the game keeps 3)", False))
        for o in [arm] + meshes:
            ad = o.animation_data
            if ad and ad.action and any(not fc.data_path.startswith("pose.") for fc in ad.action.fcurves):
                out.append((f"'{o.name}' itself is animated: only bones may be (the build crashes)", True))
                break
        if not [x for x in a.anims if x.include] and a.template != "camera":
            out.append(("no animation: it gets a still idle", False))
    if meshes and not any(o.data.color_attributes for o in meshes) and not _has_textures(meshes):
        out.append(("no colour attribute or texture: material colours are ignored (white)", False))
    if a.template == "basic" and a.collision == "mesh" and not collision_objects(a):
        out.append(("Collision meshes: its Collision collection has no mesh", True))
    for o in collision_objects(a):
        b = collision_bone(o)
        if b and (arm is None or b not in arm.data.bones):
            out.append((f"collision '{o.name}' follows bone '{b}', which the armature doesn't have", True))
        if _inward(o):
            out.append((f"collision '{o.name}': most faces point inward (Jak goes through): "
                        "Mesh > Normals > Recalculate Outside", False))
        if len(o.data.loops) > 255:
            out.append((f"collision '{o.name}' may have more than 255 vertices once exported", True))
    return out


def _inward(o):
    """Most faces point toward the mesh's centre (collision is one-sided)."""
    me = o.data
    if not me.polygons:
        return False
    from mathutils import Vector
    c = sum((v.co for v in me.vertices), Vector()) / len(me.vertices)
    inward = sum(1 for f in me.polygons if f.normal.dot(f.center - c) < 0)
    return inward > len(me.polygons) / 2


def _has_textures(meshes):
    for o in meshes:
        for m in o.data.materials:
            if m and m.use_nodes and any(n.type == "TEX_IMAGE" and n.image for n in m.node_tree.nodes):
                return True
    return False


# ── operators ──────────────────────────────────────────────────────────────

def _unique(scene, base):
    names = {x.name for x in scene.og_custom_actors}
    return base if base not in names else next(f"{base}-{k}" for k in range(2, 999) if f"{base}-{k}" not in names)


class OG_OT_CaAdd(bpy.types.Operator):
    """Add a custom actor: its collection (Model, Collision) under Custom Actors"""
    bl_idname = "og.ca_add"
    bl_label = "Add Custom Actor"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        sc = ctx.scene
        a = sc.og_custom_actors.add()
        a.name = _unique(sc, "my-actor")
        root = root_collection(sc, create=True)
        c = bpy.data.collections.new(a.name)
        c["skip_export"] = True
        root.children.link(c)
        a.collection = c
        sub(a, "Model", create=True)
        sub(a, "Collision", create=True)
        sc.og_custom_actor_index = len(sc.og_custom_actors) - 1
        return {"FINISHED"}


class OG_OT_CaRemove(bpy.types.Operator):
    """Remove the active custom actor from the list (its collection and objects stay)"""
    bl_idname = "og.ca_remove"
    bl_label = "Remove Custom Actor"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        sc = ctx.scene
        i = sc.og_custom_actor_index
        if 0 <= i < len(sc.og_custom_actors):
            sc.og_custom_actors.remove(i)
            sc.og_custom_actor_index = max(0, i - 1)
        return {"FINISHED"}


class OG_OT_CaSyncAnims(bpy.types.Operator):
    """List the armature's actions (new ones added at the end, deleted ones removed)"""
    bl_idname = "og.ca_sync_anims"
    bl_label = "Refresh Animations"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        a = active(ctx.scene)
        if a is None:
            return {"CANCELLED"}
        sync_anims(a)
        return {"FINISHED"}


class OG_OT_CaMoveAnim(bpy.types.Operator):
    """Move the animation up / down (the first exported one is the idle)"""
    bl_idname = "og.ca_move_anim"
    bl_label = "Move Animation"
    bl_options = {"REGISTER", "UNDO"}
    up: BoolProperty()

    def execute(self, ctx):
        a = active(ctx.scene)
        if a is None:
            return {"CANCELLED"}
        i = a.anim_index
        j = i - 1 if self.up else i + 1
        if 0 <= j < len(a.anims):
            a.anims.move(i, j)
            a.anim_index = j
        return {"FINISHED"}


class OG_OT_CaExport(bpy.types.Operator):
    """Write the custom actor's model file and its build line (all of them: every exported actor)"""
    bl_idname = "og.ca_export"
    bl_label = "Export"
    bl_options = {"REGISTER"}
    all: BoolProperty()

    def execute(self, ctx):
        from .export.actors_export import export_actor
        sc = ctx.scene
        acts = list(sc.og_custom_actors) if self.all else [active(sc)]
        done, errs = 0, []
        for a in acts:
            if a is None:
                continue
            e = export_actor(sc, a)
            if e:
                errs.append(f"{a.name}: {e}")
            else:
                done += 1
        if errs:
            self.report({"ERROR"}, "; ".join(errs[:3]))
            return {"CANCELLED"} if not done else {"FINISHED"}
        self.report({"INFO"}, f"{done} custom actor(s) exported (build the level to compile them)")
        return {"FINISHED"}


class OG_OT_CaPlace(bpy.types.Operator):
    """Place this custom actor in the active level at the 3D cursor"""
    bl_idname = "og.ca_place"
    bl_label = "Place in Level"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        a = active(ctx.scene)
        from .collections import _active_level_col
        if a is None or not clean(a.name) or _active_level_col(ctx.scene) is None:
            self.report({"ERROR"}, "Needs a named custom actor and a level")
            return {"CANCELLED"}
        from .operators.spawn import make_actor
        from .collections import select_only
        o = make_actor(ctx, clean(a.name), ctx.scene.cursor.location, preview=False)
        select_only(o, ctx)
        return {"FINISHED"}


class OG_OT_CaCameraRig(bpy.types.Operator):
    """Make the camera rig: an armature with a 'camera' bone (animate it) and a Blender camera that
    follows the bone, its FOV from the bone's X scale, to look through it"""
    bl_idname = "og.ca_camera_rig"
    bl_label = "Make Camera Rig"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        a = active(ctx.scene)
        if a is None or a.collection is None:
            return {"CANCELLED"}
        n = clean(a.name) or "camera"
        model = sub(a, "Model", create=True)
        arm = a.armature
        if arm is None:
            arm = bpy.data.objects.new(f"{n}-rig", bpy.data.armatures.new(f"{n}-rig"))
            model.objects.link(arm)
            arm.location = ctx.scene.cursor.location
            a.armature = arm
        cb = arm.data.bones.get(CAM_BONE)
        if cb is None or cb.parent is None:
            vl = ctx.view_layer
            prev = vl.objects.active
            if prev is not None and prev.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            vl.objects.active = arm
            bpy.ops.object.mode_set(mode="EDIT")
            eb = arm.data.edit_bones
            b = eb.get(CAM_BONE)
            if b is None:
                b = eb.new(CAM_BONE)
                b.head = (0, 0, 0)
                b.tail = (0, 0, 0.5)     # pointing up: the view (the bone's -Z) looks along +Y, up +Z
            if b.parent is None:
                # the game's first bone is a matrix joint, whose scale (the FOV) it never reads:
                # the camera goes under a still root bone (rest = no turn, so the shots don't move)
                r = eb.get("root") or eb.new("root")
                r.head, r.tail, r.roll = (0, 0, 0), (0, 0.25, 0), 0.0
                b.parent = r
            bpy.ops.object.mode_set(mode="OBJECT")
            vl.objects.active = prev if prev is not None else arm
        cam = view_camera(a)
        if cam is None:
            cc = sub(a, "Camera", create=True)
            cam = bpy.data.objects.new(f"{n}-view", bpy.data.cameras.new(f"{n}-view"))
            cc.objects.link(cam)
        for kind in ("COPY_LOCATION", "COPY_ROTATION"):
            c = next((c for c in cam.constraints if c.type == kind), None) or cam.constraints.new(kind)
            c.target, c.subtarget = arm, CAM_BONE
        cam.data.sensor_fit = "HORIZONTAL"
        cam.data.lens_unit = "FOV"
        cam.data.driver_remove("lens")
        d = cam.data.driver_add("lens").driver           # FOV 2 atan(FOV_K / sx) as a focal length
        d.type = "SCRIPTED"
        v = d.variables.new()
        v.name, v.type = "sx", "TRANSFORMS"
        v.targets[0].id = arm
        v.targets[0].bone_target = CAM_BONE
        v.targets[0].transform_type = "SCALE_X"
        v.targets[0].transform_space = "LOCAL_SPACE"
        d.expression = f"sensor / 2 * max(sx, 0.0001) / {FOV_K:.6f}"
        v = d.variables.new()
        v.name, v.type = "sensor", "SINGLE_PROP"
        v.targets[0].id_type = "CAMERA"
        v.targets[0].id = cam.data
        v.targets[0].data_path = "sensor_width"
        sync_anims(a)
        return {"FINISHED"}


def view_camera(a):
    c = sub(a, "Camera")
    return next((o for o in c.all_objects if o.type == "CAMERA"), None) if c is not None else None


class OG_OT_CaCameraView(bpy.types.Operator):
    """Look through the rig's camera (the scene camera becomes it)"""
    bl_idname = "og.ca_camera_view"
    bl_label = "Look Through"
    bl_options = {"REGISTER"}

    def execute(self, ctx):
        a = active(ctx.scene)
        cam = view_camera(a) if a is not None else None
        if cam is None:
            self.report({"ERROR"}, "No rig camera: Make Camera Rig first")
            return {"CANCELLED"}
        ctx.scene.camera = cam
        for area in (ctx.screen.areas if ctx.screen else ()):
            if area.type == "VIEW_3D":
                area.spaces.active.region_3d.view_perspective = "CAMERA"
                break
        return {"FINISHED"}


class OG_OT_CaCameraFov(bpy.types.Operator):
    """Set the shot's field of view at this frame (the camera bone's X scale, which the game reads as the FOV)"""
    bl_idname = "og.ca_camera_fov"
    bl_label = "Set FOV"
    bl_options = {"REGISTER", "UNDO"}
    fov: FloatProperty(name="FOV (degrees)", default=72.7, min=10.6, max=170.0,
                       description="Horizontal field of view")
    key: BoolProperty(name="Insert keyframe", default=True)

    def invoke(self, ctx, event):
        a = active(ctx.scene)
        pb = camera_bone(a) if a is not None else None
        if pb is not None:
            self.fov = round(scale_to_fov(pb.scale.x), 1)
        return ctx.window_manager.invoke_props_dialog(self)

    def execute(self, ctx):
        a = active(ctx.scene)
        pb = camera_bone(a) if a is not None else None
        if pb is None:
            return {"CANCELLED"}
        pb.scale.x = fov_to_scale(self.fov)
        if self.key:
            pb.keyframe_insert("scale", index=0)
        return {"FINISHED"}


def active(scene):
    i = scene.og_custom_actor_index
    return scene.og_custom_actors[i] if 0 <= i < len(scene.og_custom_actors) else None


def actor_by_name(scene, name):
    return next((a for a in scene.og_custom_actors if clean(a.name) == name), None)


# ── panels (the OpenGOAL Actors tab) ───────────────────────────────────────

class OG_UL_CustomActors(bpy.types.UIList):
    def draw_item(self, ctx, layout, data, item, icon, active_data, active_propname):
        layout.prop(item, "name", text="", emboss=False, icon="ARMATURE_DATA" if item.armature else "MESH_CUBE")


class OG_UL_CaAnims(bpy.types.UIList):
    def draw_item(self, ctx, layout, data, item, icon, active_data, active_propname, index):
        r = layout.row(align=True)
        r.prop(item, "include", text="")
        r.label(text=(item.action.name if item.action else "?") + ("  (idle)" if index == _first_included(data) else ""),
                icon="ACTION")


def _first_included(a):
    return next((i for i, x in enumerate(a.anims) if x.include), -1)


class _Tab:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "OpenGOAL Actors"


class OG_PT_CaList(_Tab, bpy.types.Panel):
    bl_label = "Custom Actors"
    bl_idname = "OG_PT_ca_list"
    bl_order = 0

    def draw(self, ctx):
        sc = ctx.scene
        l = self.layout
        r = l.row()
        r.template_list("OG_UL_CustomActors", "", sc, "og_custom_actors", sc, "og_custom_actor_index", rows=3)
        c = r.column(align=True)
        c.operator("og.ca_add", text="", icon="ADD")
        c.operator("og.ca_remove", text="", icon="REMOVE")
        r = l.row(align=True)
        r.operator("og.ca_export", text="Export This", icon="EXPORT").all = False
        r.operator("og.ca_export", text="Export All").all = True


class OG_PT_CaSettings(_Tab, bpy.types.Panel):
    bl_label = "Settings"
    bl_idname = "OG_PT_ca_settings"
    bl_order = 1

    @classmethod
    def poll(cls, ctx):
        return active(ctx.scene) is not None

    def draw(self, ctx):
        a = active(ctx.scene)
        l = self.layout
        l.prop(a, "name")
        l.prop(a, "template")
        l.prop(a, "collection")
        l.prop(a, "armature")
        l.prop(a, "origin")
        r = l.row(align=True)
        r.prop(a, "bounds_auto", text="Auto bounds")
        sub_ = r.row(align=True); sub_.enabled = not a.bounds_auto
        sub_.prop(a, "bounds", text="Bounds")
        if a.bounds_auto:
            g = l.row(); g.enabled = False; g.scale_y = 0.7
            g.label(text=f"Bounds: {auto_bounds(a)} m (from the model)", icon="INFO")
        l.operator("og.ca_place", icon="EMPTY_ARROWS")
        for text, red in checks(ctx.scene, a):
            r = l.row()
            if red:
                r.alert = True
            else:
                r.enabled = False
            r.label(text=text, icon="ERROR" if red else "INFO")


class OG_PT_CaBasic(_Tab, bpy.types.Panel):
    bl_label = "Basic Actor"
    bl_idname = "OG_PT_ca_basic"
    bl_order = 2

    @classmethod
    def poll(cls, ctx):
        a = active(ctx.scene)
        return a is not None and a.template == "basic"

    def draw(self, ctx):
        a = active(ctx.scene)
        l = self.layout
        l.prop(a, "collision")
        if a.collision == "sphere":
            r = l.row(align=True); r.prop(a, "sphere_radius"); r.prop(a, "sphere_height")
        if a.collision != "none":
            l.prop(a, "rideable")
        if a.collision == "mesh":
            box = l.box()
            box.label(text="Collision meshes follow:")
            for o in collision_objects(a):
                r = box.row(align=True)
                r.label(text=o.name, icon="MESH_CUBE")
                if a.armature is not None:
                    r.prop_search(o, "og_ca_bone", a.armature.data, "bones", text="")
                else:
                    r.label(text="the actor")
            g = box.row(); g.enabled = False; g.scale_y = 0.7
            g.label(text="Empty: the whole actor; or parent the mesh to a bone", icon="INFO")
        if a.armature is not None:
            l.prop(a, "trigger_anim")
        g = l.column(); g.enabled = False; g.scale_y = 0.7
        g.label(text="Loops its idle (the first exported animation)", icon="INFO")
        if a.collision == "mesh":
            g.label(text="Collision meshes are invisible in game, the model's meshes have no collision", icon="BLANK1")


class OG_PT_CaCamera(_Tab, bpy.types.Panel):
    bl_label = "Camera Animation"
    bl_idname = "OG_PT_ca_camera"
    bl_order = 2

    @classmethod
    def poll(cls, ctx):
        a = active(ctx.scene)
        return a is not None and a.template == "camera"

    def draw(self, ctx):
        a = active(ctx.scene)
        l = self.layout
        pb = camera_bone(a)
        l.operator("og.ca_camera_rig", icon="OUTLINER_OB_CAMERA",
                   text="Make Camera Rig" if pb is None else "Repair Camera Rig")
        if pb is not None:
            r = l.row(align=True)
            r.operator("og.ca_camera_view", icon="HIDE_OFF")
            r.operator("og.ca_camera_fov", icon="KEYFRAME")
            g = l.row(); g.enabled = False; g.scale_y = 0.7
            g.label(text=f"FOV here: {scale_to_fov(pb.scale.x):.1f} degrees (bone X scale {pb.scale.x:.3f})", icon="INFO")
        g = l.column(); g.enabled = False; g.scale_y = 0.7
        g.label(text="Animate the 'camera' bone: each action is a shot", icon="INFO")
        g.label(text="The view looks down the bone's -Z (the rig camera shows it)", icon="BLANK1")
        g.label(text="Plays from the Camera animation actor's position: the armature's origin", icon="BLANK1")
        g.label(text=f"Pick '{clean(a.name)}' in a Camera animation's Camera list", icon="BLANK1")


class OG_PT_CaAnims(_Tab, bpy.types.Panel):
    bl_label = "Animations"
    bl_idname = "OG_PT_ca_anims"
    bl_order = 3

    @classmethod
    def poll(cls, ctx):
        a = active(ctx.scene)
        return a is not None and a.armature is not None

    def draw(self, ctx):
        a = active(ctx.scene)
        l = self.layout
        r = l.row()
        r.template_list("OG_UL_CaAnims", "", a, "anims", a, "anim_index", rows=3)
        c = r.column(align=True)
        c.operator("og.ca_sync_anims", text="", icon="FILE_REFRESH")
        c.operator("og.ca_move_anim", text="", icon="TRIA_UP").up = True
        c.operator("og.ca_move_anim", text="", icon="TRIA_DOWN").up = False
        g = l.column(); g.enabled = False; g.scale_y = 0.7
        g.label(text="Each action is an animation (60 frames a second in game)", icon="INFO")
        g.label(text="The first exported one is the idle (played when placed)", icon="BLANK1")


class OG_PT_CaBuild(_Tab, bpy.types.Panel):
    bl_label = "Build Settings"
    bl_idname = "OG_PT_ca_build"
    bl_order = 4
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        sc = ctx.scene
        l = self.layout
        l.prop(sc.og_ca_settings, "bone_fix")
        from .versions import game_label
        g = l.column(); g.enabled = False; g.scale_y = 0.7
        g.label(text=f"OpenGOAL: {game_label()}", icon="INFO")
        g.label(text="Bone index fix: " + ("on" if bone_fix_on(sc) else "off"), icon="BLANK1")


CLASSES = (OGCustomActorAnim, OGCustomActor, OGCustomActorSettings, OG_OT_CaAdd, OG_OT_CaRemove, OG_OT_CaSyncAnims,
           OG_OT_CaMoveAnim, OG_OT_CaExport, OG_OT_CaPlace, OG_OT_CaCameraRig, OG_OT_CaCameraView,
           OG_OT_CaCameraFov, OG_UL_CustomActors, OG_UL_CaAnims, OG_PT_CaList, OG_PT_CaSettings, OG_PT_CaBasic,
           OG_PT_CaCamera, OG_PT_CaAnims, OG_PT_CaBuild)


def register_props():
    bpy.types.Object.og_ca_bone = StringProperty(
        name="Bone", default="",
        description="Custom actor collision mesh: the bone it moves with (empty: the whole actor)")
    bpy.types.Scene.og_custom_actors = CollectionProperty(type=OGCustomActor)
    bpy.types.Scene.og_custom_actor_index = IntProperty()
    bpy.types.Scene.og_ca_settings = PointerProperty(type=OGCustomActorSettings)


def unregister_props():
    if hasattr(bpy.types.Object, "og_ca_bone"):
        del bpy.types.Object.og_ca_bone
    for p in ("og_custom_actors", "og_custom_actor_index", "og_ca_settings"):
        if hasattr(bpy.types.Scene, p):
            delattr(bpy.types.Scene, p)
