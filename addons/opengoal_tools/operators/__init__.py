# ─────────────────────────────────────────────────────────────────────────
# operators/ — OpenGOAL Level Tools button actions
#
#   spawn.py   — spawn entities, volumes, cameras, emitters
#   level.py   — level/collection management, GOAL code, music zones
#   actors.py  — per-actor property setters + generic field ops
#   links.py   — actor/volume/navmesh links + waypoints
#   build.py   — export/compile/play/bake pipeline
#   misc.py    — camera setters + nudge ops + selection + utilities
#
# Each submodule exports CLASSES. ALL_CLASSES aggregates them.
# ─────────────────────────────────────────────────────────────────────────

from .spawn   import CLASSES as _SPAWN_OPS
from .level   import CLASSES as _LEVEL_OPS
from .actors  import CLASSES as _ACTOR_OPS
from .links   import CLASSES as _LINK_OPS
from .build   import CLASSES as _BUILD_OPS
from .misc    import CLASSES as _MISC_OPS

ALL_CLASSES = (
    *_SPAWN_OPS,
    *_LEVEL_OPS,
    *_ACTOR_OPS,
    *_LINK_OPS,
    *_BUILD_OPS,
    *_MISC_OPS,
)

# Re-export every class by name for `from .operators import OG_OT_Foo`
# compatibility with any consumer of the old single-module layout.
from .spawn  import *
from .level  import *
from .actors import *
from .links  import *
from .build  import *
from .misc   import *
