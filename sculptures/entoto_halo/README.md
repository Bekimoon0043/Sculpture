# sculptures/ — designs that live in a file

Each subdirectory is one design whose authoritative definition is a JSON request
you can read, diff and re-run. Nothing here is an export or a cache: the file is
the design, and the kernel turns it into geometry every time.

## entoto_halo — the first sculpture

**Entoto Halo**: a wet plaza fountain, 4 elements, 3 materials, one fused body.
5,072.00 kg, 2,400 × 2,400 × 1,360 mm. A hollow basalt plinth carries a basalt
pool, a bronze column with a ⌀110 service bore rises out of it, and a
mirror-polished 316L ring crowns the shaft with its aperture as the water's exit.

Rebuild it (stack up, `$0`, no API key):

```bat
python scripts\build_sculpture.py sculptures\entoto_halo\request.json --twice --exports --bom
```

The full record — measured masses, joint seats, every gate verdict, the sealed
package digests, and what is deliberately *not* certified — is
[`SCULPTURE_1_ENTOTO_HALO.md`](../../SCULPTURE_1_ENTOTO_HALO.md) at the repo root.

**Headline, unvarnished:** the build is real and reproducible, but its
`overall_status` is **`needs_input`**, so every exported geometry file is named
`PRE-FABRICATION.*` and the package says in its own warrant that it must not be
built from. That is correct behaviour: no design wind speed, no allowable ground
bearing and no declared lift points have been supplied yet. See §8 of the report.
