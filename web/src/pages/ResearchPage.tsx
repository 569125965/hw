import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, fmtAmount, fmtMv, Research } from "../api";
import KlineChart from "../components/KlineChart";

const TABS = ["盘面", "基本面", "行业", "消息", "情绪", "结论"] as const;

export default function ResearchPage() {
  const { code = "" } = useParams();
  const [data, setData] = useState<Research | null>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<(typeof TABS)[number]>("盘面");

  useEffect(() => {
    let alive = true;
    setData(null);
    setError("");
    api
      .research(code)
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

  if (error) {
    return (
      <div className="error">
        <div>
          <p>{error}</p>
          <Link to="/">返回搜索</Link>
        </div>
      </div>
    );
  }

  if (!data) {
    return <div className="loading">正在聚合盘面 / 基本面 / 消息 / 情绪…</div>;
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
            {data.degraded && <span className="badge">演示/降级数据</span>}
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

      <nav className="tabs">
        {TABS.map((t) => (
          <button key={t} className={tab === t ? "active" : ""} onClick={() => setTab(t)} type="button">
            {t}
          </button>
        ))}
      </nav>

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

      {tab === "情绪" && (
        <section className="panel">
          <h2>市场情绪</h2>
          <div className="sentiment-score">
            <div className="score-ring">{data.sentiment.score}</div>
            <div>
              <strong>{data.sentiment.label}</strong>
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
