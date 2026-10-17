# Ordered Priority features and fixes
Features and fixes to work on, have been ordered and can be checked out when they've been dealt with and tested.
Once a feature is part of a release, it'll get removed from here.

---

## Second entity pass
Based on `community-feedback/Actor Notes.md` and notes here

---

## Import from files feature
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

## Better Linux support

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

# Need some outside changes first

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
