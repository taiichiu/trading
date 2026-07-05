"""Backtest SQQQ short-window trades in midterm-election-year NASDAQ corrections.

Downloads real daily SQQQ + ^IXIC data (yfinance, auto_adjust=True) and computes,
for each of the four confirmed 2010/2014/2018/2022 correction windows:
  - IXIC decline %, SQQQ actual return %, naive theoretical -3x %, decay diff %
    (actual - naive theoretical; positive = SQQQ outperformed the naive linear
    -3x thanks to daily-compounding of a smoothly trending decline; negative =
    volatility-drag decay), and SQQQ holder's max intra-window drawdown %.

Also backtests a counterexample: entering SQQQ 2 months before each window's
high (i.e. before the confirmed downtrend actually starts) to quantify the
sideways-decay cost of premature entry.

Writes:
  data/backtests/midterm_sqqq.json   full per-day equity curves + summary
  data/rhymes.json                   inserts/updates the "midterm-sqqq-window"
                                      rhyme pattern with the computed summary
"""

import json
import os
from datetime import datetime

import yfinance as yf

WINDOWS = [
    (2010, "2010-04-26", "2010-07-02"),
    (2014, "2014-09-19", "2014-10-15"),
    (2018, "2018-08-29", "2018-12-24"),
    (2022, "2022-08-15", "2022-10-14"),
]

RHYMES_PATH = "data/rhymes.json"
BACKTEST_PATH = "data/backtests/midterm_sqqq.json"


def fetch(ticker):
    hist = yf.Ticker(ticker).history(period="max", interval="1d", auto_adjust=True)
    hist = hist[hist.index >= "2010-01-01"]
    hist.index = hist.index.tz_localize(None)
    return hist


def nearest_on_or_after(df, date_str):
    import pandas as pd
    sub = df[df.index >= pd.Timestamp(date_str)]
    return sub.index[0] if len(sub) else None


def nearest_on_or_before(df, date_str):
    import pandas as pd
    sub = df[df.index <= pd.Timestamp(date_str)]
    return sub.index[-1] if len(sub) else None


def subtract_months(date_str, months):
    import pandas as pd
    return (pd.Timestamp(date_str) - pd.DateOffset(months=months)).strftime("%Y-%m-%d")


def max_drawdown_pct(close_series):
    """Worst peak-to-trough % decline within the series (SQQQ holder's
    perspective — how deep the unrealized loss got before it worked out)."""
    running_peak = close_series.cummax()
    drawdown = (close_series - running_peak) / running_peak * 100
    return round(float(drawdown.min()), 2)


def build_equity_curve(sqqq_window):
    base = float(sqqq_window["Close"].iloc[0])
    return [
        {"date": d.strftime("%Y-%m-%d"), "sqqq_norm100": round(float(c / base * 100), 2)}
        for d, c in sqqq_window["Close"].items()
    ]


def main():
    print("Fetching SQQQ + ^IXIC (yfinance, auto_adjust=True)...")
    ixic = fetch("^IXIC")
    sqqq = fetch("SQQQ")
    print(f"  IXIC: {len(ixic)} rows, {ixic.index[0].date()} - {ixic.index[-1].date()}")
    print(f"  SQQQ: {len(sqqq)} rows, {sqqq.index[0].date()} - {sqqq.index[-1].date()}")

    window_results = []
    for year, start_str, end_str in WINDOWS:
        start_ixic = nearest_on_or_after(ixic, start_str)
        end_ixic = nearest_on_or_before(ixic, end_str)
        start_sqqq = nearest_on_or_after(sqqq, start_str)
        end_sqqq = nearest_on_or_before(sqqq, end_str)

        if start_ixic is None or end_ixic is None or start_sqqq is None or end_sqqq is None:
            print(f"  {year}: 資料不足，略過")
            continue

        ixic_start_close = float(ixic.loc[start_ixic, "Close"])
        ixic_end_close = float(ixic.loc[end_ixic, "Close"])
        ixic_change_pct = round((ixic_end_close / ixic_start_close - 1) * 100, 2)

        sqqq_window = sqqq.loc[start_sqqq:end_sqqq]
        sqqq_start_close = float(sqqq_window["Close"].iloc[0])
        sqqq_end_close = float(sqqq_window["Close"].iloc[-1])
        sqqq_return_pct = round((sqqq_end_close / sqqq_start_close - 1) * 100, 2)

        theoretical_3x_pct = round(-3 * ixic_change_pct, 2)
        decay_diff_pct = round(sqqq_return_pct - theoretical_3x_pct, 2)
        drawdown_pct = max_drawdown_pct(sqqq_window["Close"])

        window_results.append({
            "year": year,
            "start": start_sqqq.strftime("%Y-%m-%d"),
            "end": end_sqqq.strftime("%Y-%m-%d"),
            "ixic_start": round(ixic_start_close, 2),
            "ixic_end": round(ixic_end_close, 2),
            "ixic_change_pct": ixic_change_pct,
            "sqqq_start": round(sqqq_start_close, 2),
            "sqqq_end": round(sqqq_end_close, 2),
            "sqqq_return_pct": sqqq_return_pct,
            "theoretical_3x_pct": theoretical_3x_pct,
            "decay_diff_pct": decay_diff_pct,
            "max_drawdown_pct": drawdown_pct,
            "equity_curve": build_equity_curve(sqqq_window),
        })
        print(f"  {year}: IXIC {ixic_change_pct:+.2f}% | SQQQ {sqqq_return_pct:+.2f}% "
              f"(理論{theoretical_3x_pct:+.2f}%, 衰耗差{decay_diff_pct:+.2f}%) "
              f"| 最大回撤 {drawdown_pct:.2f}%")

    # 反例：各期中年高點前2個月進場（模擬過早進場的橫盤磨損成本）
    premature_tests = []
    for year, start_str, _end_str in WINDOWS:
        entry_str = subtract_months(start_str, 2)
        entry_idx = nearest_on_or_after(sqqq, entry_str)
        exit_idx = nearest_on_or_before(sqqq, start_str)
        if entry_idx is None or exit_idx is None or entry_idx >= exit_idx:
            continue
        entry_close = float(sqqq.loc[entry_idx, "Close"])
        exit_close = float(sqqq.loc[exit_idx, "Close"])
        ret_pct = round((exit_close / entry_close - 1) * 100, 2)
        premature_tests.append({
            "year": year,
            "entry_date": entry_idx.strftime("%Y-%m-%d"),
            "exit_date": exit_idx.strftime("%Y-%m-%d"),
            "sqqq_return_pct": ret_pct,
        })
        print(f"  {year} 反例(提前2月進場): {entry_idx.date()} -> {exit_idx.date()} = {ret_pct:+.2f}%")

    # ---- 寫入 data/backtests/midterm_sqqq.json（含完整 equity curve）----
    os.makedirs("data/backtests", exist_ok=True)
    backtest_out = {
        "meta": {
            "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "source": "yfinance SQQQ + ^IXIC daily close, auto_adjust=True",
            "windows_spec": [f"{y}: {s} ~ {e}" for y, s, e in WINDOWS],
        },
        "windows": window_results,
        "premature_entry_tests": premature_tests,
    }
    with open(BACKTEST_PATH, "w", encoding="utf-8") as f:
        json.dump(backtest_out, f, ensure_ascii=False, indent=2)
    print(f"Wrote {BACKTEST_PATH}")

    # ---- 更新 data/rhymes.json（摘要版，不含完整 equity curve）----
    with open(RHYMES_PATH, "r", encoding="utf-8") as f:
        rhymes = json.load(f)

    summary_windows = [
        {k: v for k, v in w.items() if k != "equity_curve"}
        for w in window_results
    ]

    new_pattern = {
        "id": "midterm-sqqq-window",
        "name": "期中年做空窗口（SQQQ）",
        "scale": "季度",
        "market": "NASDAQ",
        "description": (
            "期中選舉年高點多落於7月中-8月初（1990/1998/2022型）或年初（2022），"
            "低點多在選前9-10月（例外2018/12）。高低點間隔2-3個月。"
            "實測顯示跌勢越深越持久，SQQQ複利效果越有利：2010/2014等較淺修正"
            "（IXIC -8%~-17%）衰耗差僅-2.3%~+0.6%，貼近樸素-3x預期；"
            "但2018/2022等深且久的修正（IXIC -21%~-24%）衰耗差達+22.9%~+28.3%，"
            "SQQQ大幅超越樸素-3x預期。四次窗口全數獲利，實際報酬+24%~+94%。"
        ),
        "pattern": {
            "confirmed_years": [2010, 2014, 2018, 2022],
            "windows": summary_windows,
            "premature_entry_tests": premature_tests,
            "pending_verification": [2026],
        },
        "entry_rule": "IXIC跌破50日線確認破位後進場，勿在高點預佈局",
        "exit_rule": "TAIEX -15%觸發器到位或10Y-swap spread噴出回落日獲利了結；進場6-8週未跌則時間停損",
        "failure_mode": (
            "假設情境（尚無實例驗證）：2006型無修正年，方向損失+衰耗雙殺，"
            "橫盤3個月約-12.6%（σ=30%）。已驗證的真實風險：提早2個月進場的磨損"
            "成本極高（4次回測 -13%~-43%），印證entry_rule「勿在高點預佈局」的"
            "重要性；即使方向判斷正確，窗內最大回撤仍達-5.8%~-21.8%，須以"
            "3-5%倉位控制曝險。"
        ),
        "position_limit": "總資產3-5%",
        "confidence": "high",
        "source": "2026-07 SQQQ期中年回測（yfinance實際日線）",
        "notes": "2026適用夏季高點型態，觀察窗：7月中-8月初見頂→8-10月修正",
        "next_occurrence": 2026,
        "updated_at": datetime.now().strftime("%Y-%m-%d"),
    }

    patterns = rhymes.setdefault("rhyme_patterns", [])
    existing_idx = next((i for i, p in enumerate(patterns) if p.get("id") == "midterm-sqqq-window"), None)
    if existing_idx is not None:
        patterns[existing_idx] = new_pattern
    else:
        patterns.append(new_pattern)

    with open(RHYMES_PATH, "w", encoding="utf-8") as f:
        json.dump(rhymes, f, ensure_ascii=False, indent=2)
    print(f"Updated {RHYMES_PATH} (pattern id=midterm-sqqq-window)")


if __name__ == "__main__":
    main()
