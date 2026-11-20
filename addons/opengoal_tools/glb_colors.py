# ---------------------------------------------------------------------------
# glb_colors.py — OpenGOAL Level Tools
# Smaller level GLBs: a glTF export hook (Blender's exporter calls
# glTF2ExportUserExtension.gather_mesh_hook on every mesh, before Draco).
# Blender writes colour layers as 16-bit (linear) values; the level builder
# only keeps their top 8 bits (gltf_util.cpp: u16 >> 8, and it reads 8-bit
# colours as they are). So:
#   - COLOR_0 and the time of day layers (_SUNRISE ...) are written as 8-bit:
#     exactly the bytes the game ends up with, half the size, and no noisy
#     low bits for Draco to store
#   - COLOR_0 is left out when all 8 time of day layers are there (the level
#     builder doesn't read it then)
#   - Color Depth (level bake option, 6 / 5 / 4 bits): RGB rounded to fewer
#     levels, so Draco stores them in less space (bands)
# While the addon exports a level (ACTIVE["on"]); other glTF exports only with
# the preference "8-bit colours in every glTF export".
# ---------------------------------------------------------------------------
from __future__ import annotations

import numpy as np

TOD = ("_SUNRISE", "_MORNING", "_NOON", "_AFTERNOON", "_SUNSET", "_TWILIGHT", "_EVENING", "_GREENSUN")
_U8, _U16 = 5121, 5123
ACTIVE = {"on": False, "u8": True, "drop_color0": True, "bits": 8, "stats": None}
_TABLES: dict = {}


def _depth_table(bits):
    """Byte -> byte for a lower colour depth: rounded to 2^bits levels in sRGB
    (even steps to the eye, the darks keep their detail), back to linear."""
    if bits not in _TABLES:
        lin = np.arange(256, dtype=np.float64) / 255.0
        srgb = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055)
        n = (1 << bits) - 1
        q = np.round(srgb * n) / n
        back = np.where(q <= 0.04045, q / 12.92, ((q + 0.055) / 1.055) ** 2.4)
        _TABLES[bits] = np.round(back * 255.0).astype(np.uint8)
    return _TABLES[bits]


def _to_u8(acc, bits=8):
    """A colour accessor's 16-bit data as 8-bit (top byte, like the level
    builder); bits < 8: RGB rounded to that colour depth (alpha kept)."""
    if acc is None or int(acc.component_type) != _U16 or acc.buffer_view is None:
        return 0
    from io_scene_gltf2.io.exp.binary_data import BinaryData
    from io_scene_gltf2.io.com.constants import ComponentType
    src = np.frombuffer(acc.buffer_view.data, dtype=np.uint16)
    out = (src >> 8).astype(np.uint8)
    if bits < 8 and acc.type == "VEC4":
        rgb = out.reshape(-1, 4)[:, :3]
        rgb[:] = _depth_table(bits)[rgb]
    elif bits < 8:
        out = _depth_table(bits)[out]
    acc.buffer_view = BinaryData(out.tobytes(), acc.buffer_view.bufferViewTarget)
    acc.component_type = ComponentType.UnsignedByte
    acc.normalized = True
    return src.nbytes // 2


def _all_exports() -> bool:
    """Preference: also for glTF exports made by hand (File > Export > glTF)."""
    import bpy
    a = bpy.context.preferences.addons.get(__package__)
    return bool(a and getattr(a.preferences, "glb_colors_all_exports", False))


class glTF2ExportUserExtension:
    def __init__(self):
        pass

    def gather_mesh_hook(self, gltf2_mesh, blender_mesh, blender_object, vertex_groups, modifiers, materials,
                         export_settings):
        if gltf2_mesh is None or not (ACTIVE["on"] or _all_exports()):
            return
        st = ACTIVE["stats"] if ACTIVE["stats"] is not None else {}
        bits = ACTIVE["bits"] if ACTIVE["on"] else 8          # Color Depth: the level's bake option
        for prim in gltf2_mesh.primitives or ():
            attrs = prim.attributes or {}
            if ACTIVE["drop_color0"] and "COLOR_0" in attrs and all(t in attrs for t in TOD):
                acc = attrs.pop("COLOR_0")
                st["dropped"] = st.get("dropped", 0) + (len(acc.buffer_view.data) if acc.buffer_view else 0)
            if ACTIVE["u8"]:
                for k in [k for k in attrs if k.startswith("COLOR_") or k in TOD]:
                    st["saved"] = st.get("saved", 0) + _to_u8(attrs[k], bits)
