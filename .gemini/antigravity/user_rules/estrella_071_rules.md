# Estrella-071 分支：開發規範與避坑指南

> [!IMPORTANT]
> 在進行任何代碼修改前，請務必先閱讀項目 artifact 中的最新 `branch_rules.md` 目錄：`C:\Users\zhiwa\.gemini\antigravity\brain\a0bc972b-03d9-49b1-a4b2-0cb24ecc327d\branch_rules.md` (或本文件的副本)。

## 1. 核心哲學
「以視覺辨識取代死等（Sleep），以狀態機補償動畫延遲。」優化的是等待，而非步驟。

## 2. 重試頻率分級
- **0.1s**：純等待類。
- **0.3s**：導航、分頁切換（預設，減少 Log 噪音）。
- **0.5s**：敏感獎勵領取。

## 3. 重要禁忌
- `ocr()` **不接受** `time_out` 參數。超時辨識務必使用 `wait_ocr()`。
- 領取獎勵（`claim_daily`）嚴禁使用高頻重試連點，必須點擊一次後等待視覺變化。
- 嚴禁刪除 UI 切換中的關鍵 Esc/Sleep 步驟（如 P3 郵件選單邏輯）。

## 4. 多國語言要求
修改文字標籤後必須運行 `python compile_mo.py`。
