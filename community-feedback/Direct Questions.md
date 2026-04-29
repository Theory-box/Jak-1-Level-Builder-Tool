# Direct questions and fixes

---

## Table of Contents
- [How to use](#how-to-use)
- [Questions](#questions)
- [Fixes](#fixes)
- [Features Request](#features-request)

---

## How to use

### For the human users

Questions or requests will be added in each category by human. They'll also decide when a question or request has been fullfiled by adding [SOLVED] at the start of the title of that question. Else they can have have a back and forth.

---

### For Claude

You will read through this document and find unanswered question request to answer them. If the users has marked it as [SOLVED] then that section can be ignored. If the users ask follow up questions, those also needs to be answered.

---

### Question Example

#### Why does the data base has X?
- User: I've read through the database and found X. I'm not sure what X refer to or how it is used?
- Claude: X works this and that way. You can do Y with it, etc.
- User: I see, Can it be used to do Z too?
- Claude: It can not.

After that last message, the user then mark the question as solved by editing the title as such:
#### [SOLVED] Why does the data base has X?
Claude then doesn't need to answer more.

---

## Questions

### What is the use of the color field?
- Kui: In actors definitions, I've noticed that there's a "color" field added to each actor. This does not seem to have any uses that I can see? It's not being added in any way to the lump in the level's json file or as some property of the empty in blender. So what is its uses? And if it doesn't have any. Could this be cleaned from the database as it would save a lot of space and makes it easier to read and edit.

---

## Fixes

### Green eco vent not working
- Kui: the actor with the label "Green Eco Vent" is currently not working because, instead of having a sub type, like other vents, green eco vents instead rely on the eco-info to be set to spawn "eco-green" in the quantity of "1". I've tried to set it up myself in the database but failed. Could this be fixed but also explain how the database has to be changed to make this fix so I know for future reference.

---

## Features Request

