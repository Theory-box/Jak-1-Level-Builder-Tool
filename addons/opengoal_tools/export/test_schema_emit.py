"""Standalone unit tests for schema_emit (run: python3 export/test_schema_emit.py).
No Blender required — validates emit output matches the hardcoded lump shapes."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from schema_emit import emit_schema_lumps

def g(d): return lambda k, dflt=None: d.get(k, dflt)

PLAT_FLIP=[
 {"key":"og_flip_sync_pct","type":"float","default":0.0,"lump":{"key":"sync-percent","type":"float"},"write_if":"if_nonzero"},
 {"key":"og_flip_delay_down","type":"float","default":2.0,"lump":{"key":"delay","type":"float","slot":0},"write_if":"always"},
 {"key":"og_flip_delay_up","type":"float","default":2.0,"lump":{"key":"delay","type":"float","slot":1},"write_if":"always"},
]
STEAM_CAP=[
 {"key":"og_sync_period","type":"float","default":4.0,"lump":{"key":"sync","type":"float","slot":0},"write_if":"always"},
 {"key":"og_sync_phase","type":"float","default":0.0,"lump":{"key":"sync","type":"float","slot":1},"write_if":"always"},
 {"key":"og_sync_ease_out","type":"float","default":0.15,"lump":{"key":"sync","type":"float","slot":2},"write_if":"always"},
 {"key":"og_sync_ease_in","type":"float","default":0.15,"lump":{"key":"sync","type":"float","slot":3},"write_if":"always"},
 {"key":"og_steam_percent","type":"float","default":0.0,"lump":{"key":"percent","type":"float"},"write_if":"if_nonzero"},
]
DARK_CRYSTAL=[
 {"key":"og_crystal_underwater","type":"bool","default":False,"lump":{"key":"mode","type":"int32"},"value_if_true":1,"write_if":"if_true"},
]

def test():
    a=emit_schema_lumps(g({"og_flip_sync_pct":0.5,"og_flip_delay_down":2.0,"og_flip_delay_up":3.0}), PLAT_FLIP)
    assert a=={"sync-percent":["float",0.5],"delay":["float",2.0,3.0]}, a
    assert emit_schema_lumps(g({}), PLAT_FLIP)=={"delay":["float",2.0,2.0]}
    b=emit_schema_lumps(g({"og_steam_percent":0.5,"og_sync_phase":0.25}), STEAM_CAP)
    assert b=={"sync":["float",4.0,0.25,0.15,0.15],"percent":["float",0.5]}, b
    assert emit_schema_lumps(g({}), STEAM_CAP)=={"sync":["float",4.0,0.0,0.15,0.15]}
    assert emit_schema_lumps(g({"og_crystal_underwater":True}), DARK_CRYSTAL)=={"mode":["int32",1]}
    assert emit_schema_lumps(g({}), DARK_CRYSTAL)=={}
    print("all schema_emit tests passed")

if __name__=="__main__":
    test()
