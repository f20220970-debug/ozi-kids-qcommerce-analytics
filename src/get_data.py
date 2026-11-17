"""Downloads the Olist public e-commerce dataset (official Olist GitHub repo) into data/.  python src/get_data.py"""
import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets/"
FILES = ["olist_orders_dataset", "olist_order_items_dataset", "olist_products_dataset", "olist_order_reviews_dataset",
         "olist_customers_dataset", "product_category_name_translation", "olist_sellers_dataset", "olist_geolocation_dataset"]
DATA = Path(__file__).resolve().parents[1] / "data"
DATA.mkdir(exist_ok=True)
for f in FILES:
    out = DATA / f"{f}.csv"
    if not out.exists():
        print("downloading", f)
        urllib.request.urlretrieve(BASE + f + ".csv", out)
print("data ready")
