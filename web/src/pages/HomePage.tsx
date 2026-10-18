import { FormEvent, useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, BatchItem, StockHit } from "../api";
import WatchlistPanel from "../components/WatchlistPanel";

export default function HomePage() {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<StockHit[]>([]);
  const [error, setError] = useState("");
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [batchRows, setBatchRows] = useState<BatchItem[] | null>(null);
  const [batchLoading, setBatchLoading] = useState(false);

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

  async function runBatch(codes: string[]) {
    setBatchLoading(true);
    try {
      const res = await api.batchResearch(codes);
      setBatchRows(res.items);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBatchLoading(false);
    }
  }

  return (
    <div className="workspace home-workspace">
      <WatchlistPanel onSelect={(c) => nav(`/research/${c}`)} onBatch={(c) => void runBatch(c)} />
      <section className="hero hero-compact">
        <div className="hero-visual" aria-hidden />
        <div className="hero-inner">
          <h1 className="brand">
            研盘 <span>AShare Lab</span>
          </h1>
          <p className="tagline">自选分组 · 批量研判 · 筹码标注 · 蛛网评分</p>
          <form className="search-row" onSubmit={onSubmit}>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="代码 / 名称，如 600418 江淮汽车"
              autoFocus
            />
            <button type="submit">{apiOk === false ? "重试连接" : "研究"}</button>
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
              <pre className="cmd-box">{`./scripts/stop.sh && ./scripts/start.sh`}</pre>
              <button type="button" className="primary-btn" onClick={onRetry} disabled={retrying}>
                {retrying ? "检测中…" : "重新检测"}
              </button>
            </div>
          ) : (
            <p className="hint">{apiOk === true ? "服务已连接 · 左侧管理自选，可多选批量分析" : ""}</p>
          )}

          {(batchLoading || batchRows) && (
            <div className="batch-home panel compact">
              <div className="row-between">
                <h2>批量结果</h2>
                <button type="button" className="text-btn" onClick={() => setBatchRows(null)}>
                  关闭
                </button>
              </div>
              {batchLoading && <p className="lead">分析中…</p>}
              {batchRows && (
                <table className="batch-table">
                  <thead>
                    <tr>
                      <th>信号</th>
                      <th>股票</th>
                      <th>得分</th>
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
                          <div className="meta">{r.code}</div>
                        </td>
                        <td>
                          <b>{r.overall}</b>
                        </td>
                        <td className="sum">{r.summary}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
