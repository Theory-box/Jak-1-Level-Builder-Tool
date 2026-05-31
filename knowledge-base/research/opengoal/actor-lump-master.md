# Jak 1 Actor Lump & Settings — Master Reference (FULL)

Auto-generated 2026-05-31 from OpenGOAL `jak-project` jak1 source (155 actors). **Full** list — every lump the engine reads per actor, nothing folded away. Derived from all `res-lump-*`/`get-property-*`/`entity-actor-*`/`lookup-tag` reads across methods, states, behaviours, called helpers in the same file, the full `:parent` chain, and inherited param-loader fields (e.g. `sync-info`).

**Legend** — `key` = read & in DB · **`key`** = read but MISSING from DB · `_DB-only_` = in DB but not seen in source (stale, or read by a generic subsystem like the fact system).

> **Common lumps** (read by virtually every actor; omitted from the rows below): joint-channel, light-index, name, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans, trans-offset

## Bosses

| Actor (etype) | Label | Specific lumps |
|---|---|---|
| `ogreboss` | Klaww (Ogre Boss) | **alt-actor**, **target-actor**, **trigger-actor**, **water-actor** |
| `plant-boss` | Plant Boss | *(common only)* |
| `robotboss` | Metal Head Boss | **alt-actor** |

## Buttons and Doors

| Actor (etype) | Label | Specific lumps |
|---|---|---|
| `basebutton` | Wall Button | **alt-actor**, extra-id, next-actor, prev-actor, timeout |
| `eco-door` | Eco Door (iris) | flags, scale, state-actor · _DB-only: perm-status_ |
| `jng-iris-door` | Iris Door (Jungle) | flags, scale, state-actor · _DB-only: perm-status_ |
| `launcherdoor` | Launcher Door | **alt-actor**, continue-name |
| `rounddoor` | Round Door (Misty) | **flags**, **scale**, **state-actor** · _DB-only: distance, perm-status_ |
| `sidedoor` | Side Door (Jungle) | flags, scale, state-actor · _DB-only: height-info, perm-status_ |
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
| `balloonlurker` | Balloon Lurker | **alt-actor**, water-actor |
| `bonelurker` | Bone Lurker | *(common only)* |
| `bully` | Bully | *(common only)* |
| `cave-trap` | Cave Trap | alt-actor · _DB-only: path_ |
| `darkvine` | Dark Vine | *(common only)* |
| `double-lurker` | Double Lurker | *(common only)* |
| `driller-lurker` | Driller Lurker | *(common only)* |
| `flying-lurker` | Flying Lurker | **alt-actor** |
| `gnawer` | Gnawer | extra-count, rotoffset |
| `green-eco-lurker` | Green Eco Lurker | *(common only)* |
| `hopper` | Hopper | *(common only)* |
| `ice-cube` | Ice Cube | mode |
| `junglefish` | Jungle Fish | water-height |
| `junglesnake` | Jungle Snake | *(common only)* |
| `kermit` | Kermit (Lurker) | *(common only)* |
| `lurkercrab` | Lurker Crab | *(common only)* |
| `lurkerpuppy` | Lurker Puppy | *(common only)* |
| `lurkerworm` | Lurker Worm | *(common only)* |
| `mother-spider` | Mother Spider | *(common only)* |
| `plunger-lurker` | Plunger Lurker | **alt-actor** |
| `puffer` | Puffer | **alt-actor**, distance, **notice-dist**, **sync** |
| `quicksandlurker` | Quicksand Lurker | water-actor |
| `ram` | Ram | extra-id, mode |
| `sharkey` | Lurker Shark | delay, distance, scale, speed, water-height |
| `snow-bunny` | Snow Bunny | mode |
| `spider-egg` | Spider Egg | alt-actor |
| `spider-vent` | Spider Vent | *(common only)* |
| `swamp-bat` | Swamp Bat | num-lurkers |
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
| `dark-plant` | Dark Plant (Prop) | **alt-actor** · _DB-only: max-frame, min-frame_ |
| `ecoventrock` | Eco Vent (Rock) | **alt-actor** · _DB-only: distance, num-positions, speed_ |
| `fishermans-boat` | Fisherman's Boat | **water-actor** |
| `gondola` | Gondola | **alt-actor** |
| `lavaballoon` | Lava Balloon | speed · _DB-only: delay_ |
| `lightning-mole` | Lightning Mole | **alt-actor** |
| `muse` | Muse | **movie-pos** |
| `peeper` | Peeper | *(common only)* |
| `shortcut-boulder` | Shortcut Boulder | *(common only)* |
| `swamp-rock` | Swamp Rock | scale-factor |
| `swamp-rope` | Swamp Rope | *(common only)* |
| `swamp-spike` | Swamp Spike | **sync** · _DB-only: distance, scale-factor_ |
| `swamp-tetherrock` | Swamp Tether Rock | alt-actor |

## NPCs

| Actor (etype) | Label | Specific lumps |
|---|---|---|
| `billy` | Billy | **alt-actor** |
| `explorer` | Explorer | *(common only)* |
| `farmer` | Farmer | *(common only)* |
| `fisher` | Fisher | *(common only)* |
| `flutflut` | Flut Flut | index, rotoffset |
| `gambler` | Gambler | *(common only)* |
| `geologist` | Geologist | *(common only)* |
| `mayor` | Mayor | *(common only)* |
| `minershort` | Miner (Short) | alt-actor |
| `minertall` | Miner (Tall) | *(common only)* |
| `oracle` | Oracle | alt-task |
| `pelican` | Pelican | *(common only)* |
| `robber` | Robber (Lurker) | initial-spline-pos, timeout, water-height |
| `sculptor` | Sculptor | *(common only)* |
| `seagull` | Seagull | *(common only)* |
| `warrior` | Warrior | **alt-actor** |
| `yakow` | Yakow | **alt-actor**, alt-vector, water-height |

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
| `spike` | Spike | **alt-actor** |
| `swampgate` | Swamp Spike Gate | **sync** · _DB-only: distance, scale-factor_ |
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
| `ecovent` | Eco Vent (Green) | **alt-actor** |
| `fuel-cell` | Power Cell | movie-pos |
| `health` | Eco (Green) | **movie-pos** |
| `money` | Orb (Precursor) | **movie-pos** · _DB-only: movie-mask_ |
| `orb-cache-top` | Orb Cache | orb-cache-count · _DB-only: flags_ |
| `ventblue` | Eco Vent (Blue) | alt-actor |
| `ventred` | Eco Vent (Red) | alt-actor |
| `ventyellow` | Eco Vent (Yellow) | alt-actor |

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
| `ogre-bridge` | Ogre Drawbridge | alt-actor |
| `ogre-bridgeend` | Ogre Bridge End | *(common only)* |
| `orbit-plat` | Orbit Platform | alt-actor, scale, timeout · _DB-only: flags_ |
| `plat` | Floating Platform | sync · _DB-only: flags_ |
| `plat-button` | Button Platform | bidirectional, camera-name |
| `plat-eco` | Eco Platform | notice-dist, sync · _DB-only: flags_ |
| `plat-flip` | Flip Platform | delay, **sync**, sync-percent |
| `pontoonfive` | Pontoon (Five) | **alt-task**, **water-actor** |
| `pontoonten` | Pontoon (Ten) | alt-task, **water-actor** |
| `ropebridge` | Rope Bridge | art-name · _DB-only: campoints-offset, spline-offset_ |
| `side-to-side-plat` | Side-to-Side Plat | sync · _DB-only: flags_ |
| `springbox` | Bounce Pad (Bouncer) | spring-height |
| `square-platform` | Square Platform | alt-actor, distance |
| `steam-cap` | Steam Cap | percent, sync |
| `swingpole` | Swing Pole | *(common only)* |
| `tar-plat` | Tar Platform | **water-actor** · _DB-only: scale-factor_ |
| `teetertotter` | Teeter Totter | *(common only)* |
| `wall-plat` | Wall Platform | **sync**, tunemeters |
| `wedge-plat` | Wedge Platform | **alt-actor**, distance, rotoffset · _DB-only: rotspeed_ |

## Visuals

| Actor (etype) | Label | Specific lumps |
|---|---|---|
| `accordian` | Accordian (prop) | alt-actor · _DB-only: height-info_ |
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
| `swamp-blimp` | Swamp Blimp | **alt-actor** |
| `villa-starfish` | Villa Starfish | num-lurkers |
| `windmill-one` | Windmill | *(common only)* · _DB-only: distance, num-positions, speed_ |
| `windturbine` | Wind Turbine | particle-select |
