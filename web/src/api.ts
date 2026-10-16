const API_BASE = import.meta.env.VITE_API_BASE || "";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    throw new Error(`请求失败 ${res.status}`);
  }
  return res.json() as Promise<T>;
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

/** 短/中期买卖点；后端可能暂未返回，前端按可选兼容 */
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

export const api = {
  search: (q: string) => get<{ items: StockHit[] }>(`/api/v1/stocks/search?q=${encodeURIComponent(q)}`),
  research: (code: string) => get<Research>(`/api/v1/stocks/${encodeURIComponent(code)}/research`),
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
