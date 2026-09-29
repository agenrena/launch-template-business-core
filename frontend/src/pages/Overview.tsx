import { useData, type AgenrenaState, type AgentKey, type Business } from "../api";
import { Alert } from "../ui";
import { Heading } from "../Heading";

export function Overview({
  business,
  go,
  owner,
}: {
  business?: Business;
  go: (p: string) => void;
  owner: boolean;
}) {
  const agenrena = useData<AgenrenaState>("agenrena/");
  const keys = useData<AgentKey[]>("keys/", owner);
  const connected = agenrena.data?.status === "connected";
  const agenrenaLabel = !agenrena.data
    ? "—"
    : !agenrena.data.configured
      ? "未設定"
      : connected
        ? "已連接"
        : agenrena.data.status === "revoked"
          ? "授權已失效"
          : "尚未連接";
  const activeKeys = keys.data?.filter((k) => !k.revoked_at).length ?? 0;
  const steps: [string, string, string, boolean, string][] = [
    [
      "商家資料",
      "讓顧客認識你的商家：名稱、介紹、地址與電話。",
      "business",
      Boolean(business?.name && business.address && business.phone),
      "已填寫",
    ],
    ...(owner
      ? ([
          [
            "連接顧客服務 Agent",
            "建立金鑰，讓這間店的 Agent 查資料、服務顧客。",
            "agents",
            activeKeys > 0,
            "已連接",
          ],
          [
            "連接 Agenrena",
            "用這間店的 Agenrena 商家身分授權，顧客就能在對話裡收到進度。",
            "business",
            connected,
            "已連接",
          ],
        ] as [string, string, string, boolean, string][])
      : []),
  ];
  const done = steps.filter((s) => s[3]).length;
  return (
    <>
      <Heading
        title="你的商家工作空間"
        description="從基本資料開始，準備好你的日常營運。"
      >
        <button className="primary" onClick={() => go("business")}>
          編輯商家資料
        </button>
      </Heading>
      <section className="panel store-card">
        <span className="tile large">{(business?.name || "商")[0]}</span>
        <div>
          <h2>{business?.name || "尚未填寫商家名稱"}</h2>
          <p>
            {[business?.address, business?.phone].filter(Boolean).join(" · ") ||
              "填上地址與電話，Agent 才能回答顧客。"}
          </p>
        </div>
      </section>
      <div className="stats">
        <div>
          <span>Agenrena</span>
          <strong>
            <i className={connected ? "dot ok" : "dot"} />
            {agenrenaLabel}
          </strong>
          <small>顧客對話中的進度通知</small>
        </div>
        <div>
          <span>商家時區</span>
          <strong>{business?.timezone ?? "—"}</strong>
          <small>統一時間顯示的基準</small>
        </div>
        {owner && (
          <div>
            <span>Agent 金鑰</span>
            <strong>{keys.data ? `${activeKeys} 把有效` : "—"}</strong>
            <small>顧客服務 Agent 的連線</small>
          </div>
        )}
      </div>
      <Alert message={agenrena.error?.message || keys.error?.message} />
      <div className="section-head compact">
        <h2>開始設定</h2>
        <span className="muted">
          完成 {done} / {steps.length}
        </span>
      </div>
      <div className="setup-list">
        {steps.map(([title, desc, page, ok, okLabel]) => (
          <button key={title} className="setup-row" onClick={() => go(page)}>
            <span className={ok ? "step-check done" : "step-check"} />
            <div>
              <strong>{title}</strong>
              <p>{desc}</p>
            </div>
            <span className={ok ? "badge ok" : "badge brand"}>
              {ok ? okLabel : "未完成"}
            </span>
            <span className="arrow">→</span>
          </button>
        ))}
      </div>
    </>
  );
}
