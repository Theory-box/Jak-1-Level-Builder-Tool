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
    collect_actors, collect_ambients, collect_spawns, collect_cameras,
    collect_nav_mesh_geometry, collect_aggro_triggers, collect_custom_triggers,
    needed_ags, needed_extras_ags, needed_code, write_jsonc, write_gd, write_gc,
    make_fog_actor_dict,
    patch_level_info, patch_game_gp, export_glb,
    _collect_navmesh_actors, _canonical_actor_objects,
    _nick, _iso, _lname, _ldir, _goal_src, _level_info,
    _game_gp, _levels_dir, _entity_gc,
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

def _active_version_root() -> Path | None:
    """Return the resolved exe folder path (og_root_path / og_active_version)."""
    prefs = bpy.context.preferences.addons.get("opengoal_tools")
    if not prefs:
        return None
    p    = prefs.preferences
    root = _strip(getattr(p, "og_root_path", ""))
    ver  = _strip(getattr(p, "og_active_version", ""))
    if root and ver:
        return Path(root) / ver
    return None

def _active_data_root() -> Path | None:
    """Return the resolved data folder path (og_root_path / og_active_data)."""
    prefs = bpy.context.preferences.addons.get("opengoal_tools")
    if not prefs:
        return None
    p    = prefs.preferences
    root = _strip(getattr(p, "og_root_path", ""))
    dat  = _strip(getattr(p, "og_active_data", ""))
    if root and dat:
        return Path(root) / dat
    # Fall back to exe folder if no separate data folder set
    return _active_version_root()

def _exe_root():
    prefs = bpy.context.preferences.addons.get("opengoal_tools")
    if prefs:
        manual = _strip(prefs.preferences.exe_path)
        if manual:
            return Path(manual)
    ver = _active_version_root()
    return ver if ver else Path(".")

def _data_root():
    prefs = bpy.context.preferences.addons.get("opengoal_tools")
    if prefs:
        manual = _strip(prefs.preferences.data_path)
        if manual:
            return Path(manual)
    dat = _active_data_root()
    return dat if dat else Path(".")

def _scan_for_installs(root: Path, max_depth: int = 4):
    """Recursively find exe folders and data folders under root.

    Returns (exe_folders, data_folders) as lists of Paths.
    Skips known leaf dirs (data/, goal_src/, etc.) to avoid going deep
    into game files. Stops recursing into a folder once it's been claimed
    as an exe or data folder.
    """
    import sys as _sys
    exe_ext   = ".exe" if _sys.platform == "win32" else ""
    skip_dirs = {
        "data", "out", "decompiler_out", "goal_src", "custom_assets",
        "iso_data", "third_party", "node_modules", ".git",
    }
    exe_folders  = []
    data_folders = []

    def _walk(path: Path, depth: int):
        if depth > max_depth:
            return
        try:
            for d in sorted(path.iterdir()):
                if not d.is_dir() or d.name.startswith(".") or d.name.lower() in skip_dirs:
                    continue
                if (d / f"gk{exe_ext}").exists() and (d / f"goalc{exe_ext}").exists():
                    exe_folders.append(d)
                    continue   # don't recurse further into an exe folder
                if (d / "goal_src" / "jak1").exists() or (d / "data" / "goal_src" / "jak1").exists():
                    data_folders.append(d)
                    continue   # don't recurse further into a data folder
                _walk(d, depth + 1)
        except (PermissionError, OSError):
            pass

    _walk(root, 0)
    return exe_folders, data_folders

def _gk():         return _exe_root() / f"gk{_EXE}"
def _goalc():      return _exe_root() / f"goalc{_EXE}"

def _data() -> Path:
    """Return the effective data folder.

    Release layout  — user points data_path at the install root (e.g. .../opengoal/v0.2.29/).
                      goal_src lives inside a data/ subfolder → return root/data/.
    Dev layout      — user points data_path at the jak-project clone root.
                      goal_src lives directly at root, no data/ layer → return root as-is.

    Detection: if <root>/goal_src/jak1/ exists the user is pointing at a dev clone.
    That path is never created by the addon itself (addon only writes inside
    goal_src/jak1/levels/ and custom_assets/), so there are no false positives.
    """
    root = _data_root()
    if (root / "goal_src" / "jak1").exists():
        return root          # dev build — no data/ layer
    return root / "data"     # release build

def _decompiler_path() -> Path:
    """Return the decompiler_out/jak1/ folder.

    If the user has set a custom decompiler_path in preferences, use that directly.
    Otherwise auto-detect as _data() / 'decompiler_out' / 'jak1'.

    This folder contains (when the decompiler has been run with the right flags):
      textures/<tpage>/<name>.png          — save_texture_pngs: true
      <level>/<actor>-lod0.glb             — rip_levels: true
      <level>/<level>-background.glb       — rip_levels: true
    """
    prefs = bpy.context.preferences.addons.get("opengoal_tools")
    custom = (prefs.preferences.decompiler_path.strip().rstrip("\\/") if prefs else "")
    if custom:
        return Path(custom)
    return _data() / "decompiler_out" / "jak1"


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

def goalc_ok():
    """Return True if GOALC's nREPL is reachable on GOALC_PORT.

    On first miss, tries to restore GOALC_PORT from the port file written
    by launch_goalc() — this handles the case where GOALC was already running
    when Blender started (e.g. from a previous session).
    """
    if goalc_send("(+ 1 1)", timeout=3) is not None:
        return True
    # Fast path missed. Try restoring port from file (written at launch time).
    _load_port_file()
    return goalc_send("(+ 1 1)", timeout=3) is not None

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



def patch_entity_gc(navmesh_actors):
    """
    Patch engine/entity/entity.gc to add custom-nav-mesh-check-and-setup.

    navmesh_actors: list of (actor_aid, mesh_data) tuples.

    Adds/replaces:
      1. A (defun custom-nav-mesh-check-and-setup ...) with one case per actor.
      2. A call to it at the top of (defmethod birth! entity-actor ...).

    Safe to call repeatedly — old injected code is stripped before re-injecting.
    """
    p = _entity_gc()
    if not p.exists():
        log(f"WARNING: entity.gc not found at {p}")
        return

    raw  = p.read_bytes()
    crlf = b"\r\n" in raw
    txt  = raw.decode("utf-8").replace("\r\n", "\n")

    # ── Strip any previously injected block ──────────────────────────────────
    import re
    txt = re.sub(
        r"\n;; \[OpenGOAL Tools\] BEGIN custom-nav-mesh.*?;; \[OpenGOAL Tools\] END custom-nav-mesh\n",
        "",
        txt,
        flags=re.DOTALL,
    )
    # Strip old birth! injection line
    txt = re.sub(r"  \(custom-nav-mesh-check-and-setup this\)\n", "", txt)

    if not navmesh_actors:
        # Nothing to inject — just clean file
        out = txt.replace("\n", "\r\n") if crlf else txt
        p.write_bytes(out.encode("utf-8"))
        log("entity.gc: cleaned (no navmesh actors)")
        return

    # ── Build the defun block ─────────────────────────────────────────────────
    lines = [
        "",
        ";; [OpenGOAL Tools] BEGIN custom-nav-mesh",

        "(defun custom-nav-mesh-check-and-setup ((this entity-actor))",
        "  (case (-> this aid)",
    ]
    for aid, mesh in navmesh_actors:
        lines.append(_navmesh_to_goal(mesh, aid))
    lines += [
        "  )",
        "  ;; Manually init the nav-mesh without calling entity-nav-login.",
        "  ;; entity-nav-login calls update-route-table which writes back to the route",
        "  ;; array — but our mesh is 'static (read-only GAME.CGO memory), so that",
        "  ;; write would segfault. Instead we just set up the user-list engine.",
        "  (when (nonzero? (-> this nav-mesh))",
        "    (when (zero? (-> (-> this nav-mesh) user-list))",
        "      (set! (-> (-> this nav-mesh) user-list)",
        "            (new 'loading-level 'engine 'nav-engine 32))",
        "    )",
        "  )",
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
        "  (custom-nav-mesh-check-and-setup this)\n" + CALL_MARKER,
        1,
    )

    out = txt.replace("\n", "\r\n") if crlf else txt
    p.write_bytes(out.encode("utf-8"))
    log(f"Patched entity.gc with {len(navmesh_actors)} nav-mesh actor(s)")

def _bg_build(name, scene, depsgraph=None):
    state = _BUILD_STATE
    try:
        state["status"] = "Collecting scene..."
        # Apply engine patches (idempotent — only writes if needed)
        patched = _apply_engine_patches()
        if patched:
            state["status"] = "Applied engine patches, compiling..."
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
            state["status"] = f"Injecting code for: {[o for o,_,_ in code_deps]}..."
            log(f"[code-deps] {code_deps}")

        state["status"] = "Writing files..."
        base_id = int(_get_level_prop(scene, "og_base_id", 10000))
        aggro_actors  = collect_aggro_triggers(scene)
        custom_actors = collect_custom_triggers(scene)
        # Fog override: append a synthetic fog-control actor to the JSONC and
        # tell write_gc to emit the matching deftype.
        has_fog_override = bool(_get_level_prop(scene, "og_fog_override_enabled", False))
        actors_with_fog = list(actors) + ([make_fog_actor_dict(spawns)] if has_fog_override else [])
        write_jsonc(name, actors_with_fog, ambients, cam_actors + trigger_actors + aggro_actors + custom_actors, base_id, scene=scene)
        write_gd(name, ags, code_deps, tpages, scene=scene, extras_ags=extras)
        navmesh_actors = _collect_navmesh_actors(scene)
        _lv_objs = _level_objects(scene)
        has_cps = bool([o for o in _lv_objs if o.name.startswith("CHECKPOINT_") and o.type == "EMPTY" and not o.name.endswith("_CAM")])
        write_gc(name, has_triggers=bool(trigger_actors), has_checkpoints=has_cps, has_aggro_triggers=bool(aggro_actors), has_custom_triggers=bool(custom_actors), has_fog_override=has_fog_override, scene=scene)
        patch_entity_gc(navmesh_actors)
        patch_level_info(name, spawns, scene)
        patch_game_gp(name, code_deps, scene=scene)

        if goalc_ok():
            state["status"] = "Running (mi) via nREPL..."
            r = goalc_send("(mi)", timeout=GOALC_TIMEOUT)
            if r is not None:
                state["ok"] = True; state["status"] = "Build complete!"; return

        state["status"] = "Writing startup.gc..."
        write_startup_gc(["(mi)"])
        state["status"] = "Launching GOALC..."
        kill_goalc()
        ok, msg = launch_goalc()
        if not ok:
            state["error"] = msg; return
        state["ok"] = True
        state["status"] = "GOALC launched — watch console for compile progress."
    except Exception as e:
        state["error"] = str(e)
    finally:
        state["done"] = True



_PLAY_STATE = {"done":False, "error":None, "status":""}
_GEO_REBUILD_STATE = {"done": False, "status": "", "error": None, "ok": False}
_BUILD_PLAY_STATE  = {"done": False, "status": "", "error": None, "ok": False}



def _bg_play(name, cp_name, boot_wait=4.0, listener_wait=1.0):
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

    HOT PATH (GK already running): (lt) + (start). ~listener_wait + small.
    COLD PATH (GK not running): launch + boot_wait + (lt) + listener_wait + (start).

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
        if not goalc_ok():
            state["error"] = (
                "GOALC isn't running. Run Export & Compile first — that "
                "starts GOALC and loads the symbol info we need."
            )
            return

        # Cold path: launch GK, wait long enough for the GOAL kernel to be
        # ready to talk listener protocol.
        if not _process_running(f"gk{_EXE}"):
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



def _bg_geo_rebuild(name, scene, depsgraph=None):
    """Export geo + actor placement, repack DGO, relaunch GK. No GOAL recompile.

    (mi) is GOALC's incremental build command — it skips .gc files that haven't
    changed, so it only re-extracts the GLB and repacks the DGO.

    NOTE: if you've added a NEW enemy type since the last full Export & Compile,
    use that instead — this path skips the game.gp patch those types need.
    """
    state = _GEO_REBUILD_STATE
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
        write_jsonc(name, actors_with_fog, ambients, cam_actors + trigger_actors + aggro_actors + custom_actors, base_id, scene=scene)
        write_gd(name, ags, code_deps, tpages, scene=scene, extras_ags=extras)
        _lv_objs = _level_objects(scene)
        has_cps = bool([o for o in _lv_objs if o.name.startswith("CHECKPOINT_") and o.type == "EMPTY" and not o.name.endswith("_CAM")])
        write_gc(name, has_triggers=bool(trigger_actors), has_checkpoints=has_cps, has_aggro_triggers=bool(aggro_actors), has_custom_triggers=bool(custom_actors), has_fog_override=has_fog_override, scene=scene)
        patch_level_info(name, spawns, scene)  # update spawn continue-points if moved

        # Run (mi) — re-extracts GLB, repacks DGO, skips unchanged .gc files
        if goalc_ok():
            state["status"] = "Running (mi) — re-extracting geo..."
            r = goalc_send("(mi)", timeout=GOALC_TIMEOUT)
            if r is None:
                state["error"] = "(mi) timed out or GOALC lost connection"; return
        else:
            state["status"] = "GOALC not running — launching for (mi)..."
            write_startup_gc(["(mi)"])
            ok, msg = launch_goalc(wait_for_nrepl=True)
            if not ok:
                state["error"] = f"GOALC failed to start: {msg}"; return
            state["status"] = "Running (mi)..."
            r = goalc_send("(mi)", timeout=GOALC_TIMEOUT)
            if r is None:
                state["error"] = "(mi) timed out"; return

        state["ok"] = True
        state["status"] = "Done! Reload your level in-game."
    except Exception as e:
        state["error"] = str(e)
    finally:
        state["done"] = True




def _bg_build_and_play(name, scene, depsgraph=None):
    """Export files, compile with GOALC, then launch GK and load the level.

    FLOW:
      Phase 1 — collect scene, write all level files.
      Phase 2 — compile: ensure GOALC+nREPL are live, send (mi).
      Phase 3 — launch: write startup.gc with (lt)/(bg)/(start), restart GOALC
                 so it auto-runs those commands when GK connects.

    WHY WE RESTART GOALC AFTER COMPILE:
      After (mi) finishes we need GOALC to re-read startup.gc so it can auto-run
      (lt)/(bg)/(start) when GK boots.  Restarting is simpler and more reliable
      than trying to sequence manual goalc_send() calls with arbitrary sleeps —
      the startup.gc run_after_listen mechanism handles the GK-ready timing for us.

    WHY startup.gc INSTEAD OF goalc_send() FOR LAUNCH:
      goalc_send() is fire-and-forget with fixed sleeps.  If GK takes longer to
      boot than expected the (lt) call fails and nothing loads.  startup.gc
      run_after_listen fires only after (lt) actually connects — it is driven by
      GK being ready, not by a sleep timer.  See _bg_play() docstring for more.
    """
    state = _BUILD_PLAY_STATE
    try:
        # ── Phase 1: Build ────────────────────────────────────────────────────
        state["status"] = "Collecting scene..."
        _clean_orphaned_vol_links(scene)
        actors    = collect_actors(scene, depsgraph)
        ambients  = collect_ambients(scene)
        spawns    = collect_spawns(scene)
        ags       = needed_ags(actors)
        extras    = needed_extras_ags(actors)
        tpages    = needed_tpages(actors)
        code_deps = needed_code(actors)
        cam_actors, trigger_actors = collect_cameras(scene)

        state["status"] = "Writing level files..."
        base_id = int(_get_level_prop(scene, "og_base_id", 10000))
        aggro_actors  = collect_aggro_triggers(scene)
        custom_actors = collect_custom_triggers(scene)
        has_fog_override = bool(_get_level_prop(scene, "og_fog_override_enabled", False))
        actors_with_fog = list(actors) + ([make_fog_actor_dict(spawns)] if has_fog_override else [])
        write_jsonc(name, actors_with_fog, ambients, cam_actors + trigger_actors + aggro_actors + custom_actors, base_id, scene=scene)
        write_gd(name, ags, code_deps, tpages, scene=scene, extras_ags=extras)
        navmesh_actors = _collect_navmesh_actors(scene)
        _lv_objs = _level_objects(scene)
        has_cps = bool([o for o in _lv_objs if o.name.startswith("CHECKPOINT_") and o.type == "EMPTY" and not o.name.endswith("_CAM")])
        write_gc(name, has_triggers=bool(trigger_actors), has_checkpoints=has_cps, has_aggro_triggers=bool(aggro_actors), has_custom_triggers=bool(custom_actors), has_fog_override=has_fog_override, scene=scene)
        patch_entity_gc(navmesh_actors)
        patch_level_info(name, spawns, scene)
        patch_game_gp(name, code_deps, scene=scene)

        # ── Phase 2: Compile ──────────────────────────────────────────────────
        # Kill GK first — game must not be running during compile.
        # Keep GOALC alive if nREPL is working — saves startup time for (mi).
        state["status"] = "Killing existing GK..."
        kill_gk()
        time.sleep(0.3)

        if not goalc_ok():
            # nREPL not reachable — kill any stale GOALC holding port 8181
            # and launch fresh so (mi) can connect.
            state["status"] = "Launching GOALC (waiting for nREPL)..."
            kill_goalc()
            ok, msg = launch_goalc(wait_for_nrepl=True)
            if not ok:
                state["error"] = f"GOALC failed to start: {msg}"; return

        state["status"] = "Compiling (mi) — please wait..."
        r = goalc_send("(mi)", timeout=GOALC_TIMEOUT)
        if r is None:
            state["error"] = "Compile timed out — check GOALC console"; return

        # ── Phase 3: Launch game and load level ───────────────────────────────
        # Write startup.gc with ONLY (lt) — no (bg) here.
        # Putting (bg) in run_after_listen causes "generated code, but wasn't
        # supposed to" spam every time GK reconnects after play is done.
        # We send (bg) manually via nREPL once *game-info* is confirmed live.
        state["status"] = "Writing startup.gc..."
        write_startup_gc(["(lt)"])

        # Restart GOALC so it reads the new startup.gc.
        state["status"] = "Restarting GOALC with launch startup..."
        kill_goalc()
        ok, msg = launch_goalc(wait_for_nrepl=True)
        if not ok:
            state["error"] = f"GOALC relaunch failed: {msg}"; return

        state["status"] = "Launching game..."
        ok, msg = launch_gk()
        log(f"[launch] launch_gk returned: ok={ok} msg={msg}")
        if not ok:
            state["error"] = f"GK launch failed: {msg}"; return

        # Poll until *game-info* exists (GAME.CGO done) then spawn.
        # Match "'ready" (with leading quote) to catch only the GOAL symbol return,
        # not console noise like "Listener: ready" which causes false-positive triggers.
        # See _bg_play() for why no (bg) and no fallback — the continue-point's
        # :lev0 triggers the level load itself, and the fallback was the cause
        # of historic "Jak in the void" deaths.
        state["status"] = "Waiting for game to finish loading..."
        spawned = False
        for _ in range(240):
            time.sleep(0.5)
            r = goalc_send("(if (nonzero? *game-info*) 'ready 'wait)", timeout=3)
            if r and "'ready" in r:
                time.sleep(1.0)
                state["status"] = "Spawning player..."
                goalc_send(
                    f"(start 'play (get-continue-by-name *game-info* \"{name}-start\"))"
                )
                spawned = True
                break
        if not spawned:
            state["status"] = "Done (spawn timed out — load level manually)"
            return
        state["status"] = "Done!"
        state["ok"] = True

    except Exception as e:
        state["error"] = str(e)
    finally:
        state["done"] = True


