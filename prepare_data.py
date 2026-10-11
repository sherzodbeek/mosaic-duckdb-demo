"""
Join the Olist CSVs into two Parquet files, entirely inside DuckDB:

  orders.parquet   one row per delivered order item (fact table for the dashboard)
  reviews.parquet  one row per order that has a written review (for Embedding Atlas)

    python prepare_data.py --src data/synthetic          # synthetic CSVs
    python prepare_data.py --src ~/Downloads/olist       # real Kaggle CSVs
"""
import argparse
import time
from pathlib import Path

import duckdb


def main(src: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    for name, file in {
        "orders_raw": "olist_orders_dataset.csv",
        "items": "olist_order_items_dataset.csv",
        "customers": "olist_customers_dataset.csv",
        "products": "olist_products_dataset.csv",
        "translation": "product_category_name_translation.csv",
        "reviews_raw": "olist_order_reviews_dataset.csv",
    }.items():
        con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_csv('{src / file}', header=true)")

    t0 = time.perf_counter()
    con.execute("""
        CREATE TABLE review AS            -- real data has a few orders with >1 review: keep the latest
        SELECT order_id,
               arg_max(review_score, review_creation_date)            AS review_score,
               arg_max(review_comment_message, review_creation_date)  AS review_text
        FROM reviews_raw GROUP BY order_id
    """)
    con.execute(f"""
        COPY (
          SELECT i.order_id,
                 o.order_purchase_timestamp::TIMESTAMP                                  AS purchase_ts,
                 date_trunc('week', o.order_purchase_timestamp::TIMESTAMP)::DATE         AS purchase_week,
                 c.customer_state,
                 coalesce(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
                 i.price::DOUBLE                                                         AS price,
                 i.freight_value::DOUBLE                                                 AS freight_value,
                 round(date_diff('hour', o.order_purchase_timestamp::TIMESTAMP,
                                 o.order_delivered_customer_date::TIMESTAMP) / 24.0, 1)  AS delivery_days,
                 round(date_diff('hour', o.order_estimated_delivery_date::TIMESTAMP,
                                 o.order_delivered_customer_date::TIMESTAMP) / 24.0, 1)  AS delay_days,
                 r.review_score::INTEGER                                                 AS review_score
          FROM items i
          JOIN orders_raw o  USING (order_id)
          JOIN customers c   USING (customer_id)
          LEFT JOIN products p    USING (product_id)
          LEFT JOIN translation t USING (product_category_name)
          LEFT JOIN review r      USING (order_id)
          WHERE o.order_status = 'delivered' AND o.order_delivered_customer_date IS NOT NULL
        ) TO '{out / "orders.parquet"}' (FORMAT parquet, COMPRESSION zstd)
    """)
    con.execute(f"""
        COPY (
          SELECT r.order_id, r.review_score, r.review_text, f.customer_state, f.category,
                 f.delay_days, (f.delay_days > 0) AS late
          FROM review r
          JOIN (SELECT order_id, any_value(customer_state) AS customer_state,
                       any_value(category) AS category, any_value(delay_days) AS delay_days
                FROM read_parquet('{out / "orders.parquet"}') GROUP BY order_id) f USING (order_id)
          WHERE r.review_text IS NOT NULL AND length(trim(r.review_text)) > 0
        ) TO '{out / "reviews.parquet"}' (FORMAT parquet)
    """)
    n_items = con.execute(f"SELECT count(*) FROM '{out / 'orders.parquet'}'").fetchone()[0]
    n_rev = con.execute(f"SELECT count(*) FROM '{out / 'reviews.parquet'}'").fetchone()[0]
    print(f"orders.parquet: {n_items:,} rows | reviews.parquet: {n_rev:,} rows "
          f"| {time.perf_counter() - t0:.1f}s in DuckDB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=Path("data/synthetic"))
    ap.add_argument("--out", type=Path, default=Path("web"))
    a = ap.parse_args()
    main(a.src.expanduser(), a.out)
