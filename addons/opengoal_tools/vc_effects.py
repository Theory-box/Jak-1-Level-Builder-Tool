# ---------------------------------------------------------------------------
# vc_effects.py — OpenGOAL Level Tools
# Vertex colour effects on the bake layers (BakedLight + the time of day
# layers), Object Controls > Vertex Colors:
#   - Apply Effect: one effect (scene settings) applied now to the selected meshes.
#   - Effects After Bake: an effect stack per object (like modifiers), applied
#     in order after a bake when Light Baking > Apply effects is on.
# Effects: Curve Correction (an RGB curve, the bake curve's presets),
# Overwrite Hue (keeps saturation / value), Overwrite Alpha, Blur (the auto
# blur). All but Blur have a Factor. Values are the stored sRGB ones.
# ---------------------------------------------------------------------------
from __future__ import annotations

import numpy as np
import bpy
from bpy.props import (BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty,
                       PointerProperty, CollectionProperty, StringProperty)

KINDS = (("CURVE", "Curve Correction", "Remap the colours with a curve", "FCURVE"),
         ("HUE", "Overwrite Hue", "Give every colour this hue (saturation and value stay)", "COLOR"),
         ("ALPHA", "Overwrite Alpha", "Set the alpha of every colour", "IMAGE_ALPHA"),
         ("BLUR", "Blur", "Average neighbouring colours", "MOD_SMOOTH"))
_LABEL = {k: l for k, l, _d, _i in KINDS}
_ICON = {k: i for k, _l, _d, i in KINDS}
_SCENE_CURVE = "OG Effect Curve"


def _curve_preset_items(self, ctx):
    from .bake import _preset_items
    return _preset_items(self, ctx)


def _curve_preset_update(self, ctx):
    from .bake import _apply_preset
    if self.curve is not None:
        _apply_preset(self.curve, self.curve_preset)


class OGVcEffect(bpy.types.PropertyGroup):
    kind: EnumProperty(name="Effect", items=[(k, l, d) for k, l, d, _i in KINDS], default="CURVE")
    enabled: BoolProperty(name="On", default=True, description="Apply this effect after a bake")
    show: BoolProperty(name="Show", default=True)
    factor: FloatProperty(name="Factor", default=1.0, min=0.0, max=1.0, subtype="FACTOR",
                          description="How much the effect changes the colours")
    curve: PointerProperty(type=bpy.types.NodeTree, name="Curve")
    curve_preset: EnumProperty(name="Preset", items=_curve_preset_items, update=_curve_preset_update)
    hue: FloatVectorProperty(name="Hue", subtype="COLOR", size=3, min=0.0, max=1.0, default=(1.0, 0.5, 0.2),
                             description="Its hue is used (not its saturation / value)")
    alpha: FloatProperty(name="Alpha", default=1.0, min=0.0, max=1.0, subtype="FACTOR")
    blur_strength: FloatProperty(name="Strength", default=0.5, min=0.0, max=1.0, subtype="FACTOR")
    blur_passes: IntProperty(name="Passes", default=2, min=1, max=50)
    blur_keep_sharp: BoolProperty(name="Keep sharp edges", default=True,
                                  description="Don't mix across the mesh's sharp edges (marked sharp, or flat-shaded faces)")
    blur_auto_sharp: BoolProperty(name="Auto sharp", default=False,
                                  description="Also treat edges sharper than the angle as sharp")
    blur_angle: FloatProperty(name="Angle", default=0.5236, min=0.0, max=3.1416, subtype="ANGLE")


# ── the effects ─────────────────────────────────────────────────────────────

def _hue_of(rgb):
    r, g, b = rgb
    mx, mn = max(rgb), min(rgb)
    if mx == mn:
        return None
    d = mx - mn
    h = ((g - b) / d) % 6 if mx == r else ((b - r) / d + 2 if mx == g else (r - g) / d + 4)
    return h / 6.0


def overwrite_hue(cols, hue, factor):
    rgb = cols[:, :3]
    v = rgb.max(1)
    s = np.where(v > 0, (v - rgb.min(1)) / np.maximum(v, 1e-8), 0.0)
    h6 = hue * 6.0
    i = int(h6) % 6
    f = h6 - int(h6)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    new = [np.stack(c, 1) for c in ((v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q))][i]
    cols[:, :3] = rgb + (new - rgb) * factor
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


def apply_effect(obj, fx, layers=None, kind=None):
    """One effect (fx's kind, or `kind` for the Apply Effect settings) on the
    bake layers of obj. Returns how many layers changed."""
    kind = kind or fx.kind
    from .bake import LIGHT_LAYERS, _read, _write, curve_luts, apply_curve, blur, sharp_arrays
    mesh = obj.data
    luts = None
    if kind == "CURVE":
        m = curve_mapping(fx.curve)
        if m is None:
            return 0
        luts = curve_luts(m)
    hue = _hue_of(tuple(fx.hue)) if kind == "HUE" else None
    if kind == "HUE" and hue is None:
        hue = 0.0                                   # a grey pick: red hue
    sf = None
    n = 0
    for name in layers or LIGHT_LAYERS:
        a = mesh.color_attributes.get(name)
        if a is None:
            continue
        cols, key = _read(a)
        if kind == "CURVE":
            cols = apply_curve(cols, luts[0], luts[1], fx.factor)
        elif kind == "HUE":
            cols = overwrite_hue(cols, hue, fx.factor)
        elif kind == "ALPHA":
            cols[:, 3] += (fx.alpha - cols[:, 3]) * fx.factor
        elif kind == "BLUR":
            if fx.blur_strength <= 0:
                continue
            if sf is None and fx.blur_keep_sharp:
                sf = sharp_arrays(obj)
            cols = blur(mesh, cols, a.domain, fx.blur_strength, fx.blur_passes, fx.blur_keep_sharp,
                        fx.blur_angle if fx.blur_auto_sharp else None, sf)
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
        return {"FINISHED"}


class OG_OT_VcAddEffect(bpy.types.Operator):
    """Add an effect to the active mesh's Effects After Bake"""
    bl_idname = "og.vc_add_effect"
    bl_label = "Add Effect"
    bl_options = {"REGISTER", "UNDO"}
    kind: EnumProperty(items=[(k, l, d, i, n) for n, (k, l, d, i) in enumerate(KINDS)])

    def execute(self, ctx):
        o = ctx.view_layer.objects.active
        if o is None or o.type != "MESH":
            return {"CANCELLED"}
        fx = o.og_vc_effects.add()
        fx.kind = self.kind
        if self.kind == "CURVE":
            fx.curve = new_curve(f"OG Effect Curve {o.name}", "JAK")
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


_COPY_PROPS = ("kind", "enabled", "show", "factor", "curve_preset", "hue", "alpha", "blur_strength",
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

def draw_options(layout, fx, init_index, kind=None):
    """An effect's options (not the kind)."""
    kind = kind or fx.kind
    if kind == "CURVE":
        r = layout.row(align=True)
        r.prop(fx, "curve_preset", text="")
        m = curve_mapping(fx.curve)
        if m is None:
            op = layout.operator("og.vc_curve_init", icon="FCURVE"); op.index = init_index
        else:
            node = next(n for n in fx.curve.nodes if n.bl_idname == "ShaderNodeRGBCurve")
            layout.template_curve_mapping(node, "mapping", type="COLOR")
    elif kind == "HUE":
        layout.prop(fx, "hue")
    elif kind == "ALPHA":
        layout.prop(fx, "alpha")
    if kind == "BLUR":
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
    draw_options(layout, fx, -1, kind)
    n = len(_targets(ctx))
    op = layout.operator("og.vc_apply_effect", icon=_ICON[kind],
                         text=f"Apply {_LABEL[kind]} to {n} Mesh(es)" if n else f"Apply {_LABEL[kind]}")
    op.kind = kind


def draw_stack(layout, ctx):
    o = ctx.view_layer.objects.active
    if o is None or o.type != "MESH":
        layout.label(text="Make a mesh active", icon="INFO")
        return
    layout.label(text=o.name, icon="MESH_DATA")
    layout.operator_menu_enum("og.vc_add_effect", "kind", text="Add Effect", icon="ADD")
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
            draw_options(col, fx, i)
    if fxs:
        r = layout.row(align=True)
        r.operator("og.vc_copy_effects", icon="COPYDOWN")
        r.operator("og.vc_apply_stack", icon="CHECKMARK")
    r = layout.row(); r.enabled = False; r.scale_y = 0.7
    r.label(text="Run after a bake with Light Baking > Apply effects on", icon="INFO")


CLASSES = (OGVcEffect, OG_OT_VcApplyEffect, OG_OT_VcCurveInit, OG_OT_VcAddEffect, OG_OT_VcEffectEdit,
           OG_OT_VcCopyEffects, OG_OT_VcApplyStack)


def register_props():
    bpy.types.Object.og_vc_effects = CollectionProperty(type=OGVcEffect)
    for k, *_r in KINDS:
        setattr(bpy.types.Scene, "og_fx_" + k.lower(), PointerProperty(type=OGVcEffect))


def unregister_props():
    for k, *_r in KINDS:
        if hasattr(bpy.types.Scene, "og_fx_" + k.lower()):
            delattr(bpy.types.Scene, "og_fx_" + k.lower())
    if hasattr(bpy.types.Object, "og_vc_effects"):
        del bpy.types.Object.og_vc_effects
