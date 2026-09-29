# What we did, in plain English (Esk / Cyclone Gabrielle)

## The one-minute version

**Question:** How much plantation forest canopy did Cyclone Gabrielle strip from the Esk catchment, and where?

1. **Define the forest.** The national land-cover map is from 2018/19 and lists recently harvested land as "harvested", not forest. By the storm, most of that land was young trees. So we rebuilt the plantation map: **9,525 ha**, about a third of the catchment.
2. **Map the change.** We compared Sentinel-2 satellite greenness from a few weeks before the storm with an image taken 6 days after. Where greenness dropped by more than normal noise, we called it lost. The map flags **823 ha**.
3. **Check it.** Maps are never exactly right. We picked **130 random 30 m squares** and checked each one by eye on very sharp before/after photos, without looking at the map (16 dots per square). A second group member redid 30 squares and agreed to within about 5%.
4. **Correct the total.** A standard method (Olofsson et al. 2014) uses those checks to correct the map's total: **466 ha lost (95% range 277–654 ha), about 7% of the plantation canopy.** The raw map overstated the loss, mostly in mature forest.
5. **Explain the pattern.** Young stands lost **15%** of their canopy against **4%** for mature forest. Loss rose with slope (5% below 15°, 24% above 35°) and was highest beside streams (20% within 20 m, 7% beyond 200 m).

**Analogy:** the satellite map is a smoke detector covering the whole catchment. The 130 checked squares are someone walking round to see which alarms were real. The checks turn the map's "823 ha" into an honest "466 ha, give or take".

## Why the number changed during the project (if anyone asks)

Every step fixed a real, documented problem:

| Estimate | What changed |
|---|---|
| 1,037 ha | First check, one 10 m pixel at a time. A few points carried most of the weight. |
| 694 ha | Blind re-check. The sharp photos sat ~9 m (one pixel) off the satellite grid, so single-pixel checks were unreliable. |
| 638 ha | Switched to 30 m squares and measured and corrected that offset at every square. |
| **466 ha (final)** | Stands harvested in 2022 still looked like forest in our 2021–22 "before" photo, but were already cut by the storm. Counted as cutover, not storm loss. |

The mature-forest figure (194 ha) never moved in the last three steps. Only the young-stand figure did.

## Likely questions

- **"Manaaki Whenua said 166 ha. Why is yours bigger?"** They counted only the bare scar at the top of each slip. We also count trees flattened, buried or silted. Different definition, not an error (backup slide).
- **"Why not radar?"** We tested it. Soaked ground brightened everywhere, and slips 10–40 m wide are small for Sentinel-1. It separated loss from intact forest only weakly (0.69, where 0.5 is a coin flip) against 0.90 for Sentinel-2.
- **"Why is the purple (not in LCDB) mostly thin strips along roads and streams?"** It's an edge effect of our 10 m classifier: pixels on forest edges mix trees with the road, pasture or stream scrub next to them, and smoothing absorbed those narrow gaps into "plantation". Only ~160 ha looks like real new planting. It doesn't change the 466 ha estimate, because the checkers judged every dot as plantation or not, and the slope and stream findings hold with those strips removed.
- **"Why do young stands slip more?"** After harvest, the old roots rot before the new crop's roots take over, so the slope loses its reinforcement.
- **"How sure are you?"** 95% range 277–654 ha. Mature 82–306 ha and young 120–423 ha; the young and mature loss rates don't overlap.
- **"What's the weakest part?"** Our "before" photo is from 2021–22, so recent harvests had to be dated with Hansen satellite data. The slope and stream rates come from the uncorrected map. There is only one post-storm satellite image.

## Numbers checked against the result files (27 Sep)

All deck numbers match `provenance/*.json` and the methods log §6j. I recomputed "the stream effect holds on every slope class": it does (within 20 m of a stream 19–29% lost, beyond 200 m 1–15%, in every slope class).
