# ---------------------------------------------------------------------------
# build.py — OpenGOAL Level Tools
# GOALC process management, build/play pipeline, port file helpers,
# background thread workers, and exe/data path utilities.
# ---------------------------------------------------------------------------

import bpy
import os, re, json, socket, subprocess, threading, time
from pathlib import Path
from .data import needed_tpages
from .collections import _get_level_prop, _level_objects, _active_level_col
from .export import (
    write_nav_gc, nav_system, tfl_nav_present,
    collect_actors, collect_ambients, collect_spawns, collect_cameras,
    collect_load_boundaries,
    collect_nav_mesh_geometry, collect_aggro_triggers, collect_custom_triggers, collect_task_triggers,
    needed_ags, needed_extras_ags, needed_code, write_jsonc, write_gd, write_gc,
    make_fog_actor_dict,
    patch_level_info, patch_load_boundaries, patch_game_gp, export_glb,
    prune_orphaned_levels,
    _collect_navmesh_actors, _canonical_actor_objects,
    _nick, _iso, _lname, _ldir, _goal_src, _level_info,
    _game_gp, _levels_dir, _entity_gc, _load_boundary_data,
    _clean_orphaned_vol_links, _vol_links,
    _navmesh_to_goal, log,
)

# PATH HELPERS
# ---------------------------------------------------------------------------

import sys as _sys
_EXE = ".exe" if _sys.platform == "win32" else ""   # platform-aware exe extension

GOALC_PORT    = 8181   # runtime default; updated by launch_goalc() and _load_port_file()
GOALC_TIMEOUT = 120

import tempfile as _tempfile
_PORT_FILE = Path(_tempfile.gettempdir()) / "opengoal_blender_goalc.port"

def _save_port_file(port):
    try:
        _PORT_FILE.write_text(str(port))
    except Exception:
        pass

def _load_port_file():
    """Read port from previous launch. Only applies if goalc is still running."""
    global GOALC_PORT
    try:
        if _PORT_FILE.exists() and _process_running(f"goalc{_EXE}"):
            port = int(_PORT_FILE.read_text().strip())
            if 1024 <= port <= 65535:
                GOALC_PORT = port
                log(f"[nREPL] restored port {port} from port file")
    except Exception:
        pass

def _delete_port_file():
    try:
        _PORT_FILE.unlink(missing_ok=True)
    except Exception:
        pass

def _find_free_nrepl_port():
    """Ask the OS for a free port — guaranteed to work on any machine.
    Binds to port 0 (OS assigns a free one), records it, releases it,
    then passes it to GOALC via --port. No scanning, no timeouts.
    """
    import socket as _socket
    with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    log(f"[nREPL] OS-assigned free port: {port}")
    return port

def _strip(p): return p.strip().rstrip("\\").rstrip("/")

# Folder resolution lives in paths_core (one resolver for build + export,
# honouring this .blend's Project Folders, then preferences). These names are
# kept because they're imported all over the addon.
from . import paths_core as _pc


def _exe_root():
    return _pc.exe_root()

def _data_root():
    return _pc.data_root()

def _scan_for_installs(root: Path, max_depth: int = 4):
    return _pc.scan_for_installs(root, max_depth)

def _gk():         return _exe_root() / f"gk{_EXE}"
def _goalc():      return _exe_root() / f"goalc{_EXE}"

def _data() -> Path:
    """Effective data folder: dev clone root (has goal_src/jak1) as-is,
    release install -> <root>/data. See paths_core.data()."""
    return _pc.data()

def _decompiler_path() -> Path:
    """decompiler_out/jak1/ (Project Folders / preference override, else
    <data>/decompiler_out/jak1). Holds textures/ and ripped level glbs."""
    return _pc.decompiler_path()


def _apply_engine_patches():
    """Apply required engine source patches to vol-h.gc if not already applied.
    These fix vol-control lookup for custom levels (vanilla uses 'exact 0.0 but
    custom level builder stores tags at DEFAULT_RES_TIME = -1e9).
    Safe for vanilla levels — 'base ignores timestamp, finds by name only.

    TODO: NEEDS LIVE TEST — confirm vol-h.gc is found and patched correctly
    on a fresh jak-project install. Verify water volumes still work after
    a clean recompile triggered by this patch.
    """
    patched = []
    vol_h = _data() / "goal_src" / "jak1" / "engine" / "geometry" / "vol-h.gc"
    if not vol_h.exists():
        return patched
    text = vol_h.read_text(encoding="utf-8")
    new_text = text
    new_text = new_text.replace(
        "(method-of-type res-lump lookup-tag-idx) (the-as entity-actor s5-1) 'vol 'exact 0.0",
        "(method-of-type res-lump lookup-tag-idx) (the-as entity-actor s5-1) 'vol 'base 0.0"
    )
    new_text = new_text.replace(
        "(method-of-type res-lump lookup-tag-idx) (the-as entity-actor s5-2) 'cutoutvol 'exact 0.0",
        "(method-of-type res-lump lookup-tag-idx) (the-as entity-actor s5-2) 'cutoutvol 'base 0.0"
    )
    if new_text != text:
        vol_h.write_text(new_text, encoding="utf-8")
        patched.append("vol-h.gc")
        log("  [patch] vol-h.gc patched: 'exact -> 'base for vol-control lookup")
    return patched



# ---------------------------------------------------------------------------
# AUDIO ENUMS
# ---------------------------------------------------------------------------




def _process_running(exe_name):
    try:
        if os.name == "nt":
            r = subprocess.run(["tasklist", "/fi", f"imagename eq {exe_name}"],
                               capture_output=True, text=True)
            return exe_name.lower() in r.stdout.lower()
        else:
            r = subprocess.run(["pgrep", "-f", exe_name], capture_output=True, text=True)
            return bool(r.stdout.strip())
    except Exception:
        return False

def _kill_process(exe_name):
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/f", "/im", exe_name], capture_output=True)
        else:
            subprocess.run(["pkill", "-f", exe_name], capture_output=True)
        time.sleep(0.8)
    except Exception:
        pass

def kill_gk():
    _kill_process(f"gk{_EXE}")
    time.sleep(0.5)

def kill_goalc():
    killed_port = GOALC_PORT   # snapshot before kill — GOALC_PORT may update later
    _delete_port_file()
    _kill_process(f"goalc{_EXE}")
    time.sleep(0.5)
    # On Windows, SO_EXCLUSIVEADDRUSE holds the port until fully released.
    # Poll until the port is free so the next launch_goalc() doesn't get
    # "nREPL: DISABLED". Use 127.0.0.1 explicitly — localhost may resolve
    # to ::1 (IPv6) on Windows, causing timeouts instead of clean refusals.
    for _ in range(20):
        try:
            with socket.create_connection(("127.0.0.1", killed_port), timeout=0.3):
                pass
            time.sleep(0.3)  # port still held, keep waiting
        except (ConnectionRefusedError, OSError):
            break  # port is free
# ---------------------------------------------------------------------------
# GOALC / nREPL
# ---------------------------------------------------------------------------

def goalc_send(cmd, timeout=GOALC_TIMEOUT):
    """Send a GOAL expression to the nREPL server and return the response.

    Wire format (from common/repl/nrepl/ReplClient.cpp):
      [u32 length LE][u32 type=10 LE][utf-8 string]
    Sending raw text causes "Bad message, aborting the read" errors.
    """
    import struct
    EVAL_TYPE = 10
    try:
        with socket.create_connection(("127.0.0.1", GOALC_PORT), timeout=10) as s:
            encoded = cmd.encode("utf-8")
            header = struct.pack("<II", len(encoded), EVAL_TYPE)
            s.sendall(header + encoded)
            chunks = []
            s.settimeout(timeout)
            while True:
                try:
                    c = s.recv(4096)
                    if not c: break
                    chunks.append(c)
                    if b"g >" in c or b"g  >" in c: break
                except socket.timeout: break
            return b"".join(chunks).decode(errors="replace")
    except ConnectionRefusedError: return None
    except Exception as e: return f"ERROR:{e}"

def _nrepl_up():
    """GOALC's nREPL is on GOALC_PORT: it greets each connection ("Connected
    to OpenGOAL ... nREPL!"), then never answers evals. Another program on
    the port (e.g. 3Dconnexion takes 8181) doesn't greet like that."""
    try:
        with socket.create_connection(("127.0.0.1", GOALC_PORT), timeout=2) as s:
            s.settimeout(2)
            data = b""
            while b"nREPL" not in data and len(data) < 512:
                c = s.recv(256)
                if not c:
                    break
                data += c
            return b"nREPL" in data
    except OSError:
        return False


def goalc_ok():
    """Return True if GOALC's nREPL is reachable on GOALC_PORT.

    On first miss, tries to restore GOALC_PORT from the port file written
    by launch_goalc() — this handles the case where GOALC was already running
    when Blender started (e.g. from a previous session).
    """
    if _nrepl_up():
        return True
    # Fast path missed. Try restoring port from file (written at launch time).
    _load_port_file()
    return _nrepl_up()


GOALC_COMPILE_TIMEOUT = 3600


_COMPILE_ERRORS = ("Compilation Error", "Build failed", "REPL Error", "[die]")


def _newest_compiler_log():
    logs = sorted((_data() / "log").glob("compiler*.log"), key=lambda p: p.stat().st_mtime_ns)
    return logs[-1] if logs else None


def goalc_run(cmd, timeout=GOALC_COMPILE_TIMEOUT):
    """Run cmd in GOALC and wait for it to end: "done", "failed" (an error in
    GOALC's log) or None (GOALC not reachable / closed / timed out). The
    nREPL never sends results back, so cmd is followed by compiling a tiny
    marker file: its .o being written means cmd is done."""
    src = _user_dir() / "og-done.gc"
    if not src.exists():
        src.write_text(";; Auto-generated by OpenGOAL Tools: marks the end of a build\n(none)\n")
    outs = [_data() / "out" / "jak1" / "obj" / "og-done.o", _data() / "out" / "obj" / "og-done.o"]
    def stamp():
        return max((p.stat().st_mtime_ns for p in outs if p.exists()), default=0)
    before = stamp()
    lg = _newest_compiler_log()
    pos = lg.stat().st_size if lg else 0
    # one message: one sent while GOALC is busy is lost if we hang up first
    rel = src.relative_to(_data()).as_posix()
    if goalc_send(f'(begin {cmd} (asm-file "{rel}" :color :write))', timeout=0.5) is None:
        return None
    t0 = time.time()
    n = 0
    seen = []                                # GOALC's log since cmd was sent

    def read_log():
        nonlocal pos
        if lg is None:
            return ""
        try:
            with open(lg, "rb") as f:
                f.seek(pos)
                raw = f.read()
            pos += len(raw)
            txt = raw.decode(errors="replace")
            seen.append(txt)
            return txt
        except OSError:
            return ""
    while time.time() - t0 < timeout:
        time.sleep(0.25)
        if stamp() > before:
            read_log()
            LAST_COMPILE["summary"] = _compile_summary("".join(seen), time.time() - t0)
            return "done"
        n += 1
        if n % 4:
            continue
        if any(e in read_log() for e in _COMPILE_ERRORS):   # an error stops cmd: no marker
            return "failed"
        if n % 40 == 0 and not _process_running(f"goalc{_EXE}"):   # GOALC closed
            return None
    return None


LAST_COMPILE = {"summary": ""}
# Launch Game clicked during a compile: launch once it's done (operators/build.py)
LAUNCH = {"pending": False}
_STEP_RE = re.compile(r"\[\s*\d+%\]\s*\[([a-z-]+)\s*\]\s*([\d.]+)\s+(\S+)")


def _compile_summary(text, seconds):
    """'3 of 1345 targets, 9.8 s (build-level unedtest 8.5 s, ...)' from
    GOALC's log of one (mi)."""
    text = re.sub(chr(27) + r"\[[0-9;]*m", "", text)   # colour codes
    m = re.search(r"Found that (\d+) of (\d+) targets", text)
    steps = sorted(((float(t), tool, Path(name).stem) for tool, t, name in _STEP_RE.findall(text)
                    if "og-done" not in name), reverse=True)
    slow = ", ".join(f"{tool} {name} {t:.1f}s" for t, tool, name in steps[:3] if t >= 0.5)
    head = f"{m.group(1)} of {m.group(2)} targets rebuilt" if m else "compiled"
    log(f"[build] {head} in {seconds:.1f}s" + (f" — slowest: {slow}" if slow else ""))
    return f"{head}, {seconds:.1f}s" + (f" ({slow})" if slow else "")


USER_NAME = "blender"

def _user_base(): return _data() / "goal_src" / "user"
def _user_dir():
    d = _user_base() / USER_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d

def write_startup_gc(commands):
    base = _user_base()
    base.mkdir(parents=True, exist_ok=True)
    (base / "user.txt").write_text(USER_NAME)
    udir = _user_dir()
    (udir / "user.gc").write_text(
        ";; Auto-generated by OpenGOAL Tools Blender addon\n"
        "(define-extern bg (function symbol int))\n"
        "(define-extern bg-custom (function symbol object))\n"
        "(define-extern *artist-all-visible* symbol)\n"
    )
    p = udir / "startup.gc"
    p.write_text("\n".join(commands) + "\n")
    log(f"Wrote startup.gc: {commands}")

def _restart_goalc_if_types_changed(state):
    """The level's -obs.gc changed a deftype (a subtype update, a new
    battlecontroller camera ...): a running GOALC would fail with
    "Inconsistent type definition", so kill it; the caller then launches a
    fresh one for (mi)."""
    from .export import writers as _w
    if _w.TYPES_CHANGED:
        _w.TYPES_CHANGED = False
        if goalc_ok():
            state["status"] = "Level types changed — restarting GOALC..."
            log("[build] level types changed — restarting GOALC")
            kill_goalc()
            time.sleep(0.5)


def launch_goalc(wait_for_nrepl=False):
    global GOALC_PORT
    exe = _goalc()
    if not exe.exists():
        return False, f"goalc not found at {exe}"
    # Caller is responsible for kill_goalc() + port-free wait before calling here.
    # Do NOT kill internally — it would reset the port-free polling the caller did.
    # Find a free port starting from the user-configured preference.
    GOALC_PORT = _find_free_nrepl_port()
    _save_port_file(GOALC_PORT)
    log(f"[nREPL] launching GOALC on port {GOALC_PORT}")
    try:
        data_dir = str(_data())
        cmd = [str(exe), "--user-auto", "--game", "jak1", "--proj-path", data_dir,
               "--port", str(GOALC_PORT)]
        if os.name == "nt":
            proc = subprocess.Popen(cmd, cwd=str(_exe_root()),
                                    creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            proc = subprocess.Popen(cmd, cwd=str(_exe_root()))
        log(f"launch_goalc: pid={proc.pid}")
        if wait_for_nrepl:
            for _ in range(60):
                time.sleep(0.5)
                if goalc_ok():
                    return True, "GOALC started with nREPL"
            return False, "GOALC started but nREPL not available"
        return True, f"GOALC launched (pid={proc.pid})"
    except Exception as e:
        return False, str(e)

def launch_gk():
    exe = _gk()
    if not exe.exists(): return False, f"Not found: {exe}"
    # Kill existing GK — no window stacking
    if _process_running(f"gk{_EXE}"):
        log("launch_gk: killing existing GK")
        kill_gk()
    try:
        data_dir = str(_data())
        subprocess.Popen([str(exe), "-v", "--game", "jak1",
                          "--proj-path", data_dir,
                          "--", "-boot", "-fakeiso", "-debug"],
                         cwd=str(_exe_root()))
        return True, "gk launched"
    except Exception as e:
        return False, str(e)



def validate_ambients(ambients):
    errors = []
    for i, a in enumerate(ambients):
        t = a.get("trans", [])
        b = a.get("bsphere", [])
        name = a.get("lump", {}).get("name", f"ambient[{i}]")
        if len(t) != 4:
            errors.append(f"{name}: ambient trans has {len(t)} elements, expected 4  (value={t})")
        if len(b) != 4:
            errors.append(f"{name}: ambient bsphere has {len(b)} elements, expected 4  (value={b})")
    return errors



_BUILD_STATE = {"done":False, "status":"", "error":None, "ok":False}



def patch_entity_gc(navmesh_actors, scene=None):
    """
    Patch engine/entity/entity.gc to add lt-aid-nav-setup (the current nav-mesh system).

    navmesh_actors: list of (actor_aid, mesh_data) tuples.

    Adds/replaces:
      1. A (defun lt-aid-nav-setup ...) with one case per actor.
      2. A call to it at the top of (defmethod birth! entity-actor ...).

    Safe to call repeatedly — old injected code is stripped before re-injecting.
    """
    from .export_filter import allowed as _allowed
    if not _allowed("navmesh", scene):   # scene: from the build thread (no bpy.context there)
        return None
    p = _entity_gc()
    if not p.exists():
        log(f"WARNING: entity.gc not found at {p}")
        return

    raw  = p.read_bytes()
    crlf = b"\r\n" in raw
    txt  = raw.decode("utf-8").replace("\r\n", "\n")

    # ── Strip any previously injected block ──────────────────────────────────
    import re
    # (with the blank line the insert below adds before birth!, or every build
    # would add a line: entity.gc changed = the engine recompiled from there)
    txt = re.sub(
        r"\n;; \[OpenGOAL Tools\] BEGIN custom-nav-mesh.*?;; \[OpenGOAL Tools\] END custom-nav-mesh\n\n?",
        "",
        txt,
        flags=re.DOTALL,
    )
    # switching systems (the other hook was in): a running GOALC won't compile it
    _had = ("custom" if "(lt-custom-nav-setup this)" in txt else
            "aid" if "(lt-aid-nav-setup this)" in txt else "")
    _want = "custom" if nav_system(scene) == "CUSTOM" else ("aid" if navmesh_actors else "")
    if _had and _want and _had != _want:
        from .export import writers as _w
        _w.TYPES_CHANGED = True
        log(f"[navmesh] nav-mesh system changed ({_had} -> {_want}): GOALC restarts")
    # Strip old birth! injection line (either system)
    txt = re.sub(r"  \((?:custom-nav-mesh-check-and-setup|lt-custom-nav-setup|lt-aid-nav-setup) this\)\n", "", txt)

    # custom-nav system: a fixed hook to lt-nav-mesh.gc's setup (the meshes are
    # in each level's -nav.gc), or nothing when TFL's own hook is installed
    if nav_system(scene) == "CUSTOM":
        if not tfl_nav_present():
            block = ("\n;; [OpenGOAL Tools] BEGIN custom-nav-mesh\n"
                     ";; custom-nav system: the setup is in levels/level-tools/lt-nav-mesh.gc\n"
                     "(define-extern lt-custom-nav-setup (function entity-actor none))\n"
                     ";; [OpenGOAL Tools] END custom-nav-mesh\n")
            BIRTH = "(defmethod birth! ((this entity-actor))"
            if BIRTH not in txt:
                log("WARNING: entity.gc birth! marker not found — cannot hook custom-nav")
                return
            txt = txt.replace(BIRTH, block + "\n" + BIRTH, 1)
            txt = txt.replace("  (let* ((entity-type (-> this etype))",
                              "  (lt-custom-nav-setup this)\n  (let* ((entity-type (-> this etype))", 1)
        out = txt.replace("\n", "\r\n") if crlf else txt
        if out.encode("utf-8") != raw:
            p.write_bytes(out.encode("utf-8"))
            log("Patched entity.gc: custom-nav hook" + (" (TFL's own hook used)" if tfl_nav_present() else ""))
        return

    if not navmesh_actors:
        # Nothing to inject — just clean file
        out = txt.replace("\n", "\r\n") if crlf else txt
        if out.encode("utf-8") != raw:
            p.write_bytes(out.encode("utf-8"))
            log("entity.gc: cleaned (no navmesh actors)")
        return

    # ── Build the defun block ─────────────────────────────────────────────────
    lines = [
        "",
        ";; [OpenGOAL Tools] BEGIN custom-nav-mesh",

        ";; own name: mod-base's entity.gc already has a custom-nav-mesh-check-and-setup",
        "(defun lt-aid-nav-setup ((this entity-actor))",
        "  (case (-> this aid)",
    ]
    for aid, mesh in navmesh_actors:
        lines.append(_navmesh_to_goal(mesh, aid))
    lines += [
        "  )",
        "  ;; the real login: user list (nav-max-users), line-of-sight routes and",
        "  ;; the actor's nav-mesh-sphere lump (like The Forgotten Lands)",
        "  (when (nonzero? (-> this nav-mesh))",
        "    (entity-nav-login this))",
        "  (none)",
        ")",
        ";; [OpenGOAL Tools] END custom-nav-mesh",
        "",
    ]
    inject_block = "\n".join(lines)

    # Insert before (defmethod birth! ((this entity-actor))
    BIRTH_MARKER = "(defmethod birth! ((this entity-actor))"
    if BIRTH_MARKER not in txt:
        log("WARNING: entity.gc birth! marker not found — cannot inject nav-mesh")
        return
    txt = txt.replace(BIRTH_MARKER, inject_block + "\n" + BIRTH_MARKER, 1)

    # ── Inject call at top of birth! body ────────────────────────────────────
    # Find the body start — line after "Create a process for this entity..."
    # We look for the first (let* ... after the birth! marker
    CALL_MARKER = "  (let* ((entity-type (-> this etype))"
    txt = txt.replace(
        CALL_MARKER,
        "  (lt-aid-nav-setup this)\n" + CALL_MARKER,
        1,
    )

    out = txt.replace("\n", "\r\n") if crlf else txt
    if out.encode("utf-8") == raw:
        log("Skipped entity.gc (unchanged)")
        return
    p.write_bytes(out.encode("utf-8"))
    log(f"Patched entity.gc with {len(navmesh_actors)} nav-mesh actor(s)")

def _engine_files():
    """Shared files a build may patch. The engine ones sit in game.gp's engine
    sequence (each file depends on the previous one) and (mi) goes by file
    times, so touching one recompiles the engine from there on."""
    from .versions import mod_settings_path
    gs = _goal_src() / "engine"
    return {"entity.gc": _entity_gc(), "level-info.gc": _level_info(),
            "load-boundary-data.gc": _load_boundary_data(),
            "vol-h.gc": gs / "geometry" / "vol-h.gc",
            "mod-settings.gc": mod_settings_path(), "game.gp": _game_gp()}


def _file_times():
    out = {}
    for k, p in _engine_files().items():
        try:
            out[k] = p.stat().st_mtime_ns
        except OSError:
            out[k] = None
    return out


def _compile_scope(before):
    """'level only' or which engine files changed (logged)."""
    now = _file_times()
    changed = [k for k, t in now.items() if before.get(k) != t]
    heavy = [k for k in changed if k not in ("mod-settings.gc", "game.gp")]
    if heavy:
        msg = f"engine changed ({', '.join(heavy)}) — full compile"
    elif changed:
        msg = f"level only (+ {', '.join(changed)})"
    else:
        msg = "level only"
    log(f"[build] {msg}")
    return msg


def _compile(state, scope):
    """(mi) in the running GOALC (launched if needed) and wait for it to end.
    GOALC is kept running: a freshly started one recompiles all the game code
    (it has to load every type), a running one only what changed."""
    if not goalc_ok():
        state["status"] = "Launching GOALC (waiting for nREPL)..."
        write_startup_gc([])
        kill_goalc()
        ok, msg = launch_goalc(wait_for_nrepl=True)
        if not ok:
            state["error"] = f"GOALC failed to start: {msg}"
            return False
        scope = "first build since GOALC started: all game code"
    state["status"] = f"Compiling (mi): {scope} — please wait..."
    LAST_COMPILE["summary"] = ""
    r = goalc_run("(mi)")
    if r != "done":
        state["error"] = ("Compile failed — see the GOALC console" if r == "failed" else
                          "Compile didn't finish (GOALC closed or timed out) — check the GOALC console")
        return False
    return True


def write_level_files(name, scene, depsgraph=None, state=None, navmesh=True):
    """Write every file a level build needs (the GLB is exported first, on
    the main thread): .jsonc, .gd, level code, and its entries in the shared
    files (entity.gc nav-meshes, level-info.gc, load boundaries, game.gp).
    Each file is only written when its content changed. Returns the level's
    nav-mesh actors (navmesh=False: entity.gc left to the caller)."""
    state = state if state is not None else {}
    state["status"] = f"Collecting scene ({name})..."
    # Apply engine patches (idempotent — only writes if needed)
    _apply_engine_patches()
    _clean_orphaned_vol_links(scene)
    actors    = collect_actors(scene, depsgraph)
    ambients  = collect_ambients(scene)
    spawns    = collect_spawns(scene)
    ags       = needed_ags(actors)
    extras    = needed_extras_ags(actors)
    tpages    = needed_tpages(actors)
    code_deps = needed_code(actors)
    collect_nav_mesh_geometry(scene, name)
    cam_actors, trigger_actors = collect_cameras(scene)

    if code_deps:
        log(f"[code-deps] {code_deps}")

    state["status"] = f"Writing files ({name})..."
    base_id = int(_get_level_prop(scene, "og_base_id", 10000))
    aggro_actors  = collect_aggro_triggers(scene)
    custom_actors = collect_custom_triggers(scene)
    # Fog override: append a synthetic fog-control actor to the JSONC and
    # tell write_gc to emit the matching deftype.
    has_fog_override = bool(_get_level_prop(scene, "og_fog_override_enabled", False))
    actors_with_fog = list(actors) + ([make_fog_actor_dict(spawns)] if has_fog_override else [])
    write_jsonc(name, actors_with_fog, ambients, cam_actors + trigger_actors + aggro_actors + custom_actors + collect_task_triggers(scene), base_id, scene=scene)
    write_nav_gc(name, scene)          # custom-nav system: the level's -nav.gc
    write_gd(name, ags, code_deps, tpages, scene=scene, extras_ags=extras)
    navmesh_actors = _collect_navmesh_actors(scene)
    _lv_objs = _level_objects(scene)
    from .export.level_tools import ensure_level_tools
    ensure_level_tools()              # shared lt-checkpoint (checkpoint triggers)
    from .export.edited import ensure_shared
    ensure_shared(scene, _lv_objs)    # shared edited actors (lt-<file>.gc)
    write_gc(name, has_triggers=bool(trigger_actors), has_aggro_triggers=bool(aggro_actors), has_custom_triggers=bool(custom_actors), has_fog_override=has_fog_override, scene=scene)
    if navmesh:
        patch_entity_gc(navmesh_actors, scene)
    patch_level_info(name, spawns, scene)
    patch_load_boundaries(name, collect_load_boundaries(scene), scene)
    patch_game_gp(name, code_deps, scene=scene)
    prune_orphaned_levels()  # self-heal: drop registrations for any level whose files were deleted
    # custom tasks of the .blend (Tasks panel; only written when changed)
    from .export.tasks_export import export_tasks
    errs = export_tasks(scene)
    if errs:
        raise RuntimeError("Tasks: " + "; ".join(errs[:3]))
    return navmesh_actors


def _bg_build(name, scene, depsgraph=None, boot_cp=None):
    state = _BUILD_STATE
    try:
        times = _file_times()
        write_level_files(name, scene, depsgraph, state)

        _write_boot_cp(state, boot_cp)
        scope = _compile_scope(times)
        _restart_goalc_if_types_changed(state)
        if _compile(state, scope):
            state["ok"] = True; state["status"] = f"Build complete! ({scope}; {LAST_COMPILE['summary']})"
    except Exception as e:
        state["error"] = str(e)
    finally:
        state["done"] = True



def _bg_compile(times, boot_cp=None):
    """(mi) for files already written (Export and compile all levels)."""
    state = _BUILD_STATE
    try:
        _write_boot_cp(state, boot_cp)
        scope = _compile_scope(times)
        _restart_goalc_if_types_changed(state)
        if _compile(state, scope):
            state["ok"] = True; state["status"] = f"Build complete! ({scope})"
    except Exception as e:
        state["error"] = str(e)
    finally:
        state["done"] = True


_PLAY_STATE = {"done":False, "error":None, "status":""}
_QUICK_EXPORT_STATE = {"done": False, "status": "", "error": None, "ok": False}
_BUILD_PLAY_STATE  = {"done": False, "status": "", "error": None, "ok": False}



def _write_boot_cp(state, boot_cp):
    """mod-base: the spawn goes into mod-settings.gc before (mi) compiles it."""
    if boot_cp:
        from .versions import set_debug_continue_point
        if set_debug_continue_point(boot_cp):
            log(f"[mod-base] *debug-continue-point* = {boot_cp}")


def _bg_play(name, cp_name, boot_wait=4.0, listener_wait=1.0, booted_cp=None):
    """Spawn Jak at the given continue-point in GK.

    cp_name — full continue-point name, e.g. "my-level-start". Format is
              "<level>-<uid>" where uid is the empty's SPAWN_/CHECKPOINT_
              suffix. _make_continues writes the matching entry into
              level-info.gc with :lev0 = '<name>, so (start) loads the
              level itself.

    boot_wait — seconds to sleep after launch_gk before sending (lt).
                Covers the gap between GK opening port 8112 (early in boot)
                and the GOAL kernel actually being ready to handle the
                listener handshake. Tunable in Developer Tools as
                "GK Boot Wait (s)".
    listener_wait — seconds between (lt) and (start). Tunable in Dev
                Tools as "Listener Settle (s)".

    BEHAVIOR: always kills any existing GK and launches fresh. This
    guarantees the latest built files (DGO, .gd, level-info.gc, etc.)
    actually load — if we reused a running GK and just sent (start),
    the in-game transition would use the data GK loaded at its boot,
    making any rebuild since invisible. Cost is ~boot_wait extra
    seconds on every click vs. the previous "skip launch if running"
    behavior.

    Total time = launch + boot_wait + (lt) + listener_wait + (start)
                 ≈ boot_wait + 2s on a normal machine.

    There is no clean "GK fully ready" signal we can probe from outside.
    GK opens port 8112 early — well before its GOAL kernel can handle
    listener protocol — so TCP-probing 8112 gives a false positive and
    (lt) hangs at "Waiting for version...". Fixed sleep is reliable.

    nREPL EVAL is fire-and-forget (ReplClient::eval only writes; never
    reads). We can't observe goalc's state from here. The flow is
    unconditional: send and trust the timing.
    """
    state = _PLAY_STATE
    try:
        if booted_cp and booted_cp == cp_name:
            # mod-base: mod-settings.gc already boots into this spawn
            state["status"] = f"Launching GK (boots into {cp_name})..."
            ok, msg = launch_gk()
            if not ok:
                state["error"] = msg; return
            state["status"] = "Done!"
            return
        if not goalc_ok():
            state["error"] = (
                "GOALC isn't running. Run Export & Compile first — that "
                "starts GOALC and loads the symbol info we need."
            )
            return

        # Always kill-and-relaunch GK so the latest built files (DGO, .gd,
        # level-info.gc, etc.) actually load. If we kept an existing GK
        # running and just sent (start), the in-game transition would use
        # the OLD loaded data — any rebuild since GK started would be
        # invisible. launch_gk() kills existing GK internally before
        # spawning the fresh process.
        state["status"] = f"Launching GK (waiting {boot_wait:g}s for boot)..."
        ok, msg = launch_gk()
        if not ok:
            state["error"] = msg; return
        time.sleep(boot_wait)

        # Send (lt). If listener was already connected, this is a no-op
        # (goalc prints "already connected!" to its own console — nothing
        # comes back over nREPL).
        state["status"] = "Connecting listener..."
        goalc_send("(lt)", timeout=1)
        time.sleep(listener_wait)

        # Send the spawn. The continue-point's :lev0 triggers the level
        # load, so this transitions GK from village1 (boot default) to
        # ours and spawns Jak at the chosen checkpoint.
        state["status"] = f"Spawning at {cp_name}..."
        goalc_send(
            f"(start 'play (get-continue-by-name *game-info* \"{cp_name}\"))",
            timeout=1,
        )
        state["status"] = "Done!"
    except Exception as e:
        state["error"] = str(e)
    finally:
        state["done"] = True


# ── Waypoint operators ────────────────────────────────────────────────────────



def _bg_quick_export(name, scene, depsgraph=None, boot_cp=None):
    """Quick Level Export: write this level's own files (.jsonc, .gd, level
    code; the GLB is exported on the main thread first) and run (mi). Shared
    files are not touched: level-info.gc (checkpoints / load boundaries),
    entity.gc (nav-mesh entries), game.gp.
    """
    state = _QUICK_EXPORT_STATE
    try:
        state["status"] = "Collecting scene..."
        _clean_orphaned_vol_links(scene)
        actors   = collect_actors(scene, depsgraph)
        ambients = collect_ambients(scene)
        spawns   = collect_spawns(scene)
        ags      = needed_ags(actors)
        extras   = needed_extras_ags(actors)
        tpages   = needed_tpages(actors)
        code_deps = needed_code(actors)  # still needed for DGO .o injection
        cam_actors, trigger_actors = collect_cameras(scene)

        state["status"] = "Writing level files..."
        base_id = int(_get_level_prop(scene, "og_base_id", 10000))
        aggro_actors  = collect_aggro_triggers(scene)
        custom_actors = collect_custom_triggers(scene)
        has_fog_override = bool(_get_level_prop(scene, "og_fog_override_enabled", False))
        actors_with_fog = list(actors) + ([make_fog_actor_dict(spawns)] if has_fog_override else [])
        write_jsonc(name, actors_with_fog, ambients, cam_actors + trigger_actors + aggro_actors + custom_actors + collect_task_triggers(scene), base_id, scene=scene)
        write_nav_gc(name, scene)
        write_gd(name, ags, code_deps, tpages, scene=scene, extras_ags=extras)
        _lv_objs = _level_objects(scene)
        from .export.level_tools import ensure_level_tools
        ensure_level_tools()          # shared code: only written when missing / changed
        from .export.edited import ensure_shared
        ensure_shared(scene, _lv_objs)
        write_gc(name, has_triggers=bool(trigger_actors), has_aggro_triggers=bool(aggro_actors), has_custom_triggers=bool(custom_actors), has_fog_override=has_fog_override, scene=scene)

        # Run (mi) — re-extracts GLB, repacks DGO, skips unchanged .gc files
        _write_boot_cp(state, boot_cp)
        _restart_goalc_if_types_changed(state)
        if not _compile(state, "level only"):
            return

        state["ok"] = True
        state["status"] = f"Done! Reload your level in-game. ({LAST_COMPILE['summary']})"
    except Exception as e:
        state["error"] = str(e)
    finally:
        state["done"] = True




def _bg_build_and_play(name, scene, depsgraph=None, boot_cp=None):
    """Export files, compile with GOALC, then launch GK and load the level.

    FLOW:
      Phase 1 — collect scene, write all level files.
      Phase 2 — compile: (mi) in the running GOALC (launched if needed).
      Phase 3 — launch GK, (lt), spawn (as Play does).

    GOALC is never restarted here: a fresh GOALC recompiles all the game code
    on its first (mi) (it has to load every type), a running one only what
    changed. (It used to be restarted to run (lt) from startup.gc.)
    """
    state = _BUILD_PLAY_STATE
    try:
        # ── Phase 1: Build ────────────────────────────────────────────────────
        times = _file_times()
        write_level_files(name, scene, depsgraph, state)

        # ── Phase 2: Compile ──────────────────────────────────────────────────
        # Kill GK first — game must not be running during compile.
        # Keep GOALC alive if nREPL is working — saves startup time for (mi).
        state["status"] = "Killing existing GK..."
        kill_gk()
        time.sleep(0.3)
        _write_boot_cp(state, boot_cp)
        scope = _compile_scope(times)
        _restart_goalc_if_types_changed(state)
        if not _compile(state, scope):
            return

        # ── Phase 3: Launch game and load level ───────────────────────────────
        # GOALC keeps running (a restart would make the next build recompile
        # all the game code). Same steps as Play: GK, (lt), then the spawn.
        props = getattr(scene, "og_props", None)
        boot_wait = float(getattr(props, "og_launch_boot_wait", 4.0))
        listener_wait = float(getattr(props, "og_launch_listener_wait", 1.0))
        state["status"] = f"Launching game (waiting {boot_wait:g}s for boot)..."
        ok, msg = launch_gk()
        log(f"[launch] launch_gk returned: ok={ok} msg={msg}")
        if not ok:
            state["error"] = f"GK launch failed: {msg}"; return
        time.sleep(boot_wait)
        state["status"] = "Connecting listener..."
        goalc_send("(lt)", timeout=1)
        if boot_cp:
            # mod-base: the game boots into the spawn itself (mod-settings.gc)
            state["status"] = "Done! (boots into the spawn)"
            state["ok"] = True
            return
        time.sleep(listener_wait)
        # the continue-point's :lev0 loads the level (see _bg_play)
        state["status"] = "Spawning player..."
        goalc_send(f"(start 'play (get-continue-by-name *game-info* \"{name}-start\"))", timeout=1)
        state["status"] = "Done!"
        state["ok"] = True

    except Exception as e:
        state["error"] = str(e)
    finally:
        state["done"] = True


