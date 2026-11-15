"""Run with Blender --background --factory-startup --python-exit-code 1 --python FILE.
Creates temporary scene objects only. Does not write game data or preferences.
"""
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import bpy

repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo / 'addons'))
os.environ['OPENGOAL_TOOLS_DB'] = str(repo / 'addons/opengoal_tools/jak1_game_database.jsonc')
import opengoal_tools
opengoal_tools.register()
from opengoal_tools import db, required, link_order
from opengoal_tools.data import _actor_get_link, _actor_multi_links
from opengoal_tools.export.actors import collect_actors
from opengoal_tools.export.schema_emit import emit_schema_lumps

scene = bpy.context.scene
for obj in list(scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
def actor(et, suffix):
    obj = bpy.data.objects.new(f'ACTOR_{et}_{suffix}', None)
    scene.collection.objects.link(obj)
    return obj
switch = actor('snow-switch', 'z')
gate = actor('snow-fort-gate', 'a')
gate2 = actor('snow-fort-gate', 'b')
race = actor('gorge-start', 'r')
bumper = actor('snow-bumper', 'b')
chamber = actor('exit-chamber', 'c')
pelican = actor('pelican', 'p')
relay = actor('citadelcam', 'relay')
switch.location = (2,3,4)
bpy.context.view_layer.update()

names = [switch.name, gate.name, gate2.name]
link_order.apply_order(scene, names)
assert _actor_get_link(gate, 'prev-actor', 0).target_name == switch.name
assert _actor_get_link(gate, 'next-actor', 0).target_name == gate2.name
link_order.apply_order(scene, [gate2.name, gate.name])
assert _actor_get_link(gate, 'next-actor', 0) is None
assert _actor_get_link(gate2, 'prev-actor', 0) is None
link_order.apply_order(scene, names, relay.name, 'trigger-actor', 0)
assert [e.target_name for e in _actor_multi_links(relay, 'trigger-actor', 0)] == names

state = bpy.context.window_manager.og_link_order
state.items.clear()
for name in names: state.items.add().actor_name = name
state.index = 2
bpy.ops.og.link_order_move(direction='TOP')
assert state.items[0].actor_name == gate2.name
# Staging an order must leave actual links unchanged until confirmation.
assert [e.target_name for e in _actor_multi_links(relay, 'trigger-actor', 0)] == names
bpy.ops.og.link_order_move(direction='BOTTOM')
assert state.items[2].actor_name == gate2.name

class Layout:
    def __init__(self): self.labels=[]; self.buttons=[]
    def label(self, **kw): self.labels.append(kw.get('text',''))
    def operator(self, name, **kw):
        self.buttons.append((name,kw)); return SimpleNamespace()
    def __getattr__(self, key): return lambda *args, **kw: self

layout = Layout()
popup = SimpleNamespace(layout=layout,actor_name=race.name,panel='',soft=False)
ctx = SimpleNamespace(scene=scene,selected_objects=[race],active_object=race)
required.OG_OT_RequiredPopup.draw(popup,ctx)
assert any('Required:' in s and 'task' in s.lower() for s in layout.labels), layout.labels
assert any('Required:' in s and 'Finish' in s for s in layout.labels), layout.labels
assert any('Finish gate' in s for s in layout.labels)
assert any(m['key']=='spit' and 'cell' in m['label'] for m in required.missing(pelican,scene))
required.draw_header_count(layout,race)
assert all(k.get('icon','NONE') == 'NONE' for n,k in layout.buttons if n=='og.required_popup')
icons = bpy.types.UILayout.bl_rna.functions['operator'].parameters['icon'].enum_items
assert 'GRIP' in icons and 'TRIA_UP_BAR' in icons

entries = collect_actors(scene)
entry = next(e for e in entries if e.get('_db_etype') == 'snow-switch')
assert entry['lump']['movie-pos'][1] == [2.0,4.0,-3.0,0.0], entry['lump']
dest=bpy.data.objects.new('Cell movie position',None); scene.collection.objects.link(dest)
dest.location=(8,9,10)
switch.og_movie_pos.add().obj=dest
bumper.og_movie_pos.add().obj=dest
race.og_movie_pos.add().obj=dest
race['og_race_direct_cell']=True
race['og_race_finish']=dest.name
race['og_game_task']='custom'; race['og_game_task_custom']='feedback-race'
chamber['og_chamber_closed']=True; chamber['og_chamber_time']=7.5
bpy.context.view_layer.update()
entries=collect_actors(scene)
for et in ('snow-switch','snow-bumper','gorge-start'):
    e=next(e for e in entries if e.get('_db_etype')==et)
    assert e['lump']['movie-pos'][1][:3] == [8.0,10.0,-9.0]
e=next(e for e in entries if e.get('_db_etype')=='gorge-start')
assert e['lump']['direct-cell'] == ['uint32',1]
e=next(e for e in entries if e.get('_db_etype')=='exit-chamber')
assert e['lump']['starts-closed'] == ['uint32',1]
assert e['lump']['travel-time'] == ['float',7.5]
assert db.find_actor('gorge-start')['glb'].endswith('rolling-start-whole-lod0.glb')
assert db.find_actor('fishermans-boat')['glb'].endswith('fishermans-boat-lod0.glb')
print('FEEDBACK PASS: link order/boundaries/staging, required popup field labels, path help, icons, movie positions, direct reward and chamber export')
opengoal_tools.unregister()
