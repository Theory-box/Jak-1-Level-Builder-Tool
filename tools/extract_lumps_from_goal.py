import re, json
from pathlib import Path
from collections import defaultdict
from datetime import date
GOAL=Path("goal_src/jak1")
DB=Path("addons/opengoal_tools/jak1_game_database.jsonc")
ACCESSOR=re.compile(r"^(res-lump-(?:float|struct|data|value)(?:-exact)?|get-property-(?:value-float|struct|value|data)|lookup-tag-idx)$")
SYM=re.compile(r"^'([a-z][a-z0-9!*+/<>=._-]*)$")
DEFTYPE=re.compile(r"\(deftype\s+([a-z0-9!*+/<>=-]+)\s+\(([a-z0-9!*+/<>=-]+)")
DEFM_A=re.compile(r"\(defmethod\s+[a-z0-9!*+/<>=?-]+\s+\(\(\s*[a-z0-9-]+\s+([a-z0-9!*+/<>=-]+)")
DEFM_B=re.compile(r"\(defmethod\s+[a-z0-9!*+/<>=?-]+\s+([a-z0-9!*+/<>=-]+)\b")
DEFSTATE=re.compile(r"\(defstate\s+[a-z0-9!*+/<>=?-]+\s+\(([a-z0-9!*+/<>=-]+)\)")
DEFBEH=re.compile(r"\(defbehavior\s+[a-z0-9!*+/<>=?-]+\s+([a-z0-9!*+/<>=-]+)")
DEFUN=re.compile(r"\(defun\s+([a-z0-9!*+/<>=?-]+)")
FIELD=re.compile(r"^\s*\(([a-z0-9-]+)\s+([a-z0-9!*+/<>=-]+)")
direct=defaultdict(set); parent={}; fields=defaultdict(list)
fn_lumps=defaultdict(set)            # defun name -> lumps it reads
ctx_calls=defaultdict(set)           # context (type or fn) -> callee names
def toks(line): return line.replace("("," ( ").replace(")"," ) ").split()
def scan(p):
    cur=None; dt=None; pend=0; ptyp=None
    for raw in p.read_text(errors="replace").splitlines():
        line=raw.split(";")[0]; ls=line.lstrip()
        m=DEFTYPE.search(line)
        if m: parent[m.group(1)]=m.group(2); cur=dt=("T:"+m.group(1))
        elif dt and dt.startswith("T:"):
            fm=FIELD.match(line)
            if fm and fm.group(1) not in ("meth","states","method"): fields[dt[2:]].append((fm.group(1),fm.group(2)))
            if ls.startswith(("(defmethod","(defun","(defstate","(defbehavior")): dt=None
        if ls.startswith("(defmethod"):
            mm=DEFM_A.search(line) or DEFM_B.search(line); cur=("T:"+mm.group(1)) if mm else None; dt=None
        elif ls.startswith("(defstate"):
            mm=DEFSTATE.search(line); cur=("T:"+mm.group(1)) if mm else None; dt=None
        elif ls.startswith("(defbehavior"):
            mm=DEFBEH.search(line); cur=("T:"+mm.group(1)) if mm else None; dt=None
        elif ls.startswith("(defun"):
            mm=DEFUN.search(line); cur=("F:"+mm.group(1)) if mm else None; dt=None
        t=toks(line); i=0
        while i<len(t):
            tok=t[i]
            if tok=="(" and i+1<len(t):
                ctx_calls[cur].add(t[i+1]) if cur else None
            if ACCESSOR.match(tok): pend=10; ptyp=cur
            elif pend>0:
                sm=SYM.match(tok)
                if sm and sm.group(1) not in ("static","process","entity","exact","interp"):
                    if ptyp:
                        (direct[ptyp[2:]] if ptyp.startswith("T:") else fn_lumps[ptyp[2:]]).add(sm.group(1))
                    pend=0
                else: pend-=1
            i+=1
for f in GOAL.rglob("*.gc"): scan(f)
# transitive closure of fn lumps via fn->fn calls
for _ in range(3):
    for fn in list(fn_lumps):
        for callee in ctx_calls.get("F:"+fn,()):
            if callee in fn_lumps: fn_lumps[fn]|=fn_lumps[callee]
# only propagate from SPECIFIC helpers (called by <=3 distinct types) to avoid
# generic utilities (e.g. spline/math helpers reading 'exact/'interp) bleeding in
type_callers=defaultdict(set)
for ctx,calls in ctx_calls.items():
    if ctx and ctx.startswith("T:"):
        for callee in calls:
            if callee in fn_lumps: type_callers[callee].add(ctx[2:])
for callee,typs in type_callers.items():
    if len(typs)<=3:
        for tp in typs: direct[tp]|=fn_lumps[callee]
readers=set(direct)
def anc(t):
    s=set()
    while t in parent and t not in s: s.add(t); t=parent[t]; yield t
def eff(t,d=0):
    o=set(direct.get(t,()))
    for a in anc(t): o|=direct.get(a,set())
    if d<3:
        for _f,ft in fields.get(t,[]):
            if ft in readers and ft!=t: o|=eff(ft,d+1)
    return o
txt=re.sub(r"/\*.*?\*/","",DB.read_text(),flags=re.S); db=json.loads(re.sub(r"(?m)//.*$","",txt)); actors=db.get("Actors",[])
def db_keys(a):
    k={l.get("key") for l in a.get("lumps",[])}; k|={f["lump"]["key"] for f in a.get("fields",[]) if isinstance(f.get("lump"),dict) and f["lump"].get("key")}; k|={s["lump_key"] for s in a.get("link_slots",[]) if s.get("lump_key")}
    return {x for x in k if x}
freq=defaultdict(int)
for a in actors:
    for l in eff(a.get("etype")): freq[l]+=1
COMMON={l for l,c in freq.items() if c>=int(0.50*len(actors))} | {"joint-channel","light-index","options","shadow-mask","texture-bucket","nav-max-users","name","trans","trans-offset"}
for et in ("crate","steam-cap","fuel-cell","swingpole","plat","launcher"):
    print(f"{et:12s}",sorted(eff(et)))
by_cat=defaultdict(list)
for a in actors: by_cat[a.get("category","Uncategorised")].append(a)
out=["# Jak 1 Actor Lump & Settings — Master Reference",""]
out.append(f"Auto-generated {date.today().isoformat()} from OpenGOAL `jak-project` jak1 source ({len(actors)} actors). "
 "Lumps the engine reads, derived from every `res-lump-*` / `get-property-*` / `lookup-tag-idx` call across methods, "
 "states, behaviours, called helper functions, the `:parent` chain, and embedded param-loaders (e.g. `sync-info`).")
out+=["","**Legend** — `key` = read & in DB · **`key`** = read but MISSING from DB · "
 "`_DB-only_` = in DB but not seen in source (stale, *or* read by a generic subsystem like the fact/entity system rather than actor code).",""]
out.append(f"> **Common lumps** (read by \u226550% of actors, omitted per-row): {', '.join(sorted(COMMON))}"); out.append("")
for cat in sorted(by_cat):
    out+=[f"## {cat}","","| Actor (etype) | Label | Specific lumps |","|---|---|---|"]
    for a in sorted(by_cat[cat], key=lambda x:x.get("etype","")):
        et=a.get("etype"); src=eff(et); dbk=db_keys(a); spec=sorted(src-COMMON)
        cells=[(f"**{k}**" if k not in dbk else k) for k in spec]; only=sorted(set(dbk)-src-COMMON)
        cell=", ".join(cells) if cells else "*(common only)*"
        if only: cell+=f" \u00b7 _DB-only: {', '.join(only)}_"
        out.append(f"| `{et}` | {a.get('label',et)} | {cell} |")
    out.append("")
Path("ACTOR-LUMP-MASTER.md").write_text("\n".join(out)); print("lines:",len(out))
