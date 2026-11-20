# ---------------------------------------------------------------------------
# coords.py — OpenGOAL Level Tools
# Blender <-> game axes: Blender is Z-up, the game is Y-up with Blender's -Y
# as its +Z. A Blender point (x, y, z) is the game point (x, z, -y).
# Game distances are 4096 units per meter.
# ---------------------------------------------------------------------------
from __future__ import annotations

import mathutils

M = 4096.0                     # game units per meter
# Blender -> game axes as a rotation matrix (game = R @ blender)
R = mathutils.Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0)))


def to_game(v) -> mathutils.Vector:
    """Blender point / direction -> game axes (meters)."""
    return mathutils.Vector((v[0], v[2], -v[1]))


def to_game_vec4(v, nd: int = 4) -> list:
    """Blender point -> [x, y, z, 1.0] in game axes, rounded (path lumps, vector4m)."""
    return [round(v[0], nd), round(v[2], nd), round(-v[1], nd), 1.0]


def to_blender(p) -> mathutils.Vector:
    """Game (x, y, z) in meters -> Blender point."""
    return mathutils.Vector((p[0], -p[2], p[1]))
