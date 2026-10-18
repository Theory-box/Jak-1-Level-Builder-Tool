"""Run in Blender after tools/scan_sounds.py (blender -b --python tools/sound_db.py).
Per actor: the sounds it plays (its code's sound-play / sound specs, see
scan_sounds.py, + the sound names in its art groups' animation effects),
the ones not in the common bank written to the DB as "sounds": [...]."""
import bpy, addon_utils, json, os, re, traceback
TMP = os.path.dirname(os.path.abspath(__file__))
RAW = os.environ.get("OG_RAW_OBJ", r"C:/Users/John/Documents/JakAndDaxter/test-modbase/data/decompiler_out/jak1/raw_obj")   # the decompiler's raw_obj/
DBP = os.path.join(TMP, "..", "addons", "opengoal_tools", "jak1_game_database.jsonc")
try:
    addon_utils.enable("opengoal_tools", default_set=True)
    from opengoal_tools import db
    from opengoal_tools.data import ETYPE_AG, ENTITY_DEFS
    code = json.load(open(os.path.join(TMP, "sounds_by_type.json")))
    banks = db.bank_sfx()
    where = {}
    for b, l in banks.items():
        for x in l:
            where.setdefault(x, set()).add(b)
    art_cache = {}
    def art_sounds(ag):
        if ag not in art_cache:
            p = os.path.join(RAW, ag if ag.endswith(".go") else ag + ".go")
            d = open(p, "rb").read() if os.path.exists(p) else b""
            art_cache[ag] = {m.decode() for m in re.findall(rb"[a-z0-9][a-z0-9-]{2,}", d)} & set(where)
        return art_cache[ag]
    out, report = {}, []
    for a in db.DB["Actors"]:
        et = a["etype"]
        types = [et] + [c.get("etype") for c in (db._resolve_choices(db.variant_field(et)) if db.variant_field(et) else []) if c.get("etype")]
        snd = set()
        for t in types:
            snd |= set(code.get(t, []))
        ags = list(ETYPE_AG.get(et, []) or [])
        for c in (db._resolve_choices(db.variant_field(et)) if db.variant_field(et) else []):
            g = c.get("art_group")
            ags += g if isinstance(g, list) else ([g] if g else [])
        for g in ags:
            snd |= art_sounds(g)
        need = sorted(x for x in snd if x in where and "common" not in where[x])
        if need:
            out[et] = need
            report.append((et, need, sorted({b for x in need for b in where[x]})))
    json.dump(out, open(os.path.join(TMP, "sounds_db.json"), "w"), indent=1, sort_keys=True)
    print("ACTORS WITH NON-COMMON SOUNDS", len(out))
    for et, need, bs in report:
        print("SND", et, need, "->", bs)
    # write the DB: "sounds": [...] after "etype" of each actor record (Actors section)
    s = open(DBP, encoding="utf-8", newline="").read()
    s = re.sub(r'\n[ \t]*"sounds": \[[^\]]*\],', "", s)          # rerun: replace
    a0 = s.index('  "Actors": ['); a1 = s.index('  "OrphanEtypes": [')
    for et, need in sorted(out.items()):
        key = f'"etype": "{et}",'
        i = s.find(key, a0, a1)
        if i < 0:
            print("NOT FOUND", et); continue
        ls = s.rfind("\n", 0, i) + 1
        ind = s[ls:i]
        ins = f'\n{ind}"sounds": {json.dumps(need)},'
        s = s[:i + len(key)] + ins + s[i + len(key):]
        a1 += len(ins)
    open(DBP, "w", encoding="utf-8", newline="").write(s)
    print("DB written")
except Exception:
    traceback.print_exc()
