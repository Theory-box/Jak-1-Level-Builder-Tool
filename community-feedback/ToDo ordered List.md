# Ordered Priority features and fixes
Features and fixes to work on, have been ordered and can be checked out when they've been dealt with and tested.
Once a feature is part of a release, it'll get removed from here.

---

# Custom Tools and actors

## UV tools
New menu in Object controls with a bunch of tools for editing UVs in ways that are useful for openGOAL. Each would be a sub menu in the general UV Tools. Each tool would work on the whole mesh (or the selected faces if in edit mode)
### Fit Faces on UV
This mode would take each quad face and place all 4 points in all corner coordinates of the UV (Triangles would go to 3 of the corners. N-gons wouldn't get moved)
This would have these options:
- Scale (default to 1.0) Scale the whole UV result by that value
- Rotation (Default to 0.0) Rotate the whole UV result
- Pivot: Set where the scale and rotation pivot point is centered on. Whith these options:
  - Corner (the 0,0 corner of the UV space)
  - Center (the 0.5,0.5 center of the UV space)
- Placement: Set how multiple faces are placed
  - Overlap (every face overlap at the center)
  - Spread (Faces are spread next to each other, with connected faces still connected. Starting from a cube project so a mesh with depth can be still worked with)
### Cube Project
Simply use the cube project with a scale modifier as well as an option to normalise each faces or not.

---

## Custom art group/actor/camera implementation
It is possible to create your own actor fully from scratch for opengoal even with custom art group and animation. The process can be a bit cumbersome both on the blender side and opengoal side.
Let's first starth with researching the topic to see what's needed from the blender side as well as the opengoal code side of things.
### Ideas for implementation
#### Templates
Since advanced actors will need some coding on the user's part. I'm thinking of having a few basic templates that could be used. Such as:
- Art-group (would only export the art-group to be generated in game.gp as well as the skeleton description)
- Basic Process-drawable (would create a child of process-drawable with the basic code and one idle state)
- Platform (would be a child of plat with the custom model, maybe a few extra could be added too for more controllable platforms)
- Camera animation (This would just create the art-group for a camera animation to be used by pov-camera)
- Nav enemy (a child of nav-enemy with all its settings available in blender directly)
#### Collection and menu setup
These actors wouldn't be directly part of levels so a fully new side panel could be added for this under the "OpenGOAL" one called "Custom Actors". So all the tools related to this would be separated.

This menu would be setup in a similar way to the "opengoal" panel, with a menu at the top to create and switch between different custom actors, a menu to export current/all custom actors, a setting menu for that specific actor where you choose the template type and all its other settings and other setting as needed, art-group for each art-group that'll be part of that new actor and its specific settings.

When a new actor is created it'd create a new main collection for all custom actors and then a sub collection for that specific actor. As well as needed other collections inside.

---

## Creating custom Particles tool (extra addon?)
It's a lot easier to just have people creating their own particle files and edit them in terms of buidling the addon but ideally. 
It would be very useful to have a particle editor and preview directly in blender where you can create, edit and see how each particle group work as that would be a lot quicker than editing particle files and then seeing the affect in game.
This would, however, be a huge undertaking and isn't priority at the moment.

---

# Others
## Better Linux support

---

## -
