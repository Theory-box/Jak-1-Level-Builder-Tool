# Guide changes waiting for the next release

The user guide on `main` (`docs/guide/`, the README) always describes the **last release**, because the add-on's
**?** buttons and the release's PDF point at it. Features merged into `main` since then get their guide text on the
branch **`claude/guide-next`**, which is merged into `main` just before the release is made.

When a feature branch is merged: add its guide edits to `claude/guide-next` (screenshots retaken there too) and list
them below. When the release is made: merge `claude/guide-next`, check this list, then empty it.

## Since 2026.11.22

| Feature | Guide pages | Screenshots | On guide-next |
|---|---|---|---|
| Death plane: any height | levels (Settings table) | — | yes |
| Reverse Path button | paths-and-platforms (path list table) | — | yes |
| Load boundary Continue: checkpoint list | level-flow (load boundary commands) | — | yes |
| Race-ring circles / platform ghosts drawn (not objects), camera FOV driver fix, undo safety | — (look the same) | — | — |
| Camera animation actor + the game's camera animation list + camera choices on 15 edited actors and the battle controller | cameras (Pov-cameras rewritten: list / picker, Camera animation actor, Camera choices on actors), actors (Cameras tile), actor-list | — (a Camera animation screenshot could be added) | yes |
| Custom moods and mood functions (Moods panel): timeline, fog / lights / sun tables, Match level lighting + curve, effects (flicker, pulse, lightning, lava, caustics, Triggered slot, fog by pitch, fog breathing), Active hours, Lock time / Time speed on the game clock, function templates; Light switch actor; Cave Crystal edited (slot, glow, darken far actors, Actor Lights); Actor Light Follow effect; Fog override replaced (Edit / Make a Custom Mood, Convert) | moods (new), README, levels (Visuals), lighting (mood, Time of day: slot labels, Apply effects after bake, Ignore curve; Effects After Bake: Overwrite time of day; Actor Light: Follow effect), interface (Moods panel), glossary, troubleshooting (new warnings), actor-list | the sidebar screenshot (new Moods panel), level settings and Light Baking screenshots, a Moods screenshot could be added | yes |
