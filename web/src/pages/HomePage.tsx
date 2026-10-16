import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, StockHit } from "../api";

export default function HomePage() {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<StockHit[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    const t = setTimeout(async () => {
      try {
        const res = await api.search(q || "6");
        setHits(res.items.slice(0, 8));
        setError("");
      } catch {
        setError("无法连接研究服务，请先启动后端");
      }
    }, 220);
    return () => clearTimeout(t);
  }, [q]);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const code = q.trim() || hits[0]?.code;
    if (code) nav(`/research/${encodeURIComponent(code)}`);
  }

  return (
    <section className="hero">
      <div className="hero-visual" aria-hidden />
      <div className="hero-inner">
        <h1 className="brand">
          研盘 <span>AShare Lab</span>
        </h1>
        <p className="tagline">
          输入一只 A 股，聚合盘面、产品、行业、消息与情绪，给出后续操作思路与走势研判。
        </p>
        <form className="search-row" onSubmit={onSubmit}>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="股票代码 / 名称，如 600519 或 贵州茅台"
            autoFocus
          />
          <button type="submit">开始研究</button>
        </form>
        {hits.length > 0 && (
          <div className="suggest">
            {hits.map((h) => (
              <button key={h.code} type="button" onClick={() => nav(`/research/${h.code}`)}>
                <span>{h.name}</span>
                <span>
                  {h.market}.{h.code}
                </span>
              </button>
            ))}
          </div>
        )}
        <p className="hint">{error || "对标东财/同花顺信息密度与 TradingView 图表层级 · 红涨绿跌"}</p>
      </div>
    </section>
  );
}
