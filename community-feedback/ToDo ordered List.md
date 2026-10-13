# Ordered Priority features and fixes
Features and fixes to work on, have been ordered and can be checked out when they've been dealt with and tested.
Once a feature is part of a release, it'll get removed from here.


---

## Particles implementation
### Existing Particles
- The game has already a bunch of particles that can be used to be placed in levels.
- Most of these are usually in particle files called "level-part.gc" or in actor code files that are spawning particles
- The default etype for particles is `part-spawner`, each level file creates its own etype, (for example `swamp-part`), to separate them in the list but it is not a requirement to use those child type.
  - `art-name` lump is then used to choose which particle group that part-spawner should spawn
  - game task can be used to turn off 
- Particles can have a sound effect attached to them.
  - `effect-name` for the sound name 
  - `effect-param` 4 values to edit the sound
  - `cycle-speed` 2 values to edit how the sound play/repeat 
    - -1.0 , 0.0 for constant loop which should be default
    - Need some testing to see how these two numbers work
### Implementation for existing Particles
- Particles should probably have their own category, although, as with a few categories, there's not that many actors that'll fill the list. (like audio, volumes and level flow) Maybe some of these could end up being combined. Like audio and particles together
- Particles might need a specifically built UI panel BUT it should still be database driven
  - The list of level-part files should be in the database and then the particle group should be listed within them
  - While particles are also in other actor code files, I think only those level ones should be implemented this way to not make the list too long and also to avoid including huge code files in the level's gd for just one particle effect. (if users really want to do that, they'll be able to do it via a custom particle)
- When selecting the Particle Spawner, there would be two variant choices:
  - The particle level file
    - As a drop down list
    - This will tell the addon which code file to add to the level's gd
    - If implemented, this would also change the etype to that level's specific part-spawner child type
  - The particle group
    - As a drop down list
    - This tell what to put in the `art-name` lump of the actor.
    - It should only list the group that are contained within
    - If a second option for the variant isn't something trivial to add, this doesn't n
- Once a particle spawner is added. Those two options should still be editable.
  - Also as drop down lists.
  - This means, if the etype change is added, it needs to be able to be changed by this too. Otherwise the game might try to spawn an actor which isn't defined if a part-spawner was added as one level then edited after. Which is also why it might be easier to just set every particles to be `part-spawner` etype.
  - The Particle group menu should correctly switch everytime the particle level file is changed
- The sound options should also appear in the panel
  - None of the audio lumps need to be exported if no audio is selected.
  - The audio list option should automatically be populated by the available audio sounds (common bank + the two added bank to the level or all of them if the hack for all audio bank to be loaded is implemented)
  - If the audio isn't `none` then it can export all 3 lumps:
    - `effect-name` for the sound name that was selected as a string 
    - `effect-param` 4 float values:
    - `cycle-speed` 2 values to edit how the sound play/repeat 
      - -1.0 , 0.0 for constant loop which should be default
      - Need some testing to see how these two numbers work
### Implementation for custom Particles
- Custom particles would work almost identically but instead of choosing level and group in a list, you'd have 3 string input to write them down:
  - "File Name" to include in the gd
  - "etype" defaulting to `part-spawner` to change the etype.
  - "Particle group" to change the `effect-name` lump
- Sound options should be identical


---

# Less Important features and fixes

---

## Camera fixes
### Path
Camera aren't using the path panel. They should, even if it put the panel a different place.
### Volumes
Volumes should also use the normal volumes panel. Volumes for camera can also have priority volumes and cutout volumes.
Same as for multiple paths, those should be flags that you set in the volume panel that allows multiple volumes per menu, if it needs the priority volumes and same for the cutout.
These can be features of volumes in general which needs to be turned on for actors that need it. (at this moment I think that's only cameras but can be checked to see if useable elsewhere)

---

## Entity control features
### Select an actor on spawn
When spawning an actor, it put it as the active object, which is useful for changing its settings but it doesn't select the actor directly. Which would help in case the user want to move/rotate/scale the actor directly too.
### Use preview mesh for selection
Actors can be quite hard to select sometimes because you have to click exactly on the empty shape lines. A much easier way to select objects would be to be able to select the preview mesh. At the moment, they're set to not being selectable as they're a child of the actor so you don't separate them and such.
There's two ways I think this could work:
- Either, make it so the addon automatically select the parent instead when you select a preview mesh in the 3d view. (still let you select preview mesh in the outliner if you need to for whatever reason)
  - This might not be easily doable, especially if you're selecting multiple actors with Shift + click or with border select for example
  - An advantage of this way would be a switch you can turn on/off if you want to use the feature since it wouldn't change the relation between preview meshes and empties.
- Or, when an actor has a preview mesh, the actor becomes the preview mesh itself
  - This has the benefit of avoiding potential issues with selection that come with the other solution
  - This loses some useful features with empties as actors, such as the driver or the offset
So ideally, I'd prefer the first approach if all the selection kinks can be smoothed out.
### Automatically apply some settings on spawn based on selection
If some specific objects are selected before you spawn an actor, such as paths, volumes ,navmesh or nav-mesh-actor, they'd automatically get added to the actor as you spawn it, here's a few example:
- Select a curve and a navmesh then spawn a nav-enemy, that actor directly get the nav-mesh and path connected.
- Select a volume and spawn a water-vol, that volume get linked to that water-vol directly instead of creating a base one
- Select an actor that already is connected to a navmesh and spawn another navenemy, that new enemy get linked to that selected actor on its nav-mesh-actor
- Select a curve, spawn a platform that use paths, the platform get the path directly added
- etc
Other actor links could also be added to this but it might become a bit more messy so limitting to these 4 ones would already be pretty good.

As this is a feature that would automatically do something for the user, it should be under a toggleable option "automatically connect spawned actor to selection" in the developper tools/setting tab if one is added later.
### Adding actor through Shift + A menu.
Add an option on the shift + A menu to add an opengoal actor. This would open a search bar to search for actors directly.
Have it at the bottom of the menu, called "OpenGOAL object"
### Naming schem breaking on new levels
- When spawning an actor that already exist on another level. That actor expect to be the first so it'll be given the .001 on its name, duplicating that actor does and name that new one correctly.
- With checkpoints, you can't have two checkpoint named the same thing for two different levels because they're named `SPAWN_name` or `CHECKPOINT_name` so if you have two checkpoint named `SPAWN_start` then the second one will be `SPAWN_start.001`
  - Maybe the vis/short name of the level can be included in the object name in blender as such: `SPAWN_lev_start` but then still export it ignoring the short name level

---

## Specific tools/menu for some actors
### citb-drop-plat
This actors can have a very long list to define all of the platform that makes it up.
We need to be able to set the number of platforms on X and Z axis with `count` lumpt
Then you can either have it set as random platforms or you can set every platform yourself.
When you set every platfom, it's all in one single lump, `plat-type` that can have:
- 0 = No platform
- 1 to 5 = The different colors

To make this easier to visualize and use. You can have a collapsing menu for the plat-type which create a grid of buttons equal to the count values.
Each button would have the number and be colored, dark grey for no platform and the correct color for each of the platform types.
Clicking on the button would scroll through the numbers from 0 to 5
Then a platform preview mesh would be added and get edited for each platform at the correct spot to get a full visualisation for the user
### race-ring
The prev/next chain feature already help a lot for race-ring but it could be made even easier.
Give a path to the race-ring but instead of it being there to export a path, if it has one, it'll:
- export a race-ring on every point on the path instead
- connect a circle empty (with a rotation to match how it'd appear in game)
- connect them all through prev/next
- game task set to all
- use the "tilt" value on each point as rotoffset
  - race-ring have a built in feature that rotate rings depending on previous and next ring. This behaviour should be replicated to show it in blender and then match the tilt to how they'd change from the rotoffset
- Multiply the "weight" value to the default set delay
- movie-pos would only be set to the last ring

Race-rings color are also kind of hard coded. Havin a custom type that allow us to connect to other particles and then have automatic particle definition that get created from a single color input. Check existing race-ring particle for examples
### evilplant
### Distribute plat along paths

---

## Export settings
### Geometry compression for export (Draco)
- Draco compression algorithm is useable in useable in opengoal, which allow you to shrink level glb files by quite a lot
- Since the addon takes care of the export itself, there should be an option to turn this on as well as have all of the settings you normally have to control the compression.
- A way to achieve full export control, without having to create duplication of all these menus would be to use the "collection export" feature of blender, then users could just change the settings there. The addon would just create the export and set everything that's needed. (correct settings for vertex color, custom property export, the right glb name in the right folder, etc)
- This would also help with the next point in export settings
### Deactivating selections on a collection shouldn't stop export of this one. 
- very useful on geometry while working with actors
- I'm guessing at the moment the addon uses "export selected" and manually select everything that's needed for the export which is why things doesn't get exported if the selection is turned off
- I'm proposing to change that to use the "collection" export feature. It can even be set only to a main geometry collection. That way the glb export is also cleaner and doesn't have any extra data it doesn't need.
- Users would just need to make sure they place their geometry in those folders but a warning could be given as well as a button to move geometry in those folders if some is found. But make sure you let users create sub categories inside of that main export geometry folder so they can organise themselves as well.
### Quick level export
Might already be what "Quick Geo Rebuild" but if it is, then it can be renamed. What this should export is:
- level.gd info
- level's glb
- level.json (all actors, camera, settings, art-groups, etc)
But NOT checkpoints/load-boundaries or anything touching other files, not even nav-mesh definition.
Then rebuild too.
This isn't as needed if `Ignore unedited files` is added but good to have still.

---

## Game and Blender version check for different features
Some features of blender or in opengoal might vary depending on which one you're using. 
For blender, there's its version, 5.2, 5.1, 5.0, 4.5, 4.4 or later/earlier.
For OpenGOAL, there's 3 main ways, which then have their own versions too:
- jak-project releases:
  - 0.3.8
  - 0.3.7
  - etc
- jak-project dev environement:
  - commit names
- mod-base dev environement:
  - commit names
Being able to say when a feature is used by some versions or not would be very useful for multiple reasons. The main releases can use the versions where the two other dev environement, I think it's fair to expect the users to be on the last version and/or have a warning message to tell them to update if a feature requires a specific version.

I'll write down specific to versions ideas here so these should give you a warning or just not allow the feature.
### Make spawn use mod-base spawn feature if mod-base detected
Available in
- any mod-base version 
- not on jak-project dev/releases 
If the user is using a version that doesn't have this feature, it should just be off with a tooltip telling why.
If they're using a version with the feature, have the check for it in settings be on. 
- Current spawn option when starting the game boot the game normally and then teleports you after a few seconds
- mod-base, a fork of opengoal that's used by most people creating mods, has a file called `mod-settings.gc` in `goal_src\jak1\engine\mods\`
- This file has `(define *debug-continue-point* "village1-hut")` which can allow you to directly boot debug into any checkpoint you want.
- If the addon detect that you're using mod-base (can check if mod-settings.gc exists), this value could be changed instead of teleporting you after booting up the game.
### Time of day version check
Available in:
- release 0.3.8 and later
- jak-project from commit (d04ac9d)
- mod-base from commit (3a0aadf)
If the user's version is too old. Keep the menu there but give a warning.
(See later steps on how to implement)

---

## Baking options
### Jak handling of vertex color for lighting
There's some limits in terms of how Jak 1 handle vertex color for lighting
- Limit range of lighting 
  - Anything under 0.25 brightness will be considered black
  - Anything above 0.75 brightness will be considered over exposed/look as if it was emiting light
- Limited numbers of color
  - This already is very well handled by the level builder so no changes needed
### Current way baking works and issues
At the moment, baking lighting into vertex color is done by using the baking option "Diffuse" with "Direct" and "Indirect" selected but not "color".
This does the job for most things but it does not handle emiting materials well and doesn't take into account the limits that Jak 1 uses
### Proposed baking changes
#### Better handling of Emit
When an object has emiting materials (strenght value not set to 0). I also bakes the emition separately and then combine both of them, using a "screen" method of blending the color as it's only supposed to brighten the result. This should also have a setting of how much the Emit will affect the end result because even just a low emit pass could overblown the brightness if applied 100%. I'll try different values and see what makes most sense as default but users should be able to edit it.
#### Limiting options
To make uses of the 0.25 and 0.75 limits, I think some math could be applied to baking so it fits more between those values. However, it shouldn't just be shrinking everything to fit inbetween those. Otherwise, you can get a very bland results where nothing seems to be too dark or too bright. The game does uses values over 0.75 to indicate stuff that's being hit pretty hard by lighting so those values shouldn't just be cut.

One way to do it would be to give you an RGB curve edit option, similar to the one you can add in composition. Then users could apply how they want values to be edited following this curve with a factor on how much this should affect the result too for extra control. This curve could have a few default settings you can choose from or a full custom option.

An other way, if the curve isn't easy to implement. Would simply be a few numbers you can set:
- Lowest limit
- Highest limit
Then the results would be shrunk to fit inbetween these two
- Low lights
- Bright lights
Two intermediate values which would boost/lower values near the end, to allow for more control of how bright/dark things get on the edges. This should help with the "bland" effect of just shrinking values
- Factor
Just a general value of how much this should impact the results

I think the curve option would be more ideal but if that's not easy to setup then the 2nd option could work
#### Switching between Face corner and Vertex
Being able to switch if you want baking to be applied to Vertex or Face corner would be useful as they both have some advantages. Face corner allows you to get nice clear edges where the model is sharp but sometimes, even a flat/smooth surface isn't perfectly smooth onthe lighting where Vertex option gives you smoother results but can't have those clear edges.
Allowing the users to choose whatever option they prefer would be best. Switching this wouldn't affect existing baking but just the next ones you'll do.
#### Auto blur
Turned off by default but an option to automatically blur the result of baking can help a lot with smoothing out the result of lighting. With option to how much stuff is blured by strenght/distance.
One problem with bluring is that you then lose those clean edges given by face corner. If there would be a way to limit bluring by sharp edges so that you don't lose them would be perfect but if that's not possible, having the blur option is still good. Users can separate parts of their model if they want to keep clean edges and still use blur too
### Vertex alpha export 
Vertex alpha can be used in Jak 1 to make part of meshes transparent without having to use the texture's alpha. However the way to set this up wasn't too easy in the past so first let's see if that has changed:
- need to test in newer blender version if it works different before:
  - In the past, to get this to work you had to have the vertex color export set to material
  - then make sure each material included the vertex color or their vertex color wouldn't be exported
  - then the alpha channel would also get exported and useable
  - It's possible newer versions of blender don't work this way so it would be nice to test the last 4 main releases (5.2, 5.1, 5.0, 4.5) as well as 5.3 beta build  as that release in less than a month. For each of those versions you should test:
    - Exporting vertex color objects with an alpha channel and read the glb file to see if those got exported
    - Uses all variant of settings for vertex color export
    - Use different settings on object and material themselves (having the vertex color as part of the material of the actor)
    - make a table/list of which combination of blender version/export settings and material setting export the alpha channel of vertex color or not

---

## Time of day implementation 
Time of day for custom level has been merged as of https://github.com/open-goal/jak-project/commit/d04ac9d so I've moved this feature under the export settings.
### Enable and disabling time of day export
Have an option in baking that's just a toggle to enable time of day export or not. If the option is off then the current behaviour is kept. If the option is turned on then a bunch of new panel will appear.
### What time of day needs to work
For time of days to work properly in game, you need to have these color attributes on the visual meshes instead of a single one:
_SUNRISE
_MORNING
_NOON
_AFTERNOON
_SUNSET
_TWILIGHT
_EVENING
_GREENSUN
Once all of those are made and colored, and the mood function used in the custom level allow for time of day, they'll work. If those aren't set, it'll default to the closest time color or to COLOR_0 if none are set
### Implementation in the addon
Once time of day is enabled, a new panel will appear that allows you to select a collection of light as well as a world setting (world material) per time of day. That way you can set exactly which light and environement will affect which time of day. 

Next to the collection selection, you can also add a button to create a new collection so it's directly attached and created, named and placed in an overall lighting/time of day collection within the level.

For the world setting/material. We'll have to check attaching a world setting give it an user so it's not deleted when blender is shut down. If it doesn't then we'll have to make sure it's given a fake user. There could also be a button to add a default sun that's rotated and set up to give a default outside look similar to Hub 1 lighting.

There can also be a button for this which automatically create world setting for each of time of day which is named and maybe even has some default setting per time of day for a default outside look.

Each of the time of day can also have an enable/disable setting in case users only need a few specific ones. Disabled time of day can have their menu collapsed too to gain some space in the view.

Once everything is set and an user press "bake" as they would before, the addon is now going to render into each color attribute using the collection that was set for it, disabling the ones for the other time of day. (but not any other lights or collection outside of those so some lights can be set to work on every time of day) and also switch the world setting to the selected one. And repeat that for every time of day that is active.

---

## Ignore unedited files
At the moment, every file is rebuilt everytime you click on the export button. The way the compiler work is by checking which files got edited since last time via the file edit time. Which means it'll always have to compile almost the whole game since it's editing files such as `game.gp` or `level-info.gc`.
If only the level's .json, gd and glb were changed. Which is going to be a vast majority of edits. Then only the level needs to be compiled bringing the compile time down to a few seconds instead.
How I think this solution could work would be to still generate all files but instead of directly modifying the final files, these could be in a buffer or temporary file that is then compared to the final file. If there's any difference, then the file can get replaced with the new edited file. If there's no changes, then it can be ignored.

---

## Checkpoint/spawn
### Merge spawn and checkpoint
- There's no reasons to have checkpoint and spawn as two different actors. They both act the same.
- Instead you could have a name input when spawning checkpoints and if there's no checkpoint yet in the level, have it set as `start` then if there's a start already, `cp#` with the number automatically going up like it already do when spawning checkpoints. This also allow uses to directly change the name
### Checkpoint settings
- flags:
  - instead of a string input, this should be a collapsed menu that has all the continue-flags (check game-info-h.gc and how each work, have the list of flags in the database)
- load-commands:
  - instead of a single string output, have a list where you can add/remove commands, then each of those commands is string which will then get bundled
  - example:
    - if you have these 3 commands like this:
    - `special "med-res-level-1" #t`
    - `special "med-res-level-2" #t`
    - `special "med-res-level-4" #t`
    - then it'll get exported like this:
```lisp
:load-commands
'((special "med-res-level-1" #t)
(special "med-res-level-2" #t)
(special "med-res-level-4" #t))
```

---

## Adding missing level settings:
Don't need to separate these two categories in the settings
### For level-info.gc
- music/sound-banks (already exist, just move it inside of the level settings)
  - There's a hack to load in every sound-banks at the same time, this could be an option so that all sounds become available for audio and particles. This isn't something the addon can do directly, just that if an user is using the hack then maybe it could be indicated in the mod so that all sounds are always available and you don't get warnings for these and such
- mood (either just a string or same as level, have a list in database + custom)
- mood-func (same as mood)
- Ocean (same as mood)
- sun-fade (float, from 0.0 to 1.0)
- bsphere (linked to a empty sphere and use it's position + size/scaling for W. Add tooltip for what it does, which is about fading inbetween moods and sky iirc)
- tasks task enums that are inside of that level
- load-command, work the same way as the checkpoint load-commands
- alt-load-commands
- packages/ run-packages (check what these do exactly and if it's useful to have or not)
- priority (check what this does exactly and if it's useful to have or not)
- wait-for-load (check what this does exactly and if it's useful to have or not)
- Separate texture remap and sky texture as those can be two different settings
  - Sky (none set it to #f, then selecting it in a list set it to #t then put the right texture in the json)
  - Texture remap (tooltip under to indicate what it's useful for; flutflut eyes, water, etc) (test-zone.json comments also say this should include some tpage into the level's .gd when doing this which I'm not sure the addon does yet)
### For level's json
- Automatic_wall_angle (float, -1 = off, any number on + set the angle)
- Double sided collision (on/off with a warning that this will double the collision mesh)
### Sub categories and re-order
As there'll be a lot more settings by the end, they should have some sub category so they're in collapsing menus:
- Base settings (not in a collapsing menu):
  - Name
  - Vis Nickname
  - Level Index
- Sound & Music (moving the Music menu inside of the Level Settings menu)
  - Level Music
  - Sound Banks
- Visuals
  - mood
  - mood-func
  - Ocean
  - sun-fade
  - Sky
  - Texture remap 
- Gameplay
  - Death Plane
  - Tasks/Buzzer
  - Automatic Wall angle
  - Double Sided Collision
- Others
  - Bsphere
  - Base Actor ID
  - Commands (sub menu with all the command related options)
  - Always Include

---

## Tasks & Menu implementation
Tasks are the system that set missions to specific resolutions. It's also what the power cell count is based on. Although not every task is equal to a power cell. They can also be used for other logic like level state changes that needs to be saved as well. The task code is also heavily interlaced with the menu so we should take of both at the same time.

---

## Level files clean up when changing level name (or at least a warning?)
When you change a level name, then previous file names for that level will stay. It would be good if those were cleaned when changing names, or at least give a warning to the user to clean first, then change the name.

---

## Blender clean up feature
- Orphan node collections
- Orphan preview meshes

---

## Warnings for required fields
There's already a warning inside of a field when something is required but it's not always the most visible thing. Here's some changes I would like to see to help with this.
### Recolor of warnings
At the moment, a required field doesn't have a color to indicate itself. The only color is on unexpected types when linking actors.

I would recolor the unexpected types background to an orange instead of red.
And make the background of the "required" message red to indicate it's more important to fill them in.
### Warning icons on menus
On top of the recolor, it would be useful to have a warning icon, with a number, on the panel label itself, and have those also show on the parent panel label.
That way, it'd be easy to spot where something is missing without having to open every menu and scrolling down.
Hovering over the warning icon should also give you a popup of which fields are missing.

For example, let's say an actor requires a path, an alt-actor, a prev-actor and a next-actor:
- Next to the "Entity Links" panel name you'd see a "3 ⚠". Hovering on it would say
```
Missing 3 required field: 
- alt-actor
- prev-actor
- next-actor
```
- Next to the "Path" panel name you'd see a "1 ⚠". hovering on it would say
```
Missing 1 required field: 
- path
Click to open to the first panel.
```
- Then at the top menu "Actor Settings" panel name you'd see a "4 ⚠". Hovering on it would say
```
Missing 4 required fields: 
- path
- alt-actor
- prev-actor
- next-actor
Click to open to the first panel.
```

A nice addition to this would be able to click on it and it'd open and scroll down to the first missing required field.
### Warning icon next to export and compile button
To make it even more visible, as warnings can be spread across multiple actors, a good place where the user will have to see it is the "export and compile" button.
The warning can be shown right next to it and works the same as the per-actor warning, except the popup would indicate the name of the actors too.

For example, next to the export button you could see "5 ⚠". Hovering on it would say
```
Actor_name is missing 4 required fields: 
- path
- alt-actor
- prev-actor
- next-actor
Another_actor_name is missing 1 required field: 
- path
Click to open to the first panel.
```
### Sound bank warnings
If an actor need sound that are part of a soundbank that isn't loaded on the level. This could also give a warning somewhere. "Need X soundbank for Y sound"

---

## Hide unused entity links field under a sub menu
Same as with fact options, some actor links usages isn't always shown on an actor code itself but can be used by other code instead. It's for this reason I've wanted to keep the entity link panel visible on all actors.

However, that does add a lot of, often useless, pannels to each actor.

To fix this, while still keeping the option there. Those panels that aren't specifically defined by the actor or its parents, could be put in a "other links" menu that's collapsed by default, same as options.

---

## Move custom checkpoint actor 
- to an always loaded file in game.gd
- As it's the same type that'll be used in all levels

---

## Give the same link feature of navmesh to paths
When multiple actors are using the same paths, have the same feature that warns the user and allows you to move all other actors to a path-actor connected to the selected actor from one button. 

---

## Exta tools
### Set to floor
- Find ground (ray cast from slightly above the current position to not miss if you're already on it or slightly under)
- Set a distance from the ground (especially useful for floating orbs)
- Align or not with the floor
- Ability to affect multiple actors/object at once
- Use center or bottom vertex (for meshes)
### Export selected actors/camera/checkpoint/load-boundary
Useful to have, a button to export only the selected object definitions. Should be in the dev tools. 

This would be useful for working on older levels that aren't setup with this addon so you can just create new actors and export just the definition to easily import them into older levels. This is also useful if you want to share information to another user so they can see how you setup one particular thing.

Have a setting to select a text file in a folder or just a folder selected.
If it's a text file, it'll always just edit that file but if it's a folder, it'll create a new text file with a new name for every export

Here's how it could work for each:
- Actor/camera
  - Give you the entity as it'll be written in the level's json
  - Also give you the list of art group and code files that actor would need (.gd and .json)
  - All within one file
- checkpoint
  - give you the definition of the checkpoint as it would appear in level-info.gc
- load-boundary
  - give you the definition of the load-boundary as it would appear in load-boundary-data.gc

---

## Second entity pass

---

## Creating custom Particles tool (extra addon?)
It's a lot easier to just have people creating their own particle files and edit them in terms of buidling the addon but ideally. 
It would be very useful to have a particle editor and preview directly in blender where you can create, edit and see how each particle group work as that would be a lot quicker than editing particle files and then seeing the affect in game.
This would, however, be a huge undertaking and isn't priority at the moment.

---

# Need some outside changes first

---

## Switch Nav-mesh feature to TFL implementation 
(when it's implemented on mod-base)
- Make it not conflict if you already have mod-base (should come for free with that implementation since each nav-mesh is separated)
- add jump feature. (done through materials?)
- add nav-sphere
- Ability to connect other actors to a nav-mesh so they block pathing (like crates)


---
