"""
Olist delivery & satisfaction dashboard, written with Mosaic vgplot's Python API.

Every mark below is a Mosaic *client*: it does not receive rows, it publishes a
SQL query (bin + count, group-by, 2-D density...) that DuckDB executes. Brushing
any view updates one shared crossfilter Selection; the coordinator then re-issues
only the queries of the *other* views with the new WHERE clause.

Run three ways:
  • Jupyter:  `from dashboard import view; view`           (DuckDB in the Python kernel)
  • Export:   `python dashboard.py` → web/dashboard.json  (consumed by web/index.html)
  • Browser:  serve web/ and open index.html             (DuckDB-WASM in the tab)
"""
import json
from pathlib import Path

import vgplot as vg

orders = vg.parquet("orders.parquet")       # table name = variable name → "orders"
# Bar clicks go into their own selections so each bar chart can highlight what was
# clicked; `include` folds them into the crossfilter that every view filters by.
pick_score = vg.selection.single()
pick_state = vg.selection.single()
brush = vg.selection.crossfilter(include=[pick_score, pick_state])

BLUE, RED = "#3b6fb6", "#c4423b"

view = vg.vconcat(
    vg.hconcat(
        vg.menu(label="Category", source="orders", column="category", bind=brush),
        vg.hspace(16),
        vg.menu(label="State", source="orders", column="customer_state", bind=brush),
    ),
    vg.vspace(8),
    # 1. Temporal overview: weekly order volume; drag to select a time window.
    vg.plot(
        vg.area_y(orders, x="purchase_week", y=vg.count(), filter_by=brush,
                  fill=BLUE, fill_opacity=0.85, curve="step"),
        vg.interval_x(bind=brush),
        vg.x_domain("Fixed"), vg.y_label("Order items / week"), vg.x_label(None),
        vg.width(860), vg.height(170), vg.margin_left(56),
    ),
    vg.hconcat(
        # 2. How late was the delivery vs the promised date? (negative = early)
        vg.plot(
            vg.rect_y(orders, x=vg.bin("delay_days", steps=120), y=vg.count(), filter_by=brush,
                      fill=vg.sql("CASE WHEN delay_days > 0 THEN 'late' ELSE 'on time' END"),
                      inset_left=0.5, inset_right=0.5),
            vg.rule_x([0], stroke="currentColor", stroke_opacity=0.5),
            vg.interval_x(bind=brush),
            vg.x_domain("Fixed"), vg.color_domain(["on time", "late"]), vg.color_range([BLUE, RED]),
            vg.x_label("Days vs. estimated delivery date →"), vg.y_label("Items"),
            vg.width(430), vg.height(200), vg.margin_left(56),
        ),
        # 3. Review score distribution; click a bar (shift-click for several).
        vg.plot(
            vg.bar_y(orders, x="review_score", y=vg.count(), filter_by=brush, fill=BLUE),
            vg.toggle_x(bind=pick_score),
            vg.highlight(by=pick_score),
            vg.x_domain("Fixed"), vg.x_label("Review score"), vg.y_label("Items"),
            vg.width(430), vg.height(200), vg.margin_left(56),
        ),
    ),
    vg.hconcat(
        # 4. Where are the customers? Top states by volume.
        vg.plot(
            vg.bar_x(orders, x=vg.count(), y="customer_state", filter_by=brush, fill=BLUE,
                     sort={"y": "-x", "limit": 12}),
            vg.toggle_y(bind=pick_state),
            vg.highlight(by=pick_state),
            vg.x_label("Items →"), vg.y_label(None),
            vg.width(430), vg.height(260), vg.margin_left(40),
        ),
        # 5. Price vs freight as a density raster: DuckDB bins 110k+ points into a
        #    pixel grid; only the grid (not the points) crosses to the browser.
        vg.plot(
            vg.raster(orders, x="price", y="freight_value", fill="density",
                      filter_by=brush, pixel_size=2, bandwidth=1),
            vg.interval_xy(bind=brush),
            vg.x_domain([0, 600]), vg.y_domain([0, 80]),
            vg.color_scale("sqrt"), vg.color_scheme("blues"),
            vg.x_label("Item price (BRL) →"), vg.y_label("↑ Freight (BRL)"),
            vg.width(430), vg.height(260), vg.margin_left(56),
        ),
    ),
)

if __name__ == "__main__":
    out = Path(__file__).parent / "web" / "dashboard.json"
    spec = view.to_dict()
    out.write_text(json.dumps(spec, indent=2))
    print(f"wrote {out} ({len(spec['vconcat'])} rows, data: {list(spec.get('data', {}))})")
