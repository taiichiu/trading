import yfinance as yf
import json
import os
from datetime import datetime

def fetch_taiex():
    print("Fetching TAIEX data from Yahoo Finance...")
    ticker = yf.Ticker("^TWII")
    hist = ticker.history(period="max", interval="1mo")

    monthly = []
    for date, row in hist.iterrows():
        if not row['Close'] or str(row['Close']) == 'nan':
            continue
        monthly.append({
            "year": int(date.year),
            "month": int(date.month),
            "close": round(float(row['Close']), 2)
        })

    monthly.sort(key=lambda x: (x['year'], x['month']))

    # Annual: use December close; if current year not yet December, use latest month
    annual_dict = {}
    for item in monthly:
        y = item['year']
        if item['month'] == 12:
            annual_dict[y] = item['close']
    # Fill in latest year if not December yet
    if monthly:
        last = monthly[-1]
        if last['year'] not in annual_dict:
            annual_dict[last['year']] = last['close']

    annual = [{"year": y, "close": c} for y, c in sorted(annual_dict.items())]

    return {
        "monthly": monthly,
        "annual": annual,
        "lastUpdated": datetime.now().strftime("%Y-%m-%d %H:%M")
    }

os.makedirs("data", exist_ok=True)
data = fetch_taiex()

with open("data/taiex.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Done. Monthly records: {len(data['monthly'])}, Annual records: {len(data['annual'])}")
print(f"Range: {data['monthly'][0]['year']}/{data['monthly'][0]['month']} ~ {data['monthly'][-1]['year']}/{data['monthly'][-1]['month']}")
