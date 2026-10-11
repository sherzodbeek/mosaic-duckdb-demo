"""
Generate synthetic CSVs with the same file names and columns as the Kaggle
Olist dataset (olistbr/brazilian-ecommerce). Use this when the real data is not
at hand, or with --orders 2000000 to stress-test Mosaic at millions of rows.

    python generate_synthetic_olist.py --out data/synthetic --orders 100000

The real dataset drops in unchanged: point prepare_data.py at its folder.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

STATES = {  # share of customers, typical delivery days (rough shape of real Olist)
    "SP": (0.42, 8), "RJ": (0.13, 15), "MG": (0.117, 12), "RS": (0.055, 15),
    "PR": (0.051, 12), "SC": (0.037, 14), "BA": (0.034, 19), "DF": (0.022, 13),
    "ES": (0.020, 15), "GO": (0.020, 15), "PE": (0.017, 18), "CE": (0.013, 21),
    "PA": (0.010, 23), "MT": (0.009, 18), "MA": (0.008, 21), "MS": (0.007, 15),
    "PB": (0.005, 20), "PI": (0.005, 19), "RN": (0.005, 19), "AL": (0.004, 24),
    "SE": (0.003, 21), "TO": (0.003, 17), "RO": (0.003, 19), "AM": (0.0015, 26),
    "AC": (0.0008, 21), "AP": (0.0007, 27), "RR": (0.0005, 29),
}
CATEGORIES = {  # pt name -> (en name, share, median price BRL, median weight g)
    "cama_mesa_banho": ("bed_bath_table", 0.10, 80, 1500),
    "beleza_saude": ("health_beauty", 0.09, 110, 800),
    "esporte_lazer": ("sports_leisure", 0.08, 90, 1200),
    "moveis_decoracao": ("furniture_decor", 0.075, 85, 3000),
    "informatica_acessorios": ("computers_accessories", 0.07, 115, 700),
    "utilidades_domesticas": ("housewares", 0.065, 75, 2000),
    "relogios_presentes": ("watches_gifts", 0.055, 200, 400),
    "telefonia": ("telephony", 0.04, 70, 300),
    "ferramentas_jardim": ("garden_tools", 0.04, 100, 2500),
    "automotivo": ("auto", 0.04, 120, 1800),
    "brinquedos": ("toys", 0.04, 85, 1100),
    "cool_stuff": ("cool_stuff", 0.035, 160, 2000),
    "perfumaria": ("perfumery", 0.03, 110, 500),
    "bebes": ("baby", 0.03, 120, 2500),
    "eletronicos": ("electronics", 0.025, 60, 400),
    "papelaria": ("stationery", 0.022, 75, 900),
    "fashion_bolsas_e_acessorios": ("fashion_bags_accessories", 0.018, 70, 400),
    "pet_shop": ("pet_shop", 0.017, 90, 2000),
    "moveis_escritorio": ("office_furniture", 0.015, 160, 9000),
    "eletrodomesticos": ("home_appliances", 0.01, 180, 5000),
}
FRAGMENTS = {  # review comments are assembled from these, so the text has real variety
    # English stand-ins for the real (Portuguese) Olist comments, so the demo reads without translation.
    "praise": ["Excellent product", "Very good", "Loved it", "Great product", "Highly recommend",
               "Really liked it", "Perfect", "Exceeded my expectations"],
    "fast": ["arrived before the deadline", "fast delivery", "arrived well packaged", "delivered on time",
             "arrived super fast"],
    "good_product": ["very good quality", "looks just like the photo", "helpful seller", "worth the price",
                     "great quality material"],
    "meh": ["Product is ok", "Reasonable", "Nothing special", "Does the basics", "So-so"],
    "meh_detail": ["took a while to arrive", "simple packaging", "average quality", "expected more",
                   "could be cheaper"],
    "late": ["I did not receive the product", "Late delivery", "Still nothing so far", "Product never arrived",
             "Past the delivery date and nothing"],
    "late_detail": ["nobody answers", "tracking stuck for days", "I want to cancel the order",
                    "never buying here again", "terrible delivery service"],
    "defect": ["Came with a defect", "Product is broken", "Different from the listing", "Wrong item sent",
               "Missing a part"],
    "defect_detail": ["I want to return it", "I want my money back", "terrible customer service",
                      "very poor quality", "does not work"],
}


def compose_comment(rng, score: int, late: bool) -> str:
    pick = lambda k: FRAGMENTS[k][rng.integers(len(FRAGMENTS[k]))]
    if score >= 4:
        parts = [pick("praise"), pick("fast" if rng.random() < 0.5 else "good_product")]
    elif score == 3:
        parts = [pick("meh"), pick("meh_detail")]
    else:
        kind = "late" if (late and rng.random() < 0.85) or (not late and rng.random() < 0.15) else "defect"
        parts = [pick(kind), pick(kind + "_detail")]
    if rng.random() < 0.3:
        extra = pick("good_product" if score >= 4 else "meh_detail" if score == 3 else
                     "late_detail" if parts[0] in FRAGMENTS["late"] else "defect_detail")
        if extra not in parts:
            parts.append(extra)
    return ", ".join(parts) + rng.choice([".", "!", ""])


def main(out: Path, n_orders: int, seed: int) -> None:
    rng = np.random.default_rng(seed)
    out.mkdir(parents=True, exist_ok=True)

    # --- products & category translation -----------------------------------
    cat_pt = np.array(list(CATEGORIES))
    cat_p = np.array([v[1] for v in CATEGORIES.values()]); cat_p /= cat_p.sum()
    n_products = max(1000, n_orders // 3)
    prod_cat = rng.choice(cat_pt, n_products, p=cat_p)
    weight = np.array([CATEGORIES[c][3] for c in prod_cat]) * rng.lognormal(0, 0.6, n_products)
    base_price = np.array([CATEGORIES[c][2] for c in prod_cat]) * rng.lognormal(0, 0.7, n_products)
    product_ids = np.char.add("p", np.arange(n_products).astype(str))
    pd.DataFrame({
        "product_id": product_ids, "product_category_name": prod_cat,
        "product_name_lenght": rng.integers(10, 70, n_products),
        "product_description_lenght": rng.integers(50, 3000, n_products),
        "product_photos_qty": rng.integers(1, 6, n_products),
        "product_weight_g": weight.round(), "product_length_cm": rng.integers(10, 80, n_products),
        "product_height_cm": rng.integers(2, 60, n_products), "product_width_cm": rng.integers(8, 60, n_products),
    }).to_csv(out / "olist_products_dataset.csv", index=False)
    pd.DataFrame({"product_category_name": cat_pt,
                  "product_category_name_english": [v[0] for v in CATEGORIES.values()]}
                 ).to_csv(out / "product_category_name_translation.csv", index=False)

    # --- customers -----------------------------------------------------------
    st = np.array(list(STATES)); st_p = np.array([v[0] for v in STATES.values()]); st_p /= st_p.sum()
    cust_state = rng.choice(st, n_orders, p=st_p)
    customer_ids = np.char.add("c", np.arange(n_orders).astype(str))
    pd.DataFrame({
        "customer_id": customer_ids, "customer_unique_id": customer_ids,
        "customer_zip_code_prefix": rng.integers(1000, 99999, n_orders),
        "customer_city": "cidade", "customer_state": cust_state,
    }).to_csv(out / "olist_customers_dataset.csv", index=False)

    # --- orders: growth trend + weekly cycle + Black Friday 2017 spike -------
    days = pd.date_range("2016-10-01", "2018-08-31", freq="D")
    t = np.linspace(0, 1, len(days))
    w = (0.15 + t ** 1.3) * np.where(days.dayofweek < 5, 1.0, 0.8)
    w[(days >= "2017-11-24") & (days <= "2017-11-27")] *= 4
    day_idx = rng.choice(len(days), n_orders, p=w / w.sum())
    purchase = days[day_idx] + pd.to_timedelta(rng.integers(0, 86400, n_orders), unit="s")

    typical = np.array([STATES[s][1] for s in cust_state])
    delivery_days = typical * rng.lognormal(0, 0.45, n_orders)
    estimated_days = typical * 1.9 + rng.normal(4, 3, n_orders).clip(0)
    # late Nov 2017 and Feb-Mar 2018 carrier backlogs → more late deliveries
    backlog = ((purchase >= "2017-11-20") & (purchase <= "2017-12-15")) | \
              ((purchase >= "2018-02-15") & (purchase <= "2018-03-20"))
    delivery_days = np.where(backlog, delivery_days * 1.6, delivery_days)

    status = rng.choice(["delivered", "shipped", "canceled", "unavailable"], n_orders,
                        p=[0.97, 0.012, 0.009, 0.009])
    delivered = purchase + pd.to_timedelta(delivery_days, unit="D")
    estimated = (purchase + pd.to_timedelta(estimated_days, unit="D")).normalize()
    order_ids = np.char.add("o", np.arange(n_orders).astype(str))
    pd.DataFrame({
        "order_id": order_ids, "customer_id": customer_ids, "order_status": status,
        "order_purchase_timestamp": purchase.strftime("%Y-%m-%d %H:%M:%S"),
        "order_approved_at": (purchase + pd.Timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
        "order_delivered_carrier_date": (purchase + pd.Timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),
        "order_delivered_customer_date": pd.Series(delivered.strftime("%Y-%m-%d %H:%M:%S")).where(status == "delivered"),
        "order_estimated_delivery_date": estimated.strftime("%Y-%m-%d %H:%M:%S"),
    }).to_csv(out / "olist_orders_dataset.csv", index=False)

    # --- order items (1-4 per order, mostly 1) -------------------------------
    n_items = rng.choice([1, 2, 3, 4], n_orders, p=[0.9, 0.07, 0.02, 0.01])
    it_order = np.repeat(np.arange(n_orders), n_items)
    it_seq = np.concatenate([np.arange(1, k + 1) for k in n_items])
    it_prod = rng.integers(0, n_products, len(it_order))
    price = (base_price[it_prod] * rng.lognormal(0, 0.1, len(it_order))).round(2)
    freight = (8 + weight[it_prod] / 450 * (typical[it_order] / 10) * rng.lognormal(0, 0.25, len(it_order))).round(2)
    pd.DataFrame({
        "order_id": order_ids[it_order], "order_item_id": it_seq, "product_id": product_ids[it_prod],
        "seller_id": np.char.add("s", rng.integers(0, 3000, len(it_order)).astype(str)),
        "shipping_limit_date": (purchase[it_order] + pd.Timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S"),
        "price": price, "freight_value": freight,
    }).to_csv(out / "olist_order_items_dataset.csv", index=False)

    # --- reviews: score driven by lateness, as in the real data --------------
    late = (delivered > estimated) & (status == "delivered")
    p_on = np.array([0.08, 0.025, 0.075, 0.2, 0.62]); p_late = np.array([0.5, 0.1, 0.12, 0.1, 0.18])
    p_none = np.array([0.6, 0.1, 0.1, 0.1, 0.1])
    score = np.empty(n_orders, dtype=int)
    for mask, p in ((late, p_late), (~late & (status == "delivered"), p_on), (status != "delivered", p_none)):
        score[mask] = rng.choice([1, 2, 3, 4, 5], mask.sum(), p=p)
    has_comment = rng.random(n_orders) < np.where(score <= 2, 0.75, 0.35)
    message = np.full(n_orders, None, dtype=object)
    for i in np.flatnonzero(has_comment):
        message[i] = compose_comment(rng, int(score[i]), bool(late[i]))
    created = (np.maximum(delivered, estimated) + pd.Timedelta(days=1)).normalize()
    pd.DataFrame({
        "review_id": np.char.add("r", np.arange(n_orders).astype(str)), "order_id": order_ids,
        "review_score": score, "review_comment_title": None, "review_comment_message": message,
        "review_creation_date": created.strftime("%Y-%m-%d %H:%M:%S"),
        "review_answer_timestamp": (created + pd.Timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
    }).to_csv(out / "olist_order_reviews_dataset.csv", index=False)

    print(f"wrote {n_orders:,} orders / {len(it_order):,} items to {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("data/synthetic"))
    ap.add_argument("--orders", type=int, default=100_000)
    ap.add_argument("--seed", type=int, default=578)
    a = ap.parse_args()
    main(a.out, a.orders, a.seed)
