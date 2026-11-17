"""Runs every SQL file in sql/ in order with DuckDB and saves the result of each to results/<name>.csv.
Run from the repo root:  python src/run.py
"""
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]


def run(verbose=True):
    con = duckdb.connect()
    import os
    os.chdir(ROOT)
    (ROOT / "results").mkdir(exist_ok=True)
    out = {}
    for f in sorted((ROOT / "sql").glob("*.sql")):
        stmts = [s for s in f.read_text().split(";") if s.strip() and not all(l.strip().startswith("--") or not l.strip() for l in s.splitlines())]
        for s in stmts[:-1]:
            con.execute(s)
        df = con.execute(stmts[-1]).df()
        df.to_csv(ROOT / "results" / f"{f.stem}.csv", index=False)
        out[f.stem] = df
        if verbose and f.stem != "09_weekly_kpis":
            print(f"\n== {f.stem}\n{df.to_string(index=False)}")
    return con, out


if __name__ == "__main__":
    run()
