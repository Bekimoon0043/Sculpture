# B-11 free-form reference set

Date received: 2026-09-02  
Source: files supplied by the owner from Telegram Desktop  
Purpose: visual ground truth for PR-2.5 discovery. These images are requirements references, not designs to copy and not evidence that LuxuryForm can already generate the depicted forms.

## Executive reading

This set establishes two related targets:

1. **Engineered monumental fountains** — circular basins, petal and arc assemblies, water routing, service access, anchorage and lighting intent (references 01–07).
2. **Smooth free-form sculpture** — continuous ribbons and shells, changing cross-sections, large openings, twists, bifurcations and interwoven loops, sometimes integrated with water (references 08–16).

The strongest five references for the first free-form acceptance set are **08, 11, 13, 14 and 16**. Together they require more than scaled primitives: guide curves, controlled loft sections, variable thickness, non-planar twist, through-voids, branching or split silhouettes, and reliable base attachment.

Important limitation: **none of the supplied images shows a true open wire mesh, lattice, triangulated skin or cellular structure**. They strongly define smooth amorphous/ribbon geometry, but they do not close the boss's separate “mesh-like” requirement. At least one real mesh/lattice reference is still needed before that capability can be specified or accepted.

## Reference-by-reference analysis

### 01 — African Union fountain fabrication drawing

File: `01_african_union_fountain_fabrication_drawing.jpg`

- Four curved arc elements arranged around an Africa-shaped center panel in a circular basin.
- Explicit dimensions include a 6000 mm basin diameter, 5200 mm overall sculpture width, 3800/2400 mm arc heights, a 2200 mm Africa panel and a 450 mm basin height above grade.
- The drawing explicitly specifies 6 mm Grade 316L stainless-steel plate, hollow welded box-section construction, brushed/champagne PVD finish, full-penetration welds, base plates, isolation pads and M20 anchors.
- It also shows a nozzle ring, supply/return lines, pump room, access hatch and electrical conduit.
- Value to PR-2.5: engineering and fabrication precedent, but the arc geometry itself is relatively simple rather than amorphous.

### 02 — Lotus fountain service-routing section

File: `02_lotus_fountain_service_routing_section.jpg`

- Section/elevation of a tiered petal fountain over a concealed equipment vault.
- Shows maintenance panel, ladder, pumps, filtration, electrical distribution, concealed plumbing and electrical conduits.
- Value: serviceability and routing requirements that future free-form fountain geometry must not obstruct.
- Material and exact dimensions are not stated in this image.

### 03 — Lotus fountain water-flow diagram

File: `03_lotus_fountain_water_flow_diagram.jpg`

- Defines water rise through the center, upper-tier sheets, lower-tier cascades, basin falls, perimeter jets and pump recirculation.
- Value: a future shape is not acceptable merely because it looks organic; water paths and collection must be intentional and traceable.
- This is a hydraulic intent reference, not proof of hydraulic sizing.

### 04 — Lotus fountain lighting zones

File: `04_lotus_fountain_lighting_zones.jpg`

- Zone A: warm-white structure grazing and petal-base lighting.
- Zone B: RGBW underwater/cascade coloring.
- Zone C: concealed ground projectors for shadow projection.
- Value: records a future lighting-integration target. It does not provide fixture photometry, electrical loads or control design.

### 05 — African Union arc-fountain render

File: `05_african_union_arc_fountain_render.jpg`

- Presentation rendering of the curved-arc/Africa-panel scheme in reference 01.
- Shows the intended relationship between metallic arcs, central perforated panel, circular basin and colored jets.
- Reference 01 is the authoritative source for its stated fabrication details; appearance alone must not be used to infer additional materials.

### 06 — Lotus fountain stone-appearance render

File: `06_lotus_fountain_stone_render.jpg`

- Multi-tier radial petal fountain with cascades and perimeter jets.
- Petals are repeated but have curved, tapered profiles and nested radial placement.
- The image has a stone-like appearance, but the actual material and fabrication method are **unknown** until the owner confirms them.

### 07 — Lotus fountain dimensional elevation

File: `07_lotus_fountain_dimensions.jpg`

- Preliminary dimensions: approximately 3600 mm overall height, 5000 mm basin diameter and 500 mm basin wall height.
- Explicitly marked “subject to engineering verification.”
- Value: useful scale reference for assembly, lifting, segmentation and public-space clearances.

### 08 — Organic void sculpture in a water court

File: `08_organic_void_sculpture_water_court.jpg`

- Thick, smooth, asymmetrical loop with a large through-opening and a changing cross-section.
- The outer and inner boundaries flow independently; this is not a simple torus or extruded profile.
- Strong acceptance reference for controlled lofts, guide curves, wall thickness, curvature continuity and stable base contact.
- Material/process are unknown from the photograph.

### 09 — Nested flame/ribbon sculpture

File: `09_nested_flame_ribbon_sculpture.jpg`

- Several nested, tapering ribs curl upward around a central void.
- Requires repeated-but-non-identical guide curves, variable section size, spacing control and collision prevention.
- Bronze-colored appearance is not proof of bronze; material/process remain unknown.

### 10 — Interlocking loop sculpture

File: `10_interlocking_loop_sculpture.jpg`

- Two vertically separated loops connected through a central transverse sweep.
- Requires non-planar path control, topology with multiple openings and a connection that does not self-intersect.
- Metallic appearance only; material/process remain unknown.

### 11 — Twisted ribbon fountain sculpture

File: `11_twisted_ribbon_fountain_sculpture.jpg`

- Highly free-form reflective ribbon/solid with strong twist, changing concavity, a lower opening and an integrated falling-water edge.
- Strong acceptance reference for section rotation along a path, curvature continuity, minimum radii, variable thickness and water-interface definition.
- This is one of the most demanding references in the set.

### 12 — Crescent and suspended-figure sculpture

File: `12_crescent_figure_sculpture.jpg`

- Large crescent frame enclosing a separate elongated figure-like form.
- The image itself states approximately 1900 mm high × 2000 mm long × 400 mm wide.
- Raises a multi-body/connection question: the apparent suspended element needs a real, declared structural connection rather than visual floating.
- Material/process remain unknown despite the polished-metal appearance.

### 13 — Double-loop garden sculpture

File: `13_double_loop_garden_sculpture.jpg`

- Vertically stretched, hourglass-like continuous form with two major voids and a twist through the waist.
- Strong acceptance reference for one watertight body, controlled two-void topology, varying section orientation and structural base transition.

### 14 — Interwoven ribbon garden sculpture

File: `14_interwoven_ribbon_garden_sculpture.jpg`

- Multiple broad loops weave around a central vertical form, producing several openings and apparent over/under crossings.
- Strong acceptance reference for non-self-intersection, controlled clearances, variable ribbon width/thickness and complex topology.
- A deterministic representation must distinguish genuine joined geometry from merely intersecting surfaces.

### 15 — Ring-cascade fountain sculpture

File: `15_ring_cascade_fountain_sculpture.jpg`

- Three stacked/open ring elements with water spilling across selected gaps.
- Geometry is simpler than references 11/13/14 but adds a clear water-edge and catchment requirement.
- Useful secondary fountain acceptance reference.

### 16 — Split-ribbon garden sculpture

File: `16_split_ribbon_garden_sculpture.jpg`

- Two flowing lobes/ribbons split and reunite around upper and lower openings.
- Strong acceptance reference for bifurcation, changing section, smooth reunion, minimum wall thickness and two-void topology.

## Proposed PR-2.5 geometric acceptance vocabulary

The discovery plan should test whether the installed deterministic kernel can represent and robustly validate these capabilities without an LLM emitting vertices:

- 3D guide curves with bounded control points.
- Lofted sections with controlled scale, rotation and eccentricity.
- Swept ribbons/shells with explicit width and thickness.
- Smoothness/continuity targets at section joins.
- Large through-voids and multiple-void topology.
- Split/rejoin or bifurcated forms.
- Interwoven forms with explicit clearance and no unintended self-intersection.
- Minimum radius, minimum wall thickness and manufacturable edge treatment.
- A declared, measurable base interface and center-of-mass implications.
- Water-edge, collection and concealed-routing interfaces for fountain variants.
- Deterministic segmentation of curved modules without cutting through declared service routes.

This vocabulary is a discovery input, not a claim that these capabilities exist today.

## Recommended first acceptance subset

Use these five images as the primary visual acceptance family:

| Reference | Why it is required |
|---|---|
| 08 | Smooth asymmetrical monolithic loop and large through-void |
| 11 | Strong 3D twist, variable section and integrated water edge |
| 13 | Continuous double-loop/two-void topology |
| 14 | Interwoven ribbons, multiple voids and clearance control |
| 16 | Split/rejoin silhouette and smooth bifurcation |

Use 01–07 as engineering/fountain-integration context and 09, 10, 12 and 15 as secondary geometry cases.

## B-11 facts still requiring an owner ruling

The images close the visual-reference portion of B-11 for smooth free-form sculpture, but they do not answer these items:

1. **Material and process for references 08–16.** Choose the real intended construction family for each target: carved stone; cast concrete/GRC; cast metal; welded plate over an armature; fabricated tubular/ribbon sections; composite mold; or another process. Appearance is not reliable evidence.
2. **Manual controls.** Recommended first-version ruling: brief-driven generation plus editable parameters, control points, guide curves and section profiles. A complete Blender-style manual mesh sculptor remains outside the first version unless the owner explicitly requires it.
3. **Mesh/lattice reference.** Supply at least one image showing the actual open mesh, wire lattice, perforated skin or cellular structure the boss meant by “mesh-like.” None of these 16 images defines that requirement.
4. **Target scale.** Confirm expected height/width/depth for the five primary references. Only references 01, 07 and 12 contain explicit dimensional information.
5. **Permitted simplification.** State which features must be preserved versus which may be simplified for fabrication.

PR-2.5 should remain planning-only until these unknowns are either supplied or explicitly retained as operator decisions in its acceptance plan. No material, fabrication process or parameter range should be inferred from surface appearance.

## Source-to-renamed-file manifest

| Original file | Renamed file | SHA-256 |
|---|---|---|
| `photo_2026-09-02_05-22-51.jpg` | `01_african_union_fountain_fabrication_drawing.jpg` | `ECA60DC88DC2ED15C1337EAE02A7C7D04C7B13B99D1D65DF15514828D7671C20` |
| `photo_2026-09-02_05-22-49.jpg` | `02_lotus_fountain_service_routing_section.jpg` | `6EA0487428130F5458C5F9B80B1B1C2E46120BCFBB7DA6E59EEED8BB176A4EFA` |
| `photo_2026-09-02_05-22-47.jpg` | `03_lotus_fountain_water_flow_diagram.jpg` | `A6975B1886D070E4A157B41FE235A0089D0CFDD50E1978B0CE19A213B3581C46` |
| `photo_2026-09-02_05-22-45.jpg` | `04_lotus_fountain_lighting_zones.jpg` | `57594322F86C645BAABA0CA53A888E86399CCDA594EB1A9A688FC2D944487F03` |
| `photo_2026-09-02_05-22-44.jpg` | `05_african_union_arc_fountain_render.jpg` | `1EE28DE3E4AD43566AFAF636906BB40405FA5F813BF2C29997B3994F664DC359` |
| `photo_2026-09-02_05-22-42.jpg` | `06_lotus_fountain_stone_render.jpg` | `705C5AB6E6DFEA44CEE821610A7CB4A27E9C30BA49B60E1D3B75A01921618FFD` |
| `photo_2026-09-02_05-22-40.jpg` | `07_lotus_fountain_dimensions.jpg` | `B79D93EDAFB3BB34E54C047D7E284C73DC6FD367699F0E650A79E1EC1E0EEB79` |
| `photo_2026-09-02_05-22-38.jpg` | `08_organic_void_sculpture_water_court.jpg` | `BFE1662B587807B50E6654E756563FA7B3524415767DB3CFB8573A34C3F87A02` |
| `photo_2026-09-02_05-22-37.jpg` | `09_nested_flame_ribbon_sculpture.jpg` | `4E3BC8BD06BD466B1C70961A347DA95F143FC5B57A8B1D4F9D69ADD9D8D20FDC` |
| `photo_2026-09-02_05-22-35.jpg` | `10_interlocking_loop_sculpture.jpg` | `99C8D88493BDB6EFDE494D5C8E73AA4B2786A8F6FBF66B5704E8FB4853EDADD1` |
| `photo_2026-09-02_05-22-34.jpg` | `11_twisted_ribbon_fountain_sculpture.jpg` | `9FF6BA02BB271CE6F9E0CFF0578BF9094BF96891885EA5BE3F0320AF994F4C27` |
| `photo_2026-09-02_05-22-32.jpg` | `12_crescent_figure_sculpture.jpg` | `07D9544818FE2D1C0B01E09B69BEEEDB1F6D283E53C9692E21D4FBD6D45840D5` |
| `photo_2026-09-02_05-22-31.jpg` | `13_double_loop_garden_sculpture.jpg` | `CAB6534F7799620BD18CEA4B6AF26803B31F5D8409AACB1763A9B476BE5E32ED` |
| `photo_2026-09-02_05-22-30.jpg` | `14_interwoven_ribbon_garden_sculpture.jpg` | `E04DC0DD0E6B9704B858BFB1AD609FC64D6E75EB46F81F9105FD5A6D77E5E1CC` |
| `photo_2026-09-02_05-22-28.jpg` | `15_ring_cascade_fountain_sculpture.jpg` | `924D67DB8864EB4D16F6C02C6DC9C08B7C7A4E60A56B57088F6AD9ED62AF492F` |
| `photo_2026-09-02_05-22-23.jpg` | `16_split_ribbon_garden_sculpture.jpg` | `DC906C62663B5ACAF8A3457A7D6882D85FC3284DFE21E432119719BD7949FF34` |
