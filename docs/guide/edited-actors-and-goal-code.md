# Edited actors & GOAL code

Many of the game's actors were written for one spot in the original game. They have a hard-coded task, position, camera or level name, so in a custom level they do nothing, or crash. The add-on fixes many of them with **edited actors**: small GOAL files that change the vanilla actor so it reads its settings from the level instead. You can also add **your own GOAL code**, either as files in a **Custom code folder** or as text blocks inside the .blend.

You don't need to write any code to use edited actors. They are on by default.

## Edited actors

An actor marked **edited** in the [Actor list](actor-list.md) (Keira, the sages, the oracle, the gondola, the race ring, Klaww, ...) has an edited GOAL file in the add-on, and its database record names that file. When you build, the file is added to your level and the actor uses it. The Actor Settings panels show the extra fields the edited version reads (tasks, positions, cameras ...).

There are two kinds of edited file:

- **Child type**: a new GOAL type based on the vanilla one (`(deftype __TYPE__ (gondola) ())`). The actor is exported as this new type.
- **Patch**: no new type. The actor keeps its own etype and the file changes how that type behaves.

### Picking the code: GOAL Code › Code

Select the actor and open **OpenGOAL › Object Settings › GOAL Code** (⑥ in the [Actor screenshot](images/actor.png)). The top row, **Code**, shows which file the actor uses. Click it to pick another:

| Choice | What it means |
|---|---|
| **Default (<file>.gc)** | The database's choice for this actor (the add-on's edited file). For actors without one, **Default (vanilla)**. |
| **Vanilla** | No edited code: the game's own type, as in the original game. Not offered for the add-on's own actors (such as Actor Light), which have no vanilla type. |
| **<file>.gc** | A file from your [Custom code folder](#the-custom-code-folder) that is made for this actor. |

The pick applies to the active actor and to every other selected actor of the same type. Some variants have their own edited file (for example the red, blue and yellow caged sages). The default follows the variant.

### Level (-obs) or Shared file

Under the picker, two buttons choose where the file's code goes:

| Button | Where | Type name |
|---|---|---|
| **Level (-obs)** | Inside the level's own `<level>-obs.gc`. Each level gets its own copy. | `<level>-<file>`, for example `mylevel-gondola` |
| **Shared file** | Its own file, `goal_src/levels/level-tools/edited/lt-<file>.gc`. It is compiled once (registered in `game.gp`) and listed in the `.gd` of every level that uses it, so levels share it. | `lt-<file>`, for example `lt-gondola` |

A grey line under the buttons says what the actor will export as, for example "Exports as lt-gondola (levels/level-tools/edited/lt-gondola.gc)". For a patch it says "A patch: the actor keeps its etype (...)". For a file from your Custom code folder, it also shows the file's path.

The choice is saved in the .blend **per file**, so it applies to every actor that uses that file. Without a choice, the file's `;; place:` header decides (see below), and otherwise **Level (-obs)**. The add-on's own actors (such as Actor Light) are always shared, so they have no buttons.

The first build after changing edited code can be a full compile.

## The Custom code folder

Put your own edited-actor `.gc` files in a folder and tell the add-on where it is:

- for every project: **Edit › Preferences › Add-ons › OpenGOAL Level Tools › Custom code folder**,
- for one .blend only: **OpenGOAL › Developer Tools › Paths › Project Folders (this .blend)**. Turn on **Use this .blend's folders** and set **Custom code folder**. Leave it blank to use the preference.

Every `.gc` file in that folder is offered in **GOAL Code › Code** for the actors it is made for. The add-on notices new and changed files on its own.

### File headers

A few special lines near the top of the file tell the add-on what to do with it:

| Line | What it does |
|---|---|
| `;; edits: <etype> <etype> ...` | The actors this file is for. You can use more than one line. Without it, the file is offered for **every** actor. |
| `;; place: shared` (or `obs`) | The default for **Level (-obs)** / **Shared file**. Without it: obs. |
| `(deftype __TYPE__ (<parent>) ...)` | Makes the file a **child type**. Write `__TYPE__` everywhere you mean the new type's name. The add-on replaces it with `<level>-<file>` or `lt-<file>`. Without a `(deftype __TYPE__` the file is a **patch**. |

A tiny example, saved as `my-plat.gc` in the Custom code folder:

```lisp
;; A floating platform with my own changes.
;; edits: plat
;; place: shared
(deftype __TYPE__ (plat) ())

;; your own methods and states for __TYPE__ go here
```

Pick **my-plat.gc** in a floating platform's GOAL Code panel and it exports as `lt-my-plat`. It keeps all of the platform's panels, art and settings.

The add-on's own edited files (in its `subtypes` folder) are good examples to copy from. Each one starts with comments saying what it changes and which settings it reads.

## GOAL code blocks

Any actor can also carry a **GOAL code block**: a Blender text block whose code is added to the level's `-obs.gc` when you export, after the add-on's own code. This is for quick experiments and [your own types](#your-own-types).

In **Object Settings › GOAL Code**, under the Code picker:

| Button / field | What it does |
|---|---|
| **Create boilerplate block** | Makes a new text block named `<etype>-goal-code` with a starter `deftype`, an idle state and `init-from-entity!`, and assigns it to the actor. |
| Text block field | Assigns an existing text block instead. |
| Checkbox (left of the block name) | Turns the block on or off. Off: "disabled (won't export)". |
| X | Disconnects the block from the actor (the text block itself stays in the .blend). |
| **New block (replace)** | Makes a fresh boilerplate block and assigns it instead. |
| **Open in Editor** | Shows the block in an open Text Editor area. If none is open, the message bar tells you to open one (Shift+F11) and click again. |

A dot in the panel header shows that the actor has an active block. Several actors can share one block. The panel lists the others ("Shared with N other actor(s)"), and the block is written only once.

Compile errors in your code show up in the goalc build log, not in Blender ([Build & Play](build-and-play.md)).

## Your own types

To place an actor of a type the add-on doesn't know:

1. **Spawn Objects › Custom Types › Custom type**.
2. Type the **Deftype name**: lowercase letters, digits and hyphens, for example `spin-prop`. It can't be a name the add-on already has.
3. Click **Spawn**. You get a small yellow-green empty `ACTOR_spin-prop_0`.
4. In **GOAL Code**, click **Create boilerplate block** and write your `(deftype spin-prop ...)` in it. The name must match exactly.

Unknown types (yours, and actors of other types brought in with [Importing](importing.md)) get their panels from the database's `custom-actor` parent: **Path**, **NavMesh** and **Volume**. Anything else they need goes in [Custom Lumps](actors.md#custom-lumps).

## Export As

Often it's easier to start from a vanilla actor than from nothing. Spawn the vanilla actor (for example a Floating Platform), write a child type of it in a GOAL code block, such as `(deftype my-plat (plat) ())`, and type `my-plat` in **Object Settings › Custom Lumps › Export as**. The actor is exported as `my-plat`. Its panels, lumps, art group, code and textures stay the platform's, so your type has everything it needs to load. See [Actors](actors.md#export-as).

An edited file from the Custom code folder does the same thing without the extra step: the add-on sets the type name for you.

---
[← Previous](tasks.md) · [Guide index](README.md) · [Next →](importing.md)
