---
trigger: always_on
description: OK-Wuthering-Waves (Estrella-071 Fork) 專案架構與開發工作流規範
---

# OK-Wuthering-Waves (Estrella-071 Fork) 開發手冊

## 1. 溝通與基礎規範
- **語言**：全過程使用 **繁體中文** (Traditional Chinese) 與使用者溝通（包含計畫、任務與註釋）。
- **原則**：遵守 **Fail Fast** 與 **DRY** 原則。
- **主動性**：作為 AI 助理，應主動追蹤任務狀態，但在涉及重大邏輯修改前應徵詢使用者意見。

## 2. Estrella-071 Git 開發工作流 (核心)
- **倉庫權限**：
  - 開發在 **Estrella-071** 帳號的 fork 倉庫：`https://github.com/Estrella-071/ok-wuthering-waves`。
  - 絕對禁止直接修改或推送至 `main` / `master` 分支。
- **前置作業**：
  - 修改前先執行 `git status` 與 `git branch -a` 確認狀態。
  - 建立新分支前，必須先從 `upstream/master` (官方倉庫) 執行 `git pull` 以對齊基底。
- **開發與驗證**：
  - 於功能分支開發，完成後進行實機測試與自動化測試。
- **整理 Commit (重要)**：
  - 推送遠端前，必須透過 `git rebase` / `git reset` 將 Commit 紀錄清理為 **1 個或 2 個最簡潔的紀錄**（例如：一個實作功能，一個處理語系）。
  - 確保分支基底是上游 (`upstream/master`) 最新的狀態。
- **PR 流程**：
  - 使用者會手動建立 PR。
  - 開發完成後，整理 PR 所需的 **簡要 diff、測試通過 Log 截圖、以及修改說明** 供使用者參考。

## 3. 程式碼規範
- **代碼風格**：保持代碼精簡 (Clean Code)，移除不必要的中文註釋，尤其是循環執行中的解釋性註解。
- **同步更新**：邏輯變更後，同步更新 docstring、註解以及相關 README 說明。
- **一致性**：若專案中已存在某種解決方案（即使包含歷史遺留問題），應優先考慮與現有風格一致（入境隨俗），除非使用者明確要求重構。