"""Fetch monthly closes for TAIEX (^TWII) and NASDAQ Composite (^IXIC).

Yahoo is authoritative for recent history. Stooq is used as a best-effort
backfill for older periods Yahoo is missing (TAIEX pre-1997, etc.).
"""

import csv
import io
import json
import os
from datetime import datetime, timedelta, timezone
from urllib.error import URLError
from urllib.request import Request, urlopen

import yfinance as yf


YAHOO_INDICES = {
    "TAIEX": "^TWII",
    "NASDAQ": "^IXIC",
}

# Stooq CSV symbols tried in order. Whichever returns the most monthly rows wins.
STOOQ_CANDIDATES = {
    "TAIEX": ["^twse"],
    "NASDAQ": ["^ndq", "^ixic"],
}


def fetch_yahoo_monthly(ticker):
    hist = yf.Ticker(ticker).history(period="max", interval="1mo")
    out = []
    for date, row in hist.iterrows():
        close = row.get("Close")
        if close is None or str(close) == "nan":
            continue
        out.append({
            "year": int(date.year),
            "month": int(date.month),
            "close": round(float(close), 2),
        })
    return out


def fetch_stooq_monthly(symbol):
    url = f"https://stooq.com/q/d/l/?s={symbol}&i=m"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; trading-dashboard)"})
    try:
        with urlopen(req, timeout=30) as resp:
            text = resp.read().decode("utf-8", errors="ignore")
    except (URLError, TimeoutError) as exc:
        print(f"  stooq {symbol}: {exc}")
        return []
    out = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        date = row.get("Date") or ""
        close_s = row.get("Close") or ""
        if not date or not close_s:
            continue
        try:
            y, m, _ = date.split("-")
            out.append({
                "year": int(y),
                "month": int(m),
                "close": round(float(close_s), 2),
            })
        except ValueError:
            continue
    return out


def backfill(primary, secondary):
    """Primary takes precedence; secondary only fills year-month slots primary lacks."""
    have = {(p["year"], p["month"]) for p in primary}
    merged = list(primary)
    added = 0
    for s in secondary:
        if (s["year"], s["month"]) not in have:
            merged.append(s)
            added += 1
    merged.sort(key=lambda x: (x["year"], x["month"]))
    return merged, added


def build_annual(monthly):
    annual = {}
    for item in monthly:
        if item["month"] == 12:
            annual[item["year"]] = item["close"]
    if monthly:
        last = monthly[-1]
        annual.setdefault(last["year"], last["close"])
    return [{"year": y, "close": c} for y, c in sorted(annual.items())]


def build_index(name):
    print(f"Fetching {name}...")
    yahoo = fetch_yahoo_monthly(YAHOO_INDICES[name])
    print(f"  yahoo: {len(yahoo)} months")

    best_stooq = []
    for sym in STOOQ_CANDIDATES.get(name, []):
        candidate = fetch_stooq_monthly(sym)
        print(f"  stooq {sym}: {len(candidate)} months")
        if len(candidate) > len(best_stooq):
            best_stooq = candidate

    merged, added = backfill(yahoo, best_stooq)
    print(f"  merged: {len(merged)} months (+{added} from stooq)")
    if merged:
        print(f"  range: {merged[0]['year']}/{merged[0]['month']:02d} – "
              f"{merged[-1]['year']}/{merged[-1]['month']:02d}")

    return {"monthly": merged, "annual": build_annual(merged)}


def main():
    data = {name: build_index(name) for name in YAHOO_INDICES}
    tw = timezone(timedelta(hours=8))
    data["lastUpdated"] = datetime.now(tw).strftime("%Y-%m-%d %H:%M (TWT)")

    os.makedirs("data", exist_ok=True)
    with open("data/indices.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Wrote data/indices.json")


if __name__ == "__main__":
    main()
