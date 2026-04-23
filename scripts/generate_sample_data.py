#!/usr/bin/env python
"""Generate sample indices.json with realistic structure for local testing.

This script creates sample data with the correct structure and date ranges,
useful for testing before running actual data fetch.
"""

import json
import os
from datetime import datetime, timedelta, timezone


def generate_sample_daily(start_date, num_days):
    """Generate sample daily data."""
    daily = []
    date = datetime.strptime(start_date, "%Y-%m-%d")
    base_price = 10000

    for i in range(num_days):
        # Skip weekends
        if date.weekday() >= 5:
            date += timedelta(days=1)
            continue

        # Realistic OHLCV data with slight variation
        open_price = base_price + (i % 20 - 10) * 5
        close_price = open_price + (i % 10 - 5) * 3
        high = max(open_price, close_price) + (i % 5) * 2
        low = min(open_price, close_price) - (i % 5) * 2
        volume = 1000000000 + (i % 500000000)

        daily.append({
            "date": date.strftime("%Y-%m-%d"),
            "open": round(open_price, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(close_price, 2),
            "volume": volume,
        })

        date += timedelta(days=1)
        base_price = close_price

    return daily


def generate_sample_monthly():
    """Generate sample monthly data from 1997 onwards."""
    monthly = []
    years = list(range(1997, 2026))
    months = list(range(1, 13))

    price = 5000
    for year in years:
        for month in months:
            price += (year + month) % 100 - 50
            monthly.append({
                "year": year,
                "month": month,
                "close": round(max(price, 1000), 2),
            })

    return monthly


def build_annual(monthly):
    """Build annual data from monthly."""
    annual = {}
    for item in monthly:
        if item["month"] == 12:
            annual[item["year"]] = item["close"]
    if monthly:
        last = monthly[-1]
        annual.setdefault(last["year"], last["close"])
    return [{"year": y, "close": c} for y, c in sorted(annual.items())]


def main():
    today = datetime.now()
    ten_years_ago = (today - timedelta(days=365*10)).strftime("%Y-%m-%d")

    # TAIEX sample data
    taiex_daily = generate_sample_daily(ten_years_ago, 365*10)
    taiex_monthly = generate_sample_monthly()
    taiex_annual = build_annual(taiex_monthly)

    # NASDAQ sample data (monthly only)
    nasdaq_monthly = [
        {**m, "close": round(m["close"] * 1.5, 2)}
        for m in generate_sample_monthly()
    ]
    nasdaq_annual = build_annual(nasdaq_monthly)

    data = {
        "TAIEX": {
            "daily": taiex_daily,
            "monthly": taiex_monthly,
            "annual": taiex_annual,
        },
        "NASDAQ": {
            "monthly": nasdaq_monthly,
            "annual": nasdaq_annual,
        },
    }

    tw = timezone(timedelta(hours=8))
    data["lastUpdated"] = datetime.now(tw).strftime("%Y-%m-%d %H:%M (TWT)")

    os.makedirs("data", exist_ok=True)
    with open("data/indices.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("Generated sample data/indices.json")
    print(f"\nSummary:")
    print(f"TAIEX:")
    print(f"  Daily: {len(taiex_daily)} records ({taiex_daily[0]['date']} – {taiex_daily[-1]['date']})")
    print(f"  Monthly: {len(taiex_monthly)} records")
    print(f"  Annual: {len(taiex_annual)} records")
    print(f"NASDAQ:")
    print(f"  Monthly: {len(nasdaq_monthly)} records")
    print(f"  Annual: {len(nasdaq_annual)} records")
    print(f"Last updated: {data['lastUpdated']}")


if __name__ == "__main__":
    main()
