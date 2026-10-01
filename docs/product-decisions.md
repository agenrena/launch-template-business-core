# 已確認產品決策

2026-09-27；Agenrena 連接：2026-09-28。

1. 這是 Agenrena 旗下產品。共通基礎名為 business_core，與 booking 同層；Booking 是可選模板，不是所有 App 的底座。
2. 核心範圍：Business（這間店）、使用者、登入、基本後台、Agent 接入、Agenrena 連接、操作紀錄。
3. **一間店，一套 App。** Business 就是這間店，沒有 Location／分店結構，也不是 multi-tenant。連鎖或加盟時每間店各自部署一套 App（2026-09-28 取代原本的「一個 Business 多個 Location」）。
4. 登入預設獨立 Django 帳號密碼。沒有 Agenrena SSO，不共用 Agenrena Firebase；商家自行客製其他登入方式。
5. 人預設 owner / admin。第一位 owner 在本機由這台電腦的網頁建立（見 21），在伺服器上私下設定密碼或由 Runtime 提供隨機初始憑證。禁止移除最後一位有效 owner。
6. Coding Agent 修改程式與處理部署；Business Agent 預設面對顧客，並非管理後台的營運代理。
7. Agent 有獨立權限表，預設一個 customer_service 權限組。各功能明確檢查操作與資料範圍，後續角色由商家自行修改。
8. Agenrena 提供固定 customer_ref。App 以可空且有值時唯一的 agenrena_customer_ref 對應內部顧客身分 UUID（見 17）。手動顧客可沒有 reference，不按姓名／電話自動合併。
9. 第一版信任授權 Agent 正確帶入 Agenrena 對話 reference，不增加簽章。其隨機性由 Agenrena 產生器決定，本專案不宣稱已驗證不可猜測性。
10. CustomerIdentity 僅示範身分對應與顧客範圍，不含 CRM、訂單或預約。業務模板自行增加其功能。
11. 特殊規則由商家改程式；不為所有可能需求加入 Settings、plugins 或 workflow engine。
12. Runtime 負責託管；商家與自己的 Coding Agent 負責客製、測試與維護。不自動替商家合併 Base 更新。

## 一間店與 Agenrena（2026-09-28）

模板示範的是我們認為的未來：顧客面對的是「店」，店在 Agenrena 上有代表它的 Agent；Agent 的能力來自店的軟體，軟體掌握事實並把結果推回對話。最乾淨的形狀是：**一間店 = Agenrena 上的一個 Business Profile = 一套 App = 一個 Vendor = 一筆授權 = 一隻客服 Agent。**

13. **App 是這間店的 Vendor。** Vendor 憑證（`AGENRENA_VENDOR_ID`／`AGENRENA_VENDOR_SECRET`）只從部署環境注入，不進原始碼、log、API 回應或前端。每個部署出去的 App 各有自己的 Vendor，預設打開；沒有設定時 Agenrena 功能關閉，其他功能照常。Vendor 的建立與輪替在模板之外（目前由 Agenrena admin 發給，之後可由 Runtime 自動化）。這正是 Agenrena 所說「沒有開發商的商家，自己就是 Vendor」。
14. **拿掉 Location。** 情境比較後決定：單店不需要據點概念；加盟店共用一套 App 會缺少依店的權限；單店客製會牽動其他店；Agenrena 本來就把每間店當成不同的 Business Profile 與不同的顧客 reference。只有「同一老闆的多間分店想共用菜單、合併報表」受影響，這屬於品牌層需求，留給 Agenrena 的品牌層（BusinessGroup／group_ref）或之後另外處理，不塞進每套 App。地址、電話併入 Business。
15. **授權一次。** 這間店最多一筆 grant（scope 只有 `messages:send`），由 owner 在「商家資料」產生授權連結，該店在 Agenrena 上的 owner/admin 用 App 掃描同意。admin 只能查看狀態。
16. **Agent 金鑰代表這間店。** 客服 Agent 只替這間店服務；顧客想去其他分店，由那間店自己的 App 與 Agent 服務。
17. **顧客關係屬於這間店。** `customer_ref` 是 Agenrena 以店發給的 `bcr_` 值；同一個人在另一間店（另一套 App）是另一段關係，不跨 App 合併。
18. **通知是核心能力，事件由業務模板決定。** 核心提供 `notify_customer`，在交易提交後送進顧客與這間店的對話；送達失敗不影響業務資料，店家撤銷授權後自動停止。核心本身不主動發訊息。
19. **不在這一版：** identity link（有簽章的顧客身分連結）、Runtime 自動建立 Vendor 與輪替、接收顧客訊息（inbound webhook）、品牌層跨店識別與合併報表。

## 預設在店家自己的電腦上（2026-09-30）

20. **Agent 由商家帶來、跑在商家這一端**；Agenrena 是帶著自己 Agent 進來的社群，不代管 Agent，也不回呼 App。所以 App 不需要對外網址：Agent 在同一台電腦以 stdio 使用 MCP，通知由 App 主動連出 Agenrena。
21. **預設本機執行，伺服器是選項。** 一間店 = 一個資料夾：只需要 uv 與 Node.js，SQLite 資料在 `data/`，點兩下 `start.command`／`start.bat` 就開始，第一次在網頁上建立擁有者。拿掉的是 Docker 與資料庫伺服器（最容易卡住不懂軟體的人），保留 Python + Node（Agent 能自己裝，而且改前端本來就需要 Node）。需要顧客直接開網頁或隨時遠端連線的店（例如點餐）再用 Docker Compose + PostgreSQL 放到伺服器；同一份程式碼。
22. 同時支援 SQLite 與 PostgreSQL，只用兩者都有的功能。「先檢查再寫入」靠 services 裡的交易與鎖，不靠 PostgreSQL 專屬的資料庫限制。

## 軟體名稱（2026-10-02）

登入頁、後台左上角和瀏覽器分頁使用商家的軟體名稱；直接從 GitHub 取得時預設為 `Core`。Agenrena Business 下載會寫入 `backend/app-config.json` 的 `software_name`（最多 120 字），首次建立商家資料時保存至資料庫。檔案缺少、空白或無效時使用模板預設值。後台「商家資料」可改名，之後啟動不會用下載設定覆蓋。軟體名稱與商家名稱分開，也不會同步改動 Agenrena 上的 App/Vendor 名稱。頁底的 `Powered by Agenrena` 可自行移除，不影響功能。此版本只針對全新初始化，沒有舊資料搬移流程。
