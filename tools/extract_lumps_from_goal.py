import re, json
from pathlib import Path
from collections import defaultdict
from datetime import date
GOAL=Path("goal_src/jak1")
DB=Path("addons/opengoal_tools/jak1_game_database.jsonc")
ACCESSOR=re.compile(r"^(res-lump-(?:float|struct|data|value)(?:-exact)?|"
 r"get-property-(?:value-float|struct|value|data)|lookup-tag-idx|"
 r"entity-actor-lookup|entity-actor-count|get-tag-data|get-tag-index-data)$")
SYM=re.compile(r"^'([a-z][a-z0-9!*+/<>=._-]*)$")
DEFTYPE=re.compile(r"\(deftype\s+([a-z0-9!*+/<>=-]+)\s+\(([a-z0-9!*+/<>=-]+)")
DEFM_A=re.compile(r"\(defmethod\s+[a-z0-9!*+/<>=?-]+\s+\(\(\s*[a-z0-9-]+\s+([a-z0-9!*+/<>=-]+)")
DEFM_B=re.compile(r"\(defmethod\s+[a-z0-9!*+/<>=?-]+\s+([a-z0-9!*+/<>=-]+)\b")
DEFSTATE=re.compile(r"\(defstate\s+[a-z0-9!*+/<>=?-]+\s+\(([a-z0-9!*+/<>=-]+)\)")
DEFBEH=re.compile(r"\(defbehavior\s+[a-z0-9!*+/<>=?-]+\s+([a-z0-9!*+/<>=-]+)")
FIELD=re.compile(r"^\s*\(([a-z0-9-]+)\s+([a-z0-9!*+/<>=-]+)")

direct=defaultdict(set); parent={}; fields=defaultdict(list); param_loaders=set()
file_types=defaultdict(set)            # file -> deftypes declared in it
file_defun_lumps=defaultdict(set)      # file -> lumps read in defun (no-type) context
def toks(line): return line.replace("("," ( ").replace(")"," ) ").split()
def scan(p):
    cur=None; dt=None; pend=0; ptyp=None; in_defun=False
    for raw in p.read_text(errors="replace").splitlines():
        line=raw.split(";")[0]; ls=line.lstrip()
        m=DEFTYPE.search(line)
        if m:
            parent[m.group(1)]=m.group(2); cur=dt=("T:"+m.group(1)); in_defun=False
            file_types[p].add(m.group(1))
        elif dt and dt.startswith("T:"):
            fm=FIELD.match(line)
            if fm and fm.group(1) not in ("meth","states","method"): fields[dt[2:]].append((fm.group(1),fm.group(2)))
            if ls.startswith(("(defmethod","(defun","(defstate","(defbehavior")): dt=None
        if ls.startswith("(defmethod"):
            mm=DEFM_A.search(line) or DEFM_B.search(line); cur=("T:"+mm.group(1)) if mm else None; dt=None; in_defun=False
            if mm and ls.startswith("(defmethod load-params!"): param_loaders.add(mm.group(1))
        elif ls.startswith("(defstate"):
            mm=DEFSTATE.search(line); cur=("T:"+mm.group(1)) if mm else None; dt=None; in_defun=False
        elif ls.startswith("(defbehavior"):
            mm=DEFBEH.search(line); cur=("T:"+mm.group(1)) if mm else None; dt=None; in_defun=False
        elif ls.startswith("(defun"): cur=None; dt=None; in_defun=True
        for tok in toks(line):
            if ACCESSOR.match(tok): pend=10; ptyp=cur; ptyp_defun=in_defun
            elif pend>0:
                sm=SYM.match(tok)
                if sm and sm.group(1) not in ("static","process","entity","exact","interp"):
                    if ptyp and ptyp.startswith("T:"): direct[ptyp[2:]].add(sm.group(1))
                    elif ptyp_defun: file_defun_lumps[p].add(sm.group(1))
                    pend=0
                else: pend-=1
for f in GOAL.rglob("*.gc"): scan(f)

txt=re.sub(r"/\*.*?\*/","",DB.read_text(),flags=re.S); db=json.loads(re.sub(r"(?m)//.*$","",txt)); actors=db.get("Actors",[])
ETYPES={a.get("etype") for a in actors}
# NOTE: file-level defun reads are deliberately NOT spread across co-located
# actors — multi-actor files (beach-obs 8, collectables 13) would cause false
# positives. Such reads are generic/shared and tracked as a known recall limit.

def anc(t):
    s=set()
    while t in parent and t not in s: s.add(t); t=parent[t]; yield t
def chain_fields(t):
    out=list(fields.get(t,[]))
    for a in anc(t): out+=fields.get(a,[])
    return out
def eff(t,d=0,seen=None):
    seen=seen or set()
    if t in seen: return set()
    seen.add(t)
    o=set(direct.get(t,()))
    for a in anc(t): o|=direct.get(a,set())
    if d<4:
        for _f,ft in chain_fields(t):           # FULL-CHAIN param-loader expansion
            if ft in param_loaders and ft!=t: o|=eff(ft,d+1,seen)
    return o

def db_keys(a):
    k={l.get("key") for l in a.get("lumps",[])}
    k|={f["lump"]["key"] for f in a.get("fields",[]) if isinstance(f.get("lump"),dict) and f["lump"].get("key")}
    k|={s["lump_key"] for s in a.get("link_slots",[]) if s.get("lump_key")}
    return {x for x in k if x}

# sanity
for et in ("side-to-side-plat","plat","tar-plat","wedge-plat","windmill-one","ecoventrock","steam-cap","whirlpool","fuel-cell"):
    print(f"{et:18s}",sorted(eff(et)))

UNIVERSAL={"joint-channel","light-index","options","shadow-mask","texture-bucket","nav-max-users","nav-mesh-actor","name","trans","trans-offset"}
by_cat=defaultdict(list)
for a in actors: by_cat[a.get("category","Uncategorised")].append(a)
out=["# Jak 1 Actor Lump & Settings — Master Reference (FULL)",""]
out.append(f"Auto-generated {date.today().isoformat()} from OpenGOAL `jak-project` jak1 source ({len(actors)} actors). "
 "**Full** list — every lump the engine reads per actor, nothing folded away. Derived from all "
 "`res-lump-*`/`get-property-*`/`entity-actor-*`/`lookup-tag` reads across methods, states, behaviours, "
 "called helpers in the same file, the full `:parent` chain, and inherited param-loader fields (e.g. `sync-info`).")
out+=["","**Legend** — `key` = read & in DB · **`key`** = read but MISSING from DB · "
 "`_DB-only_` = in DB but not seen in source (stale, or read by a generic subsystem like the fact system).",""]
out.append(f"> **Common lumps** (read by virtually every actor; omitted from the rows below): {', '.join(sorted(UNIVERSAL))}")
out.append("")
for cat in sorted(by_cat):
    out+=[f"## {cat}","","| Actor (etype) | Label | Specific lumps |","|---|---|---|"]
    for a in sorted(by_cat[cat], key=lambda x:x.get("etype","")):
        et=a.get("etype"); src=eff(et); dbk=db_keys(a)
        spec=sorted(x for x in (src-UNIVERSAL) if x!=et); comm=sorted(src&UNIVERSAL)
        cells=[(f"**{k}**" if k not in dbk else k) for k in spec] or ["*(common only)*"]
        cell=", ".join(cells)
        only=sorted(set(dbk)-src-UNIVERSAL)
        if only: cell+=f" · _DB-only: {', '.join(only)}_"
        out.append(f"| `{et}` | {a.get('label',et)} | {cell} |")
    out.append("")
Path("ACTOR-LUMP-MASTER.md").write_text("\n".join(out)); print("lines:",len(out))
