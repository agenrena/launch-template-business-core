# Business Core

Agenrena 商業 App 的共同起點。它與 `booking` 同層，不包含預約、商品、訂單或會員規則。

商家取得完整原始碼，讓自己的 Coding Agent 客製、測試與維護。人使用後台管理；Business Agent 透過 MCP 面對顧客。Runtime 的部署 MCP 是另一個介面。

## 內含什麼

- **一間店，一套 App**：Business 就是這間店（名稱、介紹、地址、電話、時區），沒有分店結構。連鎖或加盟時每間店各自部署一套。
- **獨立登入**：Django 帳號密碼及 session，不依賴 Agenrena 登入或共用 Firebase。
- **人的權限**：擁有者與管理員。擁有者另可管理成員、角色與 Agent 金鑰；系統保留至少一位有效擁有者。
- **基本後台**：總覽、商家資料（含 Agenrena 連接）、團隊、Agent 連接、操作紀錄、自己的密碼管理。
- **Agent 接入**：獨立的權限表與權限組，預設只有「顧客服務」。可撤銷的金鑰、Streamable HTTP / stdio。
- **Agenrena 連接**：App 是這間店在 Agenrena 上的 Vendor，店家授權一次後，業務模板可把訂單、預約等進度送進顧客與這間店的對話。
- **最小顧客身分對應**：內部 UUID + 可留空且唯一的 `agenrena_customer_ref` + 顯示名稱，不提供完整 CRM。
- **操作紀錄**：人的變更及登入／登出、Agent 成功的查詢與寫入、Agenrena 連接與通知結果；不記錄密碼、完整金鑰、Vendor secret、顧客名稱值或訊息內容。

Base 用清楚的程式結構示範如何擴充；權限組可由商家的 Coding Agent 透過程式／migration 增修，後台只顯示它們，沒有通用權限編輯器。

## 本機啟動

需要 Docker Compose、Python 3。開發編譯使用 Node 22.12+、Python 3.13、PostgreSQL。

```sh
python3 scripts/setup.py
docker compose up --build -d
docker compose exec backend python manage.py create_owner --username owner
```

最後一步私下輸入自己的密碼，不建立預設密碼。開啟 **http://localhost:8082**。

首次登入先填商家資料（名稱、地址、電話），再視需要新增管理員、Agent 連接，以及連接 Agenrena。沒有預設使用者、Agent 金鑰或顧客資料；`setup.py` 只產生部署用隨機秘密且拒絕覆蓋 `.env`。

忘記密碼時，由部署管理者執行 `docker compose exec backend python manage.py changepassword <username>`。擁有者可從後台新增帳號；重設現有密碼目前使用此管理指令。

`docker compose down` 保留資料；`down -v` 會刪除資料庫 volume。

## 顧客服務 MCP

後台「Agent 連接」建立金鑰，填入 `http://localhost:8082/mcp` 與 `Authorization: Bearer abc_…`。正式對外須使用 HTTPS。金鑰只顯示一次。

| Tool | 預設能力 |
|---|---|
| `get_business` | 查這間店的介紹、地址、電話及時區 |
| `get_customer_profile` | 查當前顧客的最小身分資料；未建立時回 null |
| `update_customer_profile` | 顧客確認後建立／更新自己的顯示名稱 |

這間店在 Agenrena 上是一個 Business Profile，有自己的客服 Agent，用這裡發的金鑰呼叫 MCP。Agenrena 隨代理訊息提供這間店的 `customer_ref`（`bcr_` 加 32 個 hex），App 對應 `CustomerIdentity.agenrena_customer_ref`；App 內的業務資料關聯其內部 UUID。同一個人在另一間店是另一套 App 裡的另一段關係。

此版本信任商家授權的 Agent 正確轉交 reference。Reference 本身不是密碼或簽章，金鑰持有人能提交其他 reference；App 不能獨立證明目前對話身分。不得把商家金鑰放到不受信任的顧客端。Agenrena 連接與通知目前以模擬的平台回應測試，尚未與真實 Agenrena 端到端驗證。

## Agenrena 連接

```text
一間店 = Agenrena 上的一個 Business Profile = 這套 App（它的 Vendor）
  ├ 一筆授權（grant）：讓 App 以店的名義對聊過的顧客發訊息
  ├ 客服 Agent：用這裡發的金鑰呼叫 MCP
  └ 顧客的 bcr_ reference
```

1. 部署環境注入 `AGENRENA_VENDOR_ID`、`AGENRENA_VENDOR_SECRET`（由 Agenrena 發給這個 App）。沒有設定時 Agenrena 功能關閉，其他功能照常。
2. owner 在「商家資料」按「連接」，畫面出現 QR code；這間店在 Agenrena 上的 owner/admin 用 Agenrena App 掃描並按同意。連結約 5 分鐘內有效。
3. 連接後，業務模板呼叫 `core.services.notify_customer` 送出的進度，會出現在顧客與這間店的對話裡。核心本身不主動發訊息。

細節見 [Agent 與權限](docs/agent.md)。

## 與業務模板／Runtime 的關係

`business_core` 是共同起點；`booking` 是可選業務模板。目前建立為獨立同層專案，**未改造既有 Booking，也沒有把它宣稱為已繼承此核心**。

`runtime.json`、Dockerfiles、`/health/` 和 `runtime_bootstrap` 符合現有 Runtime 的部署形狀。MCP 支援 `CORE_API_URL`，另接受現有 provider 的 `BOOKING_API_URL` 相容名稱。Bootstrap 只在沒有有效擁有者時建立初始帳號，拒絕覆蓋現有帳號。提供部署接法不代表已通過 Runtime 真實部署驗證。

Base 不會自動同步更新到各商家；各商家自己的 Coding Agent 評估並整合需要的更新。登入可以自行改成商家自己的 Firebase 等方式，核心不附帶這些整合。

## 修改入口

```text
backend/core/models.py          共同資料模型
backend/core/permissions.py     人的權限與 Agent 授權／顧客範圍
backend/core/services.py        共用操作、稽核、Agenrena 連接與 notify_customer
backend/core/agenrena.py        Agenrena Business Integration API client（Vendor 身分）
backend/core/views.py           後台／Agent API adapters
backend/core/migrations/        結構與預設權限資料
frontend/src/App.tsx            登入與後台導覽
frontend/src/pages/             各個後台頁面（Agenrena.tsx：Agenrena 連接與 QR code）
frontend/src/style.css          視覺樣式
mcp/src/server.ts              顧客服務工具契約
```

[產品決策](docs/product-decisions.md) · [客製開發](docs/development.md) · [Agent 與權限](docs/agent.md) · [部署](docs/deployment.md) · [驗證](docs/verification.md)
