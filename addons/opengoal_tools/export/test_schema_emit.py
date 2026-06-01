"""Standalone unit tests for schema_emit (run: python3 export/test_schema_emit.py).
No Blender required. Validates the engine reproduces the hardcoded lump shapes
for every branch category in export/actors.py."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from schema_emit import emit_schema_lumps as E

g = lambda d: (lambda k, dflt=None: d.get(k, dflt))

SYNC=[{"key":"og_sync_period","default":4.0,"lump":{"key":"sync","type":"float","slot":0},"write_if":"always"},
      {"key":"og_sync_phase","default":0.0,"lump":{"key":"sync","type":"float","slot":1},"write_if":"always"},
      {"key":"og_sync_ease_out","default":0.15,"lump":{"key":"sync","type":"float","slot":2},"write_if":"always"},
      {"key":"og_sync_ease_in","default":0.15,"lump":{"key":"sync","type":"float","slot":3},"write_if":"always"},
      {"key":"og_sync_wrap","type":"bool","default":False,"lump":{"key":"options","type":"uint32","bit":8},"write_if":"if_true"}]
DOOR=[{"key":"og_door_auto_close","type":"bool","default":False,"lump":{"key":"flags","type":"uint32","bit":4},"write_if":"if_true"},
      {"key":"og_door_one_way","type":"bool","default":False,"lump":{"key":"flags","type":"uint32","bit":8},"write_if":"if_true"},
      {"key":"og_door_starts_open","type":"bool","default":False,"lump":{"key":"perm-status","type":"uint32"},"value_if_true":64,"write_if":"if_true"}]
SQ=[{"key":"og_sq_down","default":-2.0,"scale":4096,"lump":{"key":"distance","type":"float","slot":0},"write_if":"always"},
    {"key":"og_sq_up","default":4.0,"scale":4096,"lump":{"key":"distance","type":"float","slot":1},"write_if":"always"}]
FLAME=[{"key":"og_flame_shove","default":2.0,"lump":{"key":"shove","type":"meters"},"write_if":"always"},
       {"key":"og_flame_period","default":4.0,"lump":{"key":"cycle-speed","type":"float","slot":0},"write_if":"always"},
       {"key":"og_flame_phase","default":0.0,"lump":{"key":"cycle-speed","type":"float","slot":1},"write_if":"always"},
       {"key":"og_flame_pause","default":2.0,"lump":{"key":"cycle-speed","type":"float","slot":2},"write_if":"always"}]
BUZZER=[{"const":"(game-task none)","lump":{"key":"eco-info","type":"buzzer-info","slot":0}},
        {"const":1,"lump":{"key":"eco-info","type":"buzzer-info","slot":1}}]

def test():
    assert E(g({"og_sync_phase":0.25,"og_sync_wrap":True}),SYNC)=={"sync":["float",4.0,0.25,0.15,0.15],"options":["uint32",8]}
    assert E(g({}),SYNC)=={"sync":["float",4.0,0.0,0.15,0.15]}
    assert E(g({"og_door_auto_close":True,"og_door_one_way":True,"og_door_starts_open":True}),DOOR)=={"flags":["uint32",12],"perm-status":["uint32",64]}
    assert E(g({}),DOOR)=={}
    assert E(g({"og_sq_down":-2.0,"og_sq_up":4.0}),SQ)=={"distance":["float",-8192.0,16384.0]}
    assert E(g({}),FLAME)=={"shove":["meters",2.0],"cycle-speed":["float",4.0,0.0,2.0]}
    assert E(g({}),BUZZER)=={"eco-info":["buzzer-info","(game-task none)",1]}
    print("all schema_emit tests passed")

if __name__=="__main__":
    test()
