import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  api,
  BatchItem,
  fmtAmount,
  fmtMv,
  Research,
  RESEARCH_STEPS,
  streamResearch,
} from "../api";
import KlineChart from "../components/KlineChart";
import RadarChart from "../components/RadarChart";
import WatchlistPanel from "../components/WatchlistPanel";

type StepState = {
  id: string;
  label: string;
  status: "pending" | "running" | "done" | "error";
  preview?: string;
  error?: string;
};

export default function ResearchPage() {
  const { code = "" } = useParams();
  const nav = useNavigate();
  const [data, setData] = useState<Research | null>(null);
  const [error, setError] = useState("");
  const [steps, setSteps] = useState<StepState[]>(() =>
    RESEARCH_STEPS.map((s) => ({ id: s.id, label: s.label, status: "pending" }))
  );
  const [batchRows, setBatchRows] = useState<BatchItem[] | null>(null);
  const [batchLoading, setBatchLoading] = useState(false);
  const [batchErr, setBatchErr] = useState("");

  useEffect(() => {
    let alive = true;
    setData(null);
    setError("");
    setSteps(RESEARCH_STEPS.map((s) => ({ id: s.id, label: s.label, status: "pending" })));

    streamResearch(code, (ev) => {
      if (!alive) return;
      setSteps((prev) =>
        prev.map((s) => {
          if (s.id !== ev.step) return s;
          return {
            ...s,
            status: ev.status === "running" ? "running" : ev.status === "error" ? "error" : "done",
            preview: ev.preview,
            error: ev.error,
          };
        })
      );
    })
      .then((r) => {
        if (alive) setData(r);
      })
      .catch((e: Error) => {
        if (alive) setError(e.message || "加载失败");
      });

    return () => {
      alive = false;
    };
  }, [code]);

  const up = useMemo(() => (data ? data.quote.change >= 0 : true), [data]);
  const doneCount = steps.filter((s) => s.status === "done").length;

  async function runBatch(codes: string[]) {
    setBatchLoading(true);
    setBatchErr("");
    try {
      const res = await api.batchResearch(codes);
      setBatchRows(res.items);
    } catch (e) {
      setBatchErr((e as Error).message);
    } finally {
      setBatchLoading(false);
    }
  }

  if (error && !data) {
    return (
      <div className="workspace">
        <WatchlistPanel activeCode={code} onSelect={(c) => nav(`/research/${c}`)} onBatch={(c) => void runBatch(c)} />
        <div className="error">
          <div>
            <p>{error}</p>
            <ProgressPanel steps={steps} doneCount={doneCount} code={code} />
            <Link to="/">返回</Link>
          </div>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="workspace">
        <WatchlistPanel activeCode={code} onSelect={(c) => nav(`/research/${c}`)} onBatch={(c) => void runBatch(c)} />
        <div className="loading-steps">
          <ProgressPanel steps={steps} doneCount={doneCount} code={code} />
        </div>
      </div>
    );
  }

  const q = data.quote;
  const overlays = data.chart_overlays?.overlays || [];
  const legend = data.chart_overlays?.legend || [];
  const dims = data.scorecard?.dimensions || [];

  return (
    <div className="workspace">
      <WatchlistPanel
        activeCode={data.code}
        onSelect={(c) => nav(`/research/${c}`)}
        onBatch={(c) => void runBatch(c)}
        currentStock={{ code: data.code, name: data.name, market: q.market }}
      />

      <div className="page page-compact">
        <div className="topbar compact">
          <Link className="logo" to="/">
            研盘
          </Link>
          <div className="top-search-hint">
            <Link to="/">搜索换股</Link>
          </div>
          <span className={`signal-pill ${data.scorecard?.signal || "hold"}`}>
            {data.scorecard?.signal_icon} {data.scorecard?.signal_label || data.advice?.action}
            {data.scorecard ? ` · ${data.scorecard.overall}` : ""}
          </span>
        </div>

        {(batchLoading || batchRows || batchErr) && (
          <section className="panel compact batch-panel">
            <div className="row-between">
              <h2>批量分析</h2>
              <button type="button" className="text-btn" onClick={() => setBatchRows(null)}>
                关闭
              </button>
            </div>
            {batchLoading && <p className="lead">正在批量分析…</p>}
            {batchErr && <p className="hint error-text">{batchErr}</p>}
            {batchRows && (
              <div className="batch-table-wrap">
                <table className="batch-table">
                  <thead>
                    <tr>
                      <th>信号</th>
                      <th>股票</th>
                      <th>得分</th>
                      <th>操作</th>
                      <th>摘要</th>
                    </tr>
                  </thead>
                  <tbody>
                    {batchRows.map((r) => (
                      <tr key={r.code} onClick={() => nav(`/research/${r.code}`)}>
                        <td className={`sig-cell ${r.signal}`}>
                          <span className="sig-icon">{r.signal_icon}</span>
                        </td>
                        <td>
                          <b>{r.name}</b>
                          <div className="meta">
                            {r.code}
                            {r.change_pct != null ? ` · ${r.change_pct.toFixed(2)}%` : ""}
                          </div>
                        </td>
                        <td>
                          <b>{r.overall}</b>
                        </td>
                        <td>{r.action || "—"}</td>
                        <td className="sum">{r.summary}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        <header className="quote-bar compact">
          <div className="quote-main">
            <h1>
              {data.name}
              <span className="badge">{data.degraded ? "部分降级" : "实盘"}</span>
            </h1>
            <div className="meta">
              {q.market}.{q.code} · {data.fundamental.industry}
              {data.social?.hot_rank != null ? ` · 人气第${data.social.hot_rank}` : ""}
            </div>
            <div className="price-line">
              <span className={`price ${up ? "up" : "down"}`}>{q.price.toFixed(2)}</span>
              <span className={up ? "up" : "down"}>
                {up ? "▲" : "▼"} {q.change.toFixed(2)} ({q.change_pct.toFixed(2)}%)
              </span>
            </div>
          </div>
          <div className="metrics dense">
            <div>
              <span>今开</span>
              <b>{q.open.toFixed(2)}</b>
            </div>
            <div>
              <span>最高</span>
              <b>{q.high.toFixed(2)}</b>
            </div>
            <div>
              <span>最低</span>
              <b>{q.low.toFixed(2)}</b>
            </div>
            <div>
              <span>成交额</span>
              <b>{fmtAmount(q.amount)}</b>
            </div>
            <div>
              <span>换手</span>
              <b>{(q.turnover_rate || 0).toFixed(2)}%</b>
            </div>
            <div>
              <span>量比</span>
              <b>{(q.volume_ratio || 0).toFixed(2)}</b>
            </div>
            <div>
              <span>振幅</span>
              <b>{(q.amplitude || 0).toFixed(2)}%</b>
            </div>
            <div>
              <span>市盈</span>
              <b>{(q.pe_ttm || 0).toFixed(1)}</b>
            </div>
            <div>
              <span>市净</span>
              <b>{(q.pb || 0).toFixed(2)}</b>
            </div>
            <div>
              <span>总市值</span>
              <b>{fmtMv(q.total_mv || 0)}</b>
            </div>
          </div>
        </header>

        <div className="main-grid">
          <div className="main-col">
            <KlineChart
              items={data.kline.items}
              signals={data.kline.signals}
              overlays={overlays}
              compact
            />
            <div className="signal-legend dense" aria-label="图例">
              <span className="signal-legend-label">图例</span>
              <span className="sig short">
                <i className="mark tri-up" />
                短买
              </span>
              <span className="sig short">
                <i className="mark tri-down" />
                短卖
              </span>
              <span className="sig medium">中期买卖点</span>
              {legend.map((l) => (
                <span key={l.id} className="sig overlay" style={{ borderColor: l.color }}>
                  <i className="mark band" style={{ background: l.color }} />
                  {l.label}
                </span>
              ))}
            </div>

            {data.advice && (
              <section className="panel compact advice-inline">
                <div className={`advice-banner ${data.advice.color}`}>
                  <strong>{data.advice.action}</strong>
                  <span>{data.advice.urgency}</span>
                  <span>综合 {data.advice.combo_score}</span>
                  {data.advice.capital_label ? <span>{data.advice.capital_label}</span> : null}
                </div>
                <div className="levels dense">
                  <div>
                    <span>买区</span>
                    <b>
                      {data.advice.buy_zone[0]}-{data.advice.buy_zone[1]}
                    </b>
                  </div>
                  <div>
                    <span>卖区</span>
                    <b>
                      {data.advice.sell_zone[0]}-{data.advice.sell_zone[1]}
                    </b>
                  </div>
                  <div>
                    <span>止损</span>
                    <b>{data.advice.stop_loss}</b>
                  </div>
                  <div>
                    <span>止盈</span>
                    <b>{data.advice.take_profit}</b>
                  </div>
                </div>
                <ul className="action-list dense">
                  {data.advice.reasons.slice(0, 5).map((a) => (
                    <li key={a}>• {a}</li>
                  ))}
                </ul>
              </section>
            )}
          </div>

          <aside className="side-col">
            {dims.length > 0 && (
              <section className="panel compact">
                <h2>研判蛛网</h2>
                <RadarChart dimensions={dims} overall={data.scorecard?.overall} />
                <ul className="score-mini">
                  {dims.map((d) => (
                    <li key={d.key}>
                      <span>{d.name}</span>
                      <b>{d.score}</b>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {data.capital && (
              <section className="panel compact">
                <h2>资金 · 筹码</h2>
                <p className="lead tight">{data.capital.thesis?.label}</p>
                <div className="meta">
                  成本 {data.capital.chips?.cost_zone?.mid ?? "—"} · 出逃{" "}
                  {data.capital.thesis?.exit_score ?? "—"} · 拉升{" "}
                  {data.capital.thesis?.rally_score ?? "—"}
                </div>
                <p className="meta">{data.capital.volume_phase?.label}</p>
              </section>
            )}

            {data.macro && (
              <section className="panel compact">
                <h2>宏观</h2>
                <p className="lead tight">
                  {data.macro.regime} · 风险 {data.macro.risk_score}
                </p>
                <p className="meta">{data.macro.summary}</p>
              </section>
            )}

            <section className="panel compact">
              <h2>情绪 · 舆情</h2>
              <p className="lead tight">
                {data.sentiment.label} {data.sentiment.score}
                {data.social ? ` · 舆情 ${data.social.mood_score}` : ""}
              </p>
              <p className="meta">{data.sentiment.summary}</p>
            </section>

            <section className="panel compact">
              <h2>结论</h2>
              <p className="lead tight">{data.forecast.stance}</p>
              <p className="meta">{data.forecast.summary}</p>
            </section>

            {data.llm && (
              <section className="panel compact">
                <h2>AI</h2>
                <p className="meta">
                  {data.llm.enabled
                    ? data.llm.summary
                    : data.llm.hint || "未配置 LLM（见 .env.example）"}
                </p>
              </section>
            )}

            <section className="panel compact">
              <h2>消息</h2>
              <ul className="news-list dense">
                {data.news.items.slice(0, 6).map((n) => (
                  <li key={n.id}>
                    <b className={n.sentiment === "positive" ? "up" : n.sentiment === "negative" ? "down" : ""}>
                      {n.title}
                    </b>
                  </li>
                ))}
              </ul>
            </section>
          </aside>
        </div>
      </div>
    </div>
  );
}

function ProgressPanel({
  steps,
  doneCount,
  code,
}: {
  steps: StepState[];
  doneCount: number;
  code: string;
}) {
  const pct = Math.round((doneCount / Math.max(steps.length, 1)) * 100);
  return (
    <div className="progress-panel compact">
      <h2>研究 {decodeURIComponent(code)}</h2>
      <div className="progress-bar" aria-valuenow={pct}>
        <i style={{ width: `${pct}%` }} />
      </div>
      <ol className="step-list dense">
        {steps.map((s) => (
          <li key={s.id} className={`step ${s.status}`}>
            <span className="step-mark">
              {s.status === "done" ? "✓" : s.status === "running" ? "●" : s.status === "error" ? "!" : "○"}
            </span>
            <div>
              <b>{s.label}</b>
              {s.preview && <div className="step-preview">{s.preview}</div>}
              {s.error && <div className="step-error">{s.error}</div>}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
