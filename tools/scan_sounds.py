"""Which sounds each actor's code plays, from the game's goal_src.

Per top-level form the owner type is found (defstate / defmethod /
defbehavior / deftype); defuns have no owner but their sounds go to the
types whose code calls them (transitively). Particle sounds (sp-sound in a
defpart) go to the types that launch the part group (*part-group-id-table* N
-> defpartgroup :id N -> its sp-items -> defpart ids). A type also plays the
sounds of its parent types (their states / methods run for it).
Output: sounds_by_type.json  {type: [sound, ...]}.
"""
import json, os, re, sys
from collections import defaultdict

SRC = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\John\Documents\JakAndDaxter\test-modbase\data\goal_src\jak1"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds_by_type.json")

TOK = re.compile(r"""\s+|;[^\n]*|\#\|.*?\|\#|"(?:\\.|[^"\\])*"|[()]|'|[^\s()";']+""", re.S)


def read(text):
    stack = [[]]
    for m in TOK.finditer(text):
        t = m.group(0)
        if t[0].isspace() or t[0] == ";" or t.startswith("#|") or t == "'":
            continue
        if t == "(":
            stack.append([])
        elif t == ")":
            if len(stack) > 1:
                f = stack.pop(); stack[-1].append(f)
        else:
            stack[-1].append(t)
    return stack[0]


def walk(f):
    yield f
    if isinstance(f, list):
        for x in f:
            yield from walk(x)


def s(x):
    return x[1:-1] if isinstance(x, str) and x.startswith('"') else None


def sounds_in(form):
    out = set()
    for f in walk(form):
        if isinstance(f, list) and f and f[0] in ("sound-play", "static-sound-name", "static-sound-spec", "sound-play-by-name",
                                                 "string->sound-name") and len(f) > 1:
            v = s(f[1])
            if v:
                out.add(v.lower())
        if isinstance(f, list) and len(f) >= 3 and f[0] == "new" and "ambient-sound" in [str(x) for x in f[:3]]:
            for x in f[3:]:
                v = s(x)
                if v:
                    out.add(v.lower())
    return out


def owner(form):
    if not isinstance(form, list) or len(form) < 3:
        return None
    h = form[0]
    if h == "defstate" and isinstance(form[2], list) and form[2]:
        return form[2][0]
    if h == "defmethod":
        a = form[2]
        if isinstance(a, list) and a and isinstance(a[0], list) and len(a[0]) == 2:
            return a[0][1]
        if isinstance(a, str):
            return a
    if h == "defbehavior" and isinstance(form[2], str):
        return form[2]
    if h == "deftype":
        return form[1]
    return None


parent, tsounds, tcalls = {}, defaultdict(set), defaultdict(set)
fsounds, fcalls = defaultdict(set), defaultdict(set)
part_sounds, group_parts, tgroups = defaultdict(set), defaultdict(set), defaultdict(set)
fgroups = defaultdict(set)
names_defined = set()

files = []
for root, _d, fs in os.walk(SRC):
    for fn in fs:
        if fn.endswith(".gc"):
            files.append(os.path.join(root, fn))
for p in files:
    try:
        forms = read(open(p, encoding="utf-8", errors="replace").read())
    except RecursionError:
        continue
    for f in forms:
        if not isinstance(f, list) or not f:
            continue
        h = f[0]
        if h == "deftype" and len(f) > 2 and isinstance(f[2], list) and f[2]:
            parent[f[1]] = f[2][0]
        if h == "defpart" and len(f) > 1:
            part_sounds[f[1]] |= sounds_in(f)
            continue
        if h == "defpartgroup":
            gid = None
            for i, x in enumerate(f):
                if x == ":id" and i + 1 < len(f):
                    gid = f[i + 1]
            for x in walk(f):
                if isinstance(x, list) and x and x[0] == "sp-item" and len(x) > 1:
                    group_parts[gid].add(x[1])
            continue
        groups = {x[2] for x in walk(f) if isinstance(x, list) and len(x) == 3 and x[0] == "->" and x[1] == "*part-group-id-table*"}
        calls = {x[0] for x in walk(f) if isinstance(x, list) and x and isinstance(x[0], str)}
        calls |= {x for x in walk(f) if isinstance(x, str) and not x.startswith(('"', ":"))}   # behaviours passed as values (go / run-function)
        snd = sounds_in(f)
        o = owner(f)
        if o:
            tsounds[o] |= snd; tcalls[o] |= calls; tgroups[o] |= groups
        elif h in ("defun", "defun-debug") and len(f) > 1:
            fsounds[f[1]] |= snd; fcalls[f[1]] |= calls; fgroups[f[1]] |= groups
            names_defined.add(f[1])

# defbehavior names are also callable: their owner already got their sounds; a
# state's code calls helpers -> follow defuns transitively
def via_funcs(calls, seen):
    out, gr = set(), set()
    for c in calls:
        if c in fsounds and c not in seen:
            seen.add(c)
            out |= fsounds[c]; gr |= fgroups[c]
            a, b = via_funcs(fcalls[c], seen)
            out |= a; gr |= b
    return out, gr


def own(t):
    a, gr = via_funcs(tcalls[t], set())
    snd = set(tsounds[t]) | a
    for g in tgroups[t] | gr:
        for pid in group_parts.get(g, ()):
            snd |= part_sounds.get(pid, set())
    return snd


ROOTS = {"process", "process-drawable", "process-hidden", "basic", "structure", "object"}   # engine roots: their code isn't the actor's
result = {}
for t in set(tsounds) | set(parent):
    snd, cur, seen = set(), t, set()
    while cur and cur not in seen and cur not in ROOTS:
        seen.add(cur)
        snd |= own(cur)
        cur = parent.get(cur)
    if snd:
        result[t] = sorted(snd)
json.dump(result, open(OUT, "w"), indent=1, sort_keys=True)
print(len(files), "files,", len(result), "types with sounds ->", OUT)
for t in ("babak", "sage", "swamp-bat", "junglesnake", "crate", "launcher", "sharkey"):
    print(t, result.get(t))
