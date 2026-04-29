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
- Kui: the actor with the label "Green Eco Vent" is currently not working because, instead of having a sub type, like other vents, green eco vents instead rely on the "eco-info" to be set to spawn "eco-green" in the quantity of "1". I've tried to set it up myself in the database but failed. Could this be fixed but also explain how the database has to be changed to make this fix so I know for future reference.

---

### Next and Prev actor lump issues
- Kui: Trying to add a res-lump for prev-actor or next-actor give this blender error. 
```
Python: Traceback (most recent call last):
  File "C:\Users\XXXX\AppData\Roaming\Blender Foundation\Blender\4.5\scripts\addons\opengoal_tools\panels\tools.py", line 373, in execute
    row.ltype = self.lump_ltype
    ^^^^^^^^^
TypeError: bpy_struct: item.attr = val: enum "structure" not found in ('float', 'meters', 'degrees', 'int32', 'uint32', 'enum-int32', 'enum-uint32', 'vector4m', 'vector3m', 'vector-vol', 'vector', 'movie-pos', 'water-height', 'eco-info', 'cell-info', 'buzzer-info', 'symbol', 'string', 'type')
```
- Kui: Manually changing it to a string type instead of structure then means I'd need to write down the name instead of dirrectly linking the object in blender. Plus it'll show like this:
```json
"prev-actor": [
    "string",
    "test1_balance-plat_0001"
]
```
- Kui: When it should just show up as this: "prev-actor": "test1_balance-plat_0001" Maybe there should be a custom type too where it allows you to write whatever you want in the lump instead of always having it setup the other way. Or will the structure type work that way once it's fixed?

---

### balance-plat crashes the game
- Kui: Even after adding the prev-actor and next-actor lumps, and editing the exported json to be correct, the game still crashes when loading a level with balance-plat types added. It does seem to have the art group (balance-plat-ag.go) as well as the code (swamp-obs.o). So not sure where the crash is coming from right now. Attaching the debbugger also doesn't give me any goal code issue:
```
Target raised an exception (STATUS_STACK_BUFFER_OVERRUN [0xC0000409]). Run (:di) to get more information.
    (:di)
Read symbol table (1076480 bytes, 6363 reads, 6362 symbols, 31.96 ms)
Backtrace:
   rsp: 0x242c4d67b08 (#x1a7b08) rip: 0x69f1efb6 (#xfffffdbda535efb6)
Backtrace was too long. Exception might have happened outside GOAL code, or the stack frame is too long.
   rsp: 0x242c4d67b00 (#x1a7b00) rip: 0xbf (#xfffffdbd3b4400bf)
   rsp: 0x242c4d67af8 (#x1a7af8) rip: 0xb8 (#xfffffdbd3b4400b8)
   rsp: 0x242c4d67af0 (#x1a7af0) rip: 0x0 (#xfffffdbd3b440000)
   rsp: 0x242c4d67ae8 (#x1a7ae8) rip: 0x242e7cae870 (#x230ee870)
   rsp: 0x242c4d67ae0 (#x1a7ae0) rip: 0x2 (#xfffffdbd3b440002)
   rsp: 0x242c4d67ad8 (#x1a7ad8) rip: 0x242c4d67b80 (#x1a7b80)
   rsp: 0x242c4d67ad0 (#x1a7ad0) rip: 0xb8 (#xfffffdbd3b4400b8)
   rsp: 0x242c4d67ac8 (#x1a7ac8) rip: 0x242e7caca60 (#x230eca60)
   rsp: 0x242c4d67ac0 (#x1a7ac0) rip: 0x242c4d67ab8 (#x1a7ab8)
   rsp: 0x242c4d67ab8 (#x1a7ab8) rip: 0xd (#xfffffdbd3b44000d)
   rsp: 0x242c4d67ab0 (#x1a7ab0) rip: 0x1d (#xfffffdbd3b44001d)
   rsp: 0x242c4d67aa8 (#x1a7aa8) rip: 0xd8b852b2 (#xfffffdbe13fc52b2)
   rsp: 0x242c4d67aa0 (#x1a7aa0) rip: 0x0 (#xfffffdbd3b440000)
   rsp: 0x242c4d67a98 (#x1a7a98) rip: 0x242a7856890 (#xffffffffe2c96890)
   rsp: 0x242c4d67a90 (#x1a7a90) rip: 0x1dcd7cde50b65a1 (#x1dcd58b204f65a1)
   rsp: 0x242c4d67a88 (#x1a7a88) rip: 0x7ff60fb194fb (#x7db34af594fb)
   rsp: 0x242c4d67a80 (#x1a7a80) rip: 0x242c4d67b00 (#x1a7b00)
   rsp: 0x242c4d67a78 (#x1a7a78) rip: 0x1d (#xfffffdbd3b44001d)
   rsp: 0x242c4d67a70 (#x1a7a70) rip: 0x1d (#xfffffdbd3b44001d)
   rsp: 0x242c4d67a68 (#x1a7a68) rip: 0x5 (#xfffffdbd3b440005)
   rsp: 0x242c4d67a60 (#x1a7a60) rip: 0x242e7cae870 (#x230ee870)
   rsp: 0x242c4d67a58 (#x1a7a58) rip: 0x242c4d67b80 (#x1a7b80)
   rsp: 0x242c4d67a50 (#x1a7a50) rip: 0xfffffffffffffffe (#xfffffdbd3b43fffe)
   rsp: 0x242c4d67a48 (#x1a7a48) rip: 0x5 (#xfffffdbd3b440005)
   rsp: 0x242c4d67a40 (#x1a7a40) rip: 0x7ff610718401 (#x7db34bb58401)
   rsp: 0x242c4d67a38 (#x1a7a38) rip: 0xcf (#xfffffdbd3b4400cf)
   rsp: 0x242c4d67a30 (#x1a7a30) rip: 0xc7 (#xfffffdbd3b4400c7)
   rsp: 0x242c4d67a28 (#x1a7a28) rip: 0x242c4d679e0 (#x1a79e0)
   rsp: 0x242c4d67a20 (#x1a7a20) rip: 0xc (#xfffffdbd3b44000c)
   rsp: 0x242c4d67a18 (#x1a7a18) rip: 0x7ffa78246c11 (#x7db7b3686c11)
   rsp: 0x242c4d67a10 (#x1a7a10) rip: 0x242e7cae870 (#x230ee870)
   rsp: 0x242c4d67a08 (#x1a7a08) rip: 0x0 (#xfffffdbd3b440000)
   rsp: 0x242c4d67a00 (#x1a7a00) rip: 0x7ff610000001 (#x7db34b440001)
   rsp: 0x242c4d679f8 (#x1a79f8) rip: 0x0 (#xfffffdbd3b440000)
   rsp: 0x242c4d679f0 (#x1a79f0) rip: 0x242e7cae870 (#x230ee870)
   rsp: 0x242c4d679e8 (#x1a79e8) rip: 0xf (#xfffffdbd3b44000f)
   rsp: 0x242c4d679e0 (#x1a79e0) rip: 0x7 (#xfffffdbd3b440007)
   rsp: 0x242c4d679d8 (#x1a79d8) rip: 0x0 (#xfffffdbd3b440000)
   rsp: 0x242c4d679d0 (#x1a79d0) rip: 0x5d32303a37345b (#x5d2fed757b345b)
   rsp: 0x242c4d679c8 (#x1a79c8) rip: 0xb (#xfffffdbd3b44000b)
   rsp: 0x242c4d679c0 (#x1a79c0) rip: 0x7ff6107183fb (#x7db34bb583fb)
   rsp: 0x242c4d679b8 (#x1a79b8) rip: 0x2800000000 (#xfffffde53b440000)
   rsp: 0x242c4d679b0 (#x1a79b0) rip: 0x242a7856890 (#xffffffffe2c96890)
   rsp: 0x242c4d679a8 (#x1a79a8) rip: 0x2800000000 (#xfffffde53b440000)
   rsp: 0x242c4d679a0 (#x1a79a0) rip: 0x2700000000 (#xfffffde43b440000)
   rsp: 0x242c4d67998 (#x1a7998) rip: 0xa5d657079543a3a (#xa5d632db4983a3a)
   rsp: 0x242c4d67990 (#x1a7990) rip: 0x316b616a203d2054 (#x316b5f275b812054)
   rsp: 0x242c4d67988 (#x1a7988) rip: 0x5b202964696f7628 (#x5b202721a4b37628)
   rsp: 0x242c4d67980 (#x1a7980) rip: 0x3e2d726f74617265 (#x3e2d702cafa57265)
   rsp: 0x242c4d67978 (#x1a7978) rip: 0x706f3a3a3e657079 (#x706f37f779a97079)
   rsp: 0x242c4d67970 (#x1a7970) rip: 0x543a3a316b616a3c (#x543a37eea6a56a3c)
   rsp: 0x242c4d67968 (#x1a7968) rip: 0x727450206c636564 (#x72744ddda7a76564)
   rsp: 0x242c4d67960 (#x1a7960) rip: 0x635f5f2a2054203a (#x635f5ce75b98203a)
   rsp: 0x242c4d67958 (#x1a7958) rip: 0x6e6f6974636e7546 (#x6e6f67319eb27546)
   rsp: 0x242c4d67950 (#x1a7950) rip: 0x90a30343a682e72 (#x90a2df175ac2e72)
   rsp: 0x242c4d67948 (#x1a7948) rip: 0x74502f6e6f6d6d6f (#x74502d2baab16d6f)
   rsp: 0x242c4d67940 (#x1a7940) rip: 0x632f0032303a3734 (#x632efdef6b7e3734)
   rsp: 0x242c4d67938 (#x1a7938) rip: 0x2f656d61675c2e2f (#x2f656b1ea2a02e2f)
   rsp: 0x242c4d67930 (#x1a7930) rip: 0x657361422d646f4d (#x65735eff68a86f4d)
   rsp: 0x242c4d67928 (#x1a7928) rip: 0x242a7856890 (#xffffffffe2c96890)
   rsp: 0x242c4d67920 (#x1a7920) rip: 0x242c4d67900 (#x1a7900)
   rsp: 0x242c4d67918 (#x1a7918) rip: 0x24200000003 (#xffffffff3b440003)
   rsp: 0x242c4d67910 (#x1a7910) rip: 0x24200000003 (#xffffffff3b440003)
   rsp: 0x242c4d67908 (#x1a7908) rip: 0x7ff60fb23282 (#x7db34af63282)
   rsp: 0x242c4d67900 (#x1a7900) rip: 0x242c4d67980 (#x1a7980)
   rsp: 0x242c4d678f8 (#x1a78f8) rip: 0x242c4d67900 (#x1a7900)
   rsp: 0x242c4d678f0 (#x1a78f0) rip: 0x242c4d67980 (#x1a7980)
   rsp: 0x242c4d678e8 (#x1a78e8) rip: 0x5 (#xfffffdbd3b440005)
   rsp: 0x242c4d678e0 (#x1a78e0) rip: 0x242c4d679e0 (#x1a79e0)
   rsp: 0x242c4d678d8 (#x1a78d8) rip: 0x7ffa782b4ae5 (#x7db7b36f4ae5)
   rsp: 0x242c4d678d0 (#x1a78d0) rip: 0x7ffa782b4aee (#x7db7b36f4aee)
Unknown Function at rip

Not in GOAL code!

rax: 0x0000000000000001 rcx: 0x0000000000000007 rdx: 0x00000242a7650680 rbx: 0x00000242c4d679e0 
rsp: 0x00000242c4d678d0 rbp: 0x00000242c4d67980 rsi: 0x0000000000000005 rdi: 0x00000242e7cae870 
 r8: 0x7ffffffffffffffc  r9: 0x0000000000000002 r10: 0x0000000000000000 r11: 0x00000242c4d67890 
r12: 0x0000000000000009 r13: 0x000000000014fd24 r14: 0x00000242e6abc1f0 r15: 0x0000000000000005 
rip: 0x00007ffa782b4aee
```

## Features Request

### Making Preview mesh "useable"
- Kui: Preview meshes are great to get a good idea of what you're placing and it's position and direction related to the world around it. One thing that's annoying with having all actors as empties, is selecting them in the 3D space can be annoying as you only have the small lines of the empty to click on. Being able to use the preview mesh for this would be very intuitive and fast. However there's a few things that would need to be done to get this working:
  - At the moment the preview meshes are set to not being selectable in the collection, this would need to change.
  - Moving a preview mesh doesn't move the actor's empty since the actor empty is the child. To fix this, a constraint can be added to the empty to copy transform from the preview mesh. That way, regardless of moving the empty or the preview mesh, the other one will follow.
  - Selecting the mesh doesn't give you the settings for the actor. This isn't too bad since you can easily select the parent with "Shift + G" but maybe the addon could directly show the properties of the parent if it detect a preview mesh is selected
  - Deleting is also an issue, right now, deleting the actor doesn't delete the preview mesh but the opposite is also true. Which is fine right now but if we're able to do most actions through the preview mesh, then it would be good for both to delete when one of them is deleted.