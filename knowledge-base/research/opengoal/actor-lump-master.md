# Jak 1 Actor Lump & Settings — Master Reference

Auto-generated 2026-05-31 from OpenGOAL `jak-project` jak1 source (155 actors). Lumps the engine reads, derived from every `res-lump-*` / `get-property-*` / `lookup-tag-idx` call across methods, states, behaviours, called helper functions, the `:parent` chain, and embedded param-loaders (e.g. `sync-info`).

**Legend** — `key` = read & in DB · **`key`** = read but MISSING from DB · `_DB-only_` = in DB but not seen in source (stale, *or* read by a generic subsystem like the fact/entity system rather than actor code).

> **Common lumps** (read by ≥50% of actors, omitted per-row): joint-channel, light-index, name, nav-max-users, options, shadow-mask, texture-bucket, trans, trans-offset

## Bosses

| Actor (etype) | Label | Specific lumps |
|---|---|---|
| `ogreboss` | Klaww (Ogre Boss) | *(common only)* |
| `plant-boss` | Plant Boss | **collide-mesh-group** |
| `robotboss` | Metal Head Boss | **cycle-speed**, **effect-name**, **effect-param** |

## Buttons and Doors

| Actor (etype) | Label | Specific lumps |
|---|---|---|
| `basebutton` | Wall Button | extra-id, next-actor, prev-actor, timeout |
| `eco-door` | Eco Door (iris) | flags, scale · _DB-only: perm-status, state-actor_ |
| `jng-iris-door` | Iris Door (Jungle) | flags, scale · _DB-only: perm-status, state-actor_ |
| `launcherdoor` | Launcher Door | continue-name |
| `rounddoor` | Round Door (Misty) | **flags**, **scale** · _DB-only: distance, perm-status_ |
| `sidedoor` | Side Door (Jungle) | flags, scale · _DB-only: height-info, perm-status, state-actor_ |
| `sun-iris-door` | Iris Door (Sunken) | proximity, scale-factor, timeout |
| `warp-gate` | Warp Gate Switch | *(common only)* · _DB-only: next-actor, prev-actor, timeout_ |
| `warpgate` | Warp Gate | *(common only)* |

## Debug

| Actor (etype) | Label | Specific lumps |
|---|---|---|
| `test-actor` | Test Actor | *(common only)* |

## Enemies

| Actor (etype) | Label | Specific lumps |
|---|---|---|
| `babak` | Babak (Lurker) | *(common only)* |
| `baby-spider` | Baby Spider | *(common only)* |
| `balloonlurker` | Balloon Lurker | *(common only)* · _DB-only: water-actor_ |
| `bonelurker` | Bone Lurker | *(common only)* |
| `bully` | Bully | **cam-horz**, **cam-notice-dist**, **cam-vert**, **cutoutvol**, **cycle-speed**, **eco-info**, **effect-name**, **effect-param**, **idle-distance**, **nearest-y-threshold**, **notice-bottom**, **notice-top**, **speed**, **timeout**, **vol** |
| `cave-trap` | Cave Trap | *(common only)* · _DB-only: alt-actor, path_ |
| `darkvine` | Dark Vine | *(common only)* |
| `double-lurker` | Double Lurker | *(common only)* |
| `driller-lurker` | Driller Lurker | **cycle-speed**, **driller-lurker**, **effect-name**, **effect-param** |
| `flying-lurker` | Flying Lurker | *(common only)* |
| `gnawer` | Gnawer | **cycle-speed**, **effect-name**, **effect-param**, extra-count, gnawer, rotoffset |
| `green-eco-lurker` | Green Eco Lurker | *(common only)* |
| `hopper` | Hopper | *(common only)* |
| `ice-cube` | Ice Cube | mode |
| `junglefish` | Jungle Fish | water-height |
| `junglesnake` | Jungle Snake | *(common only)* |
| `kermit` | Kermit (Lurker) | *(common only)* |
| `lurkercrab` | Lurker Crab | *(common only)* |
| `lurkerpuppy` | Lurker Puppy | *(common only)* |
| `lurkerworm` | Lurker Worm | *(common only)* |
| `mother-spider` | Mother Spider | **mother-spider** |
| `plunger-lurker` | Plunger Lurker | *(common only)* |
| `puffer` | Puffer | **cam-horz**, **cam-notice-dist**, **cam-vert**, **collide-mesh-group**, **cutoutvol**, **cycle-speed**, distance, **eco-info**, **effect-name**, **effect-param**, **idle-distance**, **lod-dist**, **nearest-y-threshold**, **notice-bottom**, **notice-dist**, **notice-top**, **speed**, **sync**, **timeout**, **vis-dist**, **vol** |
| `quicksandlurker` | Quicksand Lurker | *(common only)* · _DB-only: water-actor_ |
| `ram` | Ram | extra-id, mode, **nav-mesh-actor** |
| `sharkey` | Lurker Shark | delay, distance, scale, speed, water-height |
| `snow-bunny` | Snow Bunny | mode |
| `spider-egg` | Spider Egg | **lod-dist**, **vis-dist** · _DB-only: alt-actor_ |
| `spider-vent` | Spider Vent | *(common only)* |
| `swamp-bat` | Swamp Bat | **cam-horz**, **cam-notice-dist**, **cam-vert**, **cutoutvol**, **cycle-speed**, **eco-info**, **effect-name**, **effect-param**, **idle-distance**, **nearest-y-threshold**, **notice-bottom**, **notice-top**, num-lurkers, **speed**, **timeout**, **vol** |
| `swamp-rat` | Swamp Rat | **water-height** |
| `swamp-rat-nest` | Swamp Rat Nest | num-lurkers |
| `yeti` | Yeti | notice-dist, num-lurkers |

## Hidden

| Actor (etype) | Label | Specific lumps |
|---|---|---|
| `water-vol` | Water Volume (legacy) | attack-event, water-height |

## Interactive Objects

| Actor (etype) | Label | Specific lumps |
|---|---|---|
| `balloon` | Balloon Obstacle | *(common only)* |
| `cavecrystal` | Cave Crystal | timeout |
| `cavegem` | Cave Gem | *(common only)* |
| `dark-crystal` | Dark Crystal | extra-id, extra-radius, mode |
| `dark-plant` | Dark Plant (Prop) | *(common only)* · _DB-only: max-frame, min-frame_ |
| `ecoventrock` | Eco Vent (Rock) | *(common only)* · _DB-only: distance, num-positions, speed_ |
| `fishermans-boat` | Fisherman's Boat | *(common only)* |
| `gondola` | Gondola | *(common only)* |
| `lavaballoon` | Lava Balloon | speed · _DB-only: delay_ |
| `lightning-mole` | Lightning Mole | *(common only)* |
| `muse` | Muse | **movie-pos** |
| `peeper` | Peeper | *(common only)* |
| `shortcut-boulder` | Shortcut Boulder | **lod-dist**, **vis-dist** |
| `swamp-rock` | Swamp Rock | scale-factor |
| `swamp-rope` | Swamp Rope | *(common only)* |
| `swamp-spike` | Swamp Spike | **sync** · _DB-only: distance, scale-factor_ |
| `swamp-tetherrock` | Swamp Tether Rock | **fov** · _DB-only: alt-actor_ |

## NPCs

| Actor (etype) | Label | Specific lumps |
|---|---|---|
| `billy` | Billy | *(common only)* |
| `explorer` | Explorer | *(common only)* |
| `farmer` | Farmer | *(common only)* |
| `fisher` | Fisher | *(common only)* |
| `flutflut` | Flut Flut | index, rotoffset |
| `gambler` | Gambler | *(common only)* |
| `geologist` | Geologist | *(common only)* |
| `mayor` | Mayor | *(common only)* |
| `minershort` | Miner (Short) | *(common only)* · _DB-only: alt-actor_ |
| `minertall` | Miner (Tall) | *(common only)* |
| `oracle` | Oracle | alt-task |
| `pelican` | Pelican | *(common only)* |
| `robber` | Robber (Lurker) | initial-spline-pos, timeout, water-height |
| `sculptor` | Sculptor | *(common only)* |
| `seagull` | Seagull | *(common only)* |
| `warrior` | Warrior | *(common only)* |
| `yakow` | Yakow | alt-vector, **cam-horz**, **cam-notice-dist**, **cam-vert**, **cutoutvol**, **cycle-speed**, **eco-info**, **effect-name**, **effect-param**, **idle-distance**, **nearest-y-threshold**, **notice-bottom**, **notice-top**, **speed**, **timeout**, **vol**, water-height |

## Obstacles

| Actor (etype) | Label | Specific lumps |
|---|---|---|
| `cavecrusher` | Cave Crusher | *(common only)* |
| `caveflamepots` | Cave Flame Pots | cycle-speed, rotoffset, shove |
| `chainmine` | Chain Mine | *(common only)* · _DB-only: delay_ |
| `crate-darkeco-cluster` | Dark Eco Crate Cluster | *(common only)* |
| `darkecobarrel` | Dark Eco Barrel | delay, speed, **sync** |
| `fireboulder` | Fire Boulder | *(common only)* · _DB-only: alt-task_ |
| `shover` | Shover Platform | collision-mesh-id, rotoffset, shove |
| `spike` | Spike | *(common only)* |
| `swampgate` | Swamp Spike Gate | *(common only)* · _DB-only: distance, scale-factor_ |
| `tntbarrel` | TNT Barrel | *(common only)* |
| `whirlpool` | Whirlpool | speed, **sync** |

## Pickups

| Actor (etype) | Label | Specific lumps |
|---|---|---|
| `buzzer` | Scout Fly | **movie-pos** |
| `crate` | Crate | crate-type · _DB-only: eco-info_ |
| `eco-blue` | Blue Eco Vent | **eco-info**, **movie-pos** |
| `eco-blue` | Eco (Blue) | **eco-info**, **movie-pos** |
| `eco-pill` | Eco Pill (Health) | **movie-pos** |
| `eco-red` | Red Eco Vent | **eco-info**, **movie-pos** |
| `eco-red` | Eco (Red) | **eco-info**, **movie-pos** |
| `eco-yellow` | Yellow Eco Vent | **eco-info**, **movie-pos** |
| `eco-yellow` | Eco (Yellow) | **eco-info**, **movie-pos** · _DB-only: alt-actor_ |
| `ecovalve` | Eco Valve | *(common only)* |
| `ecovent` | Eco Vent (Green) | *(common only)* |
| `fuel-cell` | Power Cell | movie-pos |
| `health` | Eco (Green) | **movie-pos** |
| `money` | Orb (Precursor) | **movie-pos** · _DB-only: movie-mask_ |
| `orb-cache-top` | Orb Cache | orb-cache-count · _DB-only: flags_ |
| `ventblue` | Eco Vent (Blue) | *(common only)* · _DB-only: alt-actor_ |
| `ventred` | Eco Vent (Red) | *(common only)* · _DB-only: alt-actor_ |
| `ventyellow` | Eco Vent (Yellow) | *(common only)* · _DB-only: alt-actor_ |

## Platforms

| Actor (etype) | Label | Specific lumps |
|---|---|---|
| `balance-plat` | Balance Platform | distance · _DB-only: next-actor, prev-actor_ |
| `breakaway-left` | Breakaway Plat (L) | *(common only)* · _DB-only: animation-select, height-info, particle-select_ |
| `breakaway-mid` | Breakaway Plat (M) | *(common only)* · _DB-only: animation-select, height-info, particle-select_ |
| `breakaway-right` | Breakaway Plat (R) | *(common only)* · _DB-only: animation-select, height-info, particle-select_ |
| `caveelevator` | Cave Elevator | mode, rotoffset, **sync** |
| `cavespatula` | Cave Spatula Plat | **sync** |
| `cavespatulatwo` | Cave Spatula Plat 2 | **sync** |
| `cavetrapdoor` | Cave Trap Door | delay |
| `launcher` | Launcher | alt-vector, mode, spring-height · _DB-only: trigger-height_ |
| `mis-bone-bridge` | Bone Bridge | animation-select |
| `ogre-bridge` | Ogre Drawbridge | *(common only)* · _DB-only: alt-actor_ |
| `ogre-bridgeend` | Ogre Bridge End | *(common only)* |
| `orbit-plat` | Orbit Platform | scale, timeout · _DB-only: alt-actor, flags_ |
| `plat` | Floating Platform | sync · _DB-only: flags_ |
| `plat-button` | Button Platform | bidirectional, camera-name |
| `plat-eco` | Eco Platform | **lod-dist**, notice-dist, **vis-dist** · _DB-only: flags, sync_ |
| `plat-flip` | Flip Platform | delay, **sync**, sync-percent |
| `pontoonfive` | Pontoon (Five) | **alt-task** |
| `pontoonten` | Pontoon (Ten) | alt-task |
| `ropebridge` | Rope Bridge | art-name · _DB-only: campoints-offset, spline-offset_ |
| `side-to-side-plat` | Side-to-Side Plat | *(common only)* · _DB-only: flags, sync_ |
| `springbox` | Bounce Pad (Bouncer) | spring-height |
| `square-platform` | Square Platform | distance · _DB-only: alt-actor_ |
| `steam-cap` | Steam Cap | percent, sync |
| `swingpole` | Swing Pole | *(common only)* |
| `tar-plat` | Tar Platform | *(common only)* · _DB-only: scale-factor_ |
| `teetertotter` | Teeter Totter | *(common only)* |
| `wall-plat` | Wall Platform | **sync**, tunemeters |
| `wedge-plat` | Wedge Platform | distance, rotoffset · _DB-only: rotspeed_ |

## Visuals

| Actor (etype) | Label | Specific lumps |
|---|---|---|
| `accordian` | Accordian (prop) | *(common only)* · _DB-only: alt-actor, height-info_ |
| `boatpaddle` | Boat Paddle | *(common only)* · _DB-only: animation-select, particle-select_ |
| `ceilingflag` | Ceiling Flag | *(common only)* · _DB-only: alt-task_ |
| `ecoclaw` | Eco Claw | *(common only)* |
| `evilplant` | Evil Plant (Prop) | *(common only)* · _DB-only: height-info, num-lurkers_ |
| `lavabase` | Lava Base | *(common only)* · _DB-only: delay_ |
| `lavafall` | Lava Fall | *(common only)* · _DB-only: delay_ |
| `lavafallsewera` | Lava Fall Sewer A | *(common only)* · _DB-only: delay_ |
| `lavafallsewerb` | Lava Fall Sewer B | *(common only)* · _DB-only: delay_ |
| `lavayellowtarp` | Yellow Tarp (prop) | *(common only)* · _DB-only: delay_ |
| `powercellalt` | Power Cell (alt) | *(common only)* |
| `sunkenfisha` | Sunken Fish School | count, path-max-offset, path-trans-offset, speed |
| `swamp-blimp` | Swamp Blimp | *(common only)* |
| `villa-starfish` | Villa Starfish | num-lurkers |
| `windmill-one` | Windmill | *(common only)* · _DB-only: distance, num-positions, speed_ |
| `windturbine` | Wind Turbine | particle-select |

---

## Method & known limits

Generated by `tools/extract_lumps_from_goal.py` against the OpenGOAL `jak-project` jak1 source. For each DB actor it accumulates lump tags from: the actor type's own `res-lump-*` / `get-property-*` / `lookup-tag-idx` reads; reads in its methods, states, and behaviours; reads inherited up the `:parent` chain; reads in embedded param-loader fields (e.g. `sync-info` → `sync`); and reads in specific helper functions it calls (helpers shared by >3 types are excluded to avoid generic-utility noise).

Known limits — verify these by hand rather than trusting the table blindly:

- **Dynamic lump names.** When a read uses a variable name (e.g. curve `points-name` / `knots-name`) instead of a quoted tag, the lump can't be captured statically. Curve/spline actors may read more than shown.
- **Generic-subsystem reads.** Some tags (`eco-info`, parts of the fact/entity/draw systems) are read by shared engine code for *any* entity carrying them, not by actor-specific code. These appear as `_DB-only_` here even though the DB is correct to list them.
- **`_DB-only_` ≠ stale.** It means source and DB disagree at this actor — review each: it may be a stale DB entry, or one of the two limits above.

Re-run after a jak-project update to refresh.
