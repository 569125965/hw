const API_BASE = import.meta.env.VITE_API_BASE || "";

async function get<T>(path: string, timeoutMs = 60000): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${API_BASE}${path}`, { signal: ctrl.signal });
    if (!res.ok) {
      throw new Error(`请求失败 ${res.status}`);
    }
    return (await res.json()) as T;
  } catch (e) {
    if ((e as Error).name === "AbortError") {
      throw new Error("请求超时，请重试");
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export type StockHit = { code: string; name: string; market: string };

export type Quote = {
  code: string;
  name: string;
  market: string;
  price: number;
  change: number;
  change_pct: number;
  open: number;
  high: number;
  low: number;
  pre_close: number;
  volume: number;
  amount: number;
  turnover_rate: number;
  amplitude: number;
  volume_ratio: number;
  pe_ttm: number;
  pb: number;
  total_mv: number;
  degraded?: boolean;
};

export type KlineItem = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ma5?: number;
  ma10?: number;
  ma20?: number;
  ma60?: number;
  dif?: number;
  dea?: number;
  macd?: number;
  rsi?: number;
};

export type Signal = {
  id: string;
  cycle: "short" | "medium";
  side: "buy" | "sell";
  pair_id: string;
  index: number;
  date: string;
  price: number;
  label: string;
};

export type Research = {
  code: string;
  name: string;
  quote: Quote;
  kline: { items: KlineItem[]; signals?: Signal[]; degraded?: boolean };
  fundamental: {
    industry: string;
    concepts: string[];
    products: { name: string; share: number; desc: string }[];
    business_summary: string;
    peers: { code: string; name: string; change_pct?: number; price?: number }[];
  };
  news: {
    items: {
      id: string;
      title: string;
      source: string;
      published_at: string;
      summary: string;
      sentiment: string;
    }[];
  };
  sentiment: {
    score: number;
    label: string;
    summary: string;
    factors: { name: string; value: number; impact: string }[];
  };
  forecast: {
    stance: string;
    horizon: string;
    summary: string;
    actions: string[];
    levels: Record<string, number>;
    path: { days: number; expected: number; low: number; high: number }[];
    scenarios: { name: string; probability: number; desc: string }[];
    confidence: number;
    disclaimer: string;
  };
  degraded?: boolean;
};

export type ProgressEvent = {
  step: string;
  status: "running" | "done" | "error";
  label: string;
  preview?: string;
  error?: string;
  research?: Research;
};

export const RESEARCH_STEPS: { id: string; label: string }[] = [
  { id: "resolve", label: "识别股票" },
  { id: "quote", label: "拉取盘面报价" },
  { id: "kline", label: "拉取K线并计算买卖点" },
  { id: "fundamental", label: "分析产品与行业" },
  { id: "news", label: "聚合消息面" },
  { id: "sentiment", label: "评估市场情绪" },
  { id: "forecast", label: "生成操作思路与预测" },
  { id: "done", label: "研究完成" },
];

export async function streamResearch(
  code: string,
  onEvent: (ev: ProgressEvent) => void
): Promise<Research> {
  const res = await fetch(`${API_BASE}/api/v1/stocks/${encodeURIComponent(code)}/research/stream`);
  if (!res.ok || !res.body) {
    throw new Error(`研究流请求失败 ${res.status}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let research: Research | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split("\n");
    buf = lines.pop() || "";
    for (const line of lines) {
      const t = line.trim();
      if (!t) continue;
      const ev = JSON.parse(t) as ProgressEvent;
      onEvent(ev);
      if (ev.step === "done" && ev.status === "done" && ev.research) {
        research = ev.research;
      }
      if (ev.step === "done" && ev.status === "error") {
        throw new Error(ev.error || "研究失败");
      }
    }
  }

  if (!research) {
    // fallback: non-stream
    research = await get<Research>(`/api/v1/stocks/${encodeURIComponent(code)}/research`, 90000);
  }
  return research;
}

export const api = {
  search: (q: string) => get<{ items: StockHit[] }>(`/api/v1/stocks/search?q=${encodeURIComponent(q)}`),
  research: (code: string) => get<Research>(`/api/v1/stocks/${encodeURIComponent(code)}/research`, 90000),
  streamResearch,
  health: () => get<{ status: string }>("/api/v1/health"),
};

export function fmtAmount(n: number): string {
  if (n >= 1e8) return `${(n / 1e8).toFixed(2)}亿`;
  if (n >= 1e4) return `${(n / 1e4).toFixed(1)}万`;
  return `${n}`;
}

export function fmtMv(n: number): string {
  if (n >= 1e12) return `${(n / 1e12).toFixed(2)}万亿`;
  if (n >= 1e8) return `${(n / 1e8).toFixed(2)}亿`;
  return `${n}`;
}
