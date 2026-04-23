#!/usr/bin/env python
"""Initialize historical data for all indices.

Run this script once on a machine with network access to fetch 10 years of daily data
and all available historical monthly data. Output is written to data/indices.json.

Usage:
    python scripts/init_historical_data.py
"""

import sys
import os

# Add parent directory to path to import fetch_data
sys.path.insert(0, os.path.dirname(__file__))

from fetch_data import build_index, YAHOO_INDICES
from datetime import datetime, timedelta, timezone
import json


def main():
    print("Initializing historical data (full fetch)...")
    print("This may take a few minutes due to API rate limiting.\n")

    data = {}
    for name in YAHOO_INDICES:
        # Force full history fetch (no incremental mode)
        data[name] = build_index(name, incremental=False)

    tw = timezone(timedelta(hours=8))
    data["lastUpdated"] = datetime.now(tw).strftime("%Y-%m-%d %H:%M (TWT)")

    os.makedirs("data", exist_ok=True)
    with open("data/indices.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("\nInitialization complete!")
    print(f"Wrote data/indices.json")
    print(f"Last updated: {data['lastUpdated']}")

    # Print summary
    for name, index_data in data.items():
        if isinstance(index_data, dict):
            if "daily" in index_data:
                print(f"\n{name}:")
                print(f"  Daily data: {len(index_data['daily'])} records")
                if index_data['daily']:
                    print(f"    Range: {index_data['daily'][0]['date']} – {index_data['daily'][-1]['date']}")
            if "monthly" in index_data:
                print(f"  Monthly data: {len(index_data['monthly'])} records")
                if index_data['monthly']:
                    print(f"    Range: {index_data['monthly'][0]['year']}/{index_data['monthly'][0]['month']:02d} – "
                          f"{index_data['monthly'][-1]['year']}/{index_data['monthly'][-1]['month']:02d}")


if __name__ == "__main__":
    main()
