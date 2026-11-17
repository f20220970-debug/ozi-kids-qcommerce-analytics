"""Dark-store stocking for kids SKUs: forecast weekly demand, then pick how much to stock.

Real weekly unit sales of the 40 best-selling kids SKUs (Olist, 2017-2018). Each week, using only past weeks:
  1. Forecast demand (last week, 4-week average, 8-week average, exponential smoothing); score by WAPE.
  2. Stock = a Poisson quantile around the forecast at a chosen service level (newsvendor).
  3. Replay 2018 weeks: fill rate (units served / units wanted), stock-out weeks, leftover units.
The service level is a business choice: newsvendor says stock to the critical ratio margin / (margin + holding).
ASSUMPTIONS (labelled): 30% gross margin on a sale; 5% of item price per week to hold an unsold unit.
Run: python src/stock_sim.py -> results/stock_*.csv
"""
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy.stats import poisson

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data"
MARGIN, HOLD = 0.30, 0.05            # ASSUMPTIONS, not data


def weekly():
    con = duckdb.connect()
    w = con.execute(f"""
      WITH k AS (SELECT p.product_id FROM read_csv_auto('{D}/olist_products_dataset.csv') p
                 JOIN read_csv_auto('{D}/product_category_name_translation.csv') t USING (product_category_name)
                 WHERE t.product_category_name_english IN ('baby','toys','diapers_and_hygiene','fashion_childrens_clothes')),
      s AS (SELECT i.product_id, date_trunc('week', o.order_purchase_timestamp)::DATE AS wk, count(*) AS units, avg(i.price) AS price
            FROM read_csv_auto('{D}/olist_order_items_dataset.csv') i JOIN read_csv_auto('{D}/olist_orders_dataset.csv') o USING (order_id)
            WHERE i.product_id IN (SELECT product_id FROM k) AND o.order_status NOT IN ('canceled','unavailable')
              AND o.order_purchase_timestamp BETWEEN '2017-01-02' AND '2018-08-26' GROUP BY ALL),
      top AS (SELECT product_id FROM s GROUP BY 1 ORDER BY sum(units) DESC LIMIT 40)
      SELECT * FROM s WHERE product_id IN (SELECT product_id FROM top)""").df()
    price = w.groupby("product_id").price.mean()
    grid = w.pivot_table(index="wk", columns="product_id", values="units", aggfunc="sum").fillna(0).sort_index()
    allw = pd.date_range(grid.index.min(), grid.index.max(), freq="7D").date
    return grid.reindex(allw, fill_value=0), price


def forecasts(y):
    out = {"last week": y.shift(1), "4-week avg": y.rolling(4).mean().shift(1), "8-week avg": y.rolling(8).mean().shift(1)}
    ses = y.copy() * np.nan; level = y.iloc[:8].mean()
    for i in range(len(y)):
        ses.iloc[i] = level; level = 0.3 * y.iloc[i] + 0.7 * level
    out["exp. smoothing (a=0.3)"] = ses
    # Croston / SBA: for intermittent demand, smooth the size of non-zero weeks and the gap between them separately
    sba = y.copy() * np.nan; z = p = None; q = 1
    for i in range(len(y)):
        sba.iloc[i] = np.nan if z is None else 0.95 * z / p
        if y.iloc[i] > 0:
            z = y.iloc[i] if z is None else 0.2 * y.iloc[i] + 0.8 * z
            p = q if p is None else 0.2 * q + 0.8 * p
            q = 1
        else:
            q += 1
    out["Croston-SBA (intermittent)"] = sba.fillna(0)
    out["always 0 (baseline)"] = y * 0
    return out


def main():
    g, price = weekly()
    test = np.array([pd.Timestamp(d) >= pd.Timestamp("2018-01-01") for d in g.index])
    rows = []
    fc_all = {c: forecasts(g[c]) for c in g.columns}
    for name in fc_all[g.columns[0]]:
        err = sum(np.abs(fc_all[c][name][test] - g[c][test]).sum() for c in g.columns)
        bias = sum((fc_all[c][name][test] - g[c][test]).sum() for c in g.columns)
        rows.append({"forecast": name, "WAPE_pct": round(100 * err / g[test].values.sum(), 1),
                     "bias_pct": round(100 * bias / g[test].values.sum(), 1)})
    fc_tab = pd.DataFrame(rows).sort_values("WAPE_pct"); fc_tab.to_csv(ROOT / "results" / "stock_forecast_accuracy.csv", index=False)
    best = fc_tab[~fc_tab.forecast.str.startswith("always")].forecast.iloc[0]   # 0 wins on WAPE but cannot drive stocking

    crit = MARGIN / (MARGIN + HOLD)
    res = []
    for label, sl in [("stock = forecast (no buffer)", None), ("service level 80%", .80), ("service level 90%", .90),
                      ("newsvendor (%.0f%%)" % (100 * crit), crit), ("service level 97%", .97)]:
        served = demand = left = so_weeks = cells = profit = 0.0
        for c in g.columns:
            f = fc_all[c][best][test].values; y = g[c][test].values
            stock = np.ceil(f) if sl is None else poisson.ppf(sl, np.maximum(f, 0.05))
            s = np.minimum(stock, y); served += s.sum(); demand += y.sum(); left += (stock - s).sum()
            so_weeks += (y > stock).sum(); cells += len(y)
            profit += price[c] * (MARGIN * s.sum() - HOLD * (stock - s).sum())
        res.append({"policy": label, "fill_rate_pct": 100 * served / demand, "stockout_weeks_pct": 100 * so_weeks / cells,
                    "avg_units_stocked_per_sku_week": (served + left) / cells, "leftover_units_per_sku_week": left / cells,
                    "profit_index_brl": profit})
    r = pd.DataFrame(res).round(2); r.to_csv(ROOT / "results" / "stock_policies.csv", index=False)
    S = {"skus": int(g.shape[1]), "weeks_test": int(test.sum()), "best_forecast": best,
         "avg_weekly_units_per_sku_2018": round(float(g[test].values.mean()), 2),
         "weeks_with_zero_sales_pct": round(100 * float((g[test].values == 0).mean()), 1),
         "critical_ratio": round(crit, 3), "assumptions": {"gross_margin": MARGIN, "holding_cost_per_week_of_price": HOLD}}
    (ROOT / "results" / "stock_summary.json").write_text(json.dumps(S, indent=1))
    print(json.dumps(S, indent=1)); print(fc_tab.to_string(index=False)); print(r.to_string(index=False))


if __name__ == "__main__":
    main()
