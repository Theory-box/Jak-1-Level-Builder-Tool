# Tasks

A *task* is one entry of the game's progress menu: usually a power cell, or a level's scout flies. Jak 1 has 116 vanilla tasks (numbers 0–115). The **Tasks** tab (⑦ in the [sidebar screenshot](images/sidebar.png)) adds your own, with their own menu names, so your power cells and scout flies have something to count towards.

You don't need custom tasks to place power cells: any cell can use a vanilla task (see [Using a task on actors](#using-a-task-on-actors)). Custom tasks are for when you want your own entries in the menu.

## Requirements

Custom tasks need **mod-base** (the OpenGOAL modding fork): its task code is sized by `(game-task max)`, so the list can grow. The Tasks tab says so under the checkbox when your install can't use them, and the build stops with **custom tasks need mod-base (Tasks panel)**. Your OpenGOAL kind is shown in **Developer Tools › Addon Settings › Versions** ([Developer Tools](developer-tools.md)).

## Add a task

1. Open **Tasks** and tick **Custom tasks**.
2. Pick the level in **Show** (or leave **All tasks**), then click **Add Task**. It gets the next free ID (116, 117 ...), the active level and a name like `<level>-task1`.
3. Rename it, and fill in its texts (below).
4. Give it to an actor: select a power cell (or an NPC, crate, enemy that gives a cell), open its **Game Task** panel and pick your task (custom tasks are listed as `name  (custom 116)`).
5. **Export & Compile**. The first build after adding tasks takes longer (see [What gets written](#what-gets-written)).

Each task is a box in the **Task list**; click the arrow to fold it, **X** removes it. A red **N⚠** on a task means it has problems, listed under its header.

### Task options

| Option | What it does |
|---|---|
| **Name** | The game-task name (lowercase, a–z 0–9 -). Also listed in the actors' task pickers |
| **ID** | The game-task number. Custom tasks start at 116; the limit is 254 |
| **Level** | The level whose progress menu page shows it |
| **Scout fly task** | This is the level's scout-fly task: its 7 flies give its cell and it fills the menu's fly slot. One per level |
| **Introduced** / **Reminder** / **Resolution** | The menu name at each point of the task (see [Texts](#texts)) |
| **When complete** | Which of the three texts the menu shows once the task is done: **Introduced text**, **Reminder text** or **Resolution text** (default) |
| **Stages (N)** | The task's stages (see [Stages](#stages)) |

The progress menu shows 8 tasks per level; more get a warning.

### Texts

Each text field has a search button (use an existing game text) and a **?** button that explains the rules:

- Texts are shown in capitals in game (done on export). Accents and `'` work; curly quotes become plain ones. Button icons: `<PAD_X>`, `<PAD_CIRCLE>`, `<PAD_SQUARE>`, `<PAD_TRIANGLE>`. Characters the game font may not have get a warning under the field (**May not show in game: ...**).
- An empty field uses the next filled one; if none is filled, the task's name.
- References to existing texts:

| You type | You get |
|---|---|
| `[level_name]` | The level's **Menu Name** (**Level › Settings**, see [Levels](levels.md)) |
| `[text:name]` | A game text by its name (pick it with the search button) |
| `[task:name]` | A custom task's Introduced text |
| `#xa00` | A text id (the whole field) |

Alone in the field, a reference uses that same text; inside a sentence it is replaced by its English words. For example `Free the [level_name] sage`.

The same rules apply to [hints](checkpoints-and-cameras.md#hints).

### Stages

A task moves through stages; the menu shows the first open stage whose condition is true. New tasks get The Forgotten Lands' list: **Need Hint** (closed by default) → **Need Introduction** → **Need Reminder** → **Need Resolution**. That's enough for a plain power cell: collecting the cell closes Need Resolution.

Open **Stages (N)** to change them (**Add Stage**, **-** removes one):

| Option | What it does |
|---|---|
| Status | **Need Hint** (not known yet), **Need Introduction**, **Need Reminder A**, **Need Reminder**, **Need Reward Speech**, **Need Resolution** (closed by collecting the task's power cell) |
| **Not** | Invert the condition: the stage counts while it is NOT met |
| Condition | **Always**, **Task stage closed** (a task + a **Stage**), **Task complete** (its cell collected), **Power cells ≥**, **Orbs ≥**, **Scout flies ≥** (of a task), **GOAL expression** |
| **Closed by default** | Re-closed on a game reset |
| **Saved** | Closing this stage is saved |

To hide a task until something happens, give its Need Hint stage **Not** + that condition.

### Task settings

| Option | Default | What it does |
|---|---|---|
| **Task group** | the .blend's file name | Name of this .blend's task file, `lt-tasks-<group>.gc` (shown under it). Use a different group per .blend that adds tasks to the same game |
| **Starting task ID** | 116 | First ID new tasks get. Raise it to keep clear of other mods' or old levels' tasks |
| **Starting text ID** | 2560 (`#xa00`) | First text id the task names use. Ids `#xa00`–`#xeff` are free in the vanilla game; used ids are skipped |

New IDs and text ids skip the ones other groups, mods and the game already use.

## Using a task on actors

Actors that give or check a task have a **Game Task** panel (**Object Settings › Actor Settings › Game Task**): power cells, scout flies, crates, NPCs that give cells, enemies with **Has power cell**, the Battle Controller ... Click the button to search every vanilla task and your custom ones. **Custom…** lets you type a task name, a number or a `(GOAL expression)`. Alt+click sets it on all selected actors.

- A **scout fly** also has **Scout fly (1-7)**: which of the task's 7 flies it is.
- A cell plays its pickup animation at Jak, or at the actor's **Movie Position** if you set one.
- Some actors are gated by a second task: the **Oracle** has a **Left eye task** (the second cell; None = one eye only) next to its Game Task (the right eye), plus **Price (orbs)** and **Speeches**. Other actors show a **Task Settings** panel for theirs.

NPCs that use tasks are covered in [Edited actors & GOAL code](edited-actors-and-goal-code.md).

## Task triggers

A trigger volume can close or open task stages when Jak walks in, for example to make a task appear in the menu when he reaches an area.

1. Add a trigger volume (**Spawn Objects › Triggers › Trigger volume**) and shape it (a closed, convex mesh).
2. Select it, and in **Object Settings › Volume Links › Task actions** click **Add Task Action**.
3. Pick **Close** or **Open**, the stage, and the task (**of**).

It runs each time Jak enters the volume. A volume with only task actions needs no other link. Hints can do the same with their **Close ...** commands ([Checkpoints & cameras](checkpoints-and-cameras.md#hints)). More on volumes: [Volumes & triggers](volumes-and-triggers.md).

## What gets written

When you export a level whose .blend has custom tasks, the add-on writes (only what changed):

| File | What |
|---|---|
| `goal_src/jak1/engine/game/task/game-task-h.gc` | Your task names in the game-task list, in a marked block for your group, and `(max ...)` raised to fit |
| `decompiler/config/jak1/all-types.gc` | The same block |
| `goal_src/jak1/engine/game/game-save.gc` | Once: mod-base save fixes for more than 116 tasks |
| `goal_src/jak1/levels/level-tools/lt-tasks-<group>.gc` | Your stages and progress menu pages, added to the game at boot. Registered in `game.gp` and `dgos/game.gd` |
| `game/assets/jak1/text/lt_<group>_text_en-US.json` | The menu names (and hint texts), registered in `game_text.gp` |

The game's own task and menu code stays untouched. If your task names or IDs clash with another group's, yours replace them and that group's task file is removed: export its .blend again (the build log warns). Clashes with vanilla or other mods' tasks stop the build.

Turning **Custom tasks** off (or removing every task) takes your group's entries back out on the next export.

**The first build after adding tasks is a full compile**: the game-task list is part of the engine, so changing it (adding, renaming or renumbering tasks) recompiles most of the game. Later builds are back to normal speed.<!-- check: confirm text / stage-only edits don't trigger a full compile -->

---
[← Previous](lighting.md) · [Guide index](README.md) · [Next →](edited-actors-and-goal-code.md)
