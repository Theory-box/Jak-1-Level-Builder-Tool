"""Factory-startup Blender smoke test; writes only to a supplied scratch project.

blender -b --factory-startup --python-exit-code 1 --python tools/test_entity_pass_blender.py -- SCRATCH_DATA
SCRATCH_DATA must contain a disposable copy of goal_src/jak1/game.gp.
"""
import json
import os
from pathlib import Path
import sys

import bpy

repo = Path(__file__).resolve().parents[1]
scratch = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
assert (scratch / 'goal_src/jak1/game.gp').is_file()
sys.path.insert(0, str(repo / 'addons'))
os.environ['OPENGOAL_TOOLS_DB'] = str(repo / 'addons/opengoal_tools/jak1_game_database.jsonc')
import opengoal_tools
opengoal_tools.register()
from opengoal_tools import db, required
from opengoal_tools.data import _actor_set_link
from opengoal_tools.export import actors, edited, writers
from opengoal_tools.export.levels import needed_code, needed_ags

scene = bpy.context.scene
scene.og_props.og_blend_paths_enabled = True
scene.og_props.og_blend_data_path = str(scratch)
for obj in list(scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

names = ['citb-stair-plat', 'silostep', 'reflector-mirror', 'citadelcam',
         'precursor-arm', 'lrocklrg', 'helix-water', 'helix-button',
         'helix-slide-door', 'flutflutegg', 'gorge-start', 'exit-chamber',
         'evilbro', 'evilsis', 'green-sagecage']
objects = {}
for i, name in enumerate(names):
    obj = bpy.data.objects.new(f'ACTOR_{name}_{i}', None)
    scene.collection.objects.link(obj)
    obj.location.x = i * 5
    objects[name] = obj
    assert edited.resolve(obj, name)['stem'] == name

_actor_set_link(objects['evilbro'], 'alt-actor', 0, objects['evilsis'].name)
_actor_set_link(objects['helix-button'], 'alt-actor', 0, objects['helix-water'].name)
_actor_set_link(objects['helix-button'], 'alt-actor', 1, objects['helix-slide-door'].name)
_actor_set_link(objects['citadelcam'], 'trigger-actor', 0, objects['citb-stair-plat'].name)
assert objects['citadelcam'].name in required.trigger_senders(scene)[objects['citb-stair-plat'].name]

race = objects['gorge-start']
assert {'og_game_task', 'og_race_finish'} <= {x['key'] for x in required.missing(race, scene)}
finish = bpy.data.objects.new('Race finish', None)
scene.collection.objects.link(finish)
finish.location = (2, 3, 4)
race['og_race_finish'] = finish.name
race['og_game_task'] = 'custom'
race['og_game_task_custom'] = 'entity-test-race'
bpy.context.view_layer.update()
assert not required.missing(race, scene), required.missing(race, scene)
assert actors._computed_lumps(race, 'gorge-start')['finish-pos'][1] == [8192.0, 16384.0, -12288.0, 0.0]

entries = actors.collect_actors(scene)
assert len(entries) == len(names), len(entries)
assert all(a.get('_edited_obs') in names for a in entries)
assert next(a for a in entries if a['_edited_obs'] == 'gorge-start')['game_task'] == '(game-task entity-test-race)'
code = '\n'.join(edited.gc_lines(scene, 'entity-test', scene.objects))
assert '__TYPE__' not in code
for name in names:
    assert code.count(f'(deftype entity-test-{name} ') == 1
writers.write_jsonc('entity-test', entries, [], scene=scene)
assert all(a['etype'].startswith('entity-test-') for a in entries)

scene['og_edited_place'] = {f'addon:{name}': 'shared' for name in names}
edited.ensure_shared(scene, scene.objects)
assert not edited.gc_lines(scene, 'entity-test', scene.objects)
assert set(edited.shared_objects(scene, scene.objects)) == {f'lt-{name}.o' for name in names}
entries = actors.collect_actors(scene)
assert {a['etype'] for a in entries} == {f'lt-{name}' for name in names}
deps = needed_code(entries)
assert {f'lt-{name}.o' for name in names} <= {d[0] for d in deps}
writers.write_gd('entity-test', needed_ags(entries), deps, scene=scene)
gp = (scratch / 'goal_src/jak1/game.gp').read_text(encoding='utf-8')
for name in names:
    assert gp.count(f'(goal-src "levels/level-tools/edited/lt-{name}.gc"') == 1
    assert (scratch / f'goal_src/jak1/levels/level-tools/edited/lt-{name}.gc').is_file()
edited.ensure_shared(scene, scene.objects)
assert (scratch / 'goal_src/jak1/game.gp').read_text(encoding='utf-8') == gp
# A dependency update must replace an old registration, including duplicates.
old_line = '(goal-src "levels/level-tools/edited/lt-silostep.gc" "process-drawable") ; og-level-tools'
gp_path = scratch / 'goal_src/jak1/game.gp'
gp_path.write_text(gp + '\n' + old_line + '\n', encoding='utf-8')
edited.ensure_shared(scene, scene.objects)
updated = gp_path.read_text(encoding='utf-8')
assert updated.count('(goal-src "levels/level-tools/edited/lt-silostep.gc"') == 1
assert old_line not in updated
race.og_edited_code = 'vanilla'
assert edited.resolve(race, 'gorge-start') is None
assert next(a for a in actors.collect_actors(scene) if a.get('_db_etype') == 'gorge-start')['etype'] == 'gorge-start'
print('ENTITY PASS SMOKE PASS: registration, 15 actors, required fields, vectors, custom task, JSONC, obs/shared/vanilla, idempotent shared registration')
opengoal_tools.unregister()
