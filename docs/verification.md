# 驗證紀錄

## 2026-09-28：一間店一套 App，Agenrena 連接

在 scratchpad 的獨立 venv 與臨時 PostgreSQL 14 叢集執行，不讀寫既有 Booking、Runtime 或 Agenrena 資料；Agenrena 以模擬的 HTTP 回應代替，沒有連到真實平台。當天先做過以 Location 為單位的版本，同日決定拿掉 Location，以下為最終版本的結果；沒有既有資料，initial migration 直接重寫。

| 檢查 | 結果 |
|---|---|
| Django / PostgreSQL | 32 項測試通過：原有核心測試（`bcr_` 格式、店家地址電話提供給 Agent）與 Agenrena 12 項：連接流程、授權過期、已連接需先中斷、中斷交還 grant、admin 只能查看、未設定 Vendor 時照常運作、平台故障回 502 且不外洩 secret、通知在交易提交後送出、無 reference／未連接略過、撤銷後停止、顧客不存在只記錄、Vendor token 快取與重換 |
| Migration | 重寫的 0001／0002：全新 migrate 與 makemigrations --check --dry-run 通過 |
| Frontend | TypeScript / Vite 正式建置通過（Node 22.23.2） |
| MCP | 6 項測試通過（3 個工具），含拒絕 `guest` 與大寫 reference |
| 真實 HTTP | `scripts/http_smoke.py`：Vite proxy、session／CSRF 登入、Agenrena 狀態（未設定）、Streamable HTTP 工具、撤銷金鑰被拒絕通過 |
| HTTP client | 以假的 Agenrena HTTP 伺服器驗證 token 換發、`X-Grant-Id`、token 被拒後重換、欄位錯誤碼、交還 grant（204／已失效）、平台無法連線 |
| 程式整理 | Ruff check / format，前端與 MCP 以 Prettier 整理 |

尚未執行：瀏覽器畫面與 QR 連接流程的實際操作、與真實 Agenrena 的授權與發訊息、完整 Docker image build 與 Compose 啟動、Runtime 部署。

## 2026-09-27：初版

2026-09-27。在獨立暫存環境及 PostgreSQL 17 執行，不讀寫既有 Booking、Runtime 或 Agenrena 資料。

| 檢查 | 結果 |
|---|---|
| Django / PostgreSQL | 20 項測試通過：人的角色、CSRF、最後擁有者、停用帳號、密碼更新、金鑰撤銷、權限即時變更、顧客範圍、同名不合併、並行身分建立、稽核與 bootstrap |
| Migration | 實際 migrate + makemigrations --check --dry-run 通過 |
| Frontend | TypeScript / Vite 正式建置通過（Node 22.23.2） |
| MCP | 6 項 SDK in-memory protocol/API wrapper 測試通過 |
| 真實 HTTP | 暫時 Vite / Django / MCP：後台 session、CSRF 登入、設定修改、稽核、登出通過 |
| Streamable HTTP | SDK initialize、tools/list、顧客資料讀寫／重試／另一 reference 無資料、撤銷 key 被拒絕通過 |
| Compose | docker compose config --quiet 通過 |
| nginx | 以本機 upstream 展開設定後 nginx -t 通過 |
| 程式整理 | Ruff check / format，前端與 MCP 以 Prettier 整理 |
| npm 依賴 | MCP 的 hono / qs 間接依賴已更新，npm audit 回報 0 項；frontend 安裝回報 0 項 |

尚未執行：瀏覽器視覺／互動驗收、完整 Docker image build 與 Compose 啟動、實際 Runtime 部署、AWS、Agenrena 真實聊天室端到端整合。不能把 API 成功當成畫面驗收。

交付沒有 .env、預設帳密、Agent keys、顧客資料、node_modules 或 .venv。HTTP 測試使用的隨機帳密只存在測試程序中；測試資料庫與程序均在 finally 清理。
