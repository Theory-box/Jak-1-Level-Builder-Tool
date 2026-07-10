"""Standalone tests for schema_emit against the DB's real fields[] convention.
Run: python3 export/test_schema_emit.py   (no Blender needed).
Loads the actual game DB and asserts the engine reproduces the hardcoded export
output for actors exercising every convention feature."""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(__file__))
from schema_emit import emit_schema_lumps as E

def _load_fields():
    here = os.path.dirname(__file__)
    for p in (os.path.join(here, "..", "jak1_game_database.jsonc"),
              os.path.join(here, "..", "..", "..", "refactoring", "jak1_game_database.jsonc")):
        if os.path.exists(p):
            raw = open(p).read()
            raw = re.sub(r'/\*.*?\*/', '', raw, flags=re.S)
            raw = re.sub(r'(?m)//.*$', '', raw)
            db = json.loads(raw)
            return ({a["etype"]: a.get("fields", []) for a in db["Actors"]},
                    {"CratePickups": db.get("CratePickups", [])})
    raise SystemExit("DB not found")

F, CT = _load_fields()
g = lambda d: (lambda k, dflt=None: d.get(k, dflt))

CASES = [
    # name, etype, props, expected   (expected == current hardcoded export output)
    ("enum lump_value",   "launcher",        {"og_launcher_mode": "longfall", "og_spring_height": 5.0},
                                              {"mode": ["uint32", 1], "spring-height": ["meters", 5.0]}),
    ("if_nonneg + default","launcher",        {}, {}),
    ("named choice+format","oracle",          {"og_alt_task": "ogre-boss"}, {"alt-task": ["enum-uint32", "(game-task ogre-boss)"]}),
    ("if_not_none none",  "oracle",           {}, {}),
    ("symbol_literal",    "crate",            {"og_crate_type": "wood"},
                                              {"crate-type": "'wood", "eco-info": ["eco-info", "(pickup-type money)", 1]}),
    ("picker default",    "crate",            {},
                                              {"crate-type": "'steel", "eco-info": ["eco-info", "(pickup-type money)", 1]}),
    ("picker eco-green",  "crate",            {"og_crate_pickup": "eco-green"},
                                              {"crate-type": "'steel", "eco-info": ["eco-info", "(pickup-type eco-green)", 1]}),
    ("picker amount kept","crate",            {"og_crate_pickup": "money", "og_crate_pickup_amount": 5},
                                              {"crate-type": "'steel", "eco-info": ["eco-info", "(pickup-type money)", 5]}),
    ("picker eco multi",  "crate",            {"og_crate_pickup": "eco-blue", "og_crate_pickup_amount": 4},
                                              {"crate-type": "'steel", "eco-info": ["eco-info", "(pickup-type eco-blue)", 4]}),
    ("picker buzzer force1","crate",          {"og_crate_pickup": "buzzer", "og_crate_pickup_amount": 3},
                                              {"crate-type": "'steel", "eco-info": ["eco-info", "(pickup-type buzzer)", 1]}),
    ("picker none skip",  "crate",            {"og_crate_pickup": "none"}, {"crate-type": "'steel"}),
    ("picker ecovent",    "ecovent",          {}, {"eco-info": ["eco-info", "(pickup-type eco-green)", 1]}),
    ("picker ecovent none","ecovent",         {"og_crate_pickup": "none"}, {}),
    ("lump_bit OR",       "eco-door",         {"og_door_auto_close": True, "og_door_one_way": True, "og_door_starts_open": True},
                                              {"flags": ["uint32", 12], "perm-status": ["uint32", 64]}),
    ("value_if_true",     "fuel-cell",        {"og_cell_skip_jump": True}, {"options": ["uint32", 4]}),
    ("if_any_nonzero",    "breakaway-left",   {"og_breakaway_h1": 1.0}, {"height-info": ["float", 1.0, 0.0]}),
    ("if_any_nonzero off","breakaway-left",   {}, {}),
    ("default_per_etype a","lavaballoon",     {}, {"speed": ["meters", 3.0]}),
    ("default_per_etype b","darkecobarrel",   {}, {"speed": ["meters", 15.0]}),
    ("lump.scale x4096",  "square-platform",  {"og_sq_down": -2.0, "og_sq_up": 4.0}, {"distance": ["float", -8192.0, 16384.0]}),
    ("if_not_default skip","sharkey",         {}, {"delay": ["float", 1.0], "distance": ["meters", 30.0], "speed": ["meters", 12.0]}),
    ("slot array",        "caveflamepots",    {}, {"shove": ["meters", 2.0], "cycle-speed": ["float", 4.0, 0.0, 2.0]}),
]

def test():
    bad = 0
    for name, et, props, exp in CASES:
        got = E(g(props), F[et], etype=et, choice_tables=CT)
        if got != exp:
            print("FAIL", name, "->", got, "EXPECTED", exp); bad += 1
    if bad:
        raise SystemExit(f"{bad} failures")
    print(f"all {len(CASES)} schema_emit convention tests passed")

if __name__ == "__main__":
    test()
