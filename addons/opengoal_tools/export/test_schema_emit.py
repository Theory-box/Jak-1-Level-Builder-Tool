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
    # ── Category A: migrated actors (hardcoded branch deleted) ──────────
    ("A dark-crystal off",      "dark-crystal",    {}, {}),
    ("A dark-crystal underwater", "dark-crystal",    {"og_crystal_underwater": True}, {"mode": ["int32", 1]}),
    ("A plat-flip default",     "plat-flip",       {}, {"delay": ["float", 2.0, 2.0]}),
    ("A plat-flip custom",      "plat-flip",       {"og_flip_sync_pct": 0.25, "og_flip_delay_down": 1.0, "og_flip_delay_up": 3.0}, {"sync-percent": ["float", 0.25], "delay": ["float", 1.0, 3.0]}),
    ("A sun-iris default",      "sun-iris-door",   {}, {}),
    ("A sun-iris custom",       "sun-iris-door",   {"og_door_proximity": True, "og_door_timeout": 2.5}, {"proximity": ["uint32", 1], "timeout": ["float", 2.5]}),
    ("A basebutton off",        "basebutton",      {}, {}),
    ("A basebutton timeout",    "basebutton",      {"og_button_timeout": 1.5}, {"timeout": ["float", 1.5]}),
    ("A orb-cache default",     "orb-cache-top",   {}, {"orb-cache-count": ["int32", 20]}),
    ("A orb-cache custom",      "orb-cache-top",   {"og_orb_count": 50}, {"orb-cache-count": ["int32", 50]}),
    ("A whirlpool default",     "whirlpool",       {}, {"speed": ["float", 0.3, 0.1]}),
    ("A whirlpool custom",      "whirlpool",       {"og_whirl_speed": 0.9, "og_whirl_var": 0.2}, {"speed": ["float", 0.9, 0.2]}),
    ("A ropebridge default",    "ropebridge",      {}, {"art-name": ["symbol", "ropebridge-32"]}),
    ("A ropebridge custom",     "ropebridge",      {"og_bridge_variant": "ropebridge-48"}, {"art-name": ["symbol", "ropebridge-48"]}),
    ("A orbit-plat default",    "orbit-plat",      {}, {}),
    ("A orbit-plat custom",     "orbit-plat",      {"og_orbit_scale": 2.0, "og_orbit_timeout": 5.0}, {"scale": ["float", 2.0], "timeout": ["float", 5.0]}),
    ("A square custom",         "square-platform", {"og_sq_down": -3.0, "og_sq_up": 6.0}, {"distance": ["float", -12288.0, 24576.0]}),
    ("A caveflamepots custom",  "caveflamepots",   {"og_flame_shove": 5.0, "og_flame_period": 2.0, "og_flame_phase": 1.0, "og_flame_pause": 0.5}, {"shove": ["meters", 5.0], "cycle-speed": ["float", 2.0, 1.0, 0.5]}),
    ("A shover default",        "shover",          {}, {"shove": ["meters", 3.0]}),
    ("A shover rot",            "shover",          {"og_shover_force": 4.0, "og_shover_rot": 45.0}, {"shove": ["meters", 4.0], "rotoffset": ["degrees", 45.0]}),
    ("A lavaballoon default",   "lavaballoon",     {}, {"speed": ["meters", 3.0]}),
    ("A lavaballoon custom",    "lavaballoon",     {"og_move_speed": 7.0}, {"speed": ["meters", 7.0]}),
    ("A windturbine off",       "windturbine",     {}, {}),
    ("A windturbine on",        "windturbine",     {"og_turbine_particles": True}, {"particle-select": ["uint32", 1]}),
    ("A caveelevator default",  "caveelevator",    {}, {}),
    ("A caveelevator custom",   "caveelevator",    {"og_elevator_mode": 2, "og_elevator_rot": 90.0}, {"mode": ["uint32", 2], "rotoffset": ["degrees", 90.0]}),
    ("A mis-bone default",      "mis-bone-bridge", {}, {}),
    ("A mis-bone anim",         "mis-bone-bridge", {"og_bone_bridge_anim": 3}, {"animation-select": ["uint32", 3]}),
    ("A breakaway default",     "breakaway-left",  {}, {}),
    ("A breakaway custom",      "breakaway-left",  {"og_breakaway_h1": 1.0, "og_breakaway_h2": 2.0}, {"height-info": ["float", 1.0, 2.0]}),
    ("A sunkenfisha custom",    "sunkenfisha",     {"og_fish_count": 4}, {"count": ["uint32", 4]}),
    ("A sharkey custom",        "sharkey",         {"og_shark_scale": 2.0, "og_shark_delay": 0.5, "og_shark_distance": 50.0, "og_shark_speed": 20.0}, {"scale": ["float", 2.0], "delay": ["float", 0.5], "distance": ["meters", 50.0], "speed": ["meters", 20.0]}),
    ("A oracle none",           "oracle",          {}, {}),
    ("A oracle task",           "oracle",          {"og_alt_task": "jungle-eggtop"}, {"alt-task": ["enum-uint32", "(game-task jungle-eggtop)"]}),
    ("A launcherdoor empty",    "launcherdoor",    {}, {}),
    ("A launcherdoor bare str", "launcherdoor",    {"og_continue_name": "test-checkpoint"}, {"continue-name": "test-checkpoint"}),
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
