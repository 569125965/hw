import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  fmtAmount,
  fmtMv,
  Research,
  RESEARCH_STEPS,
  streamResearch,
} from "../api";
import KlineChart from "../components/KlineChart";

const TABS = ["建议", "盘面", "基本面", "行业", "消息", "舆情", "情绪", "结论"] as const;

type StepState = {
  id: string;
  label: string;
  status: "pending" | "running" | "done" | "error";
  preview?: string;
  error?: string;
};

export default function ResearchPage() {
  const { code = "" } = useParams();
  const [data, setData] = useState<Research | null>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<(typeof TABS)[number]>("建议");
  const [steps, setSteps] = useState<StepState[]>(() =>
    RESEARCH_STEPS.map((s) => ({ id: s.id, label: s.label, status: "pending" }))
  );

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

  if (error && !data) {
    return (
      <div className="error">
        <div>
          <p>{error}</p>
          <ProgressPanel steps={steps} doneCount={doneCount} code={code} />
          <Link to="/">返回搜索</Link>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="loading-steps">
        <ProgressPanel steps={steps} doneCount={doneCount} code={code} />
      </div>
    );
  }

  const q = data.quote;

  return (
    <div className="page">
      <div className="topbar">
        <Link className="logo" to="/">
          研盘 AShare Lab
        </Link>
        <Link className="primary-btn" to="/">
          换一只
        </Link>
      </div>

      <header className="quote-bar">
        <div className="quote-main">
          <h1>
            {data.name}
            {data.degraded ? (
              <span className="badge">部分降级</span>
            ) : (
              <span className="badge">实盘</span>
            )}
          </h1>
          <div className="meta">
            {q.market}.{q.code} · {data.fundamental.industry}
          </div>
          <div className="price-line">
            <span className={`price ${up ? "up" : "down"}`}>{q.price.toFixed(2)}</span>
            <span className={up ? "up" : "down"}>
              {up ? "▲" : "▼"} {q.change.toFixed(2)} ({q.change_pct.toFixed(2)}%)
            </span>
          </div>
        </div>
        <div className="metrics">
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
            <b>{q.turnover_rate.toFixed(2)}%</b>
          </div>
          <div>
            <span>量比</span>
            <b>{q.volume_ratio.toFixed(2)}</b>
          </div>
          <div>
            <span>振幅</span>
            <b>{q.amplitude.toFixed(2)}%</b>
          </div>
          <div>
            <span>市盈率</span>
            <b>{q.pe_ttm.toFixed(1)}</b>
          </div>
          <div>
            <span>总市值</span>
            <b>{fmtMv(q.total_mv)}</b>
          </div>
        </div>
      </header>

      <KlineChart items={data.kline.items} signals={data.kline.signals} />

      <div className="signal-legend" aria-label="买卖点图例">
        <span className="signal-legend-label">买卖点</span>
        <span className="sig short">
          <i className="mark tri-up" aria-hidden />
          短买
        </span>
        <span className="sig short">
          <i className="mark tri-down" aria-hidden />
          短卖
        </span>
        <span className="sig medium">
          <i className="mark circle" aria-hidden />
          中买
        </span>
        <span className="sig medium">
          <i className="mark square" aria-hidden />
          中卖
        </span>
        <span className="signal-legend-hint">短期 / 中期定义详见文档</span>
      </div>

      <nav className="tabs" role="tablist">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            role="tab"
            aria-selected={tab === t}
            className={tab === t ? "active" : ""}
            onClick={() => setTab(t)}
            style={{ minHeight: 44, minWidth: 64 }}
          >
            {t}
          </button>
        ))}
      </nav>

      {tab === "建议" && data.advice && (
        <section className="panel">
          <h2>当前买卖操作建议</h2>
          <div className={`advice-banner ${data.advice.color}`}>
            <strong>{data.advice.action}</strong>
            <span>{data.advice.urgency}</span>
            <span>综合 {data.advice.combo_score}</span>
            <span>周期 {data.advice.horizon}</span>
          </div>
          <div className="levels">
            <div>
              <span>买入参考区</span>
              <b>
                {data.advice.buy_zone[0]} - {data.advice.buy_zone[1]}
              </b>
            </div>
            <div>
              <span>卖出参考区</span>
              <b>
                {data.advice.sell_zone[0]} - {data.advice.sell_zone[1]}
              </b>
            </div>
            <div>
              <span>止损</span>
              <b>{data.advice.stop_loss}</b>
            </div>
            <div>
              <span>止盈参考</span>
              <b>{data.advice.take_profit}</b>
            </div>
          </div>
          <p className="lead">
            技术 {data.advice.tech_score} · 舆情 {data.advice.social_score} · 现价 {data.advice.price}
          </p>
          <h3>依据</h3>
          <ul className="action-list">
            {data.advice.reasons.map((a) => (
              <li key={a}>• {a}</li>
            ))}
          </ul>
          <h3>执行清单</h3>
          <ul className="action-list">
            {data.advice.checklist.map((a) => (
              <li key={a}>• {a}</li>
            ))}
          </ul>
          <p className="disclaimer">{data.advice.disclaimer}</p>
        </section>
      )}

      {tab === "盘面" && (
        <section className="panel">
          <h2>盘面结构</h2>
          <p className="lead">K 线上方为主图，下方为量能与 MACD，便于快速判断多空与量价配合。</p>
          <div className="levels">
            <div>
              <span>MA20</span>
              <b>{data.forecast.levels.ma20?.toFixed(2)}</b>
            </div>
            <div>
              <span>MA60</span>
              <b>{data.forecast.levels.ma60?.toFixed(2)}</b>
            </div>
            <div>
              <span>支撑</span>
              <b>{data.forecast.levels.support?.toFixed(2)}</b>
            </div>
            <div>
              <span>压力</span>
              <b>{data.forecast.levels.resistance?.toFixed(2)}</b>
            </div>
          </div>
        </section>
      )}

      {tab === "基本面" && (
        <section className="panel">
          <h2>产品与业务</h2>
          <p className="lead">{data.fundamental.business_summary}</p>
          <div className="tag-row">
            {data.fundamental.concepts.map((c) => (
              <span className="tag" key={c}>
                {c}
              </span>
            ))}
          </div>
          <ul className="product-list">
            {data.fundamental.products.map((p) => (
              <li key={p.name}>
                <b>
                  {p.name} · {(p.share * 100).toFixed(0)}%
                </b>
                <div className="meta">{p.desc}</div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {tab === "行业" && (
        <section className="panel">
          <h2>行业与同业</h2>
          <p className="lead">所属行业：{data.fundamental.industry}</p>
          <ul className="peer-list">
            {data.fundamental.peers.map((p) => (
              <li key={p.code}>
                <Link to={`/research/${p.code}`}>
                  <b>
                    {p.name} ({p.code})
                  </b>
                </Link>
                <div className={(p.change_pct ?? 0) >= 0 ? "up" : "down"}>
                  {(p.change_pct ?? 0) >= 0 ? "▲" : "▼"} {(p.change_pct ?? 0).toFixed(2)}%
                  {p.price != null ? ` · ${p.price.toFixed(2)}` : ""}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {tab === "消息" && (
        <section className="panel">
          <h2>消息面</h2>
          <p className="lead">公告/资讯时间线，颜色标记情绪倾向。</p>
          <ul className="news-list">
            {data.news.items.map((n) => (
              <li key={n.id}>
                <b className={n.sentiment === "positive" ? "up" : n.sentiment === "negative" ? "down" : ""}>
                  {n.title}
                </b>
                <div className="src">
                  {n.source} · {n.published_at}
                </div>
                <p>{n.summary}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {tab === "舆情" && data.social && (
        <section className="panel">
          <h2>股吧 / 新闻舆情</h2>
          <p className="lead">{data.social.summary}</p>
          <div className="sentiment-score">
            <div className="score-ring">{data.social.mood_score}</div>
            <div>
              <strong>{data.social.mood_label}</strong>
              <div className="meta">
                平台：{(data.social.platforms || []).join("、") || "—"}
                {data.social.hot_rank != null
                  ? ` · 人气榜第 ${data.social.hot_rank}${data.social.market_count ? `/${data.social.market_count}` : ""}`
                  : ""}
                {data.social.heat_score != null
                  ? ` · 热度 ${data.social.heat_score}（${data.social.heat_label || ""}）`
                  : ""}
                {data.social.focus_index != null ? ` · 关注指数 ${data.social.focus_index}` : ""}
              </div>
              <div className="meta">
                标题倾向 {data.social.polarity_score ?? "—"} ·
                利多 {data.social.mood_breakdown?.positive ?? 0} /
                中性 {data.social.mood_breakdown?.neutral ?? 0} /
                利空 {data.social.mood_breakdown?.negative ?? 0}
              </div>
            </div>
          </div>
          {!!data.social.keywords?.length && (
            <div className="tag-row">
              {data.social.keywords.map((k) => (
                <span className="tag" key={k.name}>
                  {k.name} · {k.heat}
                </span>
              ))}
            </div>
          )}
          {!!data.social.related?.length && (
            <>
              <h3>关联热股</h3>
              <ul className="peer-list">
                {data.social.related.map((p) => (
                  <li key={p.code}>
                    <Link to={`/research/${p.code}`}>
                      <b>
                        {p.symbol || p.code}（{p.relation || "关联"}）
                      </b>
                    </Link>
                    <div className={(p.change_pct ?? 0) >= 0 ? "up" : "down"}>
                      {(p.change_pct ?? 0) >= 0 ? "▲" : "▼"} {(p.change_pct ?? 0).toFixed(2)}%
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}
          <h3>帖子 / 资讯</h3>
          <ul className="news-list">
            {(data.social.posts || []).slice(0, 25).map((n) => (
              <li key={n.id}>
                <b className={n.sentiment === "positive" ? "up" : n.sentiment === "negative" ? "down" : ""}>
                  {n.title}
                </b>
                <div className="src">
                  {n.platform_label}
                  {n.author ? ` · ${n.author}` : ""}
                  {n.published_at ? ` · ${n.published_at}` : ""}
                  {n.comment ? ` · 评 ${n.comment}` : ""}
                  {n.click ? ` · 阅 ${n.click}` : ""}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {tab === "情绪" && (
        <section className="panel">
          <h2>市场情绪</h2>
          <div className="sentiment-score">
            <div className="score-ring">{data.sentiment.score}</div>
            <div>
              <strong>{data.sentiment.label}</strong>
              <div className="meta">
                {data.sentiment.hot_rank != null ? `人气榜第 ${data.sentiment.hot_rank}` : ""}
                {data.sentiment.heat_score != null
                  ? `${data.sentiment.hot_rank != null ? " · " : ""}热度 ${data.sentiment.heat_score}`
                  : ""}
              </div>
              <p className="lead">{data.sentiment.summary}</p>
            </div>
          </div>
          <ul className="product-list">
            {data.sentiment.factors.map((f) => (
              <li key={f.name}>
                <b>{f.name}</b>
                <div className={f.impact === "positive" ? "up" : f.impact === "negative" ? "down" : ""}>
                  {f.value} · {f.impact === "positive" ? "利多" : f.impact === "negative" ? "利空" : "中性"}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {tab === "结论" && (
        <section className="panel">
          <h2>操作思路与走势预测</h2>
          <div className="stance-banner">
            <strong>{data.forecast.stance}</strong>
            <span>周期 {data.forecast.horizon}</span>
            <span>置信 {Math.round(data.forecast.confidence * 100)}%</span>
          </div>
          <p className="lead">{data.forecast.summary}</p>
          <h3>执行要点</h3>
          <ul className="action-list">
            {data.forecast.actions.map((a) => (
              <li key={a}>• {a}</li>
            ))}
          </ul>
          <h3>情景</h3>
          <ul className="product-list">
            {data.forecast.scenarios.map((s) => (
              <li key={s.name}>
                <b>
                  {s.name} · 概率 {(s.probability * 100).toFixed(0)}%
                </b>
                <div>{s.desc}</div>
              </li>
            ))}
          </ul>
          <h3>预测路径</h3>
          <div className="levels">
            {data.forecast.path.map((p) => (
              <div key={p.days}>
                <span>{p.days} 日</span>
                <b>
                  {p.expected}（{p.low}-{p.high}）
                </b>
              </div>
            ))}
          </div>
          <p className="disclaimer">{data.forecast.disclaimer}</p>
        </section>
      )}
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
    <div className="progress-panel">
      <h2>正在研究 {decodeURIComponent(code)}</h2>
      <p className="lead">分步拉取实盘数据并生成结论，请稍候…</p>
      <div className="progress-bar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
        <i style={{ width: `${pct}%` }} />
      </div>
      <ol className="step-list">
        {steps.map((s) => (
          <li key={s.id} className={`step ${s.status}`}>
            <span className="step-mark" aria-hidden>
              {s.status === "done" ? "✓" : s.status === "running" ? "●" : s.status === "error" ? "!" : "○"}
            </span>
            <div>
              <b>{s.label}</b>
              {s.preview && <div className="step-preview">{s.preview}</div>}
              {s.error && <div className="step-error">{s.error}</div>}
              {s.status === "running" && <div className="step-preview">进行中…</div>}
              {s.status === "pending" && <div className="step-preview">等待中</div>}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
