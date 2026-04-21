# 股市週期儀表板 (Stock Cycle Dashboard)

純靜態網站，透過 GitHub Pages 部署。資料源：Yahoo Finance（近期）＋ stooq.com（早期回推）。每個交易日（週二–六）台灣時間 16:30 自動更新。

## 指數

- **TAIEX** `^TWII`（台股加權指數）
- **NASDAQ** `^IXIC`（納斯達克綜合指數）

## 功能

1. **十年週期疊加圖** — 每個十年起始=100 標準化，支援線性/對數切換，可切換 TAIEX / NASDAQ
2. **尾數年月度比較圖** — 選擇年份尾數 0–9，比較該尾數所有年份 1–12 月的表現，可切換 TAIEX / NASDAQ

## 檔案結構

```
index.html                         首頁
pages/decade.html                  十年週期疊加頁
pages/yearly.html                  尾數年月度比較頁
js/charts.js                       共用資料載入與正規化函式
data/indices.json                  資料檔（由 GitHub Actions 產生）
scripts/fetch_data.py              yfinance + stooq 抓取腳本
.github/workflows/update_data.yml  每交易日台灣 16:30 自動更新
requirements.txt                   Python 相依套件
```

## 部署到 GitHub Pages

1. 進入 repo → **Settings** → **Pages**
2. 在「Build and deployment」，Source 選 **Deploy from a branch**
3. Branch 選擇部署用分支（如 `main`）、資料夾選 `/ (root)`
4. 按 **Save**
5. 幾分鐘後網站上線：`https://<帳號>.github.io/trading/`

## 首次初始化資料

`data/taiex.json` 初始為空。手動觸發 workflow 以抓取完整歷史：

1. 進入 repo → **Actions**
2. 左側選 **Update TAIEX Data** → **Run workflow**
3. 約 1 分鐘後完成，網頁重新整理即可看到圖表

## 本地測試

```bash
pip install -r requirements.txt
python scripts/fetch_data.py   # 會產生 data/taiex.json
python -m http.server 8000     # 然後開 http://localhost:8000
```

## 自動更新排程

`.github/workflows/update_data.yml` 使用 cron `30 8 * * 2-6`（UTC 08:30 = 台灣時間 16:30，週二–六對應台灣週一–五收盤後）。
