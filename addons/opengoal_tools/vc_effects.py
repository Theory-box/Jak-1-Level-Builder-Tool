# ---------------------------------------------------------------------------
# vc_effects.py — OpenGOAL Level Tools
# Vertex colour effects on the bake layers (BakedLight + the time of day
# layers), Object Controls > Vertex Colors:
#   - Apply Effect: one effect (scene settings) applied now to the selected meshes.
#   - Effects After Bake: an effect stack per object (like modifiers), applied
#     in order after a bake when Light Baking > Apply effects is on. Add Effect
#     adds to every selected mesh; the panel shows the active one's. A new
#     effect starts with the last used options of its kind: the Apply Effect
#     settings, which editing a stack effect also updates (curve: a copy of the
#     last curve added / set up, scene og_vc_last_curve).
# Effects: Curve Correction (an RGB curve, the bake curve's presets),
# Overwrite Color (moves each colour's hue / saturation / value toward the
# picked colour's, a factor each), Overwrite Alpha, Blur (the auto blur).
# Curve and Alpha have a Factor. Values are the stored sRGB ones.
# Vertex Group (every effect, optional): only that group's vertices change, by
# their weight (0.0 - 1.0); a mesh without the group isn't changed.
# ---------------------------------------------------------------------------
from __future__ import annotations

import numpy as np
import bpy
from bpy.props import (BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty,
                       PointerProperty, CollectionProperty, StringProperty)

KINDS = (("CURVE", "Curve Correction", "Remap the colours with a curve", "FCURVE"),
         ("COLOR", "Overwrite Color", "Move every colour's hue / saturation / value toward this colour's", "COLOR"),
         ("ALPHA", "Overwrite Alpha", "Set the alpha of every colour", "IMAGE_ALPHA"),
         ("BLUR", "Blur", "Average neighbouring colours", "MOD_SMOOTH"))
_LABEL = {k: l for k, l, _d, _i in KINDS}
_ICON = {k: i for k, _l, _d, i in KINDS}
_SCENE_CURVE = "OG Effect Curve"


def _curve_preset_items(self, ctx):
    from .bake import _preset_items
    return _preset_items(self, ctx)


_REMEMBER = {"CURVE": ("factor", "curve_preset"), "COLOR": ("color", "hue_factor", "sat_factor", "val_factor"),
             "ALPHA": ("alpha", "factor"),
             "BLUR": ("blur_strength", "blur_passes", "blur_keep_sharp", "blur_auto_sharp", "blur_angle")}
_REMEMBERING = []


def _remember(self, ctx):
    """A stack effect edited: its options become the last used ones of its
    kind (the Apply Effect settings, which new effects copy)."""
    if _REMEMBERING or not isinstance(self.id_data, bpy.types.Object) or ctx.scene is None:
        return
    dst = getattr(ctx.scene, "og_fx_" + self.kind.lower(), None)
    if dst is None:
        return
    _REMEMBERING.append(1)
    try:
        for p in _REMEMBER.get(self.kind, ()):
            setattr(dst, p, getattr(self, p))
    finally:
        _REMEMBERING.pop()


def _curve_preset_update(self, ctx):
    from .bake import _apply_preset
    if self.curve is not None and not _REMEMBERING:
        _apply_preset(self.curve, self.curve_preset)
        if ctx.scene is not None:
            ctx.scene.og_vc_last_curve = self.curve
    _remember(self, ctx)


class OGVcEffect(bpy.types.PropertyGroup):
    kind: EnumProperty(name="Effect", items=[(k, l, d) for k, l, d, _i in KINDS], default="CURVE")
    enabled: BoolProperty(name="On", default=True, description="Apply this effect after a bake")
    show: BoolProperty(name="Show", default=True)
    factor: FloatProperty(name="Factor", default=1.0, min=0.0, max=1.0, subtype="FACTOR",
                          description="How much the effect changes the colours", update=_remember)
    curve: PointerProperty(type=bpy.types.NodeTree, name="Curve")
    curve_preset: EnumProperty(name="Preset", items=_curve_preset_items, update=_curve_preset_update)
    color: FloatVectorProperty(name="Color", subtype="COLOR", size=3, min=0.0, max=1.0, default=(1.0, 0.5, 0.2),
                               update=_remember)
    hue_factor: FloatProperty(name="Hue Factor", default=1.0, min=0.0, max=1.0, subtype="FACTOR",
                              description="How much each colour's hue moves to the colour's hue", update=_remember)
    sat_factor: FloatProperty(name="Saturation Factor", default=1.0, min=0.0, max=1.0, subtype="FACTOR",
                              description="How much each colour's saturation moves to the colour's saturation",
                              update=_remember)
    val_factor: FloatProperty(name="Value Factor", default=0.0, min=0.0, max=1.0, subtype="FACTOR",
                              description="How much each colour's value (brightness) moves to the colour's value",
                              update=_remember)
    alpha: FloatProperty(name="Alpha", default=1.0, min=0.0, max=1.0, subtype="FACTOR", update=_remember)
    blur_strength: FloatProperty(name="Strength", default=0.5, min=0.0, max=1.0, subtype="FACTOR", update=_remember)
    blur_passes: IntProperty(name="Passes", default=2, min=1, max=50, update=_remember)
    blur_keep_sharp: BoolProperty(name="Keep sharp edges", default=True, update=_remember,
                                  description="Don't mix across the mesh's sharp edges (marked sharp, or flat-shaded faces)")
    blur_auto_sharp: BoolProperty(name="Auto sharp", default=False, update=_remember,
                                  description="Also treat edges sharper than the angle as sharp")
    blur_angle: FloatProperty(name="Angle", default=0.5236, min=0.0, max=3.1416, subtype="ANGLE", update=_remember)
    vertex_group: StringProperty(name="Vertex Group",
                                 description="Only this vertex group changes, by each vertex's weight (0.0 - 1.0). "
                                             "Empty: the whole mesh. A mesh without this group isn't changed")


# ── the effects ─────────────────────────────────────────────────────────────

def rgb_to_hsv(rgb):
    """(n, 3) -> h, s, v arrays (h in 0-1; 0 for greys)."""
    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    v = rgb.max(1); mn = rgb.min(1); d = v - mn
    s = np.where(v > 0, d / np.maximum(v, 1e-8), 0.0)
    dd = np.maximum(d, 1e-8)
    h = np.where(v == r, ((g - b) / dd) % 6, np.where(v == g, (b - r) / dd + 2, (r - g) / dd + 4))
    return np.where(d > 0, h / 6.0, 0.0), s, v


def hsv_to_rgb(h, s, v):
    h6 = (h % 1.0) * 6.0
    i = np.floor(h6).astype(np.int64) % 6
    f = h6 - np.floor(h6)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    r = np.choose(i, [v, q, p, p, t, v]); g = np.choose(i, [t, v, v, q, p, p]); b = np.choose(i, [p, p, t, v, v, q])
    return np.stack([r, g, b], 1)


def overwrite_color(cols, color, hf, sf, vf):
    """Each colour's hue / saturation / value moved toward the colour's (a
    factor each; hue the short way round; a grey's hue is the target's)."""
    h, s, v = rgb_to_hsv(cols[:, :3])
    th, ts, tv = (x[0] for x in rgb_to_hsv(np.array([color], np.float32)))
    h = np.where(s > 0, h, th)
    dh = (th - h + 0.5) % 1.0 - 0.5
    cols[:, :3] = hsv_to_rgb(h + dh * hf, s + (ts - s) * sf, v + (tv - v) * vf)
    return cols


def curve_mapping(ng):
    node = next((n for n in ng.nodes if n.bl_idname == "ShaderNodeRGBCurve"), None) if ng else None
    return node.mapping if node else None


def new_curve(name, preset="JAK"):
    from .bake import _apply_preset
    ng = bpy.data.node_groups.new(name, "ShaderNodeTree")
    ng.use_fake_user = True
    ng.nodes.new("ShaderNodeRGBCurve")
    if preset != "CUSTOM":
        _apply_preset(ng, preset)
    return ng


def group_weights(obj, name):
    """Per vertex weight of the vertex group (0 outside it); None: no such group."""
    vg = obj.vertex_groups.get(name)
    if vg is None:
        return None
    gi = vg.index
    w = np.zeros(len(obj.data.vertices), np.float32)
    for v in obj.data.vertices:
        for g in v.groups:
            if g.group == gi:
                w[v.index] = g.weight
                break
    return w


def apply_effect(obj, fx, layers=None, kind=None):
    """One effect (fx's kind, or `kind` for the Apply Effect settings) on the
    bake layers of obj. Returns how many layers changed."""
    kind = kind or fx.kind
    from .bake import LIGHT_LAYERS, _read, _write, curve_luts, apply_curve, blur, sharp_arrays, loop_verts
    mesh = obj.data
    w, wd = None, {}                            # Vertex Group weights (per vertex, per domain)
    if fx.vertex_group:
        w = group_weights(obj, fx.vertex_group)
        if w is None or not w.any():
            return 0
    luts = None
    if kind == "CURVE":
        m = curve_mapping(fx.curve)
        if m is None:
            return 0
        luts = curve_luts(m)
    sf = None
    n = 0
    for name in layers or LIGHT_LAYERS:
        a = mesh.color_attributes.get(name)
        if a is None:
            continue
        cols, key = _read(a)
        if w is not None:
            orig = cols.copy()
            if a.domain not in wd:
                if a.domain == "CORNER":
                    lv = loop_verts(mesh)
                    wd[a.domain] = w[lv][:, None]
                else:
                    wd[a.domain] = w[:, None]
        if kind == "CURVE":
            cols = apply_curve(cols, luts[0], luts[1], fx.factor)
        elif kind == "COLOR":
            cols = overwrite_color(cols, tuple(fx.color), fx.hue_factor, fx.sat_factor, fx.val_factor)
        elif kind == "ALPHA":
            cols[:, 3] += (fx.alpha - cols[:, 3]) * fx.factor
        elif kind == "BLUR":
            if fx.blur_strength <= 0:
                continue
            if sf is None and fx.blur_keep_sharp:
                sf = sharp_arrays(obj)
            cols = blur(mesh, cols, a.domain, fx.blur_strength, fx.blur_passes, fx.blur_keep_sharp,
                        fx.blur_angle if fx.blur_auto_sharp else None, sf)
        if w is not None:
            cols = orig + (cols - orig) * wd[a.domain]
        _write(a, np.clip(cols, 0.0, 1.0), key)
        n += 1
    if n:
        mesh.update()
    return n


def apply_stack(obj):
    """The object's effects (on ones, in order). Returns how many ran."""
    ran = 0
    for fx in getattr(obj, "og_vc_effects", ()):
        if fx.enabled and apply_effect(obj, fx):
            ran += 1
    return ran


def _targets(ctx):
    seen, out = set(), []
    for o in ctx.selected_objects:
        if o.type == "MESH" and not o.data.library and o.data.name not in seen:
            seen.add(o.data.name); out.append(o)
    return out


def scene_effect(scene, kind):
    return getattr(scene, "og_fx_" + kind.lower())


# ── operators ───────────────────────────────────────────────────────────────

class OG_OT_VcApplyEffect(bpy.types.Operator):
    """Apply this effect now to BakedLight and every time of day layer of the selected meshes"""
    bl_idname = "og.vc_apply_effect"
    bl_label = "Apply Effect"
    bl_options = {"REGISTER", "UNDO"}
    kind: StringProperty(options={"SKIP_SAVE"})

    def execute(self, ctx):
        fx = scene_effect(ctx.scene, self.kind)
        objs = _targets(ctx)
        n = sum(apply_effect(o, fx, kind=self.kind) for o in objs)
        no_vg = sum(1 for o in objs if fx.vertex_group and fx.vertex_group not in o.vertex_groups)
        if no_vg:
            self.report({"WARNING"}, f"{no_vg} mesh(es) without vertex group '{fx.vertex_group}' not changed")
        if not n:
            self.report({"WARNING"}, "No baked layer on the selected meshes"
                        + (" (set up the curve first)" if self.kind == "CURVE" and fx.curve is None else ""))
            return {"CANCELLED"}
        self.report({"INFO"}, f"{_LABEL[self.kind]}: {n} layer(s) on {len(objs)} mesh(es)")
        return {"FINISHED"}


class OG_OT_VcCurveInit(bpy.types.Operator):
    """Create the curve of this effect (kept in a hidden node group)"""
    bl_idname = "og.vc_curve_init"
    bl_label = "Set Up Curve"
    bl_options = {"REGISTER", "UNDO"}
    index: IntProperty(default=-1, options={"SKIP_SAVE"})     # -1: the Apply Effect curve

    def execute(self, ctx):
        if self.index < 0:
            fx = ctx.scene.og_fx_curve
            fx.curve = bpy.data.node_groups.get(_SCENE_CURVE) or new_curve(_SCENE_CURVE, fx.curve_preset)
        else:
            o = ctx.view_layer.objects.active
            fx = o.og_vc_effects[self.index]
            fx.curve = new_curve(f"OG Effect Curve {o.name}", fx.curve_preset)
        ctx.scene.og_vc_last_curve = fx.curve
        return {"FINISHED"}


class OG_OT_VcAddEffect(bpy.types.Operator):
    """Add an effect to the Effects After Bake of every selected mesh, with the last used options of that effect"""
    bl_idname = "og.vc_add_effect"
    bl_label = "Add Effect"
    bl_options = {"REGISTER", "UNDO"}
    kind: EnumProperty(items=[(k, l, d, i, n) for n, (k, l, d, i) in enumerate(KINDS)])

    def execute(self, ctx):
        objs = [o for o in ctx.selected_objects if o.type == "MESH"]
        act = ctx.view_layer.objects.active
        if act is not None and act.type == "MESH" and act not in objs:
            objs.append(act)
        if not objs:
            return {"CANCELLED"}
        last = scene_effect(ctx.scene, self.kind)
        src_curve = ctx.scene.og_vc_last_curve or last.curve
        _REMEMBERING.append(1)                      # copying the last used: don't write them back
        try:
            for o in objs:
                fx = o.og_vc_effects.add()
                fx.kind = self.kind
                for p in _REMEMBER[self.kind]:
                    setattr(fx, p, getattr(last, p))
                if self.kind == "CURVE":
                    if src_curve is not None:
                        fx.curve = src_curve.copy()
                        fx.curve.name = f"OG Effect Curve {o.name}"
                    else:
                        fx.curve = new_curve(f"OG Effect Curve {o.name}", fx.curve_preset)
        finally:
            _REMEMBERING.pop()
        if self.kind == "CURVE":
            ctx.scene.og_vc_last_curve = (act if act in objs else objs[-1]).og_vc_effects[-1].curve
        self.report({"INFO"}, f"{_LABEL[self.kind]} added to {len(objs)} mesh(es)")
        return {"FINISHED"}


def _drop_curve(fx):
    ng = fx.curve
    fx.curve = None
    if ng is not None and ng.users <= 1 and ng.name.startswith("OG Effect Curve"):
        bpy.data.node_groups.remove(ng)


class OG_OT_VcEffectEdit(bpy.types.Operator):
    """Remove this effect, or move it up / down (effects run top to bottom)"""
    bl_idname = "og.vc_effect_edit"
    bl_label = "Edit Effect"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}
    index: IntProperty()
    action: StringProperty(default="REMOVE")       # REMOVE / UP / DOWN

    def execute(self, ctx):
        o = ctx.view_layer.objects.active
        fxs = o.og_vc_effects
        i = self.index
        if self.action == "REMOVE":
            _drop_curve(fxs[i])
            fxs.remove(i)
        elif self.action == "UP" and i > 0:
            fxs.move(i, i - 1)
        elif self.action == "DOWN" and i < len(fxs) - 1:
            fxs.move(i, i + 1)
        return {"FINISHED"}


_COPY_PROPS = ("kind", "enabled", "show", "factor", "curve_preset", "color", "hue_factor", "sat_factor",
               "val_factor", "alpha", "blur_strength", "vertex_group",
               "blur_passes", "blur_keep_sharp", "blur_auto_sharp", "blur_angle")


class OG_OT_VcCopyEffects(bpy.types.Operator):
    """Give the other selected meshes the active mesh's Effects After Bake (their own are replaced)"""
    bl_idname = "og.vc_copy_effects"
    bl_label = "Copy Effects to Selected"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        src = ctx.view_layer.objects.active
        others = [o for o in ctx.selected_objects if o.type == "MESH" and o != src]
        if src is None or not others:
            self.report({"WARNING"}, "Select other meshes and make the source active"); return {"CANCELLED"}
        for o in others:
            for fx in o.og_vc_effects:
                _drop_curve(fx)
            o.og_vc_effects.clear()
            for fx in src.og_vc_effects:
                n = o.og_vc_effects.add()
                for p in _COPY_PROPS:
                    setattr(n, p, getattr(fx, p))
                if fx.curve is not None:
                    n.curve = fx.curve.copy()
                    n.curve.name = f"OG Effect Curve {o.name}"
        self.report({"INFO"}, f"{len(src.og_vc_effects)} effect(s) copied to {len(others)} mesh(es)")
        return {"FINISHED"}


def _with_effects(ctx):
    """Selected meshes (and the active one) that have Effects After Bake."""
    objs = list(ctx.selected_objects)
    act = ctx.view_layer.objects.active
    if act is not None and act not in objs:
        objs.append(act)
    return [o for o in objs if o.type == "MESH" and len(o.og_vc_effects)]


class OG_OT_VcClearEffects(bpy.types.Operator):
    """Remove every Effects After Bake effect from the selected meshes"""
    bl_idname = "og.vc_clear_effects"
    bl_label = "Remove All Effects"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        objs = _with_effects(ctx)
        n = 0
        for o in objs:
            for fx in o.og_vc_effects:
                _drop_curve(fx)
            n += len(o.og_vc_effects)
            o.og_vc_effects.clear()
        self.report({"INFO"}, f"Removed {n} effect(s) from {len(objs)} mesh(es)")
        return {"FINISHED"}


class OG_OT_VcApplyStack(bpy.types.Operator):
    """Apply the Effects After Bake of the selected meshes now (as a bake with Apply effects would)"""
    bl_idname = "og.vc_apply_stack"
    bl_label = "Apply Effects Now"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        objs = _targets(ctx)
        n = sum(apply_stack(o) for o in objs)
        self.report({"INFO"} if n else {"WARNING"}, f"{n} effect(s) applied on {len(objs)} mesh(es)")
        return {"FINISHED"} if n else {"CANCELLED"}


# ── UI (drawn by panels/object_controls.py) ─────────────────────────────────

def draw_options(layout, fx, init_index, kind=None, obj=None):
    """An effect's options (not the kind)."""
    kind = kind or fx.kind
    if obj is not None and obj.type == "MESH":
        r = layout.row(align=True)
        r.prop_search(fx, "vertex_group", obj, "vertex_groups", text="", icon="GROUP_VERTEX")
        if fx.vertex_group and fx.vertex_group not in obj.vertex_groups:
            r.alert = True
    else:
        layout.prop(fx, "vertex_group", text="", icon="GROUP_VERTEX")
    if kind == "CURVE":
        r = layout.row(align=True)
        r.prop(fx, "curve_preset", text="")
        m = curve_mapping(fx.curve)
        if m is None:
            op = layout.operator("og.vc_curve_init", icon="FCURVE"); op.index = init_index
        else:
            node = next(n for n in fx.curve.nodes if n.bl_idname == "ShaderNodeRGBCurve")
            layout.template_curve_mapping(node, "mapping", type="COLOR")
    elif kind == "COLOR":
        layout.prop(fx, "color")
        col = layout.column(align=True)
        col.prop(fx, "hue_factor"); col.prop(fx, "sat_factor"); col.prop(fx, "val_factor")
    elif kind == "ALPHA":
        layout.prop(fx, "alpha")
    if kind == "COLOR":
        pass
    elif kind == "BLUR":
        r = layout.row(align=True)
        r.prop(fx, "blur_strength"); r.prop(fx, "blur_passes")
        layout.prop(fx, "blur_keep_sharp")
        if fx.blur_keep_sharp:
            r = layout.row(align=True)
            r.prop(fx, "blur_auto_sharp")
            sub = r.row(); sub.enabled = fx.blur_auto_sharp
            sub.prop(fx, "blur_angle")
    else:
        layout.prop(fx, "factor")


def draw_apply(layout, ctx, kind):
    fx = scene_effect(ctx.scene, kind)
    draw_options(layout, fx, -1, kind, ctx.view_layer.objects.active)
    n = len(_targets(ctx))
    op = layout.operator("og.vc_apply_effect", icon=_ICON[kind],
                         text=f"Apply {_LABEL[kind]} to {n} Mesh(es)" if n else f"Apply {_LABEL[kind]}")
    op.kind = kind


def draw_stack(layout, ctx):
    o = ctx.view_layer.objects.active
    if o is None or o.type != "MESH":
        layout.label(text="Make a mesh active", icon="INFO")
        return
    n = sum(1 for x in ctx.selected_objects if x.type == "MESH" and x != o) + 1
    layout.operator_menu_enum("og.vc_add_effect", "kind", icon="ADD",
                              text=f"Add Effect to {n} Mesh(es)" if n > 1 else "Add Effect")
    r = layout.row(); r.enabled = False; r.scale_y = 0.7
    r.label(text="Adds to every selected mesh; shown: the active one's", icon="INFO")
    from .collections import _active_level_col
    lv = _active_level_col(ctx.scene)
    if lv is not None and not lv.og_bake.apply_effects:
        box = layout.box(); box.alert = True
        box.label(text="Light Baking > Apply effects is off:", icon="ERROR")
        box.label(text="these effects won't run after a bake")
        box.prop(lv.og_bake, "apply_effects", text="Turn on Apply effects")
    layout.label(text=o.name, icon="MESH_DATA")
    fxs = o.og_vc_effects
    for i, fx in enumerate(fxs):
        box = layout.box()
        r = box.row(align=True)
        r.prop(fx, "show", text="", emboss=False, icon="TRIA_DOWN" if fx.show else "TRIA_RIGHT")
        r.prop(fx, "enabled", text="")
        r.label(text=_LABEL[fx.kind], icon=_ICON[fx.kind])
        for act, icon in (("UP", "TRIA_UP"), ("DOWN", "TRIA_DOWN"), ("REMOVE", "X")):
            op = r.operator("og.vc_effect_edit", text="", icon=icon, emboss=False)
            op.index = i; op.action = act
        if fx.show:
            col = box.column(); col.enabled = fx.enabled
            draw_options(col, fx, i, obj=o)
    if fxs:
        r = layout.row(align=True)
        r.operator("og.vc_copy_effects", icon="COPYDOWN")
        r.operator("og.vc_apply_stack", icon="CHECKMARK")
    k = sum(1 for x in _with_effects(ctx))
    if k:
        layout.operator("og.vc_clear_effects", icon="TRASH",
                        text=f"Remove All Effects from {k} Mesh(es)")
    r = layout.row(); r.enabled = False; r.scale_y = 0.7
    r.label(text="Run after a bake with Light Baking > Apply effects on", icon="INFO")


CLASSES = (OGVcEffect, OG_OT_VcApplyEffect, OG_OT_VcCurveInit, OG_OT_VcAddEffect, OG_OT_VcEffectEdit,
           OG_OT_VcCopyEffects, OG_OT_VcClearEffects, OG_OT_VcApplyStack)


def register_props():
    bpy.types.Object.og_vc_effects = CollectionProperty(type=OGVcEffect)
    bpy.types.Scene.og_vc_last_curve = PointerProperty(type=bpy.types.NodeTree)
    for k, *_r in KINDS:
        setattr(bpy.types.Scene, "og_fx_" + k.lower(), PointerProperty(type=OGVcEffect))


def unregister_props():
    for k, *_r in KINDS:
        if hasattr(bpy.types.Scene, "og_fx_" + k.lower()):
            delattr(bpy.types.Scene, "og_fx_" + k.lower())
    if hasattr(bpy.types.Scene, "og_vc_last_curve"):
        del bpy.types.Scene.og_vc_last_curve
    if hasattr(bpy.types.Object, "og_vc_effects"):
        del bpy.types.Object.og_vc_effects
