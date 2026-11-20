# Actor Light (branch claude/actor-light) — plan, waiting for Kuitar

## How Jak 1 lights actors (test-v0.3.8 goal_src/jak1)
- A light-group = dir0 / dir1 / dir2 (directional: direction, color, levels.x = intensity) + ambi
  (lights-h.gc:69). Every level mood-context has 8 light-groups (mood-h.gc:60); slot 0 is the
  level's main light, slots 1-7 are extra kits the mood function fills (village1 uses all 7).
- Once per frame, in the draw loop (drawable.gc:839), update-time-of-day (time-of-day.gc:188):
  1. sets Jak's (and Daxter's) draw light-index to 0 and target-interp to 0.0;
  2. runs each loaded level's mood-func (mood-context, time, level index 0 / 1);
  3. blends the two levels' moods into *time-of-day-context* (light-group x8, current-shadow);
  4. if Jak's light-index isn't 0: light-group[index] = lerp(light-group[0], light-group[index],
     target-interp), and current-shadow moves toward -dir0 of that group (y clamped to <= -0.9063)
     by target-interp (time-of-day.gc:403-437).
  Vanilla light zones (village1 houses, village2 huts ...) are mood-function code:
  set-target-light-index N + target-interp from the distance to a hard-coded point (mood.gc:774-823).
- Drawing (drawable.gc:475-527): Jak uses tod light-group[Jak's light-index]; any other actor uses
  its level's mood light-group[draw light-index] (no blend; light-index comes from the 'light-index
  lump, process-drawable.gc:373; 255 = keep).
- Shadows: per actor shadow-ctrl settings shadow-dir. Jak copies tod current-shadow every frame
  (powerups.gc:491); other actors via shadow-control update-direction-from-time-of-day, if they call it.

## Proposed implementation
- Game code: one file (lt-actor-light / actor-light.gc), compiled once through game.gp and listed in
  the .gd of the levels that use it (the export/edited.py "lt-" custom-type route), not per-level obs.
- Hook without editing engine / mood files: the actor wraps its level's mood-func at runtime (the
  original runs first, then the active actor lights of that level write their light-group slot); put
  back when the last actor light of the level goes away. Alternative: a 1-line hook in
  update-time-of-day (engine patch, like project settings).
- Jak: the light's slot = lerp(mood slot 0, actor light group, strength); set-target-light-index slot,
  target-interp 1.0 (strength already in the slot); Control Shadow: blend current-shadow toward the
  light direction by strength x Control Shadow (in the wrapper, after the blend).
- Strength: 1 inside Min Distance, 0 beyond Max, linear between (sphere / cylinder, from the centre
  or the closest point of the path); 0 outside the volume if one is set; x the on / off fade (timers),
  mode (default on / off, time of day on / off hours, wrapping past midnight), trigger-actor
  (death / 'on 'off 'trigger events like basebutton).
- Direction: From Center (actor - light, per actor), Actor Rotation (the empty's quat: its +Z / -Z).
- alt-actors: each gets a slot (draw light-index) -> slots 1-7 are shared by every actor light of the
  level: at most 7 lit things per level (incl. Jak).

## Kuitar's answers (2026-11-20)
- Add to the current light; a way to remove light (darken) too.
- Several lights blend.
- No light groups (limit, and they could mess up the time of day lighting): change the lights of
  actors / Jak directly. (TFL's examples predate time of day; not needed.)
- New: camera distance (vis-dist, default 100 m): farther from the camera the light does nothing.

## Tested (test-v0.3.8, 2026-11-20, 1ce1855)
_claude_tmp/bl_actorlight.py (export: lumps, shared file, game.gp, .gd, patch once) + al_compile.sh +
tasks/al_ingame.py with al_q.txt / al_q3.txt (REPL): hook set, Jak strength 1 at 5 m (cylinder), key light
into the free dir2 slot, ambient +0.5, crate (alt-actor) lit, Jak shadow turned half-way away from the
light, 'on / 'trigger / timers, negative intensities halve levels, time of day 18-8 off at 12 / on at 20,
game running with the light on. (A babak without a nav-mesh crashed the first test level: not the light.)
Kuitar's changes: Lit actors = one "allow-multiple" alt-actor link (16 max, in the label); Color mode
(color-mode lump, flag 16 in game): Add / Switch (the actor's own lights x (1 - summed switch strength),
then the lights added). In game (al_q4.txt): full-strength Switch = only the key (colour x 2) + ambient
0.5, the other lights 0; both crates lit.
Not checked: how it looks (no screenshots), path / volume, trigger-actor death, Actor Rotation.

## Built
- subtypes/actor-light.gc (";; edits: actor-light", ";; place: shared"): type lt-actor-light, registry of
  handles (define-perm, 32 max), *actor-light-hook* set every frame by each light (a level unloading
  clears it on deactivate), hook = strength per light (min / max / cylinder / path closest point /
  vol), key lights blended into one directional (unused slot, else merged with the weakest), ambient
  added, negatives darken, shadow-dir from tod current-shadow; modes / timers / hours / events /
  trigger-actor death; camera distance (vis-dist lump, 100 m) from the light / closest path point.
- build.py _apply_actor_light_patch: drawable.gc define + call (tag ";; og-level-tools actor-light"),
  when a level with an Actor Light is built; left in afterwards (hook #f = one check per draw).
- DB "actor-light" (Visuals, "custom_actor": true, "edited", "show_axis"): fields, visibility (Camera
  distance 100), path, volume, alt-actor x8 + trigger-actor. edited.py: custom_actor = no Vanilla
  choice, always shared.
- Assumed (Kuitar didn't answer): Actor Rotation = light from the empty's +Z side (blue arrow).

## Revised plan (direct, no light groups)
- No way to set one actor's directional light from process code alone: the draw code
  (drawable.gc ~475-541) builds each actor's lights from the mood every frame. Per-actor
  color-mult / color-emissive (multiply all / add to ambient) exist, but game effects already
  write them (darkcave crystals, eco, ogreboss ...), and they have no direction.
- So: a small engine hook in drawable.gc, after the light group is picked and before it's turned into
  the VU lights: if any actor light is active, the hook gets (draw-control, a stack copy of the light
  group) and adds the actor lights to it. The mood / time of day light groups are never written.
  Shadow: the hook sets the draw's shadow-ctrl shadow-dir = lerp(tod current-shadow, light dir,
  strength x Control Shadow) (from current-shadow each frame: no drift).
- Adding light with 3 directional slots: the blended actor key light (direction = intensity-weighted
  sum, colour weighted) goes in a slot with level 0 if there is one, otherwise merged into the weakest;
  ambient colour x intensity added. Negative intensities darken (directional lights / ambient scaled
  down by it), so no separate mode.
- Active list: actor lights register only while the camera is within vis-dist (and they're on / fading);
  the hook loops that short list; affected = Jak / Daxter (Affect Jak) or one of the light's alt-actors
  (process compare).
