# Issues

## 1. History Filter

在擷取 history 後、送入 retrieve 前，使用 LLM 篩選與當前問題相關的歷史訊息，僅將相關訊息傳給 retrieve 和 generate 節點，避免無關對話干擾檢索與生成。

**解決方案**：新增 `filter_history` 節點，輸出 `filtered_messages` 供後續節點使用。

---

## 2. Coreference Problem

當使用者使用指代詞（如「它」、「這個」、「那份作業」）提問時，retrieve 節點僅以原始問題做向量搜尋，缺乏對話脈絡，導致檢索品質下降。

**範例**：
- 使用者：「Requirement 3 是什麼？」
- AI 回答後，使用者：「**它**有什麼限制？」
- 問題：retrieve 搜尋「它有什麼限制」→ 語意模糊，檢索效果差

**解決方案**：在 `filter_history` 節點中讓 LLM 輸出 `expanded_query`（已解析指代的查詢），retrieve 使用 `expanded_query` 進行向量搜尋。

---

## 3. Notion 課程專區與作業同步（2026-03-24）

### 已完成項目

- 左側新增「課程專區」：
  - 下拉載入 Notion 課程 DB（`/api/notion/courses`）
  - 可依課程切換歷史作業（`/api/notion/homeworks`）
- 新增作業表單：
  - 建立 Notion homework 記錄（Name / 準備時間 / 相關課程 / tag）
  - `status` 改為下拉選單（`Not started`, `In progress`, `almost_done`, `Done`）
  - `tags` 固定預設為 `作業`（不需使用者輸入）
- 作業 PDF 流程：
  - 建立作業時可上傳 PDF
  - PDF 會寫入 Notion `files` 欄位
  - PDF 同步用既有 `LangChainService.process_file()` 切片後寫入 Chroma
  - 歷史列表支援 `預覽` 連結
- 歷史補傳附件流程：
  - 若作業尚無 PDF，在原本預覽位置顯示 `上傳` 按鈕
  - 補傳後同時更新 Notion `files` 與 Chroma

### 本次修正問題

- 修正 Notion 新版 `data_sources` schema 相容問題（避免 `/api/notion/courses` 500）
- 修正 homework DB 欄位名稱大小寫不一致（`tags` vs `Tags`）導致新增失敗
- 修正 `APIResponseError` 錯誤訊息取值造成二次例外（改為 `str(error)`）

### 新增/調整 API

- `GET /api/notion/courses`
- `GET /api/notion/homeworks?course_id=...`
- `POST /api/notion/homeworks`
- `POST /api/notion/homeworks/<homework_id>/file`
