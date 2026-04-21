# 台股週期儀表板

## 上線步驟

### 1. 建立 GitHub Repository
1. 登入 GitHub → 右上角「+」→「New repository」
2. 名稱填：`taiex-cycles`
3. 選 **Public**（GitHub Pages 免費方案需要）
4. 按「Create repository」

### 2. 上傳檔案
把以下所有檔案上傳到 repository（可直接拖曳到 GitHub 網頁）：
```
index.html
pages/decade.html
pages/yearly.html
data/taiex.json
js/charts.js
scripts/fetch_data.py
.github/workflows/update_data.yml
```

注意：`.github` 資料夾要確保有上傳

### 3. 開啟 GitHub Pages
1. Repository → Settings → Pages
2. Source 選「Deploy from a branch」
3. Branch 選「main」，資料夾選「/ (root)」
4. 按 Save

幾分鐘後網站就在：`https://你的帳號.github.io/taiex-cycles/`

### 4. 手動觸發第一次數據更新
1. Repository → Actions
2. 左側選「Update TAIEX Data」
3. 按「Run workflow」→「Run workflow」
4. 等待約 1 分鐘完成
5. 回到網站重新整理，圖表出現數據

### 5. 之後自動運作
每個週二到六台灣時間 16:30 自動抓取最新數據，不需要任何操作。

---

## 未來擴充
- 新增總經指標（美債殖利率、黃金等）：在 `scripts/fetch_data.py` 加入新 ticker，新增對應 JSON 欄位
- 新增圖表頁面：複製 `pages/decade.html` 修改邏輯即可
