"""Fetch CNN's Fear & Greed Index into data/fear_greed.json.

CNN publishes no official API. This reads the JSON endpoint behind its Fear &
Greed page, which refuses requests that don't look like a browser. History
depth is whatever CNN serves; the first run backfills everything available,
later runs (--incremental) re-fetch the last few weeks and merge.

Each stored point is one US trading day's closing reading:
  - points stamped exactly at 00:00 UTC are CNN's daily records -> that date
  - any other stamp is a live reading -> kept only if the New York session
    had already closed (>= 16:00 ET), dated by the New York date
Weekend-dated points are dropped.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata/{start}"
OUT_PATH = "data/fear_greed.json"
# CNN answers HTTP 500 for start dates before ~2020-09-19, and what it serves
# before 2021-01-22 is placeholder data: flat 50.0 blocks (2020-09-21..10-23,
# 2020-11-04..2021-01-21) around an implausible week of 0.3-3.6. Keep only
# the continuous real series.
RELIABLE_FROM = "2021-01-22"
FULL_HISTORY_STARTS = [
    RELIABLE_FROM,
    (datetime.now(timezone.utc) - timedelta(days=360)).strftime("%Y-%m-%d"),
]
INCREMENTAL_LOOKBACK_DAYS = 21
NY = ZoneInfo("America/New_York")
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://edition.cnn.com/",
    "Origin": "https://edition.cnn.com",
}


def fetch(start):
    req = Request(URL.format(start=start), headers=HEADERS)
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def point_date(ms):
    """Trading date a CNN point belongs to, or None if it isn't a closed session."""
    utc = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    if (utc.hour, utc.minute, utc.second) == (0, 0, 0):
        day = utc
    else:
        ny = utc.astimezone(NY)
        if ny.hour < 16:
            return None
        day = ny
    if day.weekday() >= 5:
        return None
    return day.strftime("%Y-%m-%d")


def parse(payload):
    hist = payload.get("fear_and_greed_historical") if isinstance(payload, dict) else None
    points = hist.get("data") if isinstance(hist, dict) else None
    if not isinstance(points, list):
        keys = sorted(payload) if isinstance(payload, dict) else type(payload).__name__
        raise ValueError(f"unexpected CNN payload shape: {keys}")

    by_date, skipped = {}, 0
    for p in points:
        date = point_date(p["x"])
        if date is None:
            skipped += 1
            continue
        by_date[date] = {
            "date": date,
            "value": round(float(p["y"]), 1),
            "rating": p.get("rating", ""),
        }

    if points:
        first = datetime.fromtimestamp(points[0]["x"] / 1000, tz=timezone.utc).isoformat()
        last = datetime.fromtimestamp(points[-1]["x"] / 1000, tz=timezone.utc).isoformat()
        print(f"  raw points: {len(points)} ({first} .. {last}), kept {len(by_date)}, skipped {skipped}")
    return by_date


def load_existing():
    if not os.path.exists(OUT_PATH):
        return {}
    with open(OUT_PATH, encoding="utf-8") as f:
        return {row["date"]: row for row in json.load(f).get("data", [])}


def main():
    existing = load_existing()
    incremental = "--incremental" in sys.argv and bool(existing)

    if incremental:
        last = max(existing)
        start = (datetime.strptime(last, "%Y-%m-%d") - timedelta(days=INCREMENTAL_LOOKBACK_DAYS))
        starts = [start.strftime("%Y-%m-%d")]
    else:
        starts = FULL_HISTORY_STARTS

    fetched = None
    for start in starts:
        print(f"Fetching CNN Fear & Greed from {start}...")
        try:
            fetched = parse(fetch(start))
            break
        except HTTPError as exc:
            body = exc.read()[:200].decode("utf-8", "replace") if exc.fp else ""
            print(f"  failed: HTTP {exc.code} {body!r}")
        except (URLError, TimeoutError, ValueError, KeyError) as exc:
            print(f"  failed: {exc}")

    if not fetched:
        # Keep whatever we already have; a CNN hiccup must not fail the daily data job.
        print("WARNING: no Fear & Greed data fetched; leaving existing file unchanged.")
        return

    merged = {d: r for d, r in {**existing, **fetched}.items() if d >= RELIABLE_FROM}
    rows = [merged[d] for d in sorted(merged)]
    out = {
        "meta": {
            "source": "CNN Business Fear & Greed Index",
            "url": "https://edition.cnn.com/markets/fear-and-greed",
            "scale": "0-100（0=極度恐懼，100=極度貪婪）",
            "first_date": rows[0]["date"],
            "last_date": rows[-1]["date"],
            "count": len(rows),
            "last_updated": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M (TWT)"),
        },
        "data": rows,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"Wrote {OUT_PATH}: {len(rows)} days, {rows[0]['date']} .. {rows[-1]['date']}")


if __name__ == "__main__":
    main()
