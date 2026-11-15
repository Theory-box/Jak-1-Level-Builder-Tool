"""A staged link order: editing/cancelling never changes actor links."""
import bpy
from . import db


def apply_order(scene, names, source_name="", lump_key="", slot=0):
    from .data import (_actor_set_link, _actor_remove_link,
                       _actor_multi_links, _actor_add_multi_link)
    objects = [scene.objects.get(n) for n in names]
    if any(o is None or o.type != 'EMPTY' or not o.name.startswith('ACTOR_') for o in objects):
        raise ValueError('An actor was removed or renamed; reopen Edit order')
    if len(set(names)) != len(names):
        raise ValueError('An actor occurs more than once')
    if source_name:
        source = scene.objects.get(source_name)
        if source is None:
            raise ValueError('Source actor no longer exists')
        for e in list(_actor_multi_links(source, lump_key, slot)):
            _actor_remove_link(source, lump_key, e.slot_index)
        for name in names:
            _actor_add_multi_link(source, lump_key, slot, name)
    else:
        for i, obj in enumerate(objects):
            keys = {(s['lump_key'], s.get('slot', 0)) for s in db.link_slots(obj.name.split('_', 2)[1])}
            for key, j in [('prev-actor', i - 1), ('next-actor', i + 1)]:
                if (key, 0) in keys:
                    _actor_remove_link(obj, key, 0)
                    if 0 <= j < len(objects):
                        _actor_set_link(obj, key, 0, objects[j].name)


class OG_LinkOrderItem(bpy.types.PropertyGroup):
    actor_name: bpy.props.StringProperty()


class OG_LinkOrderState(bpy.types.PropertyGroup):
    items: bpy.props.CollectionProperty(type=OG_LinkOrderItem)
    index: bpy.props.IntProperty()


class OG_UL_LinkOrder(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        op = row.operator('og.link_order_drag', text='', icon='GRIP', emboss=False)
        op.index = index
        row.label(text=item.actor_name, icon='EMPTY_AXIS')


class OG_OT_LinkOrderMove(bpy.types.Operator):
    bl_idname = 'og.link_order_move'
    bl_label = 'Move in Link Order'
    direction: bpy.props.EnumProperty(items=[(x, x.title(), '') for x in ('TOP','UP','DOWN','BOTTOM')])

    def execute(self, ctx):
        state = ctx.window_manager.og_link_order
        i = state.index
        j = {'TOP': 0, 'UP': i-1, 'DOWN': i+1, 'BOTTOM': len(state.items)-1}[self.direction]
        j = max(0, min(len(state.items)-1, j))
        if state.items:
            state.items.move(i, j)
            state.index = j
        return {'FINISHED'}


class OG_OT_LinkOrderDrag(bpy.types.Operator):
    bl_idname = 'og.link_order_drag'
    bl_label = 'Drag to Reorder'
    bl_description = 'Drag up/down to move this actor; Escape cancels this drag'
    index: bpy.props.IntProperty()

    def invoke(self, ctx, event):
        self.start_y = event.mouse_y
        self.start_index = self.index
        ctx.window_manager.og_link_order.index = self.index
        ctx.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, ctx, event):
        state = ctx.window_manager.og_link_order
        if event.type in {'ESC', 'RIGHTMOUSE'}:
            state.items.move(state.index, self.start_index)
            state.index = self.start_index
            ctx.area.tag_redraw()
            return {'CANCELLED'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            return {'FINISHED'}
        if event.type == 'MOUSEMOVE':
            row_height = 20 * ctx.preferences.system.ui_scale
            dest = max(0, min(len(state.items)-1, self.start_index + round((self.start_y-event.mouse_y)/row_height)))
            state.items.move(state.index, dest)
            state.index = dest
            ctx.area.tag_redraw()
        return {'RUNNING_MODAL'}


class OG_OT_EditLinkOrder(bpy.types.Operator):
    bl_idname = 'og.edit_link_order'
    bl_label = 'Edit Actor Order'
    bl_options = {'UNDO'}
    source_name: bpy.props.StringProperty()
    lump_key: bpy.props.StringProperty()
    slot_index: bpy.props.IntProperty()

    def invoke(self, ctx, event):
        from .operators.actors import _selected_actor_empties
        from .data import _actor_multi_links
        source = ctx.scene.objects.get(self.source_name) if self.source_name else None
        names = [e.target_name for e in _actor_multi_links(source, self.lump_key, self.slot_index)] if source else []
        names += [o.name for o in _selected_actor_empties(ctx, exclude=source) if o.name not in names]
        state = ctx.window_manager.og_link_order
        state.items.clear()
        for name in names:
            state.items.add().actor_name = name
        state.index = 0
        return ctx.window_manager.invoke_props_dialog(self, width=620, confirm_text='Add with this order' if source else 'Chain with this order')

    def draw(self, ctx):
        state = ctx.window_manager.og_link_order
        self.layout.label(text='Drag a grip, or select a row and use the arrows.')
        row = self.layout.row()
        row.template_list('OG_UL_LinkOrder', '', state, 'items', state, 'index', rows=8)
        col = row.column(align=True)
        for direction, icon in [('TOP','TRIA_UP_BAR'),('UP','TRIA_UP'),('DOWN','TRIA_DOWN'),('BOTTOM','TRIA_DOWN_BAR')]:
            col.operator('og.link_order_move', text='', icon=icon).direction = direction

    def execute(self, ctx):
        try:
            apply_order(ctx.scene, [e.actor_name for e in ctx.window_manager.og_link_order.items],
                        self.source_name, self.lump_key, self.slot_index)
        except ValueError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return {'FINISHED'}


CLASSES = (OG_LinkOrderItem, OG_LinkOrderState, OG_UL_LinkOrder,
           OG_OT_LinkOrderMove, OG_OT_LinkOrderDrag, OG_OT_EditLinkOrder)

def register_props():
    bpy.types.WindowManager.og_link_order = bpy.props.PointerProperty(type=OG_LinkOrderState)

def unregister_props():
    del bpy.types.WindowManager.og_link_order
