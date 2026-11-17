# Ordered Priority features and fixes
Features and fixes to work on, have been ordered and can be checked out when they've been dealt with and tested.
Once a feature is part of a release, it'll get removed from here.

---
# Path additions (in main)
## Add an "add curve" option
There's already buttons to add waypoints dirrectly, There could be buttons to add a curve too as well. Instead of having to create one before and then link it. That way it'd automatically be linked too. Have both options like the waypoint where the first one add it on the 3D cursor and then "at actor position" to add it on at the actor's position.

When adding the curve, it should spawn the bottom left menu with things to adjust such as:
- Curve Type (list):
  - NURBS (default)
  - POLY
  - Bézier
- Curve Shape (list):
  - Circle
  - Straight line
  - Single point
    - An issue with NURBS and having a single point is that it'll automatically change the Order U to 2 (4 is the default and how opengoal works too). So if the addon is able to change that behaviour and keep it at 4, that'd be best
  - Half circle
- Number of points (integer) (depending on the shape and curve type this option would be visible or hidden)
  - NURBS
    - Circle (hidden, it should automatically add as many points as needed for making a perfect circle with NURBS)
    - Straight line (visible, Default to 4 points at a minimum)
    - Single point (hidden)
    - Half circle (hidden, same as circle)
  - POLY
    - Circle (visible, Default to 8, can be as low as 3 or as high as the max amount of points in a path, adding more points just make a regular polygon of that number of point, estimating a circle)
    - Straight line (visible, Default to 2 points at a minimum)
    - Single point (hidden)
    - Half circle (visible, same as circle, default to 4)
  - Bézier
    - Circle (hidden, it should automatically add as many points as needed for making a perfect circle with NURBS)
    - Straight line (visible, Default to 2 points at a minimum)
    - Single point (hidden)
    - Half circle (hidden, same as circle)
- Cyclic (on/off button) (shows for all curve type, is on or off by default depending on the curve shape:)
  - Circle (ON by default)
  - Straight line (OFF by default)
  - Single point (OFF by default)
  - Half circle (OFF by default)
- Endpoints (only show for NURBS is on or off by default depending on the shape:)
  - Circle (OFF by default)
  - Straight line (ON by default)
  - Single point (ON by default)
  - Half circle (ON by default)
- Size (in meters)
  - size of the diameter for circle/half circle (default 2m)
  - length of the line for straight line (default 2m)
  - doesn't show for single point
- Rotation
  - X/Y/Z values, defaulting to all 0 which means all curves are flat on blender's XY plane

The curve would then automatically be linked in the path menu of the actor where it was created from and be named to have the name of the actor+name of the path (path/patha/pathb/etc)+ numerical values in case there's multiple ones.

## Add edit button for curve/waypoints
Add a button inbetween the "frame" and "delete" buttons to the right to "edit curve/waypoint" which would select the curve, and then automatically switch to edit mode on it. 
If it's a waypoint (empty), it'd just select it and stay in object mode.

## Add collection for path curves
Make a collection for curve linked where they'd automatically go to when added as path and allow the collection sorter button to sort the connected curve as path to also move those to their collection 

---

# Smaller additions (in main)
## Level Orb count
At the moment, the orb count on the level seems to be calculated from orbs and crates with orb content. However, it does not seem to count orb-cache, pickup-spawner and probably any other actor that might spawn orbs. Most of those should be detected but it's still possible the count might not be correct so a way to enter it manually should be possible. Have an "orb count" settings in Level > Settings > Gameplay. If left blank, it'll auto calculate, if not, it'll use the number written down.
### List of known actors to check for orb count
- `money`
- `orb-cache-top`
- `crate` (of any type)
- Most enemies can have different pickup on death (would actually be good to be able to set that pickup too)
- `plant-boss` (5 orbs when you jump on its head after killing it)
- `pickup-spawner`
- `sunken-pipegame` (our custom type allows for any pickup in there, including orbs)
There might be more that I forgot

---

## Export selected definition options
At the moment, when exporting definition. The addon adds comments to the text and format it in a way that might be annoying to just paste back into your level files.
Here's a few options to help with those things:
- On/Off for "Add comments"
- Drop Down menu for formating:
  - Bracket & category (Would add the name of the category in front, ex: `"actors":` before the first bracket for each category)
  - Bracket (current way it exports actors/ambients/cameras)
  - No Brackets (remove the main emcompassing brackets at the start and end of categories, so you can just paste it directly in between other entities in the file)
- Identation offset (at the moment when copying cameras/actors, the indentation is off by one, this can either be defaulted to be one extra indentation or just give the user control here so they can select what they want, but default it to 1)

Also make sure to remove any extra lines at the top and bottom of the file, especially if you're using the "no bracket" so it perfectly fit when pasting into a file without having to edit it after or pasting it first in another text file to copy only what you need.

---

## Camera variant to spawn as the view instead of 3D cursor
Add a drop down menu to select the spot a camera should spawn at:
- 3D cursor (aligned view)
  - Current behaviour where the camera spawn at the 3D cursor and is aligned view
- 3D cursor (default view)
  - Spawn at the 3D cursor but default the rotation to 0,0,0
- Viewport View
  - Spawn the camera at the current view in the viewport

---

## Extra boot mode
Drop down selection, under the spawn options in the "Build and play" menu.
### Debug Mode
Current way the game boots. Make this the default option
### Debug Mode (attached debugger)
Whent he game crashes as you boot in the level, it's a bit annoying to setup the debugger yourself. If this option is selected then the game would start with debugger by doing these commands:
- task run-game 
  - this boot the game paused, waiting for the repl to send a test-play command to start, so you can catch crashes that happen on boot, might only be available in a dev environement, maybe there's just arguments you can set when starting gk for this too
- then in the repl:
  - (mi)
  - (lt)
  - (dbgc)
  - (test-play)
### Retail Mode
Starts the game in Retail Mode so you can test things out of debug

---

## Convert entities doesn't carry over nav-mesh, paths and actor entities links

---

## Changes to entity descriptions
Make the description of actors in the spawn actor menu collapsable

Also add the description at the top of the actor's "Object settings" right under its name, collapsed by default

---

## Project settings
New sub menu in the "level" tab. These are settings that are relevant to the whole project, not a specific level:
- `Retail Boot Checkpoint`: The checkpoint that loads when you boot in retail mode. Leave blank to not change it. Otherwise a menu with all base game checkpoints and the custom one from this blend file + custom option to write down anything.
- `New Game Checkpoint`: Same as above.
- `Discord RPC Status`: the status that show when you play this mod, in `goal_src/jak1/pc/pckernel.gc`. String input that's empty by default, if empty it shouldn't change what's set in the file.

---

## Snapping snap to preview mesh of the selected actor
This should be a changed behaviour, otherwise it moves the actors when you try to snap it to another surface. If possible the snap shouldn't be affected by the selected actor preview mesh that you're moving but still by the other preview mesh of other non-selected actors so you can line stuff up on them 

---

# Light baking addition 2 (in progress)
## Change Frame on time of day baking
An option I thought would give some very interesting control is to give the ability to set a frame per time of day. Then when that time of day is getting rendered, blender switch the animation frame to a set frame per time of day.

That way, users can set keyframes on these frames to change light intensity, move lights or meshs to create different shadows, change emit settings, etc. The possibilities would be endless.

The way it would be setup is a checkbox at the bottom of the time of day menu "Set time frame per time of day". Off by default, if it's on, one new line in each time of day would appear with the label "time frame" and an integer input. Then the addon can switch to that specific frame when rendering that specific time of day

## Emit per time of day
As well as this, another checkbox could be added in time of day that is "Render emit per time of day". Which as the name would indicate, will render an emit pass for every time of day instead of a single one applied to all time of days. 
This would be needed if the users want to vary emit intensity/colors depending on the time of day. As this would add a lot of rendering time, it should be off by default.
Make the pop message on hover on that option very specific that it's only useful if you're doing emit changes on time of days, if not it'll just add rendering time for no reason.

## Combining emits for render time optimisation
To speed up emit rendering, the mesh with emits could get another object together when using the "combine mesh while baking" just to render the emit pass or passes on that smaller object. Then combine the emits of that separated objects onto the larger combined meshes. That could be done regardless of if the emit per time of day option is turned on as it could save time in one single pass too.

---

## Delete color attribute tool
New tool in the "Objects control" > "Vertex Colors" called "Delete color attribute". This would delete all color attribute of a specified name (select in a list or written down) on every selected objects.

---

## Color Bit size
Having all color attributes of all time of days does increase file size quite significantly on large levels. The color depth used in blender is a lot larger than the one used by the game so a way to make the files smallers would be to to set the color depth to a lower bit value. 
Under the face corner/vertex button, you could have another option "Bit Size" with the default amount as a button then 6, 5 and 4 bit to lower the compression. These should be done at the end of the rendering pipeline so other effects aren't added after, changing the values again.
However I'm not 100% sure how this would work out. You'd think draco should take care of that but reducing color/generic values in the compression does not yield any better smaller results.
So before making any changes, we'll have to investigate how all of this works and see how to reduce best the file size

---

# Custom Tools and actors
## Actor/jak Light custom actor
Something I did in TFL is having some areas that affect the light on jak and other actors. However, the way worked was fit inside of the mood function. This comes with a lot of limitation and create a lot of extra code in there which wouldn't be needed if it was a single actor that did it with all its settings in the entity lump. You can check TFL's `goal_src/jak1/engine/gfx/mood/mood.gc` to see how it was done.
This actor code should be added to common/game.gd if the user uses it and not just per level's -obs.
### Implementation in the addon
Added in the "effect" category. Called "Actor Light" (etype `lt_actor_light`). When added it'd give you a sphere empty which size will be driven by the max distance the actor light will affect actors/jak.
Here's all the settings and what they'd do:
- `Min Distance` in meters (default 5m), the distance at which the light has full effect.
- `Max Distance` in meters (default 10m), the distance at which the light start having an effect. 
  - The strength of the effect is then calculated depending on the distance of the actor to the Actor Light using the min and max distance. (from the max intensity to 0 intensity)
- `Key Color` as a color picker (default to white), to choose the color that'll affect the Key lighting of the actor
- `Key Intensity` as a float value (default to 1.0), to choose the intensity of the key lighting
- The direction of the key light would be using the rotation of the actor. The default position would mean the light comes from straight ahead, then rotating would change that. Using the Z axis of the Actor Light in blender to determine the direction of the light, using the `quat` of the actor.
  - In the object properties, viewport display, the axis could be turned on automatically to so there's a nice visual on the direction of the light 
- `Ambient Color` as a color picker (default to white), to choose the color that'll affect the ambient lighting of the actor
- `Ambient Intensity` as a float value (default to 0.5), to choose the intensity of the ambient lighting
- `Affect Jak`, On/Off checkbox (default on), if off, the actor light would only affect the actors in `alt-actor` and not jak. 
- `Cylinder Mode`, On/off checkbox (default off), if this setting is on, the distance check would only be done on the x/z plane (in game), ignoring the height.
- `Mode`:
  - `Default on`
    - `On timer`, in seconds (default 1.0), The time it takes to go from 0.0 to max intensity when the actor light turns on
    - `Off timer`, in seconds (default 1.0), The time it takes to go from max to 0.0 intensity when the actor light turns off
  - `Default off`
    - also gets the timers
  - `Time of day`
    - `Time on`, in hours (default 18.0), time of day when it turns on
    - `Time off`, in hours (default 8.0), time of day when it turns off
    - Also gets the timers for how long it takes to turn on and off
- `Volume`, not required, if a volume is added, the actor/jak is only affected when inside of that volume. If there's no volume, then it just uses the distances set above.
- `alt-actor`, the actors that get affected by the lighting as well as jak. Allow multiple. Maybe we can set a maximum if this is heavy on the computing.
- `trigger-actor`, if this actor is dead, the light goes off, The `trigger-actor` can also send an on and off signal to turn the actor light on and off.

---

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

# Code Audit
Let's do a code audit, as well as the more general things, let's look at these things in particular:
## Cleaning old features
Cleaning old features and anything that's made to work with previous version of the addon. We don't need this code debt at the moment, we don't need to complexify the code for this at the moment
## Performance 
Take particular attention to performance for things that redraw/recalculate every frame instead of only when they should, etc
## Reusing functions
Reusing functions, whenever something has to do be done in multiple places, there should be one single function that's called instead of having multiple snippets of the same or similar code

---

# Others
## Better Linux support

---

## -
