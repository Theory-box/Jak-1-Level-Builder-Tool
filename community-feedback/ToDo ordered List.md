# Ordered Priority features and fixes
Features and fixes to work on, have been ordered and can be checked out when they've been dealt with and tested.
Once a feature is part of a release, it'll get removed from here.

---

# In main

## Import from files feature (in main)
A feature that would let you import a text file and the addon would create actors, checkpoint, navmesh, paths, etc, based on those definitions.
### UI Panel
Use the already existing `import` menu. Divide it for the 3D model import, move the texturing menu inside there and then also have an actor sections. Like this:
- Import
  - Game 3D models
  - Game textures
  - From GOAL files

The import from files would just be an input to search for files. Or a button to import text copied in the clickboard.
Once text is loaded, it should show a list of all object found, organised by categories. And allow you to select/deselect which ones you want. With a select/deselect all button and then an import button when you've made your choice.
Select all objects that were imported.
### Available to import
- Custom level Json / exported actor list from the game
  - Actors (Fill every field in the actor based on the definition in the json, if a field doesn't exist, add it as custom lump)
  - Paths (automatically made from the path definition of the actors and automatically linked)
  - Volumes (same as paths)
  - Ambients
  - Camera
- Entity.gc / nav file
  - navmesh (as mesh with the materials assigned already)
- level-info.gc
  - checkpoints

---

## Export as another entity (in main)
Useful tool to have, especially if users make custom actors that are child of another entity, would be an option where you can write down the etype that would be exported. All it'd do would just be changing the etype in the actor export. The rest of the actor would export as if nothing had changed. 
That way, if someone has made a custom version of an existing actor, they can just spawn that existing actor then change the "export as" option and it'd use their custom actor directly.
It can just be one extra field at the top of custom lump in the actor settings so it's not too much in the way as that'd be a feature that's not used that often  

---

## Small UI changes (in main)
### Main panel re-organisation
Not sure what the default order is right now since I've moved them a lot in my testing file but here's what the default order should be:
- Build & Play
- Level
- Spawn Objects
- Obects Control
- Object Settings
- Light Baking
- Tasks
- Import
- Developer Tools
### Level
- Move the `Level Manager` sub menu at the top. And remove the selection of levels inside of it. There's already a drop down menu for levels at the top of the main panel
- In `Collections` Move the `sort & Clean` button outside of the `Clean` sub menu and put it at the top of the Collection menu
### Spawn Objects
- Move the `Spawn` button right under the name of the seleted actor
### Developer Tools
At the moment, this panel is a long list so we should have a few sub menu that are collapsed for a cleaner UI:
- Paths
  - Paths
  - Use this .blend's folders
- Addon settings
  - Launch Timing
  - Build Settings
  - Versions
- Quick Open
The "clean file" button can stay at the top, without being in a sub menu. When pressing it, it should open a popup telling you which files will be deleted/edited and then confirm with a "delete" and "cancel" button.

---

## Switch Nav-mesh feature to TFL implementation 
While this isn't implemented in mod-base yet, this does not mean it's not useable if the addon just create the files and changes. 
### Research
You can check on https://github.com/Kuitar5/the-forgotten-lands/ how it works. Here's a few pointers:
- [tfl-nav-mesh.gc](https://github.com/Kuitar5/the-forgotten-lands/blob/main/goal_src/jak1/engine/mods/tfl-nav-mesh.gc)
  - Where the custom nav-mesh are defined. They're mostly similar to how they're defined in the other, mod-base way.
  - Where the list of nav-mesh is defined
  - Where the setup is made
- [entity.gc](https://github.com/Kuitar5/the-forgotten-lands/blob/e8618a3022879ce45eee7ffd227e7d41949638df/goal_src/jak1/engine/entity/entity.gc#L842)
  - Where `custom-nav-mesh-check-and-setup` is called
- [Any level .json](https://github.com/Kuitar5/the-forgotten-lands/blob/e8618a3022879ce45eee7ffd227e7d41949638df/custom_assets/jak1/levels/energy-bay/energy-bay.jsonc#L801)
  - `custom-nav` lump to select from the list of nav-mesh
- [game.gp](https://github.com/Kuitar5/the-forgotten-lands/blob/e8618a3022879ce45eee7ffd227e7d41949638df/goal_src/jak1/game.gp#L2066)
(when it's implemented on mod-base)
  - Not forgoting to add the new file in here so it compiles.
You can have a look around see if there's other things I missed.
### Advantages
The main advantage is a cleaner approach, not changing the base files much, each nav-mesh is sparated, you don't need to set it by aid so it's more understandable in the level's json too. As it's a differen file, it doesn't need to compile as much other files when making changes on nav-meshes.
### Setup for the addon
As with camera, makes this a settings but default to current implementation, this will only be the default once mod-base has been updated to it.
### Additional nav-mesh features
These features should be available regardless of which nav-mesh implementation is selected

We need a way to set some faces as "jump" (written as `:pat 1` in the nav-mesh definition, you can also check if there's more than that and what they do).
My idea is to have some special navigation materials which automatically get added as slots onto nav-mesh meshes in blender. Then users can switch to edit mode, select the faces they want as jump and change them however they want.
If you have a better idea you can propose it.

Nav-sphere are also not implemented correctly. At the moment the addon export one nav-sphere per nav-mesh. But no nav-sphere should be exported by default. Those serves to set areas that the enemies will avoid. As it's easier to sometimes put a nav-sphere to block an area than complexifying the nav-mesh itself as there's a vertex limit.

Add a collapsable menu at the bottom of nav-mesh for nav-sphere. Where you can add them by searching for empties or by directly adding one from the menu. The sphere then use the scaling of the sphere times the size of the empty and its position to write down all the nav-sphere definitions.

---

# Second entity pass (in progress)
Continuation status: new actor records and edited files implemented; static/Blender export
validation complete, runtime acceptance pending. See Actor Notes and session-notes/entity-pass-2.md.
Based on `community-feedback/Actor Notes.md` and notes here. Start by reading your note and these ones and then make a plan of actions before making changes.
### nav-enemy
Change the info to "Nav-enemy, needs navmesh and path"
Remove the "sphere radius" selection before spawning
### database driven edited actors
If an actor is using special edited code that are set in special files in the addon. The link should be done in the database. There should also be folder you can point to in the addon path settings with other custom codes. So they're easy to select and add. Also you should be able to set if an actor code will go into the level's -obs or in another file that then could be reused between different levels
### Hidden/not added entities
Actors that have been skipped because they have hard coded tasks or positions should be made into edited actors instead of just being ignored. (most NPCs probably need to be edited so they can have custom tasks)

---

# Light Baking additions
## Make the "view" buttons for time of day also set the render color
At the moment, the view button next to time of day will change which color attribute is selected but it won't change which one is set for render. Doing the later one as well would allow you to show it in textured mode too if the user has combined their material to show the effect of the lighting on the textures too.

---

## Optimising light baking
At the moment, when baking multiple objects, the addon/blender have to start 8 different renders per objects. The more object you have, the crazier the time to complete this get. 
### Test on a complex scene
Here some tests I just ran on an existing level, which is a very complexe scene (4.5m trianges as it's 4 levels in one file, many light sources)
I used 4 stone walls, totalling 22k triangles:

1 bake per object 
- 128 samples:
  - 1:35
  - 1:32
  - 1:31
  - 1:29
1 bake of 4 separated objects 
- 128 samples:
  - 5:53
1 bake of 1 combined objects:
- 128 samples:
  - 1:38
- 64 samples:
  - 1:33

As you can see, each object baked take about the same time, even if they're all 4 combined into a single object. Considering my levels are in the hundred of objects, this can easily create bakes that could last 10+ hours. I also experienced a crash trying to start a render of a full level during the night.
### Problems with combining
The obvious solution would be to combine all meshes that need to be baked into one. However this comes with some issues:
- You lose all separated objects so controlling them becomes harder as you'd need to select all the vertex inside of everything
- By losing all objects you lose their object propeties:
  - Individual origins
  - Their positions, rotations, scale
  - Their custom properties, which include the collision properties whish is very important to keep. While users can use materials to set those, it's very useful to be able to use both.
### Potential solution
After thinking for a bit, I came up with a solution, let me see if it's doable or if there's a better approach than this.

- First, for each object, instead of combining them, you separate the whole mesh from them. Which leave us with two objects:
  - The original object, which now has no mesh inside, but has kept all of its properties
  - The separated object, which contain the mesh
- Secondly, we combine all of those separate objects together, but not the original objects
  - While combining them, for each object that get merged, a vertex group (or another attribute) is created and is named the same as the name of the ORIGINAL OBJECT (not the separated object itself)
- Third, bake that singular combined mesh, and nothing else. This should be a lot quicker than separate bakes for each objects
- Fourth, the combined mesh get separate using by their vertex group (or the other attribute) and merged back into the original mesh of the same name from the attribute.

This should both allow for a much quicker bake but also let the user keep all of his original objects. This should also be an option that's off by default that users needs to turn on if they want. "Combine all meshes during light baking (Speed up baking on large scenes)"

---

## Copy lighting/color attribute from nearby
Something that doesn't always give a great result in the light baking is things like grass. Because they're vertical from the ground, the way light will hit those planes won't be the same as how they hit the ground under them. As such, the lighting might be drastically different on them.
Something I've done in the past is to manually paint them, using the vertex color from the grass under them.
I'm trying to automate this process.
### Implementation
New sub menu in `Objects controls` called  `Copy vertex lighting from closest`.
With one drop down menu at the top:
- Copy from selected to active
- Copy from any geometry to selected
Then the button to copy

---

## Quantisation for vertex color
The Palette of colors for vertex lighting is limited, especially for the darker part. So when something is in the shadow but has some color tint, it can come out as weird colored spots in game. 
If we could have the same quantisation of color in blender it'd make it easier to see end results more clearly and then adapt them as another option in the vertex light baking. Maybe even with some sub options to decolor very dark areas or other useful ways to control lighting

---

## Copy Worlds/Collection
Buttons to copy the world and collection used for time of day from another level in the blend file. Makes it quicker to setup multiple levels that use the same lighting. This should set the collections and worlds to the exact same ones, not make copies of them.

---

## Adding curve "fit 0.25 to 1.0"
Adding a light curve in the light baking curve preset that's similar to the fit 0.25 to 0.75 but with 0.25 to 1.0

---

# Path additions
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

# Smaller additions
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

## Texture remap
### water-anim texture remap doesn't seem to work

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
