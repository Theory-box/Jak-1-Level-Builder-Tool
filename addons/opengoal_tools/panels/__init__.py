# ─────────────────────────────────────────────────────────────────────────
# panels/ — OpenGOAL Level Tools UI panels
#
# The addon's UI panels, organized into focused submodules:
#
#   level.py         — level management (create, assign, audit, music, light-bake)
#   spawn.py         — spawn picker (search, category tabs)
#   selected.py      — selected object root panel + shared draw helpers
#   actor.py         — bespoke per-actor panels (complex UIs that aren't
#                      fully data-driven)
#   actor_fields.py  — generic data-driven panel (reads fields[] from DB)
#   scene.py         — non-actor scene objects (cameras, emitters, triggers)
#   tools.py         — build/dev/geometry tools
#
# Each submodule exports a CLASSES tuple of its registerable Panel/Operator
# classes. This file aggregates them into a single ALL_CLASSES tuple that
# the addon's top-level __init__.py consumes.
# ─────────────────────────────────────────────────────────────────────────

from .level import CLASSES as _LEVEL_CLASSES
from .spawn import CLASSES as _SPAWN_CLASSES
from .selected import CLASSES as _SELECTED_CLASSES
from .actor import CLASSES as _ACTOR_CLASSES
from .actor_fields import CLASSES as _ACTOR_FIELDS_CLASSES
from .scene import CLASSES as _SCENE_CLASSES
from .tools import CLASSES as _TOOLS_CLASSES

ALL_CLASSES = (
    *_LEVEL_CLASSES,
    *_SPAWN_CLASSES,
    *_SELECTED_CLASSES,
    *_ACTOR_CLASSES,
    *_ACTOR_FIELDS_CLASSES,
    *_SCENE_CLASSES,
    *_TOOLS_CLASSES,
)

# Re-export every class by name so legacy `from .panels import OG_PT_Foo`
# keeps working during the split transition. Once the addon's __init__.py
# is updated to use ALL_CLASSES, these re-exports can be cleaned up.
from .level import *
from .spawn import *
from .selected import *
from .actor import *
from .actor_fields import *
from .scene import *
from .tools import *
