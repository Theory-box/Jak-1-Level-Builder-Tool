"""Custom moods and mood functions (Moods tab) -> GOAL, compiled into GAME.CGO.

- goal_src/jak1/levels/level-tools/lt-moods-<group>.gc: every exported mood: its fog /
  lights / sun tables, hour tables and the mood-context (*<name>*), with light kits 1-7
- lt-mood-funcs-<group>.gc: every exported mood function (update-mood-<name>)
The game looks a level's mood / mood function up when the level starts loading, so they
must be in GAME.CGO (registered in game.gp + dgos/game.gd, like the tasks file). Files are
only written when they change.
"""
from __future__ import annotations

from .paths import _goal_src, _game_gp, log
from .fileio import write_if_changed, rewrite, patch

LT_DIR = "levels/level-tools"
_TAG = "; og-level-tools"
_DGO_GAME = ("dgos", "game.gd")


def _f(x):
    s = f"{float(x):.4f}".rstrip("0")
    return s + "0" if s.endswith(".") else s


def _vec(x, y, z, w):
    return f"(new 'static 'vector :x {_f(x)} :y {_f(y)} :z {_f(z)} :w {_f(w)})"


# ── hour (interp) tables ───────────────────────────────────────────────────

def timeline_rows(m):
    """24 rows (slot 1, slot 2, morph start, morph end) from the mood's timeline:
    between two slots' hours the light goes from one to the next."""
    from ..moods import _fill
    _fill(m)
    if m.time_preset == "fixed":
        s = m.fixed_slot
        return [(s, s, 0.0, 0.0)] * 24
    peaks = sorted((t.hour, i) for i, t in enumerate(m.times) if t.enabled)
    if not peaks:
        return [(0, 0, 0.0, 0.0)] * 24
    if len(peaks) == 1:
        return [(peaks[0][1], peaks[0][1], 0.0, 0.0)] * 24
    rows = []
    for h in range(24):
        prev = max((p for p in peaks if p[0] <= h), default=peaks[-1])
        k = peaks.index(prev)
        nxt = peaks[(k + 1) % len(peaks)]
        gap = (nxt[0] - prev[0]) % 24 or 24      # hours from this slot's peak to the next one
        since = (h - prev[0]) % 24                 # hours past the peak at the start of hour h
        rows.append((prev[1], nxt[1], round(since / gap, 4), round(min(1.0, (since + 1) / gap), 4)))
    return rows


def _interp_gc(sym, rows):
    lines = [f"(define {sym}", "  (new 'static 'sky-color-day :hour", "    (new 'static 'inline-array sky-color-hour 24"]
    for s1, s2, a, b in rows:
        lines.append(f"      (new 'static 'sky-color-hour :snapshot1 {s1} :snapshot2 {s2} :morph-start {_f(a)} :morph-end {_f(b)})")
    lines[-1] += ")))"
    return lines


# ── tables ─────────────────────────────────────────────────────────────────

def _fog_entry(e, got):
    if not e.enabled:
        return "(new 'static 'mood-fog)"
    c, r = got.get("fog", e.color), e.erase
    return ("(new 'static 'mood-fog"
            f" :fog-color {_vec(c[0] * 255, c[1] * 255, c[2] * 255, 128)}"
            f" :fog-dists {_vec(e.start * 4096, e.end * 4096, e.clear_start, e.clear_end)}"
            f" :erase-color {_vec(r[0] * 255, r[1] * 255, r[2] * 255, 128)})")


def _light_entry(e, got):
    if not e.enabled:
        return "(new 'static 'mood-lights)"
    from ..moods import blender_to_game_dir
    import math
    d = blender_to_game_dir(got.get("dir", e.direction))
    n = math.sqrt(sum(x * x for x in d)) or 1.0
    d = [x / n for x in d]
    p = (0.0, 0.0, 0.0) if e.prt_auto else e.prt_color
    return ("(new 'static 'mood-lights"
            f" :direction {_vec(d[0], d[1], d[2], 0)}"
            f" :lgt-color {_vec(*got.get('color', e.color), 1)}"
            f" :prt-color {_vec(*p, 1)}"
            f" :amb-color {_vec(*got.get('ambient', e.ambient), 1)}"
            f" :shadow {_vec(d[0], d[1], d[2], 0)})")


def _sun_entry(e, got):
    if not e.enabled:
        return "(new 'static 'mood-sun)"
    s, v = got.get("sun", e.sun), e.env
    return ("(new 'static 'mood-sun"
            f" :sun-color {_vec(s[0] * 255, s[1] * 255, s[2] * 255, 128)}"
            f" :env-color {_vec(v[0] * 255, v[1] * 255, v[2] * 255, 255)})")


def _table_sym(m, kind, seen=()):
    """The table the mood uses: its own (custom), a vanilla one, or another mood's (followed
    to where that one's comes from)."""
    import bpy
    from ..moods import clean, table_source
    src = table_source(m, kind)
    if src.startswith("vanilla:"):
        return f"*{src[8:]}-mood-{kind}-table*"
    if src.startswith("mood:"):
        o = next((x for x in bpy.context.scene.og_moods if x.name == src[5:]), None)
        if o is not None and o.name not in seen:
            return _table_sym(o, kind, seen + (m.name,))
        return f"*{clean(src[5:])}-{kind}-table*"
    return f"*{clean(m.name)}-{kind}-table*"


def mood_gc(m, scene=None):
    """Match level lighting reads the level's Time of day suns / worlds here, at every export."""
    import bpy
    from ..moods import clean, _fill, level_lighting, table_source
    _fill(m)
    n = clean(m.name)
    ov = [g or {} for g in level_lighting(m, scene or bpy.context.scene)]
    if not m.match_fog:
        ov = [{k: v for k, v in g.items() if k != "fog"} for g in ov]
    out = ["", f";; ---- mood *{n}* ----"]
    if m.match_level:
        out.append(f";; lights / sun{' / fog colour' if m.match_fog else ''} from the level's Time of day suns and worlds")
    for kind, entry in (("fog", _fog_entry), ("lights", _light_entry), ("sun", _sun_entry)):
        if table_source(m, kind) != "custom":
            continue
        typ = {"fog": "mood-fog", "lights": "mood-lights", "sun": "mood-sun"}[kind]
        out += [f"(define *{n}-{kind}-table*", f"  (new 'static '{typ}-table :data", f"    (new 'static 'inline-array {typ} 8"]
        out += [f"      {entry(e, got)}" for e, got in zip(getattr(m, kind), ov)]
        out[-1] += ")))"
        if kind == "lights":                     # shadows from the directions (the game's 65 degree clamp)
            out.append(f"(dotimes (i 8) (update-mood-shadow-direction (-> *{n}-lights-table* data i)))")
    interps = {}
    for prop in ("fog_interp", "palette_interp", "sky_interp"):
        v = getattr(m, prop)
        if v.startswith("vanilla:"):
            interps[prop] = f"*{v[8:]}*"
        else:
            interps[prop] = f"*{n}-hours*"
    if "timeline" in (m.fog_interp, m.palette_interp, m.sky_interp):
        out += _interp_gc(f"*{n}-hours*", timeline_rows(m))
    out += [f"(define *{n}* (new 'global 'mood-context))",
            f"(set! (-> *{n}* mood-fog-table) {_table_sym(m, 'fog')})",
            f"(set! (-> *{n}* mood-lights-table) {_table_sym(m, 'lights')})",
            f"(set! (-> *{n}* mood-sun-table) {_table_sym(m, 'sun')})",
            f"(set! (-> *{n}* fog-interp) {interps['fog_interp']})",
            f"(set! (-> *{n}* palette-interp) {interps['palette_interp']})",
            f"(set! (-> *{n}* sky-texture-interp) {interps['sky_interp']})",
            f"(set! (-> *{n}* num-stars) {_f(m.num_stars)})",
            ";; light kits 1-7 (some NPCs light themselves with one): the generic kit",
            f"(dotimes (i 7) (make-light-kit (-> *{n}* light-group (+ i 1)) 0.0 1.0 1.0 1.0))"]
    return out


# ── mood function effects ──────────────────────────────────────────────────
# Effects run on seconds of game time (`now`, stops when paused), so they are the same speed
# at any frame rate and two calls in one frame (two levels using the function) change nothing.
# Their state is in globals named after the function and the effect's place in the list.

def _fx_globals(e, p):
    k = e.kind
    if k == "flicker":
        return [f"(define *{p}-start* 0.0)", f"(define *{p}-len* 0.0)", f"(define *{p}-height* 0.0)",
                f"(define *{p}-index* 0)"]
    if k == "lava":
        return [f"(define *{p}-scale* (new 'static 'vector :x 1.5 :y 1.5 :z 1.5 :w 1.5))", f"(define *{p}-last* 0)"]
    return []


def _wave(e, u):
    """0..1 wave of `u` (a GOAL expression, in periods)."""
    if e.shape == "triangle":
        return f"(let ((fr (- {u} (the float (the int {u}))))) (- 1.0 (fabs (+ -1.0 (* 2.0 fr)))))"
    if e.shape == "wander":
        return (f"(fmax 0.0 (fmin 1.0 (+ 0.5 (* 0.3 (sin (* 65536.0 {u}))) "
                f"(* 0.2 (sin (* 65536.0 (+ 0.25 (* 2.618 {u}))))))))")
    return f"(+ 0.5 (* 0.5 (sin (* 65536.0 {u}))))"


def _fog_fx(e):
    if e.kind == "fog_pitch":
        c = e.color
        return ["  ;; fog by camera pitch: looking up, toward the colour and clearer",
                "  (let ((up (fmax 0.0 (-> *math-camera* camera-rot vector 1 z)))",
                "        (col (new 'stack-no-clear 'vector)))",
                f"    (set-vector! col {_f(c[0] * 255)} {_f(c[1] * 255)} {_f(c[2] * 255)} 128.0)",
                f"    (vector4-lerp! (the-as vector (-> arg0 current-fog)) (the-as vector (-> arg0 current-fog)) col (* {_f(e.amount)} up))",
                f"    (+! (-> arg0 current-fog fog-dists w) (* {_f(e.clear)} up (- 255.0 (-> arg0 current-fog fog-dists w)))))"]
    if e.kind == "fog_breath":
        w = _wave(e, f"(/ now {_f(e.period)})")
        return ["  ;; fog breathing",
                f"  (let ((k (+ {_f(e.dist_min)} (* {_f(e.dist_max - e.dist_min)} {w}))))",
                "    (set! (-> arg0 current-fog fog-start) (* k (-> arg0 current-fog fog-start)))",
                "    (set! (-> arg0 current-fog fog-end) (* k (-> arg0 current-fog fog-end))))"]
    return []


def _slot_fx(e, p, state):
    k, s = e.kind, e.slot
    if k == "flicker":
        n = e.count
        return [f"  ;; flicker slots {s}-{s + n - 1}",
                f"  (dotimes (i {n}) (set! (-> arg0 times (+ {s} i) w) {_f(e.base)}))",
                f"  (when (>= now (+ *{p}-start* *{p}-len*))",
                f"    (set! *{p}-start* now)",
                f"    (set! *{p}-len* (/ (rand-vu-float-range 0.1167 0.25) {_f(e.speed)}))",
                f"    (set! *{p}-height* (rand-vu-float-range 0.0 1.0))",
                f"    (set! *{p}-index* (the int (rand-vu-float-range 0.0 {_f(n - 0.01)}))))",
                f"  (set! (-> arg0 times (+ {s} *{p}-index*) w)",
                f"        (+ {_f(e.base)} (* {_f(e.strength)} *{p}-height* (sin (* 32768.0 (fmin 1.0 (/ (- now *{p}-start*) *{p}-len*)))))))"]
    if k == "pulse":
        v = f"(+ {_f(e.base)} (* {_f(e.strength)} (cos (* 65536.0 (+ {_f(e.phase)} (/ now {_f(e.period)}))))))"
        if e.night_only:                     # on 19:00-7:00, an hour's fade each side
            v = f"(* (fmax 0.0 (fmin 1.0 (+ -5.0 (fabs (+ -13.0 arg1))))) {v})"
        return [f"  ;; pulse slot {s}", f"  (set! (-> arg0 times {s} w) {v})"]
    if k == "lightning":
        return [f"  ;; lightning: sky slots {e.sky_slot}+, palette slots {s}+",
                f"  (update-mood-lightning arg0 {e.sky_slot} {e.count} {state} {s} 0.5 {'#t' if e.quiet else '#f'})"]
    if k == "lava":
        c = e.color
        out = [f"  ;; lava glow (from below on actors)",
               "  (let ((l (-> arg0 light-group 0 dir2)))",
               "    (set-vector! (-> l direction) 0.0 -1.0 0.0 0.0)",
               f"    (set-vector! (-> l color) {_f(c[0])} {_f(c[1])} {_f(c[2])} 1.0)",
               f"    (set! (-> l levels x) (* {_f(e.strength)} (+ 0.875 (* 0.075 (sin (* 65536.0 {_f(3.1 * e.speed)} now)))"
               f" (* 0.05 (sin (* 65536.0 {_f(7.3 * e.speed)} now)))))))"]
        if e.drive_slots:
            out += [f"  (let* ((u (* now {_f(3.75 * e.speed)})) (k (logand (the int u) 3)) (p (logand (+ k 3) 3))",
                    "         (fr (- u (the float (the int u)))))",
                    f"    (when (!= k *{p}-last*) (set! (-> *{p}-scale* data k) (rand-vu-float-range 1.0 2.0)) (set! *{p}-last* k))",
                    f"    (set! (-> arg0 times (+ {s} k) w) (* fr (-> *{p}-scale* data k)))",
                    f"    (set! (-> arg0 times (+ {s} p) w) (* (- 1.0 fr) (-> *{p}-scale* data p))))"]
        return out
    if k == "caustics":
        return [f"  ;; caustics slots {s}-{s + 3}",
                f"  (let* ((u (* now {_f(7.5 * e.speed)})) (k (logand (the int u) 3)) (fr (- u (the float (the int u)))))",
                f"    (set! (-> arg0 times (+ {s} (logand (+ k 3) 3)) w) (- 1.0 fr))",
                f"    (set! (-> arg0 times (+ {s} k) w) fr))"]
    if k == "actor":
        return [f"  ;; slot {s} follows its palette fade control (Light switch, crystals ...)",
                f"  (set! (-> arg0 times {s} w) (-> *palette-fade-controls* control {s} fade))"]
    return []


def _time_fx(f, n):
    if f.time_mode == "lock":
        return [f"  (set! arg1 {_f(f.lock_hour)}) ; lock time"]
    if f.time_mode != "speed":
        return []
    c = f"*{n}-clock"
    return ["  ;; time speed: this level's own clock, following the game's clock's steps x speed",
            "  (let ((tnow (current-time)))",
            f"    (if (or (zero? {c}-last*) (< (seconds 0.2) (- tnow {c}-last*)))",
            f"        (set! {c}* arg1)",
            f"        (let ((d (- arg1 {c}-game*)))",
            "          (if (< d -12.0) (+! d 24.0))",
            "          (if (< 12.0 d) (+! d -24.0))",
            f"          (+! {c}* (* d {_f(f.time_speed)}))",
            f"          (while (>= {c}* 24.0) (+! {c}* -24.0))",
            f"          (while (< {c}* 0.0) (+! {c}* 24.0))))",
            f"    (set! {c}-game* arg1)",
            f"    (set! {c}-last* tnow))",
            f"  (set! arg1 {c}*)"]


def func_gc(f):
    from ..moods import clean
    n = clean(f.name)
    fx = [(e, f"{n}-fx{j}") for j, e in enumerate(f.effects) if e.enabled]
    out = ["", f";; ---- mood function update-mood-{n} ----"]
    if f.time_mode == "speed":
        out += [f"(define *{n}-clock* 0.0)", f"(define *{n}-clock-game* 0.0)", f"(define *{n}-clock-last* (the-as time-frame 0))"]
    for e, p in fx:
        out += _fx_globals(e, p)
    fog = [x for e, p in fx for x in _fog_fx(e)]
    slots, state = [], 0
    # lightning first: it clears the actors' effect light (dir2) that lava glow sets
    for e, p in sorted(fx, key=lambda x: x[0].kind != "lightning"):
        slots += _slot_fx(e, p, state)
        state += e.kind == "lightning"           # 1 byte of the mood's effect state each
    body = [f"(defun update-mood-{n} ((arg0 mood-context) (arg1 float) (arg2 int))"]
    body += _time_fx(f, n)
    need_now = any(e.kind in ("flicker", "pulse", "lava", "caustics", "fog_breath") for e, _p in fx)
    ind = "  "
    if need_now:
        body.append("  (let ((now (* 0.0033333334 (the float (current-time))))) ; seconds of game time")
    blk = ["  (update-mood-fog arg0 arg1)"] + fog + [
        "  (update-mood-sky-texture arg0 arg1)",
        "  (clear-mood-times arg0)",
        "  (update-mood-palette arg0 arg1 arg2)"]
    # (not inside `when *time-of-day-effects*` like the game's functions: loading a custom level
    # turns that off, its bsp has no nodes)
    blk += slots
    blk += ["  ;; light kits 1-7 follow the time of day ambient",
            "  (dotimes (i 7) (update-light-kit (-> arg0 light-group (+ i 1)) (-> arg0 light-group 0 ambi) 1.0))",
            "  (update-mood-itimes arg0)"]
    if need_now:
        blk = [ind + x for x in blk]
        blk[-1] += ")"
    body += blk + ["  0", "  (none))"]
    return out + body


def _header(name, what):
    return [";;-*-Lisp-*-", "(in-package goal)",
            f";; {name}.gc -- written by OpenGOAL Level Tools from the .blend's {what} (Moods tab).",
            ";; Compiled into GAME.CGO: the game looks a level's mood up when the level starts loading."]


def _register(name):
    patch(_game_gp(), [f'(goal-src "{LT_DIR}/{name}.gc" "mood") {_TAG}'], '(group-list "all-code"', f"{name} goal-src")
    patch(_goal_src().joinpath(*_DGO_GAME), [f'  "{name}.o" {_TAG.replace(";", ";;", 1)}'], " ))", f"{name} object")


def _unregister(name):
    f = _goal_src() / LT_DIR / f"{name}.gc"
    if f.exists():
        f.unlink()
        log(f"Removed {f.name}")
    for p in (_game_gp(), _goal_src().joinpath(*_DGO_GAME)):
        if p.exists() and rewrite(p, lambda t: "".join(l for l in t.splitlines(True) if f"{name}." not in l)):
            log(f"Patched {p.name}: removed {name}")


def export_moods(scene):
    """Write this .blend's mood files (only what changed). Returns problems (nothing
    written when there are any) or []."""
    from .. import moods as M
    errs = [f"{'mood' if k == 'mood' else 'mood function'} {i + 1}: {t}" for k, i, t in M.problems(scene)]
    if errs:
        for e in errs:
            log(f"[moods] {e}")
        return errs
    g = M.group_name(scene)
    moods = [m for m in scene.og_moods if m.export]
    funcs = [f for f in scene.og_mood_funcs if f.export]
    for name, items, gen, what in ((f"lt-moods-{g}", moods, mood_gc, "moods"),
                                   (f"lt-mood-funcs-{g}", funcs, func_gc, "mood functions")):
        if not items:
            if (_goal_src() / LT_DIR / f"{name}.gc").exists():
                _unregister(name)
            continue
        lines = _header(name, what)
        for x in items:
            lines += gen(x, scene) if gen is mood_gc else gen(x)
        write_if_changed(_goal_src() / LT_DIR / f"{name}.gc", "\n".join(lines) + "\n")
        _register(name)
        log(f"[moods] {name}: {len(items)} {what}")
    return []
