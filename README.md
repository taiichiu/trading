# 市場韻腳資料庫 (Market Rhyme Database)

> 歷史不會重複，但是會押韻

純靜態網站，透過 GitHub Pages 部署。

## 內容

### 週期圖表（自動更新）
- **十年週期疊加圖** — 各十年標準化為起始=100，支援線性/對數切換，可切換 TAIEX / NASDAQ
- **尾數年月度比較圖** — 選擇年份尾數 0–9，比較該尾數所有年份 1–12 月的表現

### 規律與心法（手動編輯 `data/rhymes.json`）
- **韻腳規則** — 空頭年週期、Q4 低點慣性、四巫日策略、9 月慣性、早盤籌碼訊號等
- **風險管理** — 亞當理論 / K5 / 王醫師 三套停損與部位管理框架
- **操盤哲學** — 核心信念、心法六階段、金句

## 指數資料

- **TAIEX** `^TWII`（台股加權指數）
- **NASDAQ** `^IXIC`（納斯達克綜合指數）

資料源：Yahoo Finance（近期）＋ stooq.com（早期回推）。每個交易日（週二–六）台灣時間 16:30 自動更新。

## 檔案結構

```
index.html                         首頁
pages/decade.html                  十年週期疊加頁
pages/yearly.html                  尾數年月度比較頁
pages/rhymes.html                  韻腳規則頁
pages/risk.html                    風險管理頁
pages/philosophy.html              操盤哲學頁
js/charts.js                       共用資料載入與正規化函式
data/indices.json                  指數資料（由 GitHub Actions 產生）
data/rhymes.json                   韻腳/風管/哲學資料（手動編輯）
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

`data/indices.json` 初始為空。手動觸發 workflow 以抓取完整歷史：

1. 進入 repo → **Actions**
2. 左側選 **Update TAIEX Data** → **Run workflow**
3. 約 1 分鐘後完成，網頁重新整理即可看到圖表

## 編輯韻腳/風管/哲學

直接修改 `data/rhymes.json`，前端會自動載入新內容。Schema 細節見檔案頂端 `meta` 區塊。

## 本地測試

```bash
pip install -r requirements.txt
python scripts/fetch_data.py   # 會產生 data/indices.json
python -m http.server 8000     # 然後開 http://localhost:8000
```

## 自動更新排程

`.github/workflows/update_data.yml` 使用 cron `30 8 * * 2-6`（UTC 08:30 = 台灣時間 16:30，週二–六對應台灣週一–五收盤後）。
