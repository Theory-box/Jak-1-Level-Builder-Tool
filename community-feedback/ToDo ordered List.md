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

## Custom pov-camera actor
Custom actor, called "Camera animation" to spawn a pov-camera, either by entering a volume, a distance from it or only activated by another actor.
Options:
- to choose existing pov-camera from existing ones, made one in the blend file or just text to write down any.
- If it can only activate once, can activate on every respawn
Make actor that use custom camera for some of their action also able to trigger these custom pov-camera instead

---

## Custom mood creation tool
(this section is under construction)
- Ways to create moods directly by selecting existing/creating customs from template or blanks
- Matching mood lights from time of day env/sun

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
## Supress warning types
An option to supress some warning depending on their type. New sub menu in devlopper tools `Warning settings` With an option called `Ignore warning` and under, a list of the warning by types with a checkbox (all off by default), if that box is checked is on, then those warnings don't show up in the audit or increase the icon count.

## Import addon settings
Option at the bottom of `addon settings` which allows you to select a blend file and it'd import all addon settings from that file, with a pop up window listing which settings will be imported and a checkbox to activate/deactivate some then an import/cancel button

## Bin icon option for linked helpers 
As well as the X button to unlink those type of helpers, add a bin button which would delete the helper as well as unlinking it.
List of helpers that could get that bin button:
- paths
- waypoints
- position empties (movie-pos, launcher destination, etc)
- nav-sphere
- nav-mesh
Give a warning when pressing the bin that this will also delete the object completely, with a checkbox to not remind again if the user want to.

## Move  more created objects into collections
Both when creating them or when using collection sort
- Camera Pivot inside camera collection
- Launcher Destination into waypoints

## Link guides from addon
Buttons to open web browser on the guide, linking directly to the page and title. This should, if possible not add extra lines to make menus longer. So we'll see the best way to implement this.

## Model import duplicate meshes
As some meshes exist in multiple levels (ex: babak-lod0), these appear multiple times when searching in the model import. Any duplicate should be removed and only show one output.

## Better Linux support

---

## -
