# Image prompts and provenance

Tool: built-in image_gen (no CLI/API fallback). Raster illustration is explicitly distinguished from the original experimental photograph.

## Selected assets

- Original photograph: assets/platform_original.jpg; copied unmodified from V3正文重绘_20261011/schematics/references/platform_original.jpg.
- Selected robot illustration: assets/platform_illustration.png; generated output exec-1e4e58e3-1310-4141-9794-991e7a7344d3.png, native1254×1254.
- Geometry concept: assets/geometry_concept.png; generated output exec-e2e70d73-815b-4876-848e-8cafa83bdbfc.png, native1254×1254. The final scientific composition uses editable vector geometry so labels remain8pt; the image asset is retained as the design reference.
- Method figure: preview/F02_method.png; selected output exec-9e1bebbe-f2f1-47f8-bbd5-b6ac03b35b5a.png, native1816×866.

## Platform design specification

Create a clean scientific perspective illustration from the real platform photograph. Preserve the gray quadruped, blue upper mounting assembly, visible hardware arrangement and viewing direction. White background, restrained gray/blue, crisp dark outlines; no invented callouts, dimensions, measurement evidence or logos. Keep the illustration separate from the untouched photograph.

Final publication composition: real photograph, selected illustration, and a schematic top view. The schematic shows p1 at the right, p2 at the left, b=p2−p1, nominal0.35m, xb forward and yb left. No surveyed sensor origin is inferred from the photograph.

## Exact final method edit prompt

Use case: precise-object-edit. Edit only the supplied scientific method diagram. Keep the layout, every box, all text, math, colors, icons and every other arrow identical. One scientific wiring correction: DELETE the short horizontal black line from the words 'Roll / pitch' to the left edge of 'Frame rotation' (currently around x385..542,y557). Roll/pitch must NOT enter Frame rotation. Keep the already-present separate upper horizontal path from the right edge of the green Robot motion observations box (around y514) into the Valid GNSS event diamond; that is the direct roll/pitch observation path, and you may add the small label 'Tilt observations' ABOVE that existing path without a new box. KEEP the separate Body velocity arrow at y609 entering Frame rotation. KEEP the dashed Heading + tilt used in preprocessing arrow entering Frame rotation from below. Preserve all other arrows and formulas exactly. White background; crisp publication-style typography. Do not invent any new feedback loop.

Input/edit target: exec-77d1fe35-3938-4bfb-a136-b69ff861bdf3.png, itself generated during this round. The resulting correction was visually checked: roll/pitch no longer enters Frame rotation; the Tilt observations branch enters the event gate directly; Body velocity and dashed preprocessing heading+tilt still enter Frame rotation.
