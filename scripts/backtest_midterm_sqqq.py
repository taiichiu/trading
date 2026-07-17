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

LEGACY YEARS (1994/1998/2002/2006): SQQQ (-3x) only exists from 2010-02-09.
For midterm years before that, this script:
  - auto-DETECTS each year's local IXIC high (May-Oct search window) and the
    subsequent local low (within 200 days after the high) from real ^IXIC
    data, rather than hardcoding remembered/guessed dates
  - for 2006 only, tries ProShares QID (UltraShort QQQ, -2x, inception
    2006-07-11) as a REAL leveraged-product cross-check if QID's history
    covers the detected window
  - for years/windows with no real leveraged product available (1994/1998/
    2002, or 2006 if QID doesn't cover the detected window), synthesizes a
    daily-compounded theoretical -3x product return purely from real IXIC
    daily returns (no fund fees/tracking error modeled) — explicitly tagged
    "data_type": "simulated" so it is never confused with real fund history

Writes:
  data/backtests/midterm_sqqq.json   full per-day equity curves + summary
  data/rhymes.json                   inserts/updates the "midterm-sqqq-window"
                                      rhyme pattern with the computed summary
"""

import json
import os
from datetime import datetime

import pandas as pd
import yfinance as yf

WINDOWS = [
    (2010, "2010-04-26", "2010-07-02"),
    (2014, "2014-09-19", "2014-10-15"),
    (2018, "2018-08-29", "2018-12-24"),
    (2022, "2022-08-15", "2022-10-14"),
]

LEGACY_YEARS = [1994, 1998, 2002, 2006]
LEGACY_PEAK_SEARCH_START_MD = (5, 1)    # search local high from May 1
LEGACY_PEAK_SEARCH_END_MD = (10, 31)    # through Oct 31
LEGACY_TROUGH_SEARCH_DAYS = 200         # then local low within 200 days after the high
QID_TICKER = "QID"                      # ProShares UltraShort QQQ, -2x, inception 2006-07-11

RHYMES_PATH = "data/rhymes.json"
BACKTEST_PATH = "data/backtests/midterm_sqqq.json"


def fetch(ticker, min_date=None):
    hist = yf.Ticker(ticker).history(period="max", interval="1d", auto_adjust=True)
    if min_date:
        hist = hist[hist.index >= min_date]
    hist.index = hist.index.tz_localize(None)
    return hist


def fetch_optional(ticker, min_date=None):
    """Like fetch(), but returns None instead of raising if the ticker has no
    usable history (delisted, wrong symbol on this vendor, network hiccup)."""
    try:
        hist = fetch(ticker, min_date=min_date)
        return hist if len(hist) else None
    except Exception as e:
        print(f"  {ticker}: fetch failed ({e}), skipping")
        return None


def nearest_on_or_after(df, date_str):
    sub = df[df.index >= pd.Timestamp(date_str)]
    return sub.index[0] if len(sub) else None


def nearest_on_or_before(df, date_str):
    sub = df[df.index <= pd.Timestamp(date_str)]
    return sub.index[-1] if len(sub) else None


def subtract_months(date_str, months):
    return (pd.Timestamp(date_str) - pd.DateOffset(months=months)).strftime("%Y-%m-%d")


def max_drawdown_pct(close_series):
    """Worst peak-to-trough % decline within the series (holder's perspective —
    how deep the unrealized loss got before it worked out)."""
    running_peak = close_series.cummax()
    drawdown = (close_series - running_peak) / running_peak * 100
    return round(float(drawdown.min()), 2)


def build_equity_curve(window_df, col="Close"):
    base = float(window_df[col].iloc[0])
    return [
        {"date": d.strftime("%Y-%m-%d"), "norm100": round(float(c / base * 100), 2)}
        for d, c in window_df[col].items()
    ]


def find_peak_trough(ixic, year):
    """Auto-detect a midterm year's local IXIC high (searched within
    LEGACY_PEAK_SEARCH_START_MD..END_MD) and the subsequent local low (within
    LEGACY_TROUGH_SEARCH_DAYS after the high) from real ^IXIC data — instead
    of hardcoding remembered/guessed historical dates. Returns (peak_ts,
    trough_ts) or (None, None) if there isn't enough data in range."""
    peak_lo = pd.Timestamp(year, *LEGACY_PEAK_SEARCH_START_MD)
    peak_hi = pd.Timestamp(year, *LEGACY_PEAK_SEARCH_END_MD)
    peak_window = ixic[(ixic.index >= peak_lo) & (ixic.index <= peak_hi)]
    if peak_window.empty:
        return None, None
    peak_ts = peak_window["Close"].idxmax()

    trough_hi = peak_ts + pd.Timedelta(days=LEGACY_TROUGH_SEARCH_DAYS)
    trough_window = ixic[(ixic.index >= peak_ts) & (ixic.index <= trough_hi)]
    if trough_window.empty:
        return None, None
    trough_ts = trough_window["Close"].idxmin()
    return peak_ts, trough_ts


def build_synthetic_series(ixic_window, leverage=-3):
    """Synthesize a daily-reset leveraged product's price series purely from
    real IXIC daily returns (no fund fees/tracking error modeled — this is
    the idealized frictionless case). Starts at 100 on the window's first day."""
    ret = ixic_window["Close"].pct_change().fillna(0)
    factor = (1 + leverage * ret).cumprod()
    return pd.DataFrame({"Close": 100 * factor}, index=ixic_window.index)


def main():
    print("Fetching SQQQ + ^IXIC (yfinance, auto_adjust=True)...")
    ixic = fetch("^IXIC")  # full history — needed for legacy peak/trough auto-detect back to 1994
    sqqq = fetch("SQQQ", min_date="2010-01-01")
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

    # ---- 更早的期中選舉年（1994/1998/2002/2006）：SQQQ 2010年才成立，
    # 高低點用真實IXIC資料自動偵測（非憑記憶硬編日期）；2006嘗試用真實
    # QID(-2x, 2006/7/11成立)交叉驗證，其餘年份/若QID未涵蓋該窗口則用
    # 「理論模擬-3x複利」(純由真實IXIC日報酬複利推算，不含基金費用/追蹤誤差)
    print()
    print("Legacy years (1994/1998/2002/2006) — auto-detecting windows from real IXIC data...")
    qid = fetch_optional(QID_TICKER)
    if qid is not None:
        print(f"  QID: {len(qid)} rows, {qid.index[0].date()} - {qid.index[-1].date()}")
    else:
        print("  QID: 無法取得，2006年將全部使用模擬-3x")

    legacy_results = []
    for year in LEGACY_YEARS:
        peak_ts, trough_ts = find_peak_trough(ixic, year)
        if peak_ts is None or trough_ts is None or trough_ts <= peak_ts:
            print(f"  {year}: 找不到有效高低點區間，略過")
            continue

        ixic_window = ixic.loc[peak_ts:trough_ts]
        ixic_start_close = float(ixic_window["Close"].iloc[0])
        ixic_end_close = float(ixic_window["Close"].iloc[-1])
        ixic_change_pct = round((ixic_end_close / ixic_start_close - 1) * 100, 2)

        data_type, leverage, product_window, product_ticker = "simulated", -3, None, None
        if year == 2006 and qid is not None:
            qid_start = nearest_on_or_after(qid, peak_ts.strftime("%Y-%m-%d"))
            qid_end = nearest_on_or_before(qid, trough_ts.strftime("%Y-%m-%d"))
            # Require QID to genuinely cover the detected window (start resolves
            # within a few days of peak_ts, not weeks later due to pre-inception
            # truncation truncating the lookup forward).
            if (qid_start is not None and qid_end is not None
                    and qid_start <= peak_ts + pd.Timedelta(days=5)
                    and qid_end > qid_start):
                product_window = qid.loc[qid_start:qid_end]
                data_type, leverage, product_ticker = "real", -2, QID_TICKER

        if product_window is None:
            product_window = build_synthetic_series(ixic_window, leverage=-3)
            data_type, leverage, product_ticker = "simulated", -3, None

        prod_start_close = float(product_window["Close"].iloc[0])
        prod_end_close = float(product_window["Close"].iloc[-1])
        prod_return_pct = round((prod_end_close / prod_start_close - 1) * 100, 2)
        theoretical_pct = round(leverage * ixic_change_pct, 2)
        decay_diff_pct = round(prod_return_pct - theoretical_pct, 2)
        drawdown_pct = max_drawdown_pct(product_window["Close"])

        legacy_results.append({
            "year": year,
            "start": peak_ts.strftime("%Y-%m-%d"),
            "end": trough_ts.strftime("%Y-%m-%d"),
            "ixic_start": round(ixic_start_close, 2),
            "ixic_end": round(ixic_end_close, 2),
            "ixic_change_pct": ixic_change_pct,
            "product_ticker": product_ticker,
            "product_leverage": leverage,
            "product_start": round(prod_start_close, 2),
            "product_end": round(prod_end_close, 2),
            "product_return_pct": prod_return_pct,
            "theoretical_pct": theoretical_pct,
            "decay_diff_pct": decay_diff_pct,
            "max_drawdown_pct": drawdown_pct,
            "data_type": data_type,
            "equity_curve": build_equity_curve(product_window),
        })
        tag = f"真實 {product_ticker} {leverage}x" if data_type == "real" else f"模擬 {leverage}x"
        print(f"  {year} ({tag}): {peak_ts.date()} ~ {trough_ts.date()} | IXIC {ixic_change_pct:+.2f}% | "
              f"商品 {prod_return_pct:+.2f}% (理論{theoretical_pct:+.2f}%, 衰耗差{decay_diff_pct:+.2f}%) "
              f"| 最大回撤 {drawdown_pct:.2f}%")

    # 反例（同上，套用到 legacy 年份；沿用該年偵測到的資料來源 real/simulated）
    legacy_premature_tests = []
    for r in legacy_results:
        year = r["year"]
        entry_str = subtract_months(r["start"], 2)

        entry_idx = exit_idx = None
        src = qid if r["data_type"] == "real" else None
        if src is not None:
            entry_idx = nearest_on_or_after(src, entry_str)
            exit_idx = nearest_on_or_before(src, r["start"])
            if entry_idx is None or exit_idx is None or entry_idx >= exit_idx:
                entry_idx = exit_idx = None

        if entry_idx is not None:
            entry_close = float(src.loc[entry_idx, "Close"])
            exit_close = float(src.loc[exit_idx, "Close"])
            ret_pct = round((exit_close / entry_close - 1) * 100, 2)
            entry_date_str, data_type = entry_idx.strftime("%Y-%m-%d"), "real"
        else:
            ixic_pre = ixic[(ixic.index >= pd.Timestamp(entry_str)) & (ixic.index <= pd.Timestamp(r["start"]))]
            if len(ixic_pre) < 2:
                continue
            synth = build_synthetic_series(ixic_pre, leverage=-3)
            ret_pct = round((float(synth["Close"].iloc[-1]) / float(synth["Close"].iloc[0]) - 1) * 100, 2)
            entry_date_str, data_type = ixic_pre.index[0].strftime("%Y-%m-%d"), "simulated"

        legacy_premature_tests.append({
            "year": year,
            "entry_date": entry_date_str,
            "exit_date": r["start"],
            "product_return_pct": ret_pct,
            "data_type": data_type,
        })
        print(f"  {year} 反例(提前2月進場, {data_type}): {entry_date_str} -> {r['start']} = {ret_pct:+.2f}%")

    # ---- 寫入 data/backtests/midterm_sqqq.json（含完整 equity curve）----
    os.makedirs("data/backtests", exist_ok=True)
    backtest_out = {
        "meta": {
            "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "source": "yfinance SQQQ + ^IXIC daily close, auto_adjust=True",
            "windows_spec": [f"{y}: {s} ~ {e}" for y, s, e in WINDOWS],
            "legacy_note": (
                "1994/1998/2002/2006：SQQQ 2010年才成立，高低點由真實IXIC資料"
                "自動偵測（非硬編日期）；2006嘗試以真實QID(-2x)交叉驗證，"
                "其餘用理論模擬-3x複利（純IXIC日報酬推算，不含基金費用/追蹤誤差），"
                "見各筆 data_type 欄位（real / simulated）。"
            ),
        },
        "windows": window_results,
        "premature_entry_tests": premature_tests,
        "legacy_windows": legacy_results,
        "legacy_premature_entry_tests": legacy_premature_tests,
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
    summary_legacy_windows = [
        {k: v for k, v in w.items() if k != "equity_curve"}
        for w in legacy_results
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
            "legacy_years": [w["year"] for w in summary_legacy_windows],
            "legacy_windows": summary_legacy_windows,
            "legacy_premature_entry_tests": legacy_premature_tests,
            "legacy_note": (
                "1994/1998/2002/2006：SQQQ尚未成立，高低點由IXIC真實資料自動"
                "偵測；2006優先採真實QID(-2x)資料，其餘用理論模擬-3x複利"
                "（各筆見 data_type: real/simulated）。"
            ),
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
