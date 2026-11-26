# Ordered Priority features and fixes
Features and fixes to work on, have been ordered and can be checked out when they've been dealt with and tested.
Once a feature is part of a release, it'll get removed from here.

---

# Custom Tools and actors

## Custom pov-camera actor (in main)
Custom actor, called "Camera animation" (camera tab) to spawn a pov-camera, either by entering a volume, a distance from it or only activated by another actor.
Options:
- To choose between a pov-camera and normal camera
  - For pov-camera: choose existing pov-camera from existing ones, made one in the blend file or just text to write down any.
  - For camera: select a normal camera and an actor it's looking at + time length
- If it can only activate once per playthrough or once every time it's called
- Activate by:
  - Distance: Give you a distance in meters from the actor it'll activate when jak's within that distance.
  - Volume: Give you the volume menu to activate it. (if it's set to being able to be acticated more than once, this shouldn't call it again until the actor reload by death/load/etc, same for the distance option)
  - Alt-actor: link to send a trigger input to activate it (use same event as basic buttons so it's easily useable with existing actors)
Make actor that use custom camera for some of their action also able to trigger these custom pov-camera instead (not required as you can activate it with volume instead)
- prev-actor/next-actor to play multiple Camera Animation in a row, using each of their settings. So if you activate the first one in a chain, the next one play in sequence.

---

## Custom mood creation tool (in progress)
### Research
You can research the topic yourself but here's what I know:
- The mood function determine how the mood is used. (in mood.gc)
  - For some level it's just setting each time of day lighting 
  - For others, it's using a single time of day (interior levels)
  - Some have special effects such as thunder in village2, lamp glowing in village1, Blue eco glow in jungleb, and more
  - For levels with special effect, sometimes one of the palette is used for it instead of for time of day.
- The mood table set all of the values for: (in mood-tables.gc)
  - Creating light-groups
  - sky and sun
  - fog
  - actor lighting
  - Shadows
  - stars
- When defining the mood, you also can set each of those separately so you don't need to create something extra if you just want to reuse part of another
### Addon implementation
This will be its own tab like tasks. Inside of it, a small description at the top for moods and 2 sub menu inside, one for mood functions one for moods. This implementation is based on my understanding of the mood. If anything does not work the way I'm expecting it and it'd have to change the implementation a bit, put it in the plan.
#### Mood function menu
Inside of the Mood function menu, you can have another small description at the top, then a + button to add a new mood function. Adding a new mood function would add a new block similar to when adding tasks, to control the mood function. Here you'd have options for:
- Name of the mood function (default to the level that's selected when creating it as update-mood-levelname)
- A template button at the top which fill the options to fit that function (taken from base game levels + the already existing mood functions in this file)
- Which time of days vertex colors should be active and at which time of the day they are. (make this a collapsable menu as it will be list of 8 options)
  - For each of them, you could activate/deactivate them
  - Set the time
- Special effects
  - Checkbox per effects, then options under it, if the checkbox is activated, to set their parameter. (like which vertex color table it uses, and other settings)
  - It'd have all the already existing effects + some extra such as:
    - Lock time (lock the time of day, set a time in hours)
    - (Might think of some other, maybe some weather effects, if you have some idea of things to be implemented here, you can put them in your plan)
Each mood function would have a checkbox to export it or not, a delete button and a duplicate button. Make each function collapsable too
#### Moods menu
Similar to the mood function. For each of them, as well as the name and template have:
- A checkbox that's "Match level lighting". When active it would:
  - This would use the world settings for ambient light as well as the main sun found in the collections of time of day to determine sun positions, main key light, shadow directions, etc.
  - Show a selection of a level to use. With a message to say if it found the world/suns in there
  - Value to adjust how bright or light the values are taken from blender sun/worlds. Default would be 1.0 but then it could be changed to make it brighter (>1.0), or darker (<1.0). Useful as it might be hard to match it perfectly for everyone, especially if people have different curve settings and such.
  - When this is selected, the values would be built on export instead of just be set once. So changing the world/sun values would reflect in the exported mood. Any setting that'll be driven by this will be greyed out in the menu with a small text next to it "Driven by level lights"
- All of the tables with related settings, with an option to set an existing table of base level+blend file ones or custom, which would then give you all the settings to build your own (each of them collapsable):
  - mood-fog-table
    - Per time of day (with checkbox to deactivate some if you just want to set some up, the addon would still export a full table, just with "empty" tables as a lot of levels do in the base game)
    - fog-color
    - fog-dists
    - erase-color
  - mood-lights-table
    - Same thing per time of day
    - direction (may be controlled by "Match level lighting")
    - lgt-color (may be controlled by "Match level lighting")
    - prt-color
    - amb-color (may be controlled by "Match level lighting")
    - shadow (may be controlled by "Match level lighting")
  - mood-sun-table
    - Same thing per time of day
    - sun-color
    - env-color
  - interp-table
    - Per hours settings, not sure what each of these do. I'll see how useful it might be from your plan
  - num-stars
    - Just a number, default to 85.0
#### Export
Export all the function in a custom file and all the mood in a custom mood-table file. So these take less time to build when making changes inside instead of using the base game mood.gc and mood-tables.gc

---

## Custom ocean map creation tool
(this section is under construction)
### Research
You can research the topic yourself but here's what I know:
- Ocean setting in `level-info.gc` pointing to an ocean-map
- These ocean maps are defined in `ocean-tables.gc`, each maps is built from multiple parts:
  - `ocean-map`
    - start-coner (Position of the starting corner, using then origin as the center to set its size. Also look if there's ways to easily make the center editable so people can create ocean maps very far away from the origin)
    - far-color (the color of the far ocean, aka outside of the grid)
  - `ocean-spheres` (not sure what those spheres are exactly for, they have X/Z positions to place them onthe grid as well as a third value, probably for their size.)
  - `ocean-colors` (To set the color for each of the ocean squares,;)
  - `ocean-mid-masks` (Allows you to mask specific squares or not on one of the main squares, they're hexadecimal values that when switched to binary, read as 1 to render ocean and 0 to not)
  - `ocean-mid-indices` (to match one of the main squares to one of the mask can also uses xffff and x0 values to set them to fully rendered or not rendered at all so that you don't need to create specific mid masks for every single square)
  - `ocean-trans-indices` (Not sure what this one is for)
  - `ocean-near-indices` (I think this one is masks for when you're even closer to be even more precise but I'm not exactly sure how they relate to the rest)
- All of these are then set within a single `ocean-map`, eachg can also reuse definition of another map instead of creating your own.
### Implementation in the addon
Similar to mood and task, this will need its own menu, under the mood one. Have a buttont to add a new ocean map. When clicking it, it'll be like the task/mood as it's own sub menu that can be collapsed/deleted/etc.
Same as mood, use the name of the selected level to create the default name.
Inside of the level settings, add the same button as for mood/mood-functions to select an ocean from this blend file.
#### Ocean options
Inside of each of the ocean you'll have some options
- General options (at the top, not in a sub menu)
  - Name of the ocean map
  - Far color (color picker, find the most used color in the ocean tables and use that as default)
- `Grid settings` (sub menu, collapsed by default)
  - Not 100% sure what control we have over the grid, if we can change the number of big squares different than 36. (6x6) If so have a setting for the number of squares per sides.
  - How each square is cut. If they're as precise as mid masks or down to near. It might be a lot easier to just make all squares at mid mask level.
- `Ocean color` (sub menu, collapsed by default)
  - Drop down to use existing ones from base game or to use its own color.
  - It's "own color" would be set as a color attribute, once again, using the same default color as 
- `ocean-mid-masks` (sub menu, collapsed by default)
  - Drop down to use existing ones from base game or to use its own materials.
  - These would be set through materials, similar to how nav meshes are done. One blue material for displaying water and one black/transparent for masked squares.
- `ocen-mid-indices`(sub menu, collapsed by default)
  - Drop down to use existing ones from base game or to be automatically made from the material.
- The other two settings, we'll see in the research and plans if they're useful or not to add.
#### Export
Same as mood, put all of them in a separated file so it's onw its own. 

---

## Custom art group/actor/camera implementation
(this section is under construction)
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
(this section is under construction)
It's a lot easier to just have people creating their own particle files and edit them in terms of buidling the addon but ideally. 
It would be very useful to have a particle editor and preview directly in blender where you can create, edit and see how each particle group work as that would be a lot quicker than editing particle files and then seeing the affect in game.
This would, however, be a huge undertaking and isn't priority at the moment.

---

# Others
## Modifiers on actors (mirror/array/scatter/etc)
(this section is under construction)
  - Ability to either directly use the modifier of blender on the actor empties or have our own menu for it in object controls
  - When some modifier are present, the addon would export copies of the actors as well depending on the 


## Better Linux support
(this section is under construction)
I need to re-test latest versions of the addon on linux to make sure these points are correct.
Some features don't work directly within linux (opening terminal on its own, doing the (mi), starting the game)

---

## -
