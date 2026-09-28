import { useData, type AgenrenaState, type Business } from "../api";
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
  const agenrenaLabel = !agenrena.data
    ? "—"
    : !agenrena.data.configured
      ? "未設定"
      : agenrena.data.status === "connected"
        ? "已連接"
        : agenrena.data.status === "revoked"
          ? "授權已失效"
          : "尚未連接";
  return (
    <>
      <Heading
        eyebrow="OVERVIEW"
        title="你的商家工作空間"
        description="從基本資料開始，準備好你的日常營運。"
      />
      <section className="welcome">
        <div>
          <p className="eyebrow">ONE STORE, ONE APP</p>
          <h2>{business?.name ?? "歡迎回來"}</h2>
          <p>一間店、一套 App：讓每位成員與 Agent 從同一份商家資料開始。</p>
          <button onClick={() => go("business")}>完善商家資料 ↗</button>
        </div>
        <div className="welcome-mark" aria-hidden>
          ◈
        </div>
      </section>
      <div className="stats">
        <div className="panel">
          <span>Agenrena</span>
          <strong className="smaller">{agenrenaLabel}</strong>
          <small>顧客對話中的進度通知</small>
        </div>
        <div className="panel">
          <span>商家時區</span>
          <strong className="smaller">{business?.timezone ?? "—"}</strong>
          <small>統一時間顯示的基準</small>
        </div>
      </div>
      <Alert message={agenrena.error?.message} />
      <div className="section-head compact">
        <h2>開始設定</h2>
        <span className="muted">先完成這些基本項目</span>
      </div>
      <div className="setup-list">
        {[
          [
            "01",
            "商家資料",
            "讓顧客認識你的商家：名稱、介紹、地址與電話。",
            "business",
          ],
          ...(owner
            ? [
                [
                  "02",
                  "團隊與服務",
                  "新增管理員，或連接面對顧客的 Agent。",
                  "members",
                ],
                [
                  "03",
                  "連接 Agenrena",
                  "用這間店的 Agenrena 商家身分授權，顧客就能在對話裡收到進度。",
                  "business",
                ],
              ]
            : []),
        ].map(([n, title, desc, page]) => (
          <button key={n} className="setup-row" onClick={() => go(page)}>
            <span className="step">{n}</span>
            <div>
              <strong>{title}</strong>
              <p>{desc}</p>
            </div>
            <span>→</span>
          </button>
        ))}
      </div>
    </>
  );
}
