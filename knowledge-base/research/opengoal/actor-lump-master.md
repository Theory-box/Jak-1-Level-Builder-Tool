# Jak 1 Actor Lump & Settings — Master Reference (FULL)

Auto-generated 2026-05-31 from OpenGOAL `jak-project` jak1 source (155 actors). **Full** list — every lump the engine reads per actor, nothing folded away. Derived from all `res-lump-*`/`get-property-*`/`entity-actor-*`/`lookup-tag` reads across methods, states, behaviours, called helpers in the same file, the full `:parent` chain, and inherited param-loader fields (e.g. `sync-info`).

**Legend** — `key` = read & in DB · **`key`** = read but MISSING from DB · _(common: …)_ = entity/draw lumps most actors share · `_DB-only_` = in DB but not seen in source (stale, or read by a generic subsystem like the fact system).

## Bosses

| Actor (etype) | Label | Lumps read (engine) |
|---|---|---|
| `ogreboss` | Klaww (Ogre Boss) | **alt-actor**, **target-actor**, **trigger-actor**, **water-actor** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `plant-boss` | Plant Boss | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `robotboss` | Metal Head Boss | **alt-actor** _(common: joint-channel, light-index, name, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |

## Buttons and Doors

| Actor (etype) | Label | Lumps read (engine) |
|---|---|---|
| `basebutton` | Wall Button | **alt-actor**, extra-id, next-actor, prev-actor, timeout _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `eco-door` | Eco Door (iris) | flags, scale, state-actor _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: perm-status_ |
| `jng-iris-door` | Iris Door (Jungle) | flags, scale, state-actor _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: perm-status_ |
| `launcherdoor` | Launcher Door | **alt-actor**, continue-name _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `rounddoor` | Round Door (Misty) | **flags**, **scale**, **state-actor** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: distance, perm-status_ |
| `sidedoor` | Side Door (Jungle) | flags, scale, state-actor _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: height-info, perm-status_ |
| `sun-iris-door` | Iris Door (Sunken) | proximity, scale-factor, timeout _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `warp-gate` | Warp Gate Switch | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: next-actor, prev-actor, timeout_ |
| `warpgate` | Warp Gate | — _(common: nav-max-users, nav-mesh-actor)_ |

## Debug

| Actor (etype) | Label | Lumps read (engine) |
|---|---|---|
| `test-actor` | Test Actor | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |

## Enemies

| Actor (etype) | Label | Lumps read (engine) |
|---|---|---|
| `babak` | Babak (Lurker) | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `baby-spider` | Baby Spider | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `balloonlurker` | Balloon Lurker | **alt-actor**, water-actor _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `bonelurker` | Bone Lurker | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `bully` | Bully | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `cave-trap` | Cave Trap | alt-actor _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: path_ |
| `darkvine` | Dark Vine | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `double-lurker` | Double Lurker | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `driller-lurker` | Driller Lurker | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `flying-lurker` | Flying Lurker | **alt-actor** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `gnawer` | Gnawer | extra-count, rotoffset _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `green-eco-lurker` | Green Eco Lurker | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `hopper` | Hopper | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `ice-cube` | Ice Cube | mode _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `junglefish` | Jungle Fish | water-height _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `junglesnake` | Jungle Snake | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `kermit` | Kermit (Lurker) | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `lurkercrab` | Lurker Crab | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `lurkerpuppy` | Lurker Puppy | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `lurkerworm` | Lurker Worm | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `mother-spider` | Mother Spider | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `plunger-lurker` | Plunger Lurker | **alt-actor** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `puffer` | Puffer | **alt-actor**, distance, **notice-dist**, **sync** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `quicksandlurker` | Quicksand Lurker | water-actor _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `ram` | Ram | extra-id, mode _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `sharkey` | Lurker Shark | delay, distance, scale, speed, water-height _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `snow-bunny` | Snow Bunny | mode _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `spider-egg` | Spider Egg | alt-actor _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `spider-vent` | Spider Vent | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `swamp-bat` | Swamp Bat | num-lurkers _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `swamp-rat` | Swamp Rat | **water-height** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `swamp-rat-nest` | Swamp Rat Nest | num-lurkers _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `yeti` | Yeti | notice-dist, num-lurkers _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |

## Hidden

| Actor (etype) | Label | Lumps read (engine) |
|---|---|---|
| `water-vol` | Water Volume (legacy) | attack-event, water-height _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |

## Interactive Objects

| Actor (etype) | Label | Lumps read (engine) |
|---|---|---|
| `balloon` | Balloon Obstacle | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `cavecrystal` | Cave Crystal | timeout _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `cavegem` | Cave Gem | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `dark-crystal` | Dark Crystal | extra-id, extra-radius, mode _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `dark-plant` | Dark Plant (Prop) | **alt-actor** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: max-frame, min-frame_ |
| `ecoventrock` | Eco Vent (Rock) | **alt-actor** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: distance, num-positions, speed_ |
| `fishermans-boat` | Fisherman's Boat | **water-actor** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `gondola` | Gondola | **alt-actor** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `lavaballoon` | Lava Balloon | speed _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: delay_ |
| `lightning-mole` | Lightning Mole | **alt-actor** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `muse` | Muse | **movie-pos** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `peeper` | Peeper | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `shortcut-boulder` | Shortcut Boulder | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `swamp-rock` | Swamp Rock | scale-factor _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `swamp-rope` | Swamp Rope | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `swamp-spike` | Swamp Spike | **sync** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: distance, scale-factor_ |
| `swamp-tetherrock` | Swamp Tether Rock | alt-actor _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |

## NPCs

| Actor (etype) | Label | Lumps read (engine) |
|---|---|---|
| `billy` | Billy | **alt-actor** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `explorer` | Explorer | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `farmer` | Farmer | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `fisher` | Fisher | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `flutflut` | Flut Flut | index, rotoffset _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `gambler` | Gambler | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `geologist` | Geologist | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `mayor` | Mayor | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `minershort` | Miner (Short) | alt-actor _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `minertall` | Miner (Tall) | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `oracle` | Oracle | alt-task _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `pelican` | Pelican | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `robber` | Robber (Lurker) | initial-spline-pos, timeout, water-height _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `sculptor` | Sculptor | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `seagull` | Seagull | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `warrior` | Warrior | **alt-actor** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `yakow` | Yakow | **alt-actor**, alt-vector, water-height _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |

## Obstacles

| Actor (etype) | Label | Lumps read (engine) |
|---|---|---|
| `cavecrusher` | Cave Crusher | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `caveflamepots` | Cave Flame Pots | cycle-speed, rotoffset, shove _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `chainmine` | Chain Mine | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: delay_ |
| `crate-darkeco-cluster` | Dark Eco Crate Cluster | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `darkecobarrel` | Dark Eco Barrel | delay, speed, **sync** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `fireboulder` | Fire Boulder | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: alt-task_ |
| `shover` | Shover Platform | collision-mesh-id, rotoffset, shove _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `spike` | Spike | **alt-actor** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `swampgate` | Swamp Spike Gate | **sync** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: distance, scale-factor_ |
| `tntbarrel` | TNT Barrel | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `whirlpool` | Whirlpool | speed, **sync** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |

## Pickups

| Actor (etype) | Label | Lumps read (engine) |
|---|---|---|
| `buzzer` | Scout Fly | **movie-pos** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `crate` | Crate | crate-type _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: eco-info_ |
| `eco-blue` | Blue Eco Vent | **eco-info**, **movie-pos** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `eco-blue` | Eco (Blue) | **eco-info**, **movie-pos** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `eco-pill` | Eco Pill (Health) | **movie-pos** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `eco-red` | Red Eco Vent | **eco-info**, **movie-pos** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `eco-red` | Eco (Red) | **eco-info**, **movie-pos** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `eco-yellow` | Yellow Eco Vent | **eco-info**, **movie-pos** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `eco-yellow` | Eco (Yellow) | **eco-info**, **movie-pos** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: alt-actor_ |
| `ecovalve` | Eco Valve | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `ecovent` | Eco Vent (Green) | **alt-actor** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `fuel-cell` | Power Cell | movie-pos _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `health` | Eco (Green) | **movie-pos** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `money` | Orb (Precursor) | **movie-pos** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: movie-mask_ |
| `orb-cache-top` | Orb Cache | orb-cache-count _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: flags_ |
| `ventblue` | Eco Vent (Blue) | alt-actor _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `ventred` | Eco Vent (Red) | alt-actor _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `ventyellow` | Eco Vent (Yellow) | alt-actor _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |

## Platforms

| Actor (etype) | Label | Lumps read (engine) |
|---|---|---|
| `balance-plat` | Balance Platform | distance _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: next-actor, prev-actor_ |
| `breakaway-left` | Breakaway Plat (L) | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: animation-select, height-info, particle-select_ |
| `breakaway-mid` | Breakaway Plat (M) | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: animation-select, height-info, particle-select_ |
| `breakaway-right` | Breakaway Plat (R) | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: animation-select, height-info, particle-select_ |
| `caveelevator` | Cave Elevator | mode, rotoffset, **sync** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `cavespatula` | Cave Spatula Plat | **sync** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `cavespatulatwo` | Cave Spatula Plat 2 | **sync** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `cavetrapdoor` | Cave Trap Door | delay _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `launcher` | Launcher | alt-vector, mode, spring-height _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: trigger-height_ |
| `mis-bone-bridge` | Bone Bridge | animation-select _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `ogre-bridge` | Ogre Drawbridge | alt-actor _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `ogre-bridgeend` | Ogre Bridge End | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `orbit-plat` | Orbit Platform | alt-actor, scale, timeout _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: flags_ |
| `plat` | Floating Platform | sync _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: flags_ |
| `plat-button` | Button Platform | bidirectional, camera-name _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `plat-eco` | Eco Platform | notice-dist, sync _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: flags_ |
| `plat-flip` | Flip Platform | delay, **sync**, sync-percent _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `pontoonfive` | Pontoon (Five) | **alt-task**, **water-actor** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `pontoonten` | Pontoon (Ten) | alt-task, **water-actor** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `ropebridge` | Rope Bridge | art-name _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: campoints-offset, spline-offset_ |
| `side-to-side-plat` | Side-to-Side Plat | sync _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: flags_ |
| `springbox` | Bounce Pad (Bouncer) | spring-height _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `square-platform` | Square Platform | alt-actor, distance _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `steam-cap` | Steam Cap | percent, sync _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `swingpole` | Swing Pole | — _(common: nav-max-users, nav-mesh-actor)_ |
| `tar-plat` | Tar Platform | **water-actor** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: scale-factor_ |
| `teetertotter` | Teeter Totter | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `wall-plat` | Wall Platform | **sync**, tunemeters _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `wedge-plat` | Wedge Platform | **alt-actor**, distance, rotoffset _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: rotspeed_ |

## Visuals

| Actor (etype) | Label | Lumps read (engine) |
|---|---|---|
| `accordian` | Accordian (prop) | alt-actor _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: height-info_ |
| `boatpaddle` | Boat Paddle | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: animation-select, particle-select_ |
| `ceilingflag` | Ceiling Flag | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: alt-task_ |
| `ecoclaw` | Eco Claw | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `evilplant` | Evil Plant (Prop) | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: height-info, num-lurkers_ |
| `lavabase` | Lava Base | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: delay_ |
| `lavafall` | Lava Fall | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: delay_ |
| `lavafallsewera` | Lava Fall Sewer A | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: delay_ |
| `lavafallsewerb` | Lava Fall Sewer B | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: delay_ |
| `lavayellowtarp` | Yellow Tarp (prop) | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: delay_ |
| `powercellalt` | Power Cell (alt) | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `sunkenfisha` | Sunken Fish School | count, path-max-offset, path-trans-offset, speed _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `swamp-blimp` | Swamp Blimp | **alt-actor** _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `villa-starfish` | Villa Starfish | num-lurkers _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |
| `windmill-one` | Windmill | — _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ · _DB-only: distance, num-positions, speed_ |
| `windturbine` | Wind Turbine | particle-select _(common: joint-channel, light-index, nav-max-users, nav-mesh-actor, options, shadow-mask, texture-bucket, trans-offset)_ |

---

## Coverage, method & known limits

Per actor, lump tags are accumulated from all `res-lump-*` / `get-property-*` / `entity-actor-lookup`/`-count` / `lookup-tag` reads in the actor type's methods, states, and behaviours; reads inherited up the full `:parent` chain; and **inherited** param-loader fields (types with a `load-params!` method, e.g. `sync-info` → `sync`) gathered across that whole chain. Moving platforms are driven by `sync` (period/phase), **not** a `speed` lump — only ~5 actors (e.g. `grottopole`, `whirlpool`) read a real `speed` lump.

**Important on co-located files.** Many actors share one source file (`beach-obs.gc` has 8, `collectables.gc` 13, `swamp-obs.gc` 8). A read belongs to the *type whose method/state it sits in*, not to every actor in the file — e.g. `speed`/`distance` in `beach-obs.gc` are `grottopole`'s, not `windmill-one`'s; `eco-info` near pickups is the `eco`/`fact` system's, not each pickup's.

**Known limits (verify by hand):**

- **Generic-subsystem reads** — `eco-info`, `movie-mask`, parts of the fact/entity/draw systems are read by shared engine code for any qualifying entity, not by actor code; they appear as `_DB-only_` even when the DB is right to list them.
- **Dynamic lump names** — reads using a variable tag (e.g. curve `points-name`/`knots-name`) can't be captured statically.
- **Helper `defun` reads** — lumps read only inside shared helper functions (not type methods) are not attributed, to avoid spreading them across unrelated actors.

**Residual edge-cases flagged for manual confirmation** (reads in single-actor files not auto-attributed — likely real, confirm against source before adding to DB):

| Actor | Possible additional lump(s) |
|---|---|
| `wedge-plat` | rotspeed |
| `square-platform` | timeout (read by its `-master` controller) |
| `warpgate` | cam-notice-dist, index, trigger-actor |
| `dark-plant` | max-frame, min-frame |
| `rounddoor` | distance |
| `crate` | alt-actor |
| `launcher` | art-name, index, level |
