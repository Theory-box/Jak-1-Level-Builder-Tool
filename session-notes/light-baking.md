# Light baking additions (branch claude/light-baking)

## Done
- View buttons (eye per time of day) set the active and the render colour attribute.
- Copy Worlds / Collections from another level (same worlds / collections, not copies).
- Curve preset "Fit 0.25-1.0" (enum number 1000 so saved files keep their preset).
- Bake time in the end message ("Baked N mesh(es), N time(s) of day in mm:ss (combined): ...").
- "Combine meshes while baking" (bake options, off by default), as planned below. Test
  (_claude_tmp/bl_fastbake.py, headless, 980k-triangle unselected ground, 43 meshes, 32
  samples, 8 times + emit): per mesh 21.6 s, combined 1.8 s (x12); colours within ~2 %
  (sampling). Corner normals come from the evaluated mesh when its corners match (Smooth by
  Angle). A mesh without a UV map gets an empty one on the copy (Blender's bake asks for one).
  Negative scale: faces wound the other way in the copy (fe4bb69). Ray visibility (shadow
  off ...): meshes are only combined with meshes that have the same settings; the copy takes them.

## Plan: Optimising light baking (done, see above)
Why it's slow: one `bpy.ops.object.bake` call with N selected objects bakes them one by one,
and every object re-syncs the whole scene (BVH of all its triangles) before rendering. Kuitar's
numbers: 4 walls = 4 x ~1:30, the same walls joined = ~1:35. Time of day multiplies that by
the number of times (8), plus the emit pass.

Proposed (instead of separating / joining the user's objects):
1. Option on the level's bake settings, off by default: "Combine meshes while baking
   (faster on large scenes)".
2. Build one temporary mesh from the selected meshes, without touching them:
   world-space vertices, faces, material slots (union, face material index remapped),
   custom / sharp normals (corner normals), the render UV map (textures still colour bounce
   light), and, if "Ignore vertex colours in materials" is off, the colour layers the
   materials read. Each source object's corner range (and vertex range) is remembered.
3. While baking, the source objects are hidden from render (they'd sit on top of the copy),
   the copy is the only selected object: one render per pass instead of one per object.
4. After each pass the copy's colours are cut back into each object's layer (corner or
   vertex domain) by those ranges. Post-processing (emit combine, curve, blur, alpha) then
   runs per object exactly as now. The copy is deleted, render visibility restored (also on
   cancel / error).
5. Safety: very large selections are baked in chunks (e.g. up to ~1-2 M triangles per
   copy) so one render doesn't get huge, with the status line showing chunk i of n.
Limits: modifiers that change topology (the current bake already refuses those), deform
modifiers / shape keys use the base mesh (could use the evaluated mesh when its topology
matches). Linked (library) meshes are skipped like now.
Test: a synthetic heavy scene, per-object vs combined: time per pass and the colour
difference per object (should be only sampling noise).

## Copy vertex lighting from closest (done: bake.copy_lighting, Object Controls sub-panel)
Test: _claude_tmp/bl_copylight.py (ramp-coloured ground, 300 grass quads half under it: max error 0.3 %).
Original plan:
Objects Control > "Copy vertex lighting from closest":
- Mode: "Selected to active" (sources: the other selected meshes, target: the active one) or
  "Any geometry to selected" (sources: the level's exported meshes that aren't selected).
- Search: "Closest point" or "Below first" (ray straight down, closest point if it misses), and
  a max distance (beyond it a vertex keeps its colour).
- For each target corner / vertex: find the source face (BVH in world space), interpolate its
  colour at the hit point (barycentric on the triangle's corners), write it into the target's
  layer of the same name: BakedLight and every time of day layer both have; the target's alpha
  is kept. Numpy + mathutils.bvhtree.

## Color Quantisation preview (done: palette.py, Light Baking > Color Quantisation)
Python port of build_level's palette (k-d tree, 13 deep, 8192 colours); bytes = the GLB's
16-bit linear colours >> 8; closest-time fill; 4-byte colours on installs without time of
day (versions "time_of_day"). Checked against build_level's own log
(_claude_tmp/bl_palette.py, 3 grids, 8 times, one mesh missing odd times):
- test-v0.3.8 (32 bytes): 11163 unique -> 8192, worst diff 66.098 (build_level: same).
- test-modbase binary (4 bytes): 8969 unique -> 8192, worst diff 1.732 (build_level: same).
Preview writes "OG Palette Preview" (float, corner) and makes it active + render; the export
switches back to the bake (use_baked), Restore removes the layers.
Fixes (Kuitar: both ways): Desaturate darks (Level, Strength), Snap near-greys (Threshold); Apply
after every bake (last post step), Apply to Selected (once, stacks), Preview with fixes. On the
test level the fixes lower the average error per time by about 10-15 %.
Original notes:
How build_level makes the palette (jak-project goalc/build_level/common/color_quantization.cpp,
gltf_mesh_extract.cpp): every vertex's colour is a 32-byte vector (8 times of day x RGBA; a
level without time of day layers has the same colour 8 times). One k-d tree of depth 13
(kColorTreeDepth: 8192 colours max) for the whole level's tfrag, and one for the tie. The split
dimension goes round-robin 0, 1, 2 ... (skipping one that's constant in that node), split at
the mean of the unique values, and each final colour is the average of its bucket.
What that means:
- Depth 13 only reaches dims 0-12: sunrise RGBA, morning RGBA, noon RGBA, afternoon R.
  Sunset / twilight / evening / green sun are never used to split, they're averages of
  whatever lands in the same bucket: those times can look quite different from the bake.
- Without time of day: with alpha constant, R / G / B get about 5 / 4 / 4 splits, so roughly
  32 / 16 / 16 levels per channel spread over the level's colour range. Splits at the mean
  of the unique values: few dark values = few dark buckets, so tinted shadows get averaged
  with other colours (the odd coloured spots).
Proposed:
1. "Preview palette" button: runs the same algorithm in Python / numpy on all the level's
   exported meshes (all their times of day) and writes the result into a preview layer
   (or temporarily over the shown layer, with a Restore), so Blender shows what the game will.
2. Options to help, applied in post-processing: desaturate very dark colours (below a level,
   blend to grey), snap near-greys to grey. Decide after seeing the preview on real levels.
3. Possibly a jak-project change later (more depth, a better split choice); outside the addon.

## Light baking addition 2 (branch claude/light-baking-2, waiting for Kuitar's test)
- Level GLB colours 8-bit + COLOR_0 left out when all 8 times are baked (glb_colors.py, a glTF
  gather_mesh_hook before Draco). Blender writes colours as u16 normalized; build_level keeps
  u16 >> 8 and reads u8 directly, so the game data is identical (built 3 ways on test-v0.3.8:
  same palette). Draco's colour / generic quantization only applies to float attributes, which is
  why it never helped. Test level (62.5k faces, 8 times): Draco 3.03 MB -> 1.02 MB; Kuitar's big
  level (Draco, COLOR_0 already dropped): 97 MB -> 60 MB. Preference "8-bit colours in every glTF
  export" for hand-made exports.
- Color Depth (bake options, under Face Corner / Vertex: 8 / 6 / 5 / 4 bit, 8 by default, warning
  with the levels per channel otherwise): the GLB hook rounds RGB to 2^bits levels in sRGB (back to
  linear bytes, alpha kept); Color Quantisation's preview uses it too. Only smaller with Draco
  (-5 / -20 / -48 % on the test level).
- Kuitar's test (2026-11-17): time frame, emit copy, Delete Color Attribute, Float to Byte work.
  Keyframed emission crashed on Blender 5.3 (no Action.fcurves in 5.x): fixed with the action
  slot's channelbag (7ff8401).
- Light collection select button (RESTRICT_SELECT_OFF) and world "make it the scene's world" button
  per time of day; Auto save before bake (off by default; an unsaved .blend doesn't bake);
  per-effect Vertex Group (empty: whole mesh; a mesh without the group isn't changed). Test:
  _claude_tmp/bl_lb2b.py (4.4 and 5.3).
- Time frame per time of day (frame_set per time, combined copies rebuilt when the frame changes:
  object transforms only), Render emit per time of day (emit:<time> passes, _og_bake_emit<time>
  layers), emit passes on a small combined copy of the emissive meshes, keyframed emission counts as
  emissive, Delete Color Attribute, Float Colors to Byte. Tests: _claude_tmp/bl_bake2.py,
  bl_glbsize.py, bl_glbbuild.py, bl_bytecol.py.

## Vertex colour effects (vc_effects.py, Object Controls > Vertex Colors)
- Apply Effect: Curve Correction (own curve "OG Effect Curve", bake curve presets), Overwrite Color
  (hue / saturation / value factors, 1 / 1 / 0), Overwrite Alpha, Blur (auto blur options); Factor on curve,
  alpha; on BakedLight + every time of day layer of the selected meshes.
- Effects After Bake: per-object stack (Object.og_vc_effects; a curve effect owns its node
  group), on / off, up / down / remove, Copy Effects to Selected, Apply Effects Now. Light
  Baking > Bake options > Apply effects (off by default) runs each mesh's stack after its
  post-processing (after the combined copies are split back).
Test: _claude_tmp/bl_vcfx.py.
