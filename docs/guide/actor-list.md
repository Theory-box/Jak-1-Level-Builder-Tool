# Actor list

Every actor you can place from **Spawn Objects** (258 in all), grouped like its tiles. The search in Spawn Objects finds them by name or etype. Notes: **nav-mesh** = an enemy that needs a nav-mesh to move ([Enemies & nav-meshes](enemies-and-navmesh.md)), **path** = needs a path ([Paths & platforms](paths-and-platforms.md)), **edited** = a vanilla actor made to work in custom levels ([Edited actors](edited-actors-and-goal-code.md)).

*Generated from the add-on's database by `tools/gen_actor_list.py`.*

Jump to: [Enemies](#enemies) · [Platforms](#platforms) · [Interactive Objects](#interactive-objects) · [Obstacles](#obstacles) · [Buttons and Doors](#buttons-and-doors) · [Visuals](#visuals) · [NPCs](#npcs) · [Pickups](#pickups) · [Effects](#effects)

## Enemies

| Actor | etype | Notes | What it is |
|---|---|---|---|
| Aphid | `aphid` | nav-mesh, path | The aphid lurker is an insectoid lurker enemy in The Precursor Legacy. |
| Babak (Lurker) | `babak` | nav-mesh, path | The babak is a type of lurker in The Precursor Legacy, Daxter, and Jak II. |
| Babak with cannon (Lurker) | `babak-with-cannon` | nav-mesh, path | Babak that runs back to its spawn spot and jumps on its linked Misty Cannon to fire at Jak, and jumps off when Jak comes close. |
| Baby Spider | `baby-spider` | nav-mesh, path | Small spider lurkers found in Spider Cave. |
| Balloon Lurker | `balloonlurker` | path | The mine dropper, also known as the lurker balloon, is a vehicle operated by a balloon lurker in The Precursor Legacy. |
| Battle Controller (Ambush) | `battlecontroller` | path | Lurker ambush: when Jak comes within 30 m it spawns lurkers along its spawn paths until enough have been beaten. |
| Bone Lurker | `bonelurker` | nav-mesh, path | The bone armor lurker is an enemy in The Precursor Legacy, only seen on Misty Island. |
| Bully | `bully` |  | The bully, also known as the spinning lurker, is an enemy in The Precursor Legacy. |
| Cave Spider Trap | `cave-trap` | path | Spawns baby spiders from its linked eggs / vents (max 8 alive) when Jak is within 46 m. |
| Citadel Bunny Lurker | `citb-bunny` | nav-mesh, path | The citadel bunny is a varient of the Snow Bunny |
| Dark Vine | `darkvine` |  |  |
| Double Lurker | `double-lurker` | nav-mesh, path | The double lurker is a team of enemies in The Precursor Legacy — two blue-tinted lurkers stacked on top of each other, the smaller riding on the larger to provide height… |
| Driller Lurker | `driller-lurker` | path | The driller lurker is an enemy in The Precursor Legacy that mines cave rock with its drill. |
| Flying Lurker | `flying-lurker` | path | The pedal-copter lurker, also known as a flying lurker, is an enemy in The Precursor Legacy. |
| Gnawer | `gnawer` | path | The gnawing lurker is a species of lurker encountered at Spider Cave. |
| Green Eco Lurker | `green-eco-lurker` | nav-mesh, path | The green eco lurker, also known as the dark eco lurker, is a lurker enemy in The Precursor Legacy. |
| Hopper | `hopper` | nav-mesh, path | A type of lurker encountered in the Forbidden Jungle during The Precursor Legacy. |
| Ice Cube | `ice-cube` | nav-mesh, path |  |
| Jungle Fish | `junglefish` | nav-mesh, path | The jungle fish, also known as the fish lurker, is an enemy in The Precursor Legacy. |
| Jungle Snake | `junglesnake` |  | The lurker snake is an enemy in The Precursor Legacy — large brown serpentine lurkers residing in the canopy of Forbidden Jungle. |
| Kermit (Lurker) | `kermit` | nav-mesh, path | The lurker toad is an enemy in The Precursor Legacy. |
| Klaww (Ogre Boss) | `ogreboss` | boss, edited | Klaww is a large lurker boss in The Precursor Legacy, operating from a volcanic section of Mountain Pass. |
| Lurker Crab | `lurkercrab` | nav-mesh, path | The lurker crab is an enemy found at Sentinel Beach. |
| Lurker Puppy | `lurkerpuppy` | nav-mesh, path | The lurker puppy is a small lurker patrolling the higher regions of Sentinel Beach. |
| Lurker Shark | `sharkey` | nav-mesh, path | The lurker shark is a large orange shark-like creature inhabiting the oceans in The Precursor Legacy, serving as the game's invisible wall mechanism to prevent the playe… |
| Lurker Worm | `lurkerworm` |  | The sand worm, also known as the sea serpent lurker, is an enemy in The Precursor Legacy. |
| Mother Spider | `mother-spider` | path | Place it on the floor under where it should hang: it hangs from Anchor height above the placement and lowers to Thread min height above it once Jak is within Activate di… |
| Plant Boss | `plant-boss` | boss, path | The dark eco plant is a boss-level enemy in The Precursor Legacy — a massively mutated dark eco plant in the Forbidden Temple. |
| Plunger Lurker | `plunger-lurker` |  |  |
| Precursor Robot Boss | `robotboss` | boss, path, edited | Gol and Maia's Precursor robot, the final boss. |
| Puffer | `puffer` | path | The puffer, also known as a flying lurker, is an enemy in The Precursor Legacy, found in the lost Precursor city. |
| Quicksand Lurker | `quicksandlurker` |  | The quicksand lurker, also known as the fireball lurker, is an enemy in The Precursor Legacy. |
| Ram | `ram` | path | Keep rams apart (own nav-mesh area): a ram boss jumping down while another is on the ground can freeze and become unkillable. |
| Ram Boss | `ram-boss` | nav-mesh, path | The Ram Boss has a shield and red eco is required to break it. |
| Robber (Lurker) | `robber` | path | Robbers of one task must be linked both ways (A next = B, B prev = A): the cell comes from the last one caught, and a lone robber never gives one. |
| Snow Bunny Lurker | `snow-bunny` | nav-mesh, path | The snow bunny is an enemy in The Precursor Legacy, encountered at Snowy Mountain and Gol and Maia's citadel. |
| Spider Egg | `spider-egg` |  | Link it to a Cave Spider Trap (the trap's Alt actors) to hatch baby spiders. |
| Spider Vent | `spider-vent` |  | Connect to a Cave Spider Trap (cave-trap) to infinitely spawn spiders from here |
| Swamp Bat | `swamp-bat` | path | The swamp bat is an enemy in The Precursor Legacy, commonly found flying in swarms near Boggy Swamp. |
| Swamp Rat | `swamp-rat` | nav-mesh, path | The swamp rat, also known as the rat lurker, is an enemy in The Precursor Legacy. |
| Swamp Rat Nest | `swamp-rat-nest` | path |  |
| Yeti | `yeti` | path | Invisible spawner: yeti slaves appear at random path points (never within 6 m of Jak) and patrol the path, using this actor's nav-mesh and activation settings. |

## Platforms

| Actor | etype | Notes | What it is |
|---|---|---|---|
| Balance Platform | `balance-plat` |  |  |
| Bone Bridge | `mis-bone-bridge` |  | Breaks after 3 hits (or one with red eco), only from its local +Z side. |
| Bone Platform | `bone-platform` |  | Floats on its linked Water Anim, or at ocean height (Y = 0 when the level has no ocean) without one. |
| Bounce Pad (Bouncer) | `springbox` |  |  |
| Breakaway Plat | `breakaway-mid` |  |  |
| Button Platform | `plat-button` | path |  |
| Cave Elevator | `caveelevator` |  | Moves along a baked animation (the path can't be edited). |
| Cave Spatula Plat | `cavespatula` | edited | Edited (subtypes/cavespatula.gc): the spinning cave spatula platform, always with its Dark Cave look (vanilla used it only in a level named darkcave; the other model has… |
| Cave Spatula Plat 2 | `cavespatulatwo` |  |  |
| Cave Trap Door | `cavetrapdoor` |  |  |
| Chain Platforms (Citadel) | `citb-chain-plat` |  |  |
| Citadel Arm | `citb-arm` |  | Rotating arm platform Jak can ride (a = shortest .. |
| Disc Platform (citadel) | `citb-disc` |  |  |
| Drop Platforms (citadel) | `citb-drop-plat` |  | A grid of coloured platforms that rise when it gets a 'trigger (link it from a button or a trigger volume) and drop after a while or when Jak walks away; stepping on one… |
| Eco Platform | `plat-eco` |  |  |
| Eco Platform (Final Boss) | `plat-eco-finalboss` |  | Final boss eco platform: moves along its path when the robot boss (alt-actor slot 12) sends it 'target. |
| Exit Chamber Ride | `exit-chamber` | edited | External trigger/open unlocks the door without starting a ride; its built-in button travels. |
| Exit Platform (Citadel) | `citb-exit-plat` | path |  |
| Fisherman's Boat | `fishermans-boat` | path, edited | Edited (subtypes/fishermans-boat.gc): stand on the boat and press circle: it sails along path (Jak held on deck), docks at its end; ride it back along pathb (none: path… |
| Flip Platform | `plat-flip` |  |  |
| Floating Launcher (citadel) | `citb-launcher` |  | Citadel's floating launcher will follow paths like other floating platforms |
| Floating Launcher (Sunken) | `floating-launcher` | path | Starts at the last path point; when triggered it moves to the first point in 1 s and becomes a launcher there. |
| Floating Platform | `plat` |  |  |
| Floating Platform (Citadel) | `citb-plat` |  |  |
| Grotto Pole | `grottopole` |  |  |
| Klaww Drawbridge | `ogre-bridge` |  |  |
| Klaww Platform Isles | `ogre-isle` |  | Floats at water height (ocean height without a water link), pulled back toward its placed X/Z. |
| Klaww Step | `ogre-step` |  | Hidden 7 m below its placement until active; then rises and floats at water height while Jak is within 150 m. |
| Launcher | `launcher` |  |  |
| Minecarts | `minecartsteel` |  |  |
| Ogre Bridge End | `ogre-bridgeend` |  |  |
| Orbit Platform | `orbit-plat` |  | Link two orbit-plats to each other. |
| Piston | `lurkerm-piston` |  |  |
| Pontoon (Five) | `pontoonfive` |  |  |
| Pontoon (Ten) | `pontoonten` |  |  |
| Precursor Bridge | `precurbridge` |  | Precursor bridge that assembles when Jak comes near with blue eco. |
| Qbert Platforms | `qbert-plat` |  |  |
| Qbert Platforms Master | `qbert-plat-master` |  | Qbert puzzle master: every qbert-plat in its next/prev chain must be lit. |
| Rising Stair Platform (Citadel) | `citb-stair-plat` | edited | Edited: waits hidden below its placed height, then rises on trigger. |
| Rope Bridge | `ropebridge` |  |  |
| Rotate Box (Citadel) | `citb-rotatebox` |  |  |
| Sail (Tall) | `lurkerm-tall-sail` |  |  |
| Side-to-Side Plat | `side-to-side-plat` |  |  |
| Silo Door (Final Boss) | `silodoor` |  | Final boss silo door. |
| Silo Step (Misty) | `silostep` | edited | Edited: trigger raises the step and its linked following steps, without a fixed camera or the Misty Warehouse task. |
| Sliding Tube | `slide-control` | path | Will force jak into his sliding state. |
| Snow Log | `snow-log` |  |  |
| Snow Spatula | `snow-spatula` |  |  |
| Snowy Platform (Flut Flut) | `flutflut-plat` |  | Flut flut platform. |
| Spider Web (Bouncer) | `spiderwebs` |  |  |
| Spinning Donut (Citadel) | `citb-donut` |  |  |
| Square Platform | `square-platform` |  | Starts lowered at its down travel. |
| Square Platform Button | `square-platform-button` |  | Button that starts its square-platform-master (link it in Alt actors). |
| Square Platform Master | `square-platform-master` |  | Raises the square-platforms in its next/prev chain one after another (0.3 s apart) when a square-platform-button linked to it is pressed, then lowers them after the time… |
| Steam Cap | `steam-cap` |  |  |
| Stop Box (Citadel) | `citb-stopbox` |  |  |
| Swing Pole | `swingpole` |  | Invisible pole Jak can swing on (the pole itself is level geometry). |
| Tar Platform | `tar-plat` |  | Floats at its placed height (bobs when ridden). |
| Teeter Totter | `teetertotter` |  |  |
| Wall Platform | `wall-plat` |  |  |
| Wedge Platform | `wedge-plat` |  |  |
| Wedge Platform Master | `wedge-plat-master` |  |  |
| Wedge Platform Outer | `wedge-plat-outer` |  |  |
| Windmill Cog Wheel | `windmill-one` |  |  |

## Interactive Objects

| Actor | etype | Notes | What it is |
|---|---|---|---|
| Balloon | `balloon` |  | Floating balloon mine: pops when attacked and knocks Jak back. |
| Blue Eco Charger | `blue-eco-charger` |  | Opens (orb spins) when Jak comes within 4 m charged with blue eco; closes 20 s later. |
| Breakable Beam Mirror | `reflector-mirror` | edited | Edited: punch or spin to break the mirror and send stop to its linked receivers (e.g. |
| Cave Crystal | `cavecrystal` |  |  |
| Citadel Generator | `citb-generator` |  | Hit it to break it: opens its open actors, gives its task's cell, then triggers its linked actors. |
| Dark Crystal | `dark-crystal` |  | Explodes when hit. |
| Dark Plant | `dark-plant` | edited | Exported as a level subtype (subtypes/dark-plant.gc). |
| Eco Beam Origin | `reflector-origin` | edited | Edited (subtypes/reflector-origin.gc): draws the eco beam to the Beam target empty (none: its blocker, at the blocker's height, the mirror's top) until the blocker is co… |
| Eco Beam Target | `reflector-end` |  | Invisible end point for an eco beam: make it the last periscope's next actor. |
| Eco Harvester | `harvester` |  | Deflated harvester; inflates and pumps once its linked actor is complete (an Eco Vent Rock notifies it when it breaks). |
| Eco Vent (Rock) | `ecoventrock` |  |  |
| Energy Hub | `energyhub` | edited | Edited (subtypes/energyhub.gc): spinning hub (place it on an energybase) with 5 arms holding energy balls; shoot them all with yellow eco to stop it. |
| Flut Flut | `flutflut` |  | Rideable Flut Flut: press circle next to it. |
| Flut Flut Egg | `flutflutegg` | edited | Edited (subtypes/flutflutegg.gc): punch / spin it toward its Hatch position empty (none: the way it faces); after Push distance it falls, its task's need-reminder closes… |
| Gondola | `gondola` | edited | Edited (subtypes/gondola.gc): stand in it and press circle to ride its cutscene up / down (Jak ends where the vanilla cutscene ends: the top station sits where it does i… |
| Happy Plant | `happy-plant` | edited | Exported as a level subtype (subtypes/happy-plant.gc): opens with its cutscene and gives its task's cell once every dark plant linked to it is gone. |
| Helix Floor Button | `helix-button` | edited | Edited (subtypes/helix-button.gc): standing on it depresses the button, closes the linked door and starts the linked rising eco (or the water that has it as Started by). |
| Helix Slide Door | `helix-slide-door` | edited | Edited: starts open and closes on trigger (from a Helix Button or trigger volume). |
| Lightning Mole | `lightning-mole` | nav-mesh, path, edited | Exported as a level subtype (subtypes/lightning-mole.gc): its hole is at the linked peeper; 'Appears' sets when it shows up. |
| Misty Cannon | `mistycannon` |  | Lurker cannon. |
| Muse | `muse` | nav-mesh, path, edited | Exported as a level subtype (subtypes/muse.gc): runs along its path loop; catching it plays the vanilla catch cutscene (at movie-pos if set), then gives its task's cell. |
| Peeper | `peeper` |  | Peeks out of the lightning mole's hole; link it as the moles' peeper. |
| Pelican | `pelican` | path, edited | Edited (subtypes/pelican.gc): circles on path holding the cell; when Jak comes within 20 m of the cell, the dive camera shows it diving (dive path) and grabbing the cell… |
| Periscope (eco beam) | `periscope` | edited | Edited (subtypes/periscope.gc): rises when the previous beam piece activates it; once powered Jak grabs the grips and aims at the next piece (or the Beam end empty). |
| Precursor Tether Arm | `precursor-arm` | edited | Edited: the swamp blimp tether arm, positioned at its base/waterline. |
| Race Ring | `race-ring` | edited | Chain of timed rings: jump through the first to start; each ring must be reached before its time or the chain resets. |
| Race Start (custom course) | `gorge-start` | edited | Edited: vanilla timer/record HUD with placed start position/facing and a linked finish empty. |
| Rising Helix Dark Eco | `helix-water` | edited | Edited (subtypes/helix-water.gc): rises from the placed height by Rise distance after a trigger, a press of its Started by button or one linking it. |
| Seagull Avalanche Rock | `lrocklrg` | edited | Edited (subtypes/lrocklrg.gc): the seagull flock rock. |
| Shortcut Boulder | `shortcut-boulder` |  | Breaks only with a yellow eco shot. |
| Swamp Rock | `swamp-rock` |  | Breaks with a yellow eco shot. |
| Swamp Rope | `swamp-rope` |  | Static model when placed: the real ropes are spawned by the swamp blimp, one per link. |
| Swamp Tether Rock | `swamp-tetherrock` | edited | Edited (subtypes/swamp-tetherrock.gc): shoot it with yellow eco; it gives its task's cell and lets go of the blimp. |
| Test Actor | `test-actor` |  |  |
| Training Dummy | `scarecrow-a` |  | Punching dummy: hit it and it wobbles, then breaks apart. |
| Trigger Relay (Citadel) | `citadelcam` | edited | Edited invisible relay: receives trigger and forwards it to every linked receiver after birthing it. |
| Zoomer | `racer` |  | Rideable zoomer: press circle next to it. |

## Obstacles

| Actor | etype | Notes | What it is |
|---|---|---|---|
| Cave Crusher (robocave) | `cavecrusher` |  |  |
| Cave Flame Pots | `caveflamepots` | path |  |
| Chain Mine (lavatube) | `chainmine` |  | The origin is the top of the chain; the mine hangs about 18 m below it. |
| Dark Eco Barrel | `darkecobarrel` | path |  |
| Dark Eco Crate Cluster | `crate-darkeco-cluster` |  |  |
| Fire Boulder | `fireboulder` | edited | Exported as a level subtype that also gives every boulder its hover sound (vanilla only creates it for the actor named fireboulder-6, and a hovering boulder without it c… |
| Fire Hose (citadel) | `citb-firehose` |  | Activates when Jak is within 70 m. |
| Keg Conveyor (misty) | `keg-conveyor` | path | Kegs drop onto path point 2, roll to the last point over 16 s, fly off and break. |
| Log Trap (jungle) | `logtrap` |  |  |
| Pusher (rolling) | `pusher` |  |  |
| Shover | `shover` | path | Damages Jak and pushes him toward the nearest path point. |
| Snow Ball (Snowy) | `snow-ball` | path, edited | Edited (subtypes/snow-ball.gc): rolling snow balls spawned every 1.5 - 5.5 s on path, or at random on path / pathb (never three times the same in a row). |
| Snow Pusher (snowy) | `snowpusher` |  |  |
| Spike | `spike` |  | Rises when Jak on the zoomer comes within 55 m (once). |
| Swamp Spike (Swamp) | `swamp-spike` |  |  |
| TNT Barrel (ogre) | `tntbarrel` |  |  |
| Whirlpool | `whirlpool` |  |  |

## Buttons and Doors

| Actor | etype | Notes | What it is |
|---|---|---|---|
| Citadel Button | `citb-button` |  | Flop button like the wall button, but it pops back up after 1 s (hard-coded). |
| Eco Top (snow) | `snow-eggtop` |  | Holds its task's cell; once collected it plays the eggtop camera and completes ('ecovent-278' cue is vanilla). |
| Egg Top Button (Jungleb) | `eggtop` |  | Spawns its task's power cell; once collected it closes. |
| Energy Door (lavatube) | `energydoor` | edited | Edited (subtypes/energydoor.gc): open while Jak comes from its -X side; once he's 15 m past it (+X) it closes behind him until it's solved, then opens. |
| Final Door (100-cell) | `final-door` |  | One half of the 100 power cell door (solid collision mesh). |
| Flut Flut Button | `snow-button` |  | Pressed by Flut Flut only. |
| Gorge Pusher (rolling) | `gorge-pusher` | edited | Edited (subtypes/gorge-pusher.gc): a pusher that moves from max-frame to min-frame once its task's need-introduction stage is closed (the actor's task; none = vanilla ro… |
| Iris Door | `jng-iris-door` |  | Iris door (eco door). |
| Iris Door (Sunken) | `sun-iris-door` |  |  |
| Launcher Door | `launcherdoor` |  |  |
| Main Door (Jungle) | `maindoor` |  |  |
| Pipe Game (sunken) | `sunken-pipegame` | path, edited | Edited (subtypes/sunken-pipegame.gc): 3 buttons (-7.5 / 0 / +7.5 m X, +1.25 m Z from the actor); each carries its prize along its own path (path / pathb / pathc) in its… |
| Round Door (Misty) | `rounddoor` |  | Eco door (misty warehouse). |
| Side Door (Jungle) | `sidedoor` |  | Eco door. |
| Snow Bumper | `snow-bumper` | edited | Edited (subtypes/snow-bumper.gc): knock all the linked bumpers down (next / prev actor chain); the last one gives the task's cell. |
| Snow Fort Gate | `snow-fort-gate` | edited | Edited (subtypes/snow-fort-gate.gc): opens when it gets 'notice (link the snow switch to it). |
| Snow Fort Switch | `snow-switch` | edited | Edited (subtypes/snow-switch.gc): holds its task's cell; taking it presses the switch, which sends 'notice to its linked actors (the fort gate). |
| Snow Log Button | `snow-log-button` |  |  |
| Swamp Spike Gate | `swampgate` |  | Lowers for good when it gets 'trigger (e.g. |
| Wall Button | `basebutton` |  | Flop (ground-pound) button. |
| Warp Gate (position marker) | `warpgate` |  | Marks itself dead when placed (the vanilla ring is level geometry). |
| Warp Gate Switch | `warp-gate-switch` | edited | Exported as a level subtype (subtypes/warp-gate-switch.gc) so its gate offers the warp menu in a custom level; destinations are the vanilla hubs. |

## Visuals

| Actor | etype | Notes | What it is |
|---|---|---|---|
| Accordion Machine | `accordian` |  | Jungle bellows machine looping its pumping animation (only while drawn). |
| Blade Assembly | `bladeassm` |  | Beach wind-blade wheel turning 20 deg/s around its local Z axis. |
| Boat Paddle Wheel | `boatpaddle` |  | Misty boat paddle wheel turning 30 deg/s around its local X axis, with splash particles. |
| Cave Gem | `cavegem` |  |  |
| Ceiling Flag | `ceilingflag` |  | Hanging banner from the Rock Village; the origin is at the top. |
| Citadel Arm Shoulder | `citb-arm-shoulder` |  | Rotating shoulder piece of the citadel arms (no collision). |
| Citadel Coil | `citb-coil` |  | Glowing generator coil. |
| Citadel Lurker Hose | `citb-hose` |  | Hanging hose that spits out lurkers. |
| Eco Claw | `ecoclaw` |  | Final boss eco claw (static). |
| Energy Hub Base | `energybase` |  | Spinning column under the Lava Tube energy hub. |
| Evil Plant | `evilplant` |  | Dark eco plant from the Sage's hut. |
| Gondola Pistons | `pistons` | edited | Edited (subtypes/pistons.gc): gondola machinery pistons. |
| Hut Lamp | `hutlamp` |  | Hanging lamp that swings gently (about 10 degrees, 3 s cycle, random start). |
| Klaww (Village 2 Backdrop) | `villageb-ogreboss` | edited | Edited (subtypes/villageb-ogreboss.gc): Klaww on the cliff, idling and throwing boulders that follow the vanilla throw animations from his spot (they splash about where… |
| Lava Base | `lavabase` |  | Animated lava pool base (22 m bounds). |
| Lava Fall | `lavafall` |  | Animated lava fall. |
| Lava Shortcut | `lavashortcut` |  | Animated lava from the Lava Tube shortcut. |
| Mayor's Gears | `mayorgears` | edited | The mayor's machine gears. |
| Mayor's Windmill Sail | `windmill-sail` | edited | Edited (subtypes/windmill-sail.gc): sail turning around its local X axis, slow (Slow turn, vanilla 300 s) or fast (Fast turn, vanilla 16 s, with wind particles and the F… |
| Misty Wheel | `wheel` |  | Has no game code: the engine's viewer fallback draws wheel-ag and loops its animation (as in vanilla Misty). |
| Pontoon Cutscene Helper | `allpontoons` |  | Vanilla helper, intentionally invisible while idle. |
| Rev Cycle (Zoomer prop) | `revcycle` |  | Sage's hut pedal machine: the cycle body or its separate propeller. |
| Robot Boss (Citadel, shielded) | `citb-robotboss` |  | The giant robot in the Citadel centre, behind its shield; head, guns, arms etc. |
| Sage's Hut Sail | `sagesail` |  | Large windmill sail from the Sage's hut. |
| Seaweed | `seaweed` |  | Swaying seaweed with a random start frame and speed. |
| Starfish Spawner | `villa-starfish` | path | Invisible spawner: while Jak is within 50 m it keeps up to N small starfish (one more every 0.5 s) at random points of its path. |
| Sunken Fish School | `sunkenfisha` | path | School of fish (each a random one of 3 colours) swimming back and forth along a path and wandering around it. |
| Swamp Blimp | `swamp-blimp` |  | Lurker blimp roped to its linked actors; rises a little per broken rope. |
| Wind Turbine | `windturbine` |  | Small Misty turbine spinning around its local Y axis at a wind-driven speed. |
| Yellow Tarp | `lavayellowtarp` |  | Small flapping yellow tarp (5 m bounds). |

## NPCs

| Actor | etype | Notes | What it is |
|---|---|---|---|
| Billy (rat game) | `billy` | path, edited | Edited (subtypes/billy.gc): Billy and his pet Farthy, with the actor's own task (Game Task panel; none = vanilla swamp-billy), any stage layout. |
| Bird Lady (Beach, Flut Flut hatch) | `bird-lady-beach` | edited | Edited (subtypes/bird-lady-beach.gc): link the Flut Flut egg (alt-actor): she appears once it has fallen and broken and her task isn't done; talking plays the hatching c… |
| Bird Lady (Village) | `bird-lady` | edited | Edited (subtypes/bird-lady.gc): the actor's own task (Game Task panel; none = vanilla beach-flutflut). |
| Caged Sage (Citadel) | `red-sagecage` |  | Edited (subtypes/<colour>-sagecage.gc): red / blue / yellow sage in his energy cage (Jak can stand on the cage). |
| Farmer | `farmer` | edited | Edited (subtypes/farmer.gc): introduction / reminders, then the resolution and his task's cell once the yakow herd (same task) is penned. |
| Final Boss Sage (ending cutscenes) | `sage-finalboss` | edited | Exported as a level subtype (subtypes/sage-finalboss.gc): the final boss ending cutscenes with the actor's own task (Game Task panel; none = vanilla finalboss-movies; a… |
| Fisherman | `fisher` | path, edited | Edited (subtypes/fisher.gc): the fishing minigame with the actor's own task (Game Task panel; none = vanilla jungle-fishgame). |
| Flut Flut (Blue Hut) | `flutflut-bluehut` |  | Idle Flut Flut; never talks. |
| Gambler | `gambler` | edited | Exported as a level subtype (subtypes/gambler.gc): its vanilla cutscenes play without the level commands that unloaded the custom level. |
| Geologist | `geologist` | edited | Exported as a level subtype (subtypes/geologist.gc): its vanilla cutscenes play without the level commands that unloaded the custom level. |
| Green Sage (Citadel, caged) | `green-sagecage` | edited | Edited (subtypes/green-sagecage.gc): the Green Sage in his cage, freed like the red / blue / yellow sages: by talking to him (once; gives his task's cell) or by breaking… |
| Keira (Blue Hut) | `assistant-bluehut` |  | Vanilla village2-levitator / sunken-room / rolling-robbers / swamp-flutflut speeches. |
| Keira (Citadel entrance) | `assistant-lavatube-end` | edited | Edited (subtypes/assistant-lavatube-end.gc): the actor's own task (Game Task panel; none = vanilla village4-button). |
| Keira (Fire Canyon) | `assistant-firecanyon` | edited | Edited (subtypes/assistant-firecanyon.gc): a cell-gate NPC with the actor's own task (Game Task panel; none = vanilla firecanyon-assistant). |
| Keira (Lava Tube start) | `assistant-lavatube-start` |  | Keira at the heat shield. |
| Keira (Levitator) | `assistant-levitator` |  | Shown only while village2-levitator is at its reward speech (Jak has the cells): plays the levitator cutscene, lifts the linked boulder and gives the cell. |
| Keira (Sage's Hut) | `assistant` | edited | Exported as a level subtype (subtypes/assistant.gc): its vanilla cutscenes play without the level commands that unloaded the custom level. |
| Keira (Volcanic Crater) | `assistant-villagec` | edited | Edited (subtypes/assistant-villagec.gc): a talker with the actor's own task (Game Task panel; none = vanilla assistant-village3). |
| Mayor | `mayor` |  | Talking plays the vanilla mayor speeches: jungle-lurkerm (power beams) and village1-mayor-money (90 orb donation, gives its cell). |
| Miner (Short) | `minershort` | edited | Exported as a level subtype (subtypes/minershort.gc): its vanilla cutscenes play without the level commands that unloaded the custom level. |
| Miner (Tall) | `minertall` |  | Never talks; the short miner's partner (joins his cutscenes). |
| Oracle | `oracle` | edited | Edited (subtypes/oracle.gc): two power cells in its eyes, each traded for Price orbs: right eye = its game task, left eye = its Left eye task (custom tasks work: no stag… |
| Sage (Volcanic Crater) | `sage-villagec` | edited | Edited (subtypes/sage-villagec.gc): a talker with the actor's own task (Game Task panel; none = vanilla cave-dark-crystals). |
| Samos (Blue Sage's Hut) | `sage-bluehut` |  | Vanilla rolling-plants and swamp-arm speeches (Keira joins in). |
| Samos (Sage's Hut) | `sage` | edited | Exported as a level subtype (subtypes/sage.gc): its vanilla cutscenes play without the level commands that unloaded the custom level. |
| Sculptor | `sculptor` |  | Vanilla misty-muse: introduction and reminder, then the reward speech (with the muse) once misty-muse reaches its reward speech, giving the misty-muse cell. |
| Seagull Flock | `seagullflock` | path, edited | Edited (subtypes/seagullflock.gc): 21 seagulls at path point 0; walking up scares them on to points 1, 2, 3 (with Daxter's seagull hints), then to the end and, once the… |
| Uncle (Explorer) | `explorer` | edited | Exported as a level subtype (subtypes/explorer.gc): talks from anywhere near (vanilla: only from a fixed Sandover area). |
| Warrior | `warrior` | edited | Edited (subtypes/warrior.gc): an orb trade with the actor's own task (Game Task panel; none = vanilla village2-warrior-money): introduction, reminder, then he takes 90 o… |
| Yakow | `yakow` | edited | Wanders and runs off when kicked. |

## Pickups

| Actor | etype | Notes | What it is |
|---|---|---|---|
| Crate | `crate` |  |  |
| Eco (Blue) | `eco-blue` |  |  |
| Eco (Green) | `health` |  |  |
| Eco (Red) | `eco-red` |  |  |
| Eco (Yellow) | `eco-yellow` |  |  |
| Eco Pill (Health) | `eco-pill` |  |  |
| Eco Vent (Blue) | `ventblue` |  |  |
| Eco Vent (Green) | `ecovent` |  |  |
| Eco Vent (Red) | `ventred` |  |  |
| Eco Vent (Yellow) | `ventyellow` |  |  |
| Orb (Precursor) | `money` |  |  |
| Orb Cache | `orb-cache-top` |  |  |
| Pickup Spawner | `pickup-spawner` |  |  |
| Power Cell | `fuel-cell` |  |  |

## Effects

| Actor | etype | Notes | What it is |
|---|---|---|---|
| Actor Light | `actor-light` | add-on actor | Addon actor (exports as lt-actor-light, in a shared file): adds light to Jak and its Lit actors near it, or takes it away with negative intensities. |
| Particle Spawner | `part-spawner` |  | Spawns a vanilla particle group (waterfalls, steam, torches, bubbles, moths ...) at its position, optionally with a sound. |

---
[← Previous](glossary.md) · [Guide index](README.md)
