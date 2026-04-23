"""Fetch monthly closes and daily K-line data for TAIEX (^TWII) and NASDAQ Composite (^IXIC).

For TAIEX daily data, uses Taiwan Stock Exchange official API or yfinance as fallback.
For monthly data and NASDAQ, uses yfinance + Stooq backfill.

This script can run in two modes:
- Full mode (default): Fetches all historical data (10 years for daily, all available for monthly)
- Incremental mode (--incremental): Updates only the latest trading day
"""

import csv
import io
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.error import URLError
from urllib.request import Request, urlopen

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False


YAHOO_INDICES = {
    "TAIEX": "^TWII",
    "NASDAQ": "^IXIC",
}

# Stooq CSV symbols tried in order. Whichever returns the most monthly rows wins.
STOOQ_CANDIDATES = {
    "TAIEX": ["^twse"],
    "NASDAQ": ["^ndq", "^ixic"],
}


def fetch_yahoo_daily(ticker, full_history=True):
    """Fetch daily OHLCV data from Yahoo Finance.

    Args:
        full_history: If True, fetch 10 years of data. If False, fetch only last 5 days.
    """
    if not HAS_YFINANCE:
        print(f"  yfinance not available for {ticker}")
        return []

    try:
        period = "10y" if full_history else "5d"
        hist = yf.Ticker(ticker).history(period=period, interval="1d")
        out = []
        for date, row in hist.iterrows():
            close = row.get("Close")
            if close is None or str(close) == "nan":
                continue

            def safe_round(val):
                if val is None or str(val) == "nan":
                    return None
                return round(float(val), 2)

            def safe_int(val):
                if val is None or str(val) == "nan":
                    return None
                return int(float(val))

            out.append({
                "date": date.strftime("%Y-%m-%d"),
                "open": safe_round(row.get("Open")),
                "high": safe_round(row.get("High")),
                "low": safe_round(row.get("Low")),
                "close": safe_round(close),
                "volume": safe_int(row.get("Volume")),
            })
        return out
    except Exception as e:
        print(f"  Yahoo daily {ticker}: {e}")
        return []


def fetch_twse_daily(full_history=True):
    """Fetch TAIEX daily data from Taiwan Stock Exchange official API.

    Uses MI_5MINS_HIST endpoint which returns daily OHLC for the TAIEX index.

    Args:
        full_history: If True, fetch from 2015 onwards. If False, fetch only current month.
    """
    out = []

    if full_history:
        start_date = datetime(2015, 1, 1)
    else:
        # For incremental update, only fetch current month
        start_date = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    today = datetime.now()
    current_date = start_date

    while current_date <= today:
        year_month = current_date.strftime("%Y%m")
        url = f"https://www.twse.com.tw/rwd/zh/indices/MI_5MINS_HIST?date={year_month}01&response=json"

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://www.twse.com.tw/",
            }
            req = Request(url, headers=headers)
            with urlopen(req, timeout=15) as resp:
                text = resp.read().decode("utf-8")
                data = json.loads(text)

                # MI_5MINS_HIST format:
                # {"data": [[date, open, high, low, close], ...]}
                # Date is in ROC format like "114/01/02" (民國年/月/日)
                for row in data.get("data", []):
                    if len(row) >= 5:
                        date_str = row[0]
                        try:
                            # Parse ROC date "114/01/02" → 2025-01-02
                            parts = date_str.split("/")
                            if len(parts) == 3:
                                roc_year = int(parts[0])
                                month = int(parts[1])
                                day = int(parts[2])
                                # ROC year + 1911 = AD year
                                year = roc_year + 1911
                                date_obj = datetime(year, month, day)

                                def parse_num(s):
                                    if not s or s == "--":
                                        return None
                                    return float(s.replace(",", ""))

                                open_v = parse_num(row[1])
                                high_v = parse_num(row[2])
                                low_v = parse_num(row[3])
                                close_v = parse_num(row[4])

                                if close_v is None:
                                    continue

                                out.append({
                                    "date": date_obj.strftime("%Y-%m-%d"),
                                    "open": round(open_v, 2) if open_v else None,
                                    "high": round(high_v, 2) if high_v else None,
                                    "low": round(low_v, 2) if low_v else None,
                                    "close": round(close_v, 2),
                                    "volume": None,  # MI_5MINS_HIST doesn't include volume
                                })
                        except (ValueError, IndexError, TypeError):
                            continue

        except Exception as e:
            print(f"  TWSE {year_month}: {e}")

        # Move to next month
        if current_date.month == 12:
            current_date = datetime(current_date.year + 1, 1, 1)
        else:
            current_date = datetime(current_date.year, current_date.month + 1, 1)

        time.sleep(0.3)  # Rate limit

    return out


def fetch_yahoo_monthly(ticker):
    """Fetch monthly closes from Yahoo Finance."""
    if not HAS_YFINANCE:
        print(f"  yfinance not available for {ticker}")
        return []

    try:
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
    except Exception as e:
        print(f"  Yahoo {ticker}: {e}")
        return []


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


def load_existing_data(filepath):
    """Load existing indices.json if it exists."""
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load existing {filepath}: {e}")
    return {}


def update_daily_incremental(existing_daily, new_daily):
    """Merge new daily data with existing, removing duplicates."""
    if not new_daily:
        return existing_daily

    # Create a dict of existing data by date for easy lookup
    existing_dict = {d["date"]: d for d in existing_daily}

    # Add or update with new data
    for item in new_daily:
        existing_dict[item["date"]] = item

    # Return sorted by date
    return sorted(existing_dict.values(), key=lambda x: x["date"])


def build_index(name, incremental=False):
    print(f"Fetching {name}...")

    if name == "TAIEX":
        # Try yfinance first (more stable), fall back to TWSE official API
        daily = fetch_yahoo_daily(YAHOO_INDICES[name], full_history=not incremental)
        print(f"  yahoo daily: {len(daily)} days")

        if not daily:
            print(f"  yahoo daily failed, trying TWSE API...")
            daily = fetch_twse_daily(full_history=not incremental)
            print(f"  TWSE daily: {len(daily)} days")

        if daily:
            print(f"  daily range: {daily[0]['date']} – {daily[-1]['date']}")
    else:
        daily = []

    # Fetch monthly data
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

    result = {
        "monthly": merged,
        "annual": build_annual(merged),
    }

    if daily:
        result["daily"] = daily

    return result


def main():
    incremental = "--incremental" in sys.argv

    data_file = "data/indices.json"
    existing_data = load_existing_data(data_file) if incremental else {}

    data = {}
    for name in YAHOO_INDICES:
        new_index_data = build_index(name, incremental=incremental)

        if incremental and name in existing_data:
            # Merge daily data if it exists
            if "daily" in new_index_data and "daily" in existing_data[name]:
                new_index_data["daily"] = update_daily_incremental(
                    existing_data[name]["daily"],
                    new_index_data["daily"]
                )
            # Keep other fields if not updated
            if "monthly" not in new_index_data and "monthly" in existing_data[name]:
                new_index_data["monthly"] = existing_data[name]["monthly"]
            if "annual" not in new_index_data and "annual" in existing_data[name]:
                new_index_data["annual"] = existing_data[name]["annual"]

        data[name] = new_index_data

    tw = timezone(timedelta(hours=8))
    data["lastUpdated"] = datetime.now(tw).strftime("%Y-%m-%d %H:%M (TWT)")

    os.makedirs("data", exist_ok=True)
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Wrote {data_file}")


if __name__ == "__main__":
    main()
