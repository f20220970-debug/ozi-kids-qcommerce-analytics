"""python src/plot.py -> docs/results.png (run src/run.py first)"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
R = lambda n: pd.read_csv(ROOT / "results" / f"{n}.csv")
fig, ax = plt.subplots(1, 4, figsize=(20, 4.6))

s = R("02_speed_vs_satisfaction")
for seg, col in [("kids", "#e4572e"), ("other", "#9aa5b1")]:
    d = s[s.segment == seg]
    ax[0].plot(d.delivery_bucket.str[3:], d.pct_1_2_star, "o-", color=col, label=seg)
ax[0].set_ylabel("% of orders rated 1-2 stars"); ax[0].set_xlabel("delivery time"); ax[0].legend()
ax[0].set_title("1. Satisfaction falls off a cliff after 2 weeks")

p = R("03_late_vs_ontime"); p = p[p.segment == "kids"]
ax[1].bar(["on time", "missed promised date"], p.sort_values("promise", ascending=False).pct_1_2_star, color=["#9aa5b1", "#e4572e"])
ax[1].set_ylabel("% rated 1-2 stars (kids orders)"); ax[1].set_title("2. A broken promise hurts 8x")

a = R("05_assortment")
ax[2].bar([f"{int(t*100)}% of units" for t in a.target_share], a.pct_of_skus, color="#3b82f6")
for i, (n, pc) in enumerate(zip(a.skus_needed, a.pct_of_skus)):
    ax[2].text(i, pc + 1, f"{n} SKUs", ha="center")
ax[2].set_ylabel("% of kids SKUs needed"); ax[2].set_title("3. Dark-store assortment: few SKUs carry demand")

l = R("10_local_stock")
lab = ["SP, other state", "SP, same state", "outside SP, other state", "outside SP, same state"]
ax[3].bar(lab, l.avg_delivery_days, color=["#9aa5b1", "#3b82f6", "#9aa5b1", "#3b82f6"])
ax[3].set_xticks(range(4), lab, rotation=15, fontsize=8); ax[3].set_ylabel("avg delivery days")
ax[3].set_title("4. Local stock halves delivery time")
plt.tight_layout(); plt.savefig(ROOT / "docs" / "results.png", dpi=130); print("saved docs/results.png")
