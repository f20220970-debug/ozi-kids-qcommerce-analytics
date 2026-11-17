"""ETA promise model: predict delivery time, then choose what ETA to SHOW so promises are kept.

Why: finding 2 says a missed promise is what drives 1-2 star reviews. The marketplace in this data promised
~24 days and delivered in ~12, yet still missed ~8% of promises. A model can promise less AND keep more.

Method (conformalized quantile regression):
  1. Features known at checkout: seller-to-customer distance, states, weight/volume, freight, price, items,
     sellers, time of order, and each seller's past handling time (computed from training data only).
  2. Gradient-boosted quantile models (p50/p80/p90) trained on orders before Nov 2017.
  3. Calibration on Nov-Dec 2017: add the smallest shift so the shown ETA is kept for a target share of orders.
  4. Test on Jan-Aug 2018 (future orders the model never saw): promise-kept rate vs days promised,
     compared with the marketplace's own promise.
Run: python src/eta_model.py -> results/eta_*.csv, docs/eta_tradeoff.png
"""
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data"


def load():
    con = duckdb.connect()
    q = f"""
    WITH geo AS (SELECT geolocation_zip_code_prefix::INT AS zip, median(geolocation_lat) AS lat, median(geolocation_lng) AS lng
                 FROM read_csv_auto('{D}/olist_geolocation_dataset.csv') GROUP BY 1),
    p AS (SELECT p.product_id, p.product_weight_g AS w, p.product_length_cm * p.product_height_cm * p.product_width_cm AS vol,
                 coalesce(t.product_category_name_english,'') IN ('baby','toys','diapers_and_hygiene','fashion_childrens_clothes') AS kids
          FROM read_csv_auto('{D}/olist_products_dataset.csv') p
          LEFT JOIN read_csv_auto('{D}/product_category_name_translation.csv') t USING (product_category_name)),
    s AS (SELECT s.seller_id, s.seller_state, g.lat AS slat, g.lng AS slng
          FROM read_csv_auto('{D}/olist_sellers_dataset.csv') s LEFT JOIN geo g ON g.zip = s.seller_zip_code_prefix::INT),
    o AS (SELECT o.order_id, o.order_purchase_timestamp AS t0, o.order_approved_at AS t_appr, o.order_delivered_carrier_date AS t_carrier,
                 o.order_delivered_customer_date AS t1, o.order_estimated_delivery_date AS t_est,
                 c.customer_state, g.lat AS clat, g.lng AS clng
          FROM read_csv_auto('{D}/olist_orders_dataset.csv') o
          JOIN read_csv_auto('{D}/olist_customers_dataset.csv') c USING (customer_id)
          LEFT JOIN geo g ON g.zip = c.customer_zip_code_prefix::INT
          WHERE o.order_status = 'delivered' AND o.order_delivered_customer_date IS NOT NULL)
    SELECT o.order_id, o.t0, o.t_carrier, o.t1, o.t_est, o.customer_state, any_value(o.clat) clat, any_value(o.clng) clng,
           arg_max(s.seller_id, i.price) AS seller_id, arg_max(s.seller_state, i.price) AS seller_state,
           max(2 * 6371 * asin(sqrt(pow(sin(radians(o.clat - s.slat) / 2), 2) + cos(radians(s.slat)) * cos(radians(o.clat))
               * pow(sin(radians(o.clng - s.slng) / 2), 2)))) AS dist_km,
           sum(p.w) AS weight_g, sum(p.vol) AS vol_cm3, sum(i.freight_value) AS freight, sum(i.price) AS price,
           count(*) AS n_items, count(DISTINCT i.seller_id) AS n_sellers, bool_or(p.kids) AS kids
    FROM o JOIN read_csv_auto('{D}/olist_order_items_dataset.csv') i USING (order_id)
    JOIN s USING (seller_id) JOIN p USING (product_id)
    GROUP BY o.order_id, o.t0, o.t_carrier, o.t1, o.t_est, o.customer_state
    """
    df = con.execute(q).df()
    df["days"] = (df.t1 - df.t0).dt.total_seconds() / 86400
    df["promised_days"] = (df.t_est - df.t0).dt.total_seconds() / 86400
    df["handling_days"] = (df.t_carrier - df.t0).dt.total_seconds() / 86400
    df["dow"], df["hour"], df["month"] = df.t0.dt.dayofweek, df.t0.dt.hour, df.t0.dt.month
    df["same_state"] = (df.seller_state == df.customer_state).astype(int)
    return df[(df.days > 0) & (df.days < 120)].reset_index(drop=True)


CAT = ["customer_state", "seller_state"]
NUM = ["dist_km", "weight_g", "vol_cm3", "freight", "price", "n_items", "n_sellers", "dow", "hour",
       "same_state", "seller_prev_handling", "seller_prev_orders"]


def add_seller_history(df):
    """Seller's median handling time over its PREVIOUS orders only (strictly earlier purchases).
    A first version used each seller's training-period median, which includes the order itself: in-sample
    error was 3.6 days but out-of-time error 8.1 days. This version removes that leak."""
    df = df.sort_values("t0").copy()
    g = df.groupby("seller_id").handling_days
    df["seller_prev_handling"] = g.transform(lambda s: s.expanding().median().shift(1))
    df["seller_prev_orders"] = df.groupby("seller_id").cumcount()
    return df.sort_index()


def features(df, train):
    X = df.copy()
    for c in CAT:
        X[c] = pd.Categorical(X[c].where(X[c].isin(train[c].unique())), categories=sorted(train[c].dropna().unique()))
    return X[CAT + NUM]


def main():
    df = add_seller_history(load())
    tr = df[df.t0 < "2017-11-01"]
    ca = df[(df.t0 >= "2017-11-01") & (df.t0 < "2018-01-01")]
    te = df[df.t0 >= "2018-01-01"]
    Xtr, Xca, Xte = features(tr, tr), features(ca, tr), features(te, tr)
    models = {}
    for q in [0.5, 0.8, 0.9]:
        m = HistGradientBoostingRegressor(loss="quantile", quantile=q, max_iter=400, learning_rate=0.06,
                                          max_leaf_nodes=31, categorical_features="from_dtype", random_state=0)
        models[q] = m.fit(Xtr, tr.days)
    p50 = models[0.5].predict(Xte)
    mae = float(np.mean(np.abs(p50 - te.days)))
    base_mae = float(np.mean(np.abs(np.median(tr.days) - te.days)))
    rt = tr.groupby(["seller_state", "customer_state"]).days.median().rename("r")
    route_mae = float(np.mean(np.abs(te.join(rt, on=["seller_state", "customer_state"]).r.fillna(np.median(tr.days)) - te.days)))

    rows = []
    # the marketplace's own promise
    kept = (te.days <= te.promised_days).mean()
    rows.append({"policy": "marketplace promise (actual)", "target_kept": None, "avg_days_promised": te.promised_days.mean(),
                 "promise_kept_pct": 100 * kept, "kids_promise_kept_pct": 100 * (te.days <= te.promised_days)[te.kids].mean()})
    # conformalized quantile ETAs: calibrate a shift on Nov-Dec 2017 so that `target` of promises are kept
    for q, target in [(0.5, 0.80), (0.8, 0.90), (0.9, 0.93), (0.9, 0.95), (0.9, 0.97)]:
        resid = ca.days.values - models[q].predict(Xca)
        shift = np.quantile(resid, target)        # ETA = ceil(model + shift) is kept for `target` of calib orders
        eta = np.ceil(models[q].predict(Xte) + shift)
        rows.append({"policy": f"model p{int(q*100)} + calibrated buffer", "target_kept": 100 * target,
                     "avg_days_promised": eta.mean(), "promise_kept_pct": 100 * (te.days <= eta).mean(),
                     "kids_promise_kept_pct": 100 * (te.days <= eta)[te.kids].mean()})
    # rolling (adaptive) calibration: each week, set the buffer from orders bought 4-8 weeks earlier
    # (old enough to have been delivered), so the ETA keeps up with drift (e.g. a slow Black Friday season).
    allX = features(df, tr)
    pq = {q: models[q].predict(allX) for q in [0.5, 0.8, 0.9]}
    wk = df.t0.dt.to_period("W").dt.start_time
    for q, target in [(0.5, 0.80), (0.8, 0.90), (0.9, 0.93), (0.9, 0.95), (0.9, 0.97)]:
        res_all = df.days.values - pq[q]
        eta = np.full(len(df), np.nan)
        for w in sorted(wk[df.t0 >= "2018-01-01"].unique()):
            win = (wk >= w - pd.Timedelta(weeks=8)) & (wk < w - pd.Timedelta(weeks=4))
            idx = (wk == w).values
            eta[idx] = np.ceil(pq[q][idx] + np.quantile(res_all[win.values], target))
        e = eta[(df.t0 >= "2018-01-01").values]
        rows.append({"policy": f"model p{int(q*100)} + rolling weekly buffer", "target_kept": 100 * target,
                     "avg_days_promised": e.mean(), "promise_kept_pct": 100 * (te.days.values <= e).mean(),
                     "kids_promise_kept_pct": 100 * (te.days.values <= e)[te.kids.values].mean()})
        if (q, target) == (0.8, 0.90):
            rolling93 = e
    # a naive rule: one fixed promise for everyone set to keep the same share as the marketplace
    fixed = np.ceil(np.quantile(ca.days, kept))
    rows.append({"policy": f"same promise for everyone ({int(fixed)} days)", "target_kept": 100 * kept, "avg_days_promised": fixed,
                 "promise_kept_pct": 100 * (te.days <= fixed).mean(), "kids_promise_kept_pct": 100 * (te.days <= fixed)[te.kids].mean()})
    res = pd.DataFrame(rows).round(1)
    res.to_csv(ROOT / "results" / "eta_tradeoff.csv", index=False)

    # how much shorter can the promise be at the marketplace's own reliability?
    resid = ca.days.values - models[0.9].predict(Xca)
    eta_match = np.ceil(models[0.9].predict(Xte) + np.quantile(resid, kept))
    summary = {"_note": "model_*_same_reliability uses the buffer fixed once on Nov-Dec 2017", "train_orders": len(tr), "calib_orders": len(ca), "test_orders": len(te),
               "p50_mae_days": round(mae, 2), "baseline_mae_global_median": round(base_mae, 2), "baseline_mae_route_median": round(route_mae, 2),
               "marketplace_avg_promise_days": round(float(te.promised_days.mean()), 1), "marketplace_kept_pct": round(100 * kept, 1),
               "model_avg_promise_days_same_reliability": round(float(eta_match.mean()), 1),
               "model_kept_pct_same_reliability": round(100 * float((te.days <= eta_match).mean()), 1)}
    from sklearn.inspection import permutation_importance
    pi = permutation_importance(models[0.5], Xte.sample(5000, random_state=0), te.days.loc[Xte.sample(5000, random_state=0).index],
                                scoring="neg_mean_absolute_error", n_repeats=3, random_state=0)
    summary["feature_importance_mae_increase_days"] = dict(sorted(zip(Xte.columns, np.round(pi.importances_mean, 2)), key=lambda x: -x[1])[:6])
    # monthly view of the chosen rolling policy vs the marketplace
    # week-block bootstrap: is the chosen ETA (p80, rolling, 90% target) really better than the marketplace promise?
    kept_m = (te.days.values <= rolling93).astype(float); kept_b = (te.days.values <= te.promised_days.values).astype(float)
    tw = te.t0.dt.to_period("W").astype(str).values; weeks = np.unique(tw); rng = np.random.default_rng(0)
    by = {w: np.flatnonzero(tw == w) for w in weeks}; diffs, pdays = [], []
    for _ in range(1000):
        ix = np.concatenate([by[w] for w in rng.choice(weeks, len(weeks))])
        diffs.append(kept_m[ix].mean() - kept_b[ix].mean()); pdays.append(rolling93[ix].mean() - te.promised_days.values[ix].mean())
    summary["chosen_policy"] = "p80 model + weekly rolling buffer, 90% target"
    summary["chosen_avg_promise_days"] = round(float(rolling93.mean()), 1)
    summary["chosen_kept_pct"] = round(100 * float(kept_m.mean()), 1)
    summary["kept_diff_pp_vs_marketplace_95ci"] = [round(100 * float(np.percentile(diffs, p)), 1) for p in (2.5, 50, 97.5)]
    summary["promise_days_diff_vs_marketplace_95ci"] = [round(float(np.percentile(pdays, p)), 1) for p in (2.5, 50, 97.5)]
    summary["missed_promises_marketplace_pct"] = round(100 * (1 - float(kept_b.mean())), 1)
    summary["missed_promises_model_pct"] = round(100 * (1 - float(kept_m.mean())), 1)
    mon = pd.DataFrame({"month": te.t0.dt.strftime("%Y-%m").values, "actual": te.days.values, "mp": te.promised_days.values, "eta": rolling93})
    mon = mon.groupby("month").apply(lambda g: pd.Series({"orders": len(g), "marketplace_avg_promise": g.mp.mean(),
        "marketplace_kept_pct": 100 * (g.actual <= g.mp).mean(), "model_avg_promise": g.eta.mean(),
        "model_kept_pct": 100 * (g.actual <= g.eta).mean()}), include_groups=False).round(1)
    mon.to_csv(ROOT / "results" / "eta_by_month.csv"); print(mon.to_string())
    (ROOT / "results" / "eta_summary.json").write_text(json.dumps(summary, indent=1))
    (ROOT / "results" / "eta_summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1)); print(res.to_string(index=False))

    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for key, col, lab in [("calibrated buffer", "#93c5fd", "model ETA, buffer fixed once"), ("rolling", "#1d4ed8", "model ETA, buffer re-set weekly")]:
        m = res[res.policy.str.contains(key)]
        ax.plot(m.avg_days_promised, m.promise_kept_pct, "o-", color=col, label=lab)
    b = res.iloc[0]; f = res.iloc[-1]
    ax.scatter([b.avg_days_promised], [b.promise_kept_pct], color="#e4572e", s=80, zorder=3, label="marketplace's actual promise")
    ax.scatter([f.avg_days_promised], [f.promise_kept_pct], color="#9aa5b1", s=80, zorder=3, label="same promise for everyone")
    ax.set_xlabel("average days promised to the customer"); ax.set_ylabel("% of promises kept (Jan-Aug 2018, unseen)")
    ax.set_title("Same promise length, more promises kept"); ax.legend(); ax.grid(alpha=.3)
    plt.tight_layout(); plt.savefig(ROOT / "docs" / "eta_tradeoff.png", dpi=130)


if __name__ == "__main__":
    main()
