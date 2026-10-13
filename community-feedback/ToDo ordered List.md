# Ordered Priority features and fixes
Features and fixes to work on, have been ordered and can be checked out when they've been dealt with and tested.
Once a feature is part of a release, it'll get removed from here.

---

## Expending paths for more features/control (merged to main)
The menu itself should be called Path as that'd be more consistent with how it's used in the game code.
When adding waypoints, I'm personally not sure if I'm a fan of the preview mesh getting added. Personally I'm moslty only using it with curves which at least don't do that.
### Extra Path modes
At the moment, there's not much control on paths. You can just change inbetween straight lines and curved. However, the path-k allows for much more control.
Instead of having just those two options, here's what I'm proposing:
- Automatic
  - Depending on the curve, waypoint and some settings used, it'll automatically determine which one to use. 
  - This can be set as default too so unless people want extra control, 
- Linear
  - Working identical as the already existing Linear option. No path-k exported for straight lines
  - The way Linear would be automatically detected: 
    - waypoints are used 
    - or if the curve used is set to "Poly" and active spline "cyclic U" is OFF.
    - if more than one waypoint/curve is used, this should also be the one that's automatically selected.
    - If none of the other option can be picked, it also default to this
- Linear (Looped)
  - Working very similar to Linear, except an extra point is added at bottom of the list which is a copy of the first point. 
  - This is moslty useful for when the "wrap phase" is used so the start and end overlap for a smooth transition. But that shouldn't be what's used to determine if this mode is used as you might want to use wrap phase there without looping the path.
  - The way Linear (Looped) would be automatically detected: 
    - if the curve used is set to "Poly" and active spline "cyclic U" is ON.
- Smooth 
  - Not actually the same as the current "Smooth". The current smooth option is actually "Smooth Clamped".
  - The path-k for a smooth non-clamped has a linear progression instead of the 4 first and last being identical
    - It also need to have an identical value for the first and 4th point as well as the last and 4th from last.
    - Here's an example of a smooth path-k for 8 points: `"path-k":["float", 0, -2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 5]`
  - The way Smooth would be automatically detected: 
    - if the curve used is set to "NURBS" and active spline "cyclic" and "endpoint" are both set to OFF.
- Smooth (looped)
  - Similar to the Linear (looper), but for non-clamped NURBS, the last 3 points need to be repeated.
    - The repetition is done as such: A, B, C, D, E, F, A, B, C
    - Where F is the last point then it starts repeating from A up to C
  - Because of those 3 extra repeated points, the path-k aslo has to addapt and have extra 3 values.
  - The way Smooth (looped) would be automatically detected: 
    - if the curve used is set to "NURBS" and active spline "cyclic" is ON and "endpoint" is OFF.
- Smooth Clamped 
  - This is how the current "Smooth" option works
  - The path-k for a clamped at the start and the end and linearly increase inbetween
    - Her's an example of a Smooth and clamped path-k for 8 points: `"path-k":["float", 0, 0, 0, 0, 1, 2, 3, 4, 5, 5, 5, 5]`
  - The way Smooth Clamped would be automatically detected: 
    - if the curve used is set to "NURBS" and active spline "cyclic" is OFF and "endpoint" is ON.
- Smooth Clamped (looped)
  - Because both ends are already clamped, only one point need to be copied at the end, same as a linear looped path
  - Because of the extra point, the path-k also need an extra value.
  - The way Smooth Clamped (looped) would be automatically detected: 
    - if the curve used is set to "NURBS" and active spline "cyclic" is ON and "endpoint" is ON.
- Bezier (Sharp corners)
  - Bezier implementation would be a bit more complex but it is possible to use NURBS point and the path-k to simulate Bezier curve with sharp corners.
  - To do so, each 2 anchor point and inbtween 2 handles of a bezier curve can be viewed as one clamped NURB curve then repeat for the next one
  - Here's an example of how it could work:
    - Let's say you have a Bezier curve with 4 anchor points (each with 2 handles)
    - Let's use letters, A, B, C, D for those anchor points position
    - And A1, A2, B1, B2, C1, C2, D1, D2 for the handle positions
    - The first segment consist of this order: A, A2, B1, B (the A1 handle is on the other side of the first anchor and is only used on a looped bezier)
    - The second segment is: B, B2, C1, C (As you can see the first point is a repeat of the last segment as they're clamped at each other)
    - The third and last segment is: C, C2, D1, D (D2 handle is also not used because the curve doesn't loop around)
    - In total the path points will look like this: A, A2, B1, B, B, B2, C1, C, C, C2, D1, D (12 total points)
    - And the path-k for this would look as such: `"path-k":["float", 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3]` (16 path-k as it's path points + 4)
  - The way Bezier (Sharp corners) would be automatically detected: 
    - if the curve used is set to "BEZIER" and active spline "cyclic" is OFF.
- Bezier (looped)
  - Very similar to Bezier (Sharp corners) but one more segment is generated at the end from the last anchor point to the first using the handles inbetween
  - Using the same example as before
    - A 4th segment would be added which would look like this: D, D2, A1, A
    - Which would make the total path look like: A, A2, B1, B, B, B2, C1, C, C, C2, D1, D, D, D2, A1, A (16 total points)
    - And the path-k for this would look as such: `"path-k":["float", 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4]`
  - The way Bezier (looped) would be automatically detected: 
    - if the curve used is set to "BEZIER" and active spline "cyclic" is ON.
- Manual path-k
  - Not 100% sure this should be added yet 
  - if this option is on then you could manually set all the path-k values yourself for full control.
  - This would need to automatically be able to add and remove fields depending on the number of points in the path.
  - This would never be automatically picked by the "Automatic" option
### Extra paths
Some actors require more than one path. These are usually demoninated as patha, pathb, etc up til pathh. And have their own path-k, patha-k, etc.
The Menu should be identical as other paths for these but maybe have a button that's "add extra path" for actors that require these so the user can add as many path as needed without having the UI cluttered by 8 different path UI when they might not use all of them.

Some actors might also use both path and then patha,b, etc while other actors might start directly at patha. Maybe an option for each path to set which one it is manually could also be useful for those cases.

Maybe a full remodel of the path/waypoints UI so you have one general paths UI and inside of it, buttons to add/remove paths, then each path added is a sub menu inside of there with the option to set how each path is needed. This could either be the default or only be available if a "multiple_path" option is allowed in the actor's database entry.

---


## Ways to include code without it coming from an actor (merged to main)
While, ideally, you should never have to add anything extra and everything should be automated. It'll be hard to cover every cases and someone making custom features might be blocked a bit. Having custom code to always include could cover weird edge cases much easier than trying to manually fix every single one of them.
### General idea for custom code
What I'm thinking is having text files in blender you can edit which would either be separated files for each or have one well organised file.
Then having one or multiple option in the level settings to include those files with a descriptive tool tip.
### Included code files
This would include a list of you always want included in your level's .gd and .json file.
Here's how it could look:
```json
"gd":[
  "codefile.o",
  "anothercodefile.o",
  "artgroup-ag.go",
  "anotherartgroup-ag.go"
],
"json_ag":[
  "artgroup-ag",
  "anotherartgroup-ag"
],
"json_texture":[
  "some-texture-name"
]
```
These would then get added as well as all the ones defined by actors in the blend file.
### Included actors
This would include actor code you want to always include that's not defined by an actor object in the blend file.
Here's how it could look:
```json
"actors":[
  {
      "trans": [-511.08, 2.8933, -209.8895],
      "etype": "eco-blue",
      "game_task": "(game-task none)",
      "quat": [0.0, 0.0, 0.0, 1.0],
      "vis_id": 0,
      "bsphere": [-511.08, 2.8933, -209.8895, 10.0],
      "lump": {"name": "eco-blue-0"}
    }
],
"ambiants":[]
```
Then all the actors and ambients defined here would be added to the level's json as well as the ones added in the blend file.
### Included level-info in level-info.gc
This might not be fully needed, not 100% sure how the addon work with existing level code but if it might wipe out other custom level code in `level-info.gc` then there should be a way to include these in a text file. If they're not being affected then this isn't needed.
### Included level build data in game.gp
Same as with the level-info data, if other custom levels aren't affected then there's no need for this.

---

## Going through actor list to fix preview model/included code. (in progress)
This is moslty a step that'll done by users to check on every actor, with the database it should be possible to fix most actor by changing the preview glb path, the added code and art groups needed as well as the fields.

### General changes for entities (merged to main)
- code and art-groups changes
  - Make it so both the code and AG fields can be used to add multiple entries as some actors need multiple code files as well as mutliple art groups
    - it shouldn't change much in the way it's setup already. It should just allow multiple string entries in a bracket when there's multiple ones.
    - Example: `"art-group" : ["keg-conveyor-ag.go","keg-conveyor-paddle-ag.go","keg-ag.go"]`
    - There's already a way to add multiple files in some variant example but it's done as another entry and that complexity shouldn't be added if it can all live within the same entry.
    - The "extra_art-group" could be kept as is since that one doesn't copy the art-group in the level json. Which is fine for things that are just adding animation without models (jak animations or camera for example)
  - Simplify how "code" files it's written in the database
    - instead of having "code" entry which then has "o", "o_only" and "in_game_cgo". It should just be a single "code" or "o" entry with the code file (or files)
    - Then to know if there's no need to include code files ort art groups, it should refere to a list which can simply be copied over to the database from game.gd
    - That way, the code is always the same and cleaner for all actors in the database and if a modder has included some other actors in their game.gd, they can just also add it to the database and that'll directly work
    - Could also keep the "code" entry and just have everything that's related to exporting code files there, such as "o", "art-group", "tpages", "tpage_group"
- Reworking all the panel into one field in the database
  - At the moment there's multiple ways to add panel information to actors via the database:
    - "fields" to add custom fields
    - "needs-sync" which add all the platform info (sync data + path data)
    - "panel" which add a specific panel to some actors
    - "links" which add a couple of different pannels, including path which also alreay has another way to get added.
    - etc
  - All of those are working differently and exist in separate places so grouping them and getting them all to work in a similar way would go a long way
  - I'd like to reuse that "panel" field but instead of pointing it to one type and then create the whole panel from that, it'd contain all the panel information:
    - inside of that panel field, you would have group of data for each of the different pannels that could be added 
    - Example of the panels : "fields", "path", "sync", "actor link", "fact options", "volume", "nav-mesh", any other panel that will be needed to be used multiple time and is better as its own panel than custom entries in fields
    - For each panel, you'd just be able to turn them on by having them in the "panel" field with a "show-panel" set to true
    - If a panel would be set to shown, it would use some default values but you could also change any of the field of that default panel if you need to
    - Here's an example of what it could look like:
```json
"Panels": [
  {
    "panel": "sync", // Name of the existing panel this will add
    "show-panel": true, // with this set to true, the panel will appear in the actor options
    "fields":[
      {"key": "og_sync_period", "default": 10.0}, // as you can see the added field here only has the default value noted because everything else about that field will use the standard values
      // the field for phase is not written at all since it'll just use the default values for that field
      {"key": "og_sync_ease_out", "show-field": false}, // This actor, for example, wouldn't need the ease_out and ease_in so they're manually turned off here
      {"key": "og_sync_ease_in", "show-field": false}, 
    ]
  },
  {
    "panel": "path",
    "show-panel": true, 
  },
  {
    "panel": "fact-option", // see the fact-option info a bit lower
    "show-panel": true, 
    "fields":[
      {"key": "og_fact_option_wrap_phase", "show-field": true}, // For fact options, they probably should all be turned off by default as there's many of them and only a few are used per actors. So turning them true here instead.
    ]
  },
  {
    "panel": "custom-fields", // This would replace the old "fields", as "fields" is now used in each
    "show-panel": true, 
    "fields":[
    // For custom fields, you'd need to type out the whole fields instead
      {
        "key": "og_plat-type",
        "label": "Platform mode",
        "type": "enum",
        "choices": "FlutflutPlatMode",
        "default": 0,
        "lump":{
          "key": "mode",
          "type": "int32"
        },
        "write_if":"if_nonzero"
      },
      {
        "key": "og_extra-id",
        "label": "Order of aparition for button mode (order * 0.15s)",
        "type": "int",
        "default": 0,
        "lump":{
          "key": "extra-id",
          "type": "int32"
        },
        "write_if":"if_nonzero"
      }
    ]
  }
]
```
- Panel/fields heritance from parents
  - The point of having the parent actor in the database was for the child actor to be able to innherit from said parent.
    - That way, any platform that moves along path could just be a child from a main platform parent
    - It'd then innherit all of the panel and settings for platform
    - then each specific platform would only need to have settings for things that are different or extra
    - This would cut on a lot of repeated information in the database
- Actor link fields changes
  - An "allow-multiple" feature you can turn on would be nice as sometimes, things such as "alt-actor" can have multiple entries
    - While it's already possible to add multiple ones by adding several links of the same type with increasing slot, that's not ideal when the number of actors isn't a specific set number. Some can have like 10+ alt-actor
  - Maybe don't fully block the users from linking an actor that's not part of the allowed list and instead warn them instead that it might not work
    - Reason is that it's hard to catch and add every single actors that would work in those links but then just changing all to "any" wouldn't help users
- Variants being able to change etype
  - Some actors are mostly copies of each other with some very small changes and having all of them added to the list would be too cumbersome
  - Variants would be perfect for the task but at the moment, they're not able to change the etype of the actor
  - It would be pretty simple in implementation in the database, just having an "etype" field in variant choices should automatically let the addon know they need to change the etype of that specific actor
  - There's already some examples in the database of what it'd looks like, see "OgreStepVariants" and "CitbDiscVariants"
- `fact-option ` is an enum that allows you to set extra options for a lot of actors
  - It's already kind of used for platforms, for the wrap-phase or fuel cell for the skip jump anim
  - Generalise all of these as an "options" panel inside of the actor settings
  - Have all the options that can be set live in the database with their name, description and the string required to add to the json.
  - they can be found in `goal_src\jak1\engine\game\fact-h.gc` `fact-options` enum with some comments already
  - You can ignore all the unused options (fop4, fop5 and fop17)
  - Then it would be as simple as adding an "options" field in each of the actors that need it
  - Then all the options that are available for that actor and if they should be turned on or off by default
  - Then only the checkboxes for the existing options would appear on each specific actor, with them enabled/disabled correctly by default
- Scale lump
  - Some actors have a scale lump, while this can be added as fields there could be some better way to deal with it
  - A really intuitive way would be to simply export that scale lump whenever an actor doesn't have default scaling in blender
  - Some actors also require that scale lump (ex: citb-plat will crash without it) so an option to always export scale, even if default (1,1,1,1) could be added to the database
  - scale lump wouldn't do anything on most actor 
    - but there's very easy hack that I have added on TFL that allow me to use the scale on any process-drawable 
    - so having it automatically when changing scale in blender would be ideal
- Drivers between object properties and exported OG values
  - This would allow for two things: 
    - Either a good way to visualise changing one exported value into blender. (ex: having the size of the empty arrow in blender increase in size to show how high a launcher launches you)
    - Or, let you modify a value in blender that'll then be applied to the export. (ex: Scaling objects and having that scale being exported as a res-lump for custom scaling, see TFL. Or the rotoffset on some object being directly taken from the Z axis rotation like for caveelevators)
  - Drivers could live in the database as well as such:
    - Set the driven variable
    - Set the driver variable
    - Set the default value
    - Conditions to use the default value (ex for launcher, if value is negative, it should be 40)
- Default empty size
  - Being able to set the empty size in the database would be useful for some actors
  - Wouldn't be set on all but nice for a few that clearly need to be smaller or larger
- Removing/changing Color entry
  - The color isn't that useful since the empties don't really show it or preview meshes which don't either
  - If the color could be set on the preview mesh, that could be maybe useful
  - Even if it was added to the preview mesh, I would still like it removed from the entry of every actor as it clogs the data a lot
  - If anything it should be set per category, so the color coding can quickly show to users what type of actor are placed

### Per categories changes: (in progress)
Going through all categories in this order, if I can't fix some things I'll not it here under each category:
- Pickups
  - `movie-pos` field for flies/cells and crates/pickup-spawner which are holding a fly/cell
    - For Cells this will determine where the animation is played, including the rotation of this one with the W value
    - For Flies, this will determine where the cell will spawn if this is the last fly collected as well as the position/rotation of the animation
    - Should just be a small helper that spawn an empty (either at cursor or at the actor position)
    - Similar to the alt-actor for launcher
    - The rotation should be set by the Z rotation of the spawned empty
    - `movie-pos` also have its own type called the same that'll take XYZ in meters and W as a 360 angle directly. So no weird translation needed.
- Platforms
  - Empty "Platform settings"
    - A lot of platforms have a "platform settings" menu that's empty since they don't need the sync options and others
    - This empty menu could simply be removed if they don't have any settings there anyway
  - caveelevator 
    - require multiple code files to add `cavecrystal-light.o` 
  - cavespatula
    - when not in darkcave, cavespatula try to set a skeleton group that doesn't really exist (cavespatula-sg) Not sure how to fix that without editing cavespatula code
    - require multiple code files to add `cavecrystal-light.o` 
  - Pontoonfive and pontoonten
    - The task menu right now is all over the place, should definitely not have a checkbox list like this for something this long. It should be a drop down menu when you can only select one anyway. Also this might not even be needed to be in the pannel and can maybe just be part of the lump definitions
  - square-platform, 
    - need to test after square-platform-button and square-platform-master are implemented
  - ease in/out caviats doesn't work
    - Values still seem to export even when they're set to 0
  - swingpole
    - Adding a general way to change base rotation as swingpoles need to be rotated 90° on their X axis to work at all
    - That general way could then be used on any other actor that might need to use that as well
    - don't have it on all actor in the database, just the one that might need it, like the preview mesh offset
  - floating-launcher (floating-launcher.gc) 
    - alt-vector option doesn't work properly in blender
  - ogre-isle (ogre-obs.gc) 
    - need variants to be able to change etype as well
    - Looks to have some model offset
    - crashes
  - ogre-step (ogre-obs.gc) (+ a-b-c-d) 
    - need variants to be able to change etype as well
    - crash game after a second when they do spawn
    - seems to be some offsets for preview model 
  - minecartsteel (minecart.gc)  
    - maybe a way to show the anim path in blender?
  - flutflut-plat-small (snow-flutflut-obs.gc) 
    - variants would need to be able to set etypes like ogre-step
  - citb-disc (citadel-obs.gc) (+ a-b-c-d) 
    - variants would need to be able to set etypes like ogre-step
  - Crashing actors:
    - balance-plat (not in goal code stack trace) (looks to have correct art-group and code files included)
    - mis-bone-bridge (same as balance plat)
    - breakaway-right (same as balance plat)
    - breakaway-mid (same as balance plat)
    - breakaway-left (same as balance plat)
    - tar-plat (same as balance plat)
    - citb-disc (same as balance plat)
    - citb-launcher (same as balance plat)
    - bone-platform (same as balance plat)
    - ogre-isle (Assertion failed when trying to :di the stack trace)
  - Missing platforms:
    - citb-drop-plat (citb-drop-plat.gc) This one would need some pretty complex setup to be intuitive to work within blender
    - citb-arm (citadel-obs.gc) (+ a bunch of others) Waiting on this for etype variants
- Obstacles
  - keg-conveyor (misty-conveyor.o misty/keg-conveyor-lod0.glb keg-conveyor-ag.go keg-conveyor-paddle-ag.go keg-ag.go)
    - Need multipe art group
  - spike (firecanyon-obs.o firecanyon/spike-lod0.glb spike-ag.go)
    - Need racer/zoomer to try it out
  - swamp-spike (swamp-obs.o swamp/swamp-spike-lod0.glb swamp-spike-ag.go)
    - Not in goal code crash
  - snow-ball (snow-ball.o snow/snow-ball-lod0.glb snow-ball snow-ball-ag.go)
    - Need path keying
    - Need multiple art-group
  - citb-firehose (citb-plat.o citadel/citb-firehose-lod0.glb citb-firehose-ag.go citadel-part.o)
    - Need multiple code files (for particles )
- Enemies
  - Being in the "enemies" category shouldn't automatically add any fields/panels. A lot of those are only useful for nav-enemies, which not all enemies are. Category, in general, shouldn't affect anything other than putting them in the correct menu in the UI.
  - "need-nav" seems to only work if the parent is "nav-enemy". That shouldn't be the case, any actor with "need-nav" should give you field. Some actors aren't nav-enemies by themselves but they do still need the field because they can spawn nav-enemy actors, such as mother-spider or battlecontroller for example.
  - sharkey (sharkey.o beach/sharkey-lod0.glb sharkey-ag.go)
    - Error when spawning in blender:
    - Could not select entity type sharkey: bpy_struct: item.attr = val: enum "sharkey" not found in
  - babak-with-canon (babal-with-canon.o beach/babak-lod0.glb babak-ag.go)
    - test with canon
  - pelican
  - junglefish (junglefish.o jungle/junglefish-lod0.glb junglefish-ag.go)
    - Done
    - Interestingly, junglefish only agro jak if he's walking in shallow water and not while swimming
  - plantboss (plant-boss.o aphid.o jungleb/plant-boss-main-lod0.glb plant-boss-ag.go plant-boss-main+0-ag.go aphid-lurker-ag.go)
    - Done
    - Need multiple code/ag (for aphids)
    - Need to test movie-pos when that's implemented
  - quicksandlurker (quicksandlurker.o misty/quicksandlurker-lod0.glb quicksandlurker-ag.go)
    - Crashes (has GOAL stack trace)
  - misty-battlecontroller (misty-obs.o)
    - Maybe just have battlecontroller instead
  - balloonlurker (balloonlurker.o misty/balloonlurker-lod0.glb balloonlurker-ag.go) 
    - Test alt-actor for cell later (would need extra code/ag)
  - robber (rolling-robber.o ogre/robber-lod0.glb robber-ag.go) 
    - Need game-task implementation for the cell
  - double-lurker (double-lurker.o sunken/double-lurker-lod0.glb double-lurker-ag.go double-lurker-top-ag.go)
    - Need extra art-group, the current "extra_art_groups" doesn't add it to the .json
  - swamp-rat-nest (swamp-rat-nest.o swamp-rat-nest-a-lod0.glb swamp-rat-nest-ag.go)
    - need extra code/ag for rats
  - swamp-bat (swamp-bat.o swamp/swamp-bat-lod0.glb swamp-bat-ag.go)
    - pathb implementation isn't ideal (see the path changes)
    - need_vol doesn't seem to add the volume linking panel
  - swamp-battlecontroller (swamp-obs.o)
    - Maybe just have battlecontroller instead
  - ogreboss (ogreboss.o ogre/ogreboss-lod0.glb ogreboss-ag.go)
    - Would need game-task for cell
    - Would need movie-pos for cell
    - Cutscene start positions are hard coded
  - plunger-lurker (flying-lurker.o ogre-obs.o ogre/plunger-lurker-lod0.glb plunger-lurker-ag.go)
    - need extra code "ogre-obs.o" for particles
  - gnawer (gnawer.o maincave/gnawer-lod0.glb gnawer-ag.go)
    - need movie-pos implementation
    - need extra code and art-group for the cam
    - Camera/cell position seems to be hardcoded
    - check what the "gnawer" lump does 
    - extra-count second value need investigation for how it works and should be implemented for orb spawning
  - mother-spider (mother-spider.o mother-spider-h.o baby-spider.o mother-spider-egg.o mother-spider-proj.o maincave/mother-spider-lod0.glb mother-spider-ag.go mother-spider-egg.o baby-spider-ag.go)
    - need extra code/art group for eggs and spiders
    - Maybe a way to multiply/divide values before they're sent because the mother-spider lump is a float with a lot of meters but then also has a count. So either you'd have to write the meters values as x4096 or the count as x4096
    - mother-spider need to check slot 4 to see what it does
    - Not in goal code crash
  - spider-egg (spider-egg.o baby-spider.o mother-spider-egg.o robocave/spider-egg-unbroken-lod0.glb spider-egg-ag.go baby-spider-ag.go)
    - need extra code for "cavecrystal-light.o" or crashes and others
  - baby-spider (baby-spider.o cavecrystal-light.o maincave/baby-spider-lod0.glb baby-spider-ag.go)
    - need extra code for "cavecrystal-light.o" or crashes
  - cave-trap (cavecrystal-light.o)
    - need "multi" link-slop as there can be a lot more than 4 eggs and vents 
    - need extra code for "cavecrystal-light.o" or crashes
  - driller-lurker (driller-lurker.o cavecrystal-light.o robocave/driller-lurker-lod0.glb driller-lurker-ag.go)
    - need extra code for "cavecrystal-light.o" or crashes
    - find what option 17 does if anything
  - ram (snow-ram.o snow-ram-h.o snow/ram-lod0.glb ram-ag.go)
    - need game task implementation
    - alt-actor needs to be able to include itself somehow as that's needed for the task.
    - next-actor for all surrounding enemies which means all enemies might need next/prev-actor linking
    - need extra code for ram-boss code/art
    - not in goal crash
  - ram-boss (snow-ram-boss.o snow/ram-boss-lod0.glb ram-boss-ag.go)
    - Don't throw their fireball?
  - citb-bunny (citb-bunny.o citadel/citb-bunny-lod0.glb citb-bunny-ag.go)
    - Error when trying to spawn in blender
    - Could not select entity type citb-bunny: bpy_struct: item.attr = val: enum "citb-bunny" not found in
  - green-eco-lurker (green-eco-lurker.o finalboss/green-eco-lurker-lod0.glb green-eco-lurker-ag.go)
    - Memory map assertion failed crash
  - robotboss 
    - need extra code for: robotboss.o robotboss-h.o robotboss-part.o robotboss-weapon.o robotboss-misc.o
    - need extra code and art group from green-eco-lurker and darkecobomb-ag.go
    - works until it needs to play the cutscene before light eco then crash
  - battlecontroller
    - Would need a pretty specific UI setup
    - Choosing lurkers, % spawn per lurker, eco drops, etc
- Buttons and Doors
  - warp-gate-switch
    - task for activating it or that gets activated when pressing it?
    - level list and how they get unlocked is hard coded
    - Doesn't seem to give the menu atm
  - tra-iris-door
    - check if all iris door can be combined into one (maybe eco-door has all features?)
  - sidedoor
    - cmds lump?
    - play-mode?
    - sound-name?
    - text-id?
    - game task implementation
  - maindoor
    - game task implementation
  - jng-iris-door
    - start-open option doesn't seem to do anything atm
  - eggtop
    - game task implementation
    - movie-pos
  - launcherdoor
  - rounddoor
  - gorge-pusher (rolling-obs.o rolling/pusher-lod0.glb pusher-ag.go)
  - sun-iris-door
  - square-platform-button
  - sunken-pipegame
  - helix-button
  - swampgate
  - snow-bumper
  - snow-button
  - snow-switch
  - snow-fort-gate
  - snow-log-button
  - snow-eggtop
  - energydoor
  - citb-iris-door
  - citb-button
- Interactive Objects
  - scarecrow
  - reflector-end
  - fishermans-boat
  - flutflutegg
  - mistycannon
  - harvester
  - ecoventrock
  - periscope
  - reflector-mirror
  - racer
  - balloon
  - racering
  - gorge-start
  - dark-plant
  - blue-eco-charger
  - exit-chamber
  - swamp-tetherrock
  - swamp-rock
  - flutflut
  - shortcut-boulder
  - dark-crystal
  - cavecrystal
  - lavaballoon (variant to balloon if there's any differences, if not, ignore)
  - energybase
  - energyhub
  - citb-generator
- Visuals
  - evilplant
  - hutlamp
  - sagesail
  - revcycle
  - revcycleprop
  - windmill-sail
  - mayorgeers
  - bladeassm
  - accordian
  - windturbine
  - boatpaddle
  - wheel
  - ceilingflag
  - villageb-ogreboss
  - peeper
  - sunkenfisha
  - seaweed
  - swamp-blimp
  - pistons
  - lavabase
  - lavafall
  - lavafallsewera
  - lavafallsewerb
  - lavashortcut
  - lavayellowtarp
  - citb-robotboss
  - citb-hose
  - citb-coil
  - citb-arm-shoulder-a (a/b variant)
  - ecoclaw
- NPCs
  - sage
  - assistant
  - mayor
  - explorer
  - sculptor
  - bird-lady
  - yakow
  - farmer
  - oracle
  - bird-lady-beach
  - seagullflock
  - muse
  - sage-bluehut
  - flutflut-bluehut
  - assistant-bluehut
  - assistant-levitator
  - geologist
  - warrior
  - gambler
  - lightning-mole
  - billy
  - assistant-lavatube-start
  - yellow-sagecage
  - blue-sagecage
  - red-sagecage
  - sage-finalboss
- Volumes
  - General Volume notes:
    - Volumes shouid be added as a panel. At the moment there's no panel on water-vol, so if you don't use the connected volume that appear at spawn, you can't connect another volume later.
    - The panel should be similar to navmesh panel
    - Give the panel a button to create a default volume as well as being able to connect to an existing volume/turn a selected mesh into a volume
    - If you select a mesh object, you should have the option to turn it into a volume, same as for navmesh
    - when spawning water-vol/water-anim or any other actor that needs a volume, don't need to spawn a volume automatically anymore as the volume panel will have an option to do so. No other actor spawn with other things they need, water shouldn't be any different
    - Place the panel inbetween path and nav in the order
  - water-vol
    - Make "Sync Surface from Volume Top" a toggle which automatically adjust the height everytime the volume is edited. Instead of copying it once. You can grey out the water surface field to show that it's being controlled by something else.
    - water volume can be all of these and those act different for jak. (unless they're only available in water-anim, if that's the case then only add these there)
      - water (jak can swim and drown in it)
      - mud (jak is slowed by it)
      - tar (jak is slowed by it and damaged)
      - lava (instant kill jak)
      - dark-eco (instant kill jak)
      - electric water (from sunken, damages jak)
  - water-anim
    - variant for the look
      - changes the etype if needed
      - load correct file for that etype
      - load correct art group
      - load correct glb for preview mesh
      - automatically switch to the correct type of liquid as explained in water-vol
    - sunken has water that goes on and off being electric
      - see how that works exactly and how to set it up when one of those is selected
    - Each of the look should have the # (level) (water type) in the name to differentiate them
### Compile rest of of actor changes
We should keep track of every remaining actor that still need some changes, isn't working or has some other notes to it in a text file on the repo for later check.

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
### Creating custom Particles
It's a lot easier to just have people creating their own particle files and edit them in terms of buidling the addon but ideally. 
It would be very useful to have a particle editor and preview directly in blender where you can create, edit and see how each particle group work as that would be a lot quicker than editing particle files and then seeing the affect in game.
This would, however, be a huge undertaking and isn't priority at the moment.

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
### racering
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
### Vertex alpha export 
- need to test in newer blender version if it works different before:
  - In the past, to get this to work you had to have the vertex color export set to material
  - then make sure each material included the vertex color or their vertex color wouldn't be exported
  - then the alpha channel would also get exported and useable
  - It's possible newer versions of blender don't work this way so it would be nice to test the last 4 main releases (5.2, 5.1, 5.0, 4.5) as well as 5.3 beta build  as that release in less than a month. For each of those versions you should test:
    - Exporting vertex color objects with an alpha channel and read the glb file to see if those got exported
    - Uses all variant of settings for vertex color export
    - Use different settings on object and material themselves (having the vertex color as part of the material of the actor)
    - make a table/list of which combination of blender version/export settings and material setting export the alpha channel of vertex color or not
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
If the user's version is too old. Keep the menu there but give a warning

---

## Baking options
- Better handling of emiting materials
- Limit range of lighting 
  - Anything under 0.25 brightness will be considered black
  - Anything above 0.75 brightness will be considered over exposed/look as if it was emiting light
  - don't fully limit those, maybe a setting for how much you want to "limit" it?
- Being able to switch between face corner and vertex

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
  - instead of a string input, this should be a collapsed menu that has all the continue-flags (check game-info-h.gc and how each work)
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
### For level-info.gc
- music/sound-banks (already exist, just move it inside of the level settings)
  - There's a hack to load in every sound-banks at the same time, this could be an option so that all sounds become available for audio and particles
- mood (either just a string or same as level, have a list in database + custom)
- mood-func (same as mood)
- Ocean (same as mood)
- sun-fade (float, from 0.0 to 1.0)
- bsphere (linked to a empty sphere and use it's position + size/scaling for W)
- tasks task enums that are inside of that level
- load-command, work the same way as the checkpoint load-commands
- alt-load-commands
### For level's json
- Automatic_wall_angle (float, -1 = off, any number on + set the angle)
- Double sided collision (on/off)

---

## Tasks & Menu implementation
Tasks are the system that set missions to specific resolutions. It's also what the power cell count is based on. Although not every task is equal to a power cell. They can also be used for other logic like level state changes that needs to be saved as well. The task code is also heavily interlaced with the menu so we should take of both at the same time.

---

## Level files clean up when changing level name (or at least a warning?)

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

# Need some outside changes first

---

## Switch Nav-mesh feature to TFL implementation 
(when it's implemented on mod-base)
- Make it not conflict if you already have mod-base (should come for free with that implementation since each nav-mesh is separated)
- add jump feature. (done through materials?)
- add nav-sphere
- Ability to connect other actors to a nav-mesh so they block pathing (like crates)


---
