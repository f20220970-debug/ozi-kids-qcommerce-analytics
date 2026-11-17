"""Sanity checks on the SQL: row counts, no double counting, and the headline findings hold."""
import pytest

from run import run


@pytest.fixture(scope="module")
def res():
    con, out = run(verbose=False)
    return con, out


def test_one_row_per_order(res):
    con, _ = res
    n, d = con.execute("SELECT count(*), count(DISTINCT order_id) FROM orders").fetchone()
    assert n == d and n > 95_000


def test_kids_share_reasonable(res):
    _, out = res
    b = out["01_base"].iloc[0]
    assert 0.04 < b.kids_orders / b.orders < 0.10


def test_late_orders_rated_worse(res):
    _, out = res
    k = out["03_late_vs_ontime"].query("segment == 'kids'").set_index("promise")
    assert k.loc["late (missed promised date)", "pct_1_2_star"] > 4 * k.loc["on time", "pct_1_2_star"]


def test_repeat_rate_counts_one_time_buyers(res):
    _, out = res
    # Olist is a marketplace with ~3% repeat; a bug that drops one-time buyers gives ~70%
    assert (out["04_repeat"].pct_repeat_180d < 10).all()


def test_assortment_monotonic(res):
    _, out = res
    a = out["05_assortment"]
    assert a.skus_needed.is_monotonic_increasing and a.skus_needed.iloc[-1] <= a.total_skus.iloc[0]


def test_seller_history_uses_only_past_orders():
    import pandas as pd
    from eta_model import add_seller_history
    df = pd.DataFrame({"seller_id": ["a", "a", "a", "b"], "handling_days": [1.0, 5.0, 9.0, 2.0],
                       "t0": pd.to_datetime(["2018-01-03", "2018-01-01", "2018-01-02", "2018-01-01"])})
    h = add_seller_history(df)
    assert pd.isna(h.loc[1, "seller_prev_handling"])        # seller a's first order has no history
    assert h.loc[2, "seller_prev_handling"] == 5.0           # second order sees only the first
    assert h.loc[0, "seller_prev_handling"] == 7.0           # third sees median(5, 9), never its own value
