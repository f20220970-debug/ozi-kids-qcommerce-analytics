"""Excel version for business users: python src/build_workbook.py -> ozi_kids_kpi_workbook.xlsx
Every derived number is a live formula; blue cells are inputs you can change."""
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from run import run

ROOT = Path(__file__).resolve().parents[1]
con, R = run(verbose=False)
BLUE, BOLD, YEL = Font(name="Arial", color="0000FF"), Font(name="Arial", bold=True), PatternFill("solid", fgColor="FFFF00")
wb = Workbook()


def style(ws, widths):
    for row in ws.iter_rows():
        for c in row:
            if c.font != BLUE and not c.font.bold:
                c.font = Font(name="Arial")
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


# ---- 1. Promise what-if
ws = wb.active; ws.title = "Promise what-if"
p = R["03_late_vs_ontime"]; k = p[p.segment == "kids"].set_index("promise")
late_n, ontime_n = int(k.loc["late (missed promised date)", "orders"]), int(k.loc["on time", "orders"])
ws.append(["Kids orders: what happens to bad reviews if fewer deliveries miss the promised date?"]); ws["A1"].font = BOLD
ws.append(["Source: sql/03_late_vs_ontime.sql on 6,573 delivered kids orders with a review (Olist public data)."])
rows = [("Late orders", late_n), ("On-time orders", ontime_n),
        ("% rated 1-2 stars when late", k.loc["late (missed promised date)", "pct_1_2_star"] / 100),
        ("% rated 1-2 stars when on time", k.loc["on time", "pct_1_2_star"] / 100)]
for i, (a, b) in enumerate(rows, 4):
    ws.cell(i, 1, a); c = ws.cell(i, 2, b); c.font = BLUE
    if "%" in a: c.number_format = "0.0%"
ws["A9"] = "Late rate today"; ws["B9"] = "=B4/(B4+B5)"; ws["B9"].number_format = "0.0%"
ws["A10"] = "Target late rate (change me)"; ws["B10"] = 0.03; ws["B10"].font = BLUE; ws["B10"].fill = YEL; ws["B10"].number_format = "0.0%"
ws["A12"] = "1-2 star share today"; ws["B12"] = "=B9*B6+(1-B9)*B7"
ws["A13"] = "1-2 star share at target"; ws["B13"] = "=B10*B6+(1-B10)*B7"
ws["A14"] = "Relative reduction in bad reviews"; ws["B14"] = "=IF(B12=0,0,1-B13/B12)"
for c in ["B12", "B13", "B14"]:
    ws[c].number_format = "0.0%"
ws["A16"] = "Assumes the late/on-time gap is causal; it is an association. Test it (README, experiment 1)."
style(ws, [44, 14])

# ---- 2. SKU coverage (dark-store assortment)
ws = wb.create_sheet("SKU coverage")
sku = con.execute("SELECT product_id, category, count(*) AS units FROM items WHERE is_kids GROUP BY ALL ORDER BY units DESC, product_id").df()
ws.append(["Target share of kids units (change me)", 0.8]); ws["B1"].font = BLUE; ws["B1"].fill = YEL; ws["B1"].number_format = "0%"
ws.append(["SKUs needed", "=MATCH(TRUE,INDEX(E6:E{0}>=B1,0),0)".format(5 + len(sku))])
ws.append(["% of all kids SKUs", f"=B2/COUNTA(A6:A{5 + len(sku)})"]); ws["B3"].number_format = "0.0%"
ws.append([])
ws.append(["product_id", "category", "units", "cumulative units", "cumulative share"])
for c in ws[5]:
    c.font = BOLD
for i, r in enumerate(sku.itertuples(), 6):
    ws.cell(i, 1, r.product_id); ws.cell(i, 2, r.category); ws.cell(i, 3, int(r.units)).font = BLUE
    ws.cell(i, 4, f"=C{i}" if i == 6 else f"=D{i-1}+C{i}")
    ws.cell(i, 5, f"=D{i}/SUM($C$6:$C${5 + len(sku)})").number_format = "0.0%"
style(ws, [36, 26, 10, 16, 16])

# ---- 3. Weekly KPIs with week-on-week change
ws = wb.create_sheet("Weekly KPIs")
w = R["09_weekly_kpis"]
ws.append(list(w.columns) + ["orders WoW %", "late rate 4-wk avg"])
for c in ws[1]:
    c.font = BOLD
for i, r in enumerate(w.itertuples(index=False), 2):
    for j, v in enumerate(r, 1):
        ws.cell(i, j, str(v) if j == 1 else (None if pd.isna(v) else float(v))).font = BLUE
    ws.cell(i, 7, "" if i == 2 else f"=IF(B{i-1}=0,\"\",B{i}/B{i-1}-1)").number_format = "0%"
    ws.cell(i, 8, "" if i < 5 else f"=AVERAGE(D{i-3}:D{i})").number_format = "0.0"
style(ws, [12, 12, 10, 9, 10, 20, 13, 17])

# ---- 4. Notes
ws = wb.create_sheet("Notes")
for line in ["Built exclusively for OZi's PS-II Product / Product Analyst internship by Pavitra Seth.",
             "Data: Olist public e-commerce dataset (~99K real orders, Brazil, 2016-2018). Kids = baby, toys, diapers & hygiene, children's clothes.",
             "This is a proxy for a kids quick-commerce business, not OZi data. Delivery here is days, not minutes; the method transfers.",
             "Blue = input or data from SQL; yellow = change me; black = formula."]:
    ws.append([line])
style(ws, [120])
wb.save(ROOT / "ozi_kids_kpi_workbook.xlsx"); print("saved ozi_kids_kpi_workbook.xlsx")
