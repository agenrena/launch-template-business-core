# 驗證紀錄

## 2026-09-30：預設在這台電腦上執行

後續（同步 booking 時）：MCP 設定裡的伺服器名稱改由 `settings.MCP_NAME` 提供（核心 `business-core`、booking `booking`），讓 `core/views.py` 與 `pages/Agents.tsx` 在各模板保持相同；36 項測試在 SQLite 與 PostgreSQL 重跑通過，前端建置通過。

在 scratchpad 複製一份乾淨專案（沒有 `.env`、`node_modules`、建置結果或資料），以只有 `/usr/bin:/bin` 的 PATH 執行 `./start.command --no-browser`；Agenrena 未設定，沒有連到真實平台。

| 檢查 | 結果 |
|---|---|
| 首次啟動 | wrapper 自己找到 uv 與 nvm 裡符合 `.nvmrc` 的 Node（預設 alias 是 22.11，低於 22.12，改用 `nvm use`），產生 `.env`、安裝與建置前端和 MCP、建立 `data/db.sqlite3`（WAL），在 127.0.0.1:8082 提供畫面與 API |
| 首次建立擁有者 | 真實 HTTP（含 CSRF 與 Origin）：session 回報可建立 → 建立後直接登入 → 第二次建立被拒（403）；另以 Chrome 截圖確認建立畫面、建立後進入工作空間 |
| 本機 Agent | 用後台給的 `mcpServers` 設定以 stdio 啟動 MCP：tools/list、get_business、update/get_customer_profile 都成功 |
| Agent 連接頁 | 截圖確認 stdio 設定段落；建立金鑰後設定已填入金鑰 |
| 重新啟動 | 執行中再啟動只提示已在執行；停止後再啟動不重新安裝或建置，資料與登入都在 |
| `manage` | `./start.command manage shell -c …` 讀得到這間店的資料 |
| Django | 36 項測試在 SQLite 與 PostgreSQL 17 都通過（新增：本機建立擁有者只限一次與本機、伺服器模式與非本機拒絕、MCP 連接資訊、提供建置畫面與拒絕跳出資料夾的路徑）；makemigrations --check 通過 |
| Frontend / MCP | 正式建置通過（含 check:style）；MCP 6 項測試通過 |
| 程式整理 | Ruff、Prettier（修改過的檔案） |
| 伺服器也改用 waitress | 拿掉 gunicorn。以 Dockerfile 的同一個 `waitress-serve` 指令接 PostgreSQL 17：runtime_bootstrap、health、登入、網頁建立擁有者不開放；帶 `X-Forwarded-Proto: https` 時 MCP 網址為 `https://`。對照組不加 `--no-clear-untrusted-proxy-headers` 時 waitress 會刪掉這個標頭，網址變回 `http://`，所以此參數必要 |
| Docker Compose | 乾淨副本 `docker compose up --build`（Docker 24）：四個 image 建置成功，backend 由 waitress 服務且健康檢查通過。經 nginx：畫面、`/health/`、runtime_bootstrap、登入、修改商家資料、網頁建立擁有者不開放（403）、MCP 網址在 HTTPS proxy 後為 `https://`、Streamable HTTP MCP（initialize、tools/list、顧客範圍讀寫與重試）、撤銷金鑰後 401。測完 `down -v` 刪除 |

尚未執行：Windows 上的 `start.bat`、macOS 在 Finder 點兩下 `start.command`（下載來的檔案可能被 Gatekeeper 擋下）、與真實 Agenrena 的授權與通知。

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
