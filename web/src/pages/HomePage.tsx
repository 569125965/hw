import { FormEvent, useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, StockHit } from "../api";

export default function HomePage() {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<StockHit[]>([]);
  const [error, setError] = useState("");
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [retrying, setRetrying] = useState(false);

  const refresh = useCallback(async (query: string) => {
    try {
      await api.health();
      setApiOk(true);
      const res = await api.search(query || "6");
      setHits(res.items.slice(0, 8));
      setError("");
    } catch (e) {
      setApiOk(false);
      setHits([]);
      setError((e as Error).message || "无法连接研究服务，请先启动后端");
    }
  }, []);

  useEffect(() => {
    const t = setTimeout(() => {
      void refresh(q);
    }, 220);
    return () => clearTimeout(t);
  }, [q, refresh]);

  async function onRetry() {
    setRetrying(true);
    await refresh(q);
    setRetrying(false);
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (apiOk === false) {
      void onRetry();
      return;
    }
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
          <button type="submit">{apiOk === false ? "重试连接" : "开始研究"}</button>
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
        {apiOk === false ? (
          <div className="backend-help">
            <p className="hint error-text">{error}</p>
            <p className="hint">页面能打开只说明前端在跑；还需要后端 API（127.0.0.1:8000）。</p>
            <pre className="cmd-box">{`cd /Users/rouser/Documents/dev/hw
./scripts/stop.sh
./scripts/start.sh
# 看到 [ok] API / [ok] Web 后再刷新本页
# 自检: curl http://127.0.0.1:8000/api/v1/health`}</pre>
            <button type="button" className="primary-btn" onClick={onRetry} disabled={retrying}>
              {retrying ? "检测中…" : "我已启动，重新检测"}
            </button>
          </div>
        ) : (
          <p className="hint">
            {apiOk === true ? "服务已连接 · " : ""}
            对标东财/同花顺信息密度与 TradingView 图表层级 · 红涨绿跌
          </p>
        )}
      </div>
    </section>
  );
}
