# Ordered Priority features and fixes
Features and fixes to work on, have been ordered and can be checked out when they've been dealt with and tested.

---

## level .gd and .json clean up
If a code or art group file is included in the game.gd, it does not need to be included in the level's .gd or in the level's .json. 
As those files are always loaded and part of the common fr3 too for art groups.
How I'm imagining it to work.:
- Have a list of all included files in game.gd stored in the database. (Or check if it already exist, I can't see one myself)
- Before any art group or code file is added to game.gd or the level's json, compare it with that list.
- If the files are already part of that list, don't copy them.
- maybe have an option in the developer tools to turn on/off "ignore game.gd files" to easily switch back to old behaviour if needed

---

## Switching to built-in camera entities
Jak 1 now has built in camera entities. They can be defined in the level's json's in the Camera field. 
There's an example in test-zone.jsonc, here it is:
```json
  // Camera entities you want to use in your level. These are used to dynamically adjust camera settings/modes when Jak enters a volume.
  // There are a couple of different camera modes, depending on what lumps are present:
  // - cam-circular: orbits a specified point. requires "pivot" lump.
  //   - optional lumps: "maxAngle", "focalPull"
  // - cam-standoff: requires "align" lump.
  // - cam-string: the default camera mode. used when any of these lumps are present to override the default cam mode behavior:
  //   - "stringMaxLength", "stringMinLength", "stringMaxHeight", "stringMinHeight"
  //
  // Some generic lumps that can be used for all camera modes:
  // - "fov": set the camera fov (default is 64).
  // - "interpTime": set the cam blend time when entering the camera entity volume.
  // - "tiltAdjust": set the camera roll value.
  //
  // There's a "flags" lump that takes a cam-slave-options enum value:
  // "flags": ["enum-uint32", "(cam-slave-options SAME_SIDE COLLIDE)"]
  //
  // There's three different volume types (these all have to be defined in keyframe 0, e.g. ["vector-vol@0.0": ...]):
  // vol: sets camera entity when Jak is inside.
  // pvol: preferred volume when camera entities overlap.
  // cutoutvol: disables camera entity when Jak is inside.
  //
  // "interesting" is an optional vector lump that can be set to be used as a "point of interest" for the camera to focus on.
"cameras": [
  {
    "trans": [17.26, 9.0, 13.2],
    "quat": [0, 1, 0, 0],
    "lump": {
      "name": "test-cam",
      "flags": ["enum-uint32", "(cam-slave-options SAME_SIDE)"],
      "pivot": ["vector3m", [15.0761, 2.6482, 25.548]],
      "interpTime": ["float", 1.0],
      "vol": [
        "vector-vol@0",
        [-0.09046, 0.025624, 0.99557, 32.528575],
        [-0.995854, 0.007292, -0.090673, -8.671137],
        [0.09046, -0.025624, -0.99557, -16.528584],
        [0.995854, -0.007292, 0.090673, 24.671144],
        [-0.009584, -0.999645, 0.024858, 0.695884],
        [0.009584, 0.999645, -0.024858, 15.304117]
      ]
    }
  }
]
```
The current implementation, using a custom actor built for these camera might have more features so it could be kept.
But if not, or if the features are not that meaningful, we can completely replace them. This can be discussed further.

---

## Expending paths for more features/control
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

---

## Going through actor list to fix preview model/included code.
This is moslty a step that'll done by users to check on every actor, with the database it should be possible to fix most actor by changing the preview glb path, the added code and art groups needed as well as the fields.

There's a few features that might need to be added as well:
- `movie-pos` field for flies/cell
  - For Cells this will determine where the animation is played, including the rotation of this one with the W value
  - For Flies, this will determine where the cell will spawn if this is the last fly collected as well as the position/rotation of the animation
  - Should just be a small helper that spawn an empty (either at cursor or at the actor position)
  - Similar to the alt-actor for launcher
  - The rotation is set by the Z rotation of the spawned empty
- Prev/next/alt actor fields
  - While it's already in the lump reference on some actors, these should be direct fields that are already there and easy to use for some of the actors

Known Missed actors:
- pickup-spawner missing
  - Allow you to spawn any collectable
  - Can be set to off by default and then triggered by another actor which is very useful

---

## Addon/project settings
- overwrite folders
  - Being able to overwrite the folders directly in the blend file
  - Useful if you're working on multiple projects so you don't have to change inbetween, risk to overwrite files from one project on another
  - Also useful when you need to update/re-install the addon, the file will already have those selected and you don't need to do it agian
- overwrite database
  - Being able to directly load a file which overwrite the loaded database
  - This way people can make changes to it without having to edit the base addon and re-install it
- Fix folder detections on dev env
  - At the moment, when a dev env folder is set as the main folder:
    - You need to set the data folder manually even tho it's identical to the main folder
    - You need to set the EXE folder which should always just look like this: BaseFolder\out\build\Release\bin\
    - The Decompiler folder get set correctly when the data folder is set
- Fix lag in settings
  - Maybe due to the dev env issue, the setting menu for the addon become very unresponsive once the main folder is selected
  - Guessing it might have to do with the fact that it's looking for the folder automatically but can't find them?
  - But even after selecting them manually it's still very slow
  - While fixing the previous issue could help with this, not finding the folders automatically shouldn't mean it becomes that slow
- Make spawn use mod-base spawn feature if mod-base detected
  - Current spawn option when starting the game boot the game normally and then teleports you after a few seconds
  - mod-base, a fork of opengoal that's used by most people creating mods, has a file called `mod-settings.gc` in `goal_src\jak1\engine\mods\`
  - This file has `(define *debug-continue-point* "village1-hut")` which can allow you to directly boot debug into any checkpoint you want.
  - If the addon detect that you're using mod-base (can check if mod-settings.gc exists), this value could be changed instead of teleporting you after booting up the game.
### Export settings
- Geometry compression for export (Draco)
  - Draco compression algorithm is useable in useable in opengoal, which allow you to shrink level glb files by quite a lot
  - Since the addon takes care of the export itself, there should be an option to turn this on as well as have all of the settings you normally have to control the compression
- Deactivating selections on a collection shouldn't stop export of this one. 
  - very useful on geometry while working with actors
  - I'm guessing at the moment the addon uses "export selected" and manually select everything that's needed for the export which is why things doesn't get exported if the selection is turned off
  - I'm proposing to change that to use the "collection" export feature. It can even be set only to a main geometry collection. That way the glb export is also cleaner and doesn't have any extra data it doesn't need.
- Vertex alpha export (need to test in newer blender version if it works different before)

---

# Less Important features and fixes

---

## Adding missing level settings:
### For level-info.gc
- music/sound-banks (already exist, just move it inside of the level settings)
- mood (either just a string or same as level, have a list in database + custom)
- mood-func (same as mood)
- Ocean (same as mood)
- sun-fade (float, from 0.0 to 1.0
- bsphere (linked to a empty sphere and use it's position + size/scaling for W)
### For level's json
- Automatic_wall_angle (float, -1 = off, any number on + set the angle)
- Double sided collision (on/off)

---

## Tasks & Menu implementation

---

## Level files clean up when changing level name (or at least a warning?)

---

## Blender clean up feature
- Orphan node collections
- Orphan preview meshes

---

## Move custom checkpoint actor 
- to an always loaded file in game.gd
- As it's the same type that'll be used in all levels

---

## Baking options
- Better handling of emiting materials
- Limit range of lighting 
  - Anything under 0.25 brightness will be considered black
  - Anything above 0.75 brightness will be considered over exposed/look as if it was emiting light
  - don't fully limit those, maybe a setting for how much you want to "limit" it?
- Being able to switch between face corner and vertex

---

## Exta tools
### Set to floor
- Find ground (ray cast from slightly above the current position to not miss if you're already on it or slightly under)
- Set a distance from the ground (especially useful for floating orbs)
- Align or not with the floor
- Ability to affect multiple actors/object at once
- Use center or bottom vertex (for meshes)

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

## Time of day implementation 
(when it's implemented in main project/mod-base)
- Enable/disable
- Select a collection per time of day (containing lights)
- Select a world setting per time of day
- baking lights when these things are selected should 

---