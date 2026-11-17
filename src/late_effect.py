"""Is it the broken promise, or just slowness? Compare late and on-time orders that took the SAME time.

Finding 2 compared late orders (34 days on average) with on-time ones (10 days), which mixes two things.
Here: (a) late vs on-time inside the same delivery-time band, and (b) a logistic regression of a 1-2 star review
on lateness, controlling for delivery days (spline), distance, freight, price, items, sellers, customer state
and category.  Run: python src/late_effect.py -> results/late_effect_*.csv
"""
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import SplineTransformer

from eta_model import load

ROOT = Path(__file__).resolve().parents[1]


def main():
    df = load()
    con = duckdb.connect()
    D = ROOT / "data"
    rv = con.execute(f"""SELECT order_id, try_cast(review_score AS INT) AS score FROM read_csv_auto('{D}/olist_order_reviews_dataset.csv', all_varchar=true)
                         QUALIFY row_number() OVER (PARTITION BY order_id ORDER BY review_answer_timestamp DESC) = 1""").df()
    cat = con.execute(f"""SELECT i.order_id, arg_max(coalesce(t.product_category_name_english,'unknown'), i.price) AS category
        FROM read_csv_auto('{D}/olist_order_items_dataset.csv') i JOIN read_csv_auto('{D}/olist_products_dataset.csv') p USING (product_id)
        LEFT JOIN read_csv_auto('{D}/product_category_name_translation.csv') t USING (product_category_name) GROUP BY 1""").df()
    d = df.merge(rv, on="order_id").merge(cat, on="order_id").dropna(subset=["score", "dist_km"])
    d["late"] = (d.t1 > d.t_est).astype(int)
    d["bad"] = (d.score <= 2).astype(int)
    d["slack_days"] = d.promised_days - d.days            # >0 = arrived early

    # (a) same delivery time, late vs on time
    d["band"] = pd.cut(d.days, [0, 7, 14, 21, 28, 40, 120], labels=["0-7", "7-14", "14-21", "21-28", "28-40", "40+"])
    a = d.groupby(["band", "late"], observed=True).agg(orders=("bad", "size"), pct_1_2_star=("bad", "mean")).unstack("late")
    a.columns = [f"{m}_{'late' if l else 'on_time'}" for m, l in a.columns]
    a = a[(a.orders_late >= 100) & (a.orders_on_time >= 100)]
    a["pct_1_2_star_on_time"] *= 100; a["pct_1_2_star_late"] *= 100
    a["gap_pp"] = a.pct_1_2_star_late - a.pct_1_2_star_on_time
    a.round(1).to_csv(ROOT / "results" / "late_effect_same_time.csv")

    # (b) logistic regression with controls
    spl = SplineTransformer(n_knots=6, degree=3).fit(d[["days"]])
    S = pd.DataFrame(spl.transform(d[["days"]]), columns=[f"days_s{i}" for i in range(spl.n_features_out_)], index=d.index)
    top_cat = d.category.value_counts().index[:25]
    X = pd.concat([d[["late"]], S, np.log1p(d[["dist_km", "freight", "price"]]), d[["n_items", "n_sellers"]],
                   pd.get_dummies(d.customer_state, prefix="st", drop_first=True, dtype=int),
                   pd.get_dummies(d.category.where(d.category.isin(top_cat), "other"), prefix="cat", drop_first=True, dtype=int)], axis=1)
    lr = LogisticRegression(max_iter=3000, C=10).fit(X, d.bad)
    # average effect: predicted 1-2 star share if every order were late vs on time (others unchanged)
    p1 = lr.predict_proba(X.assign(late=1))[:, 1].mean(); p0 = lr.predict_proba(X.assign(late=0))[:, 1].mean()
    rng = np.random.default_rng(0); boot = []
    for _ in range(100):
        ix = rng.integers(0, len(d), len(d))
        m = LogisticRegression(max_iter=3000, C=10).fit(X.iloc[ix], d.bad.iloc[ix])
        boot.append(m.predict_proba(X.assign(late=1))[:, 1].mean() - m.predict_proba(X.assign(late=0))[:, 1].mean())
    # (c) does arriving EARLY help? on-time orders only, by days of slack
    on = d[d.late == 0].copy()
    on["slack_band"] = pd.cut(on.slack_days, [-1, 3, 7, 14, 21, 200], labels=["0-3", "3-7", "7-14", "14-21", "21+"])
    c = on.groupby("slack_band", observed=True).agg(orders=("bad", "size"), pct_1_2_star=("bad", "mean"), avg_score=("score", "mean"))
    c["pct_1_2_star"] *= 100
    c.round(2).to_csv(ROOT / "results" / "early_arrival_effect.csv")
    out = {"orders": int(len(d)), "late_share_pct": round(100 * d.late.mean(), 1),
           "odds_ratio_late_with_controls": round(float(np.exp(lr.coef_[0][0])), 2),
           "avg_effect_pp_if_late": round(100 * (p1 - p0), 1),
           "avg_effect_pp_95ci": [round(100 * float(np.percentile(boot, q)), 1) for q in (2.5, 97.5)],
           "kids_orders": int((d.order_id.isin(df[df.kids].order_id)).sum())}
    (ROOT / "results" / "late_effect_summary.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1)); print(a.round(1).to_string()); print(c.round(2).to_string())


if __name__ == "__main__":
    main()
