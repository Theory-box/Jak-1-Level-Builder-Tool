# Ordered Priority features and fixes
Features and fixes to work on, have been ordered and can be checked out when they've been dealt with and tested.
Once a feature is part of a release, it'll get removed from here.

---

# Custom Tools and actors

## Custom pov-camera actor
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

## Custom mood creation tool
(this section is under construction)
- Ways to create moods directly by selecting existing/creating customs from template or blanks
- Matching mood lights from time of day env/sun

---

## Custom ocean map creation tool
(this section is under construction)
- Driven by it's position/size and materials
- Each sections should have a way to select the level of "details" for how precise you want to be 

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

---

## -
