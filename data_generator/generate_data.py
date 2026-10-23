"""Generate fake retail data: a product catalog plus daily order files.
Includes intentionally messy rows so the silver layer has real cleaning to do."""
import argparse
import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
Faker.seed(SEED)
fake = Faker("en_IN")

CITIES = ["Mumbai", "Delhi", "Bengaluru", "Chennai", "Kolkata"]
PAYMENTS = ["UPI", "Card", "COD", "NetBanking"]
CATEGORIES = ["Electronics", "Fashion", "Home", "Grocery"]


def make_products(n=20) -> pd.DataFrame:
    return pd.DataFrame({
        "product_id": range(1, n + 1),
        "product_name": [f"Product {i}" for i in range(1, n + 1)],
        "category": [random.choice(CATEGORIES) for _ in range(n)],
        "unit_price": np.round(np.random.uniform(99, 4999, n), 2),
    })


def make_orders(day: date, n: int, n_products: int) -> pd.DataFrame:
    rows = []
    for i in range(n):
        rows.append({
            "order_id": f"{day:%Y%m%d}-{i:05d}",
            "order_date": day.isoformat(),
            "customer_id": random.randint(1000, 1500),
            "customer_name": fake.name(),
            "city": random.choice(CITIES),
            "product_id": random.randint(1, n_products),
            "quantity": random.randint(1, 5),
            "payment_type": random.choice(PAYMENTS),
        })
    df = pd.DataFrame(rows)

    # ---- inject dirty data (~3% total) ----
    k = max(1, int(n * 0.01))
    df.loc[df.sample(k).index, "city"] = None                      # missing city
    df.loc[df.sample(k).index, "city"] = "  mumbai "               # messy text
    df.loc[df.sample(k).index, "payment_type"] = "upi"             # inconsistent case
    df = pd.concat([df, df.sample(k)], ignore_index=True)          # duplicate rows
    return df.sample(frac=1, random_state=SEED).reset_index(drop=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--rows", type=int, default=500)
    p.add_argument("--end", default=None, help="last date YYYY-MM-DD (default: yesterday)")
    p.add_argument("--out", default="data")
    a = p.parse_args()

    end = date.fromisoformat(a.end) if a.end else date.today() - timedelta(days=1)
    out = Path(a.out)
    (out / "orders").mkdir(parents=True, exist_ok=True)

    products = make_products()
    products.to_csv(out / "products.csv", index=False)

    for d in range(a.days):
        day = end - timedelta(days=a.days - 1 - d)
        make_orders(day, a.rows, len(products)).to_csv(
            out / "orders" / f"orders_{day.isoformat()}.csv", index=False)

    print(f"Wrote {a.days} order files + products.csv to '{out}'")


if __name__ == "__main__":
    main()