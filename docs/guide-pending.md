# Guide changes waiting for the next release

The user guide on `main` (`docs/guide/`, the README) always describes the **last release**, because the add-on's
**?** buttons and the release's PDF point at it. Features merged into `main` since then get their guide text on the
branch **`claude/guide-next`**, which is merged into `main` just before the release is made.

When a feature branch is merged: add its guide edits to `claude/guide-next` (screenshots retaken there too) and list
them below. When the release is made: merge `claude/guide-next`, check this list, then empty it.

## Since 2026.11.20

| Feature | Guide pages | Screenshots | On guide-next |
|---|---|---|---|
| UV Tools (Object Controls › UV Tools: Fit Faces on UV, Cube Project, Randomize UV) | object-controls (new section), geometry (Textures link), README index, project README | object-controls (④ UV Tools) | yes |
| Model import: models ripped in several levels listed once | importing | — | yes |
| Camera anchor / pivot / look-at → Cameras, launcher destinations → Waypoints | interface, cameras, paths-and-platforms | — | yes |
| Bin button on linked helpers + preference **Ask before deleting linked helpers** | paths-and-platforms, actors, enemies-and-navmesh, install | — | yes |
| Developer Tools › Warning Settings | developer-tools (new section), interface, troubleshooting | — | yes |
| Addon Settings › Import Settings from .blend | developer-tools (new section), interface | — | yes |
| **?** guide buttons in panel headers | interface | every sidebar screenshot (shows the ?) | yes |
