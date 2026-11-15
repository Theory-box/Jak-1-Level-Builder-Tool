"""Standalone tests against the current panel/inheritance schema, without bpy.

Run: python addons/opengoal_tools/export/test_schema_emit.py
The old pre-panel fixtures referenced removed fields and imported schema_emit
outside its package, which broke task-expression imports.
"""
import importlib
import os
from pathlib import Path
import sys
import types
import unittest

ADDON = Path(__file__).resolve().parents[1]
os.environ['OPENGOAL_TOOLS_DB'] = str(ADDON / 'jak1_game_database.jsonc')
for name, path in [('_schema_test_addon', ADDON), ('_schema_test_addon.export', ADDON / 'export')]:
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules[name] = module
db = importlib.import_module('_schema_test_addon.db')
E = importlib.import_module('_schema_test_addon.export.schema_emit').emit_schema_lumps


def emit(etype, values=None):
    return E((values or {}).get, db.inherited_fields(etype), etype=etype, choice_tables=db.DB)


class SchemaTests(unittest.TestCase):
    def test_crate_picker(self):
        self.assertEqual(emit('crate'), {'crate-type': "'steel", 'eco-info': ['eco-info', '(pickup-type money)', 1]})
        self.assertEqual(emit('crate', {'og_crate_pickup_amount': 5})['eco-info'], ['eco-info', '(pickup-type money)', 5])
        self.assertNotIn('eco-info', emit('crate', {'og_crate_pickup': 'none'}))
        self.assertEqual(emit('crate', {'og_crate_pickup': 'buzzer', 'og_crate_pickup_amount': 7})['eco-info'], ['eco-info', '(pickup-type buzzer)', 1])

    def test_pathless_platform_keeps_sync(self):
        self.assertEqual(emit('steam-cap')['sync'], ['float', 6.0, 0.0])
        self.assertEqual(emit('steam-cap')['percent'], ['float', 0.4, 0.9])

    def test_custom_task_expression(self):
        self.assertEqual(emit('oracle', {'og_alt_task': 'custom', 'og_alt_task_custom': 'test-reward'})['alt-task'], ['enum-uint32', '(game-task test-reward)'])
        self.assertNotIn('alt-task', emit('oracle', {'og_alt_task': 'custom', 'og_alt_task_custom': ''}))

    def test_bare_continue_name(self):
        self.assertEqual(emit('launcherdoor', {'og_continue_name': 'test-checkpoint'})['continue-name'], 'test-checkpoint')

    def test_scaled_slot_array(self):
        self.assertEqual(emit('square-platform', {'og_sq_down': -2.0, 'og_sq_up': 4.0})['distance'], ['float', -8192.0, 16384.0])

    def test_stair_fields(self):
        self.assertEqual(emit('citb-stair-plat', {'og_stair_rise': 7.5, 'og_stair_delay': 0.25}), {'rise-distance': ['meters', 7.5], 'delay': ['float', 0.25]})

    def test_rising_eco_defaults_and_override(self):
        out = emit('helix-water')
        self.assertEqual(out['look'], ['int32', 40])
        self.assertEqual(out['attack-event'], "'dark-eco-pool")
        self.assertEqual(out['water-height'][-1], '(water-flags wt03 wt19 wt20)')
        self.assertEqual(emit('helix-water', {'og_water_ripple': False})['water-height'][-1], '(water-flags wt03 wt19)')
        self.assertEqual(emit('water-vol')['water-height'][-1], '(water-flags wt02 wt03)')

    def test_relay_gate_custom_task(self):
        self.assertNotIn('gate-task', emit('citadelcam'))
        self.assertEqual(emit('citadelcam', {'og_relay_gate_task': 'custom', 'og_relay_gate_task_custom': '(game-task custom-gate)'})['gate-task'], ['enum-uint32', '(game-task custom-gate)'])

    def test_object_refs_remain_computed(self):
        self.assertNotIn('finish-pos', emit('gorge-start', {'og_race_finish': 'Finish'}))
        self.assertNotIn('beam-end', emit('reflector-mirror', {'og_mirror_beam_end': 'Beam'}))

    def test_edited_records_have_files(self):
        ids = [a['etype'] for a in db.actors()]
        self.assertEqual(len(ids), len(set(ids)))
        for actor in db.actors():
            if actor.get('edited'):
                self.assertTrue((ADDON / 'subtypes' / (actor['edited'] + '.gc')).is_file(), actor['etype'])

    def test_required_race_fields(self):
        self.assertEqual({f['key'] for f in db.inherited_fields('gorge-start') if f.get('required')}, {'og_game_task', 'og_race_finish'})

    def test_helix_records_are_placeable(self):
        for et in ['helix-water', 'helix-button', 'helix-slide-door']:
            self.assertIsNotNone(db.find_actor(et))
            self.assertNotIn(et, [r['etype'] for r in db.DB['OrphanEtypes']])


if __name__ == '__main__':
    unittest.main()
