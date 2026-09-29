"""s17 -- rule-based dot suggestions for the labelling page (protocol amendment 5).

Inputs: sample_blocks/dot_features.csv (s17f; reference imagery only, no map). Thresholds were set by eye from the
48 dots of B-001 to B-003 labelled before suggestions existed, and are fixed here:
  canopy before = aerial 2021-22 brightness < 100 and excess green >= 0.03
  lost after    = canopy before and (21 Feb brightness >= 75, or brightness >= 55 with excess green < 0.10)
Dots outside the estate are left to the page's estate mask. Suggestions are withheld on a random 20% of the blocks
not yet labelled (seed 20230304) so anchoring can be measured; the interpreter-2 page never shows suggestions.
Output: sample_blocks/dot_suggestions.csv (block_id, dot_no, sugg, show)
"""
import numpy as np, pandas as pd
from v3cfg import V3

OUT = f"{V3}/sample_blocks"
f = pd.read_csv(f"{OUT}/dot_features.csv")
can = (f.bright_pre < 100) & (f.exg_pre >= 0.03)
lost = can & ((f.bright_post >= 75) | ((f.bright_post >= 55) & (f.exg_post < 0.10)))
f["sugg"] = np.where(f.bright_pre.isna() | f.bright_post.isna(), "unset", np.where(lost, "lost", np.where(can, "can", "none")))

done = {"B-001", "B-002", "B-003"}                      # labelled before suggestions existed
todo = sorted(set(f.block_id) - done)
rng = np.random.default_rng(20230304)
withheld = set(rng.choice(todo, size=round(0.2 * len(todo)), replace=False))
f["show"] = ~f.block_id.isin(withheld | done)
f[["block_id", "dot_no", "sugg", "show"]].to_csv(f"{OUT}/dot_suggestions.csv", index=False)

# agreement with the three blocks labelled without suggestions (in-sample, so optimistic). The thresholds were set on
# the first export of B-001 to B-003 (73%); B-001 to B-003 were re-viewed on the corrected chips, so this can differ.
try:
    lab = pd.read_csv(f"{OUT}/v3_blocks_interp1_export.csv")
    lab = lab[lab.block_id.isin(done)]
    d = lab.assign(dot=lab.dots.str.split("|")).explode("dot")
    d["dot_no"] = d.groupby("block_id").cumcount() + 1
    m = d.merge(f, on=["block_id", "dot_no"]); m = m[m["dot"] != "out"]
    print("in-sample agreement on", len(m), "dots:", round(float((m["dot"] == m.sugg).mean()), 2))
    print(pd.crosstab(m["dot"], m.sugg, rownames=["label"], colnames=["suggested"]))
except FileNotFoundError:
    pass
print("blocks with suggestions:", int(f.groupby("block_id").show.first().sum()), "| withheld:", len(withheld), "| labelled before:", len(done))
print("suggested dot states:", f[f.show].sugg.value_counts().to_dict())
