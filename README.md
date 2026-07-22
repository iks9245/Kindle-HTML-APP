# Kindle AI 每日文摘

一個部署在 GitHub Pages 上、專為 Kindle 實驗性瀏覽器設計的 AI 每日文摘網頁。

原理很簡單：GitHub Actions 每天定時抓取你設定的 RSS 來源，用 LLM（Gemini 或
OpenAI／OpenAI 相容端點）把每篇文章摘要成 2-4 句話，排版成純靜態、高對比、無
JavaScript 的 HTML，推送到 `docs/` 目錄由 GitHub Pages 發佈。Kindle 端只需要打開
瀏覽器訪問一個網址，不需要跑任何前端邏輯 — 這是刻意的設計，因為 Kindle 的實驗性
瀏覽器是老舊 WebKit，對現代 JS/CSS 支援很差、螢幕刷新也慢。

抓取全文時擷取到的內文會一併存成**離線全文頁**（`docs/article/`），文摘裡每篇的
「全文」連結指向這些本地頁面，讓你在 Kindle 上直接讀乾淨排版的內文，不必用那顆
慢吞吞的瀏覽器去載入充滿現代 JS 的外部網站；需要時仍可從頁面上的「原文網頁」外連
到原始來源。

每天的文摘最上方還有一段 **AI 主編導讀**：把當天所有摘要餵給 LLM，寫成一段跨文章的
「今日大局」，讓文摘從「一堆摘要」變成有編輯視角的一份報紙。導讀會一併烤進當天的
存檔頁，過去每天都保有自己的導讀。可在 `config.yaml` 把 `editor_brief` 設成 `false`
關閉。

首頁還有一個**昨日回顧小考**（`docs/quiz.html`）：每天用 LLM 依前一天讀過的文章
出幾道題，點開題目才顯示答案（純 CSS `<details>`，一樣不需要 JS）。這是刻意的間隔
複習設計，把「早上滑一下新聞」變成順手回想昨天讀了什麼。題數可在 `config.yaml` 的
`quiz_questions` 調整，設成 `0` 即關閉。

## 目錄結構

```
config.yaml                 # 訂閱來源、語言、時區、模型設定
digest/                     # 產生文摘的 Python 程式
  fetch.py                    # 抓 RSS + 擷取全文
  summarize.py                # 呼叫 Gemini / OpenAI 相容 API 摘要
  render.py                   # 用 Jinja2 產生靜態 HTML
  main.py                     # 串起以上流程的入口
templates/                  # Kindle 友善的 HTML 模板（大字體、高對比、無 JS）
docs/                       # 產生出來的靜態網站（GitHub Pages 發佈來源）
  index.html                  # 今日文摘
  quiz.html                   # 昨日回顧小考（純 CSS，無 JS）
  archive/                    # 過去每日文摘存檔
  article/                    # 每篇文章的離線全文頁
.github/workflows/          # 每日排程的 GitHub Actions
```

## 設定步驟

1. **選擇 LLM 供應商**：編輯 `config.yaml` 的 `provider`：
   - `gemini`：使用 Google Gemini API，`model` 填 `gemini-2.5-flash` 之類。
   - `openai`：使用 OpenAI 或任何 OpenAI 相容端點（OpenRouter、自架 vLLM／
     gateway 等），`model` 填對應的模型名稱；如果不是打 api.openai.com，
     把 `openai_base_url` 取消註解並填上端點網址。
2. **新增 API 金鑰**：Repo 的 `Settings → Secrets and variables → Actions →
   New repository secret`，依你選的 provider 新增：
   - 用 Gemini：新增 `GEMINI_API_KEY`
   - 用 OpenAI／相容端點：新增 `OPENAI_API_KEY`
   （兩個都加也沒關係，workflow 會把兩個都傳進去，只有實際用到的那個會被讀取。）
3. **編輯 `config.yaml`**：調整 RSS 來源清單（`feeds`）、摘要語言（`language`）、
   時區（`timezone`）。
4. **開啟 GitHub Pages**：`Settings → Pages → Source` 選擇 `Deploy from a branch`，
   Branch 選 `main`，資料夾選 `/docs`。
5. **確認排程**：`.github/workflows/daily-digest.yml` 預設每天 UTC 22:00（台灣時間
   早上 6 點）執行一次，也可以到 Actions 分頁手動觸發 `Daily AI Digest` 立即產生
   第一份文摘。

## 在 Kindle 上使用

1. 打開 Kindle 的實驗性瀏覽器（工具 → 實驗性瀏覽器，或依機型從主選單進入）。
2. 輸入你的 GitHub Pages 網址：`https://<你的帳號>.github.io/<repo 名稱>/`
3. 把它加入書籤 / 設成首頁，之後每天打開就能看到最新文摘，左上角也有「存檔列表」
   可以回顧過去幾天的內容。

## 本機測試

```bash
pip install -r requirements.txt

# 依 config.yaml 裡的 provider 擇一設定：
export GEMINI_API_KEY=...
# 或
export OPENAI_API_KEY=...

python -m digest.main
```

執行完成後 `docs/` 目錄會更新，可以直接用瀏覽器打開 `docs/index.html` 預覽。

## 之後可以擴充的方向

- 用 Kindle 的 *Send to Kindle* email 或 Readwise 匯入每日高亮，讓 AI 做主題整理。
- 加入生詞卡片頁面，把摘要中出現的生字自動做成單字卡。
- 依使用者興趣關鍵字做個人化排序，而不是固定的 RSS 清單。
