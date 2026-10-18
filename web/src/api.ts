const API_BASE = (import.meta.env.VITE_API_BASE || "").replace(/\/$/, "");

/** 相对路径走 Vite 代理；失败再直连本机后端 */
const API_FALLBACKS = [API_BASE, "http://127.0.0.1:8000"];

async function get<T>(path: string, timeoutMs = 60000): Promise<T> {
  const errors: string[] = [];
  for (const base of API_FALLBACKS) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    const url = `${base}${path}`;
    try {
      const res = await fetch(url, { signal: ctrl.signal });
      if (!res.ok) {
        errors.push(`${url} -> HTTP ${res.status}`);
        continue;
      }
      return (await res.json()) as T;
    } catch (e) {
      const msg = (e as Error).name === "AbortError" ? "超时" : (e as Error).message || "网络错误";
      errors.push(`${url} -> ${msg}`);
    } finally {
      clearTimeout(timer);
    }
  }
  throw new Error(
    `无法连接研究服务（后端 :8000）。请在项目根目录执行 ./scripts/start.sh。详情: ${errors.join(" | ")}`
  );
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

export type SocialPost = {
  id: string;
  platform: string;
  platform_label: string;
  title: string;
  summary: string;
  author?: string;
  published_at?: string;
  click?: number;
  comment?: number;
  sentiment: string;
  url?: string;
};

export type Advice = {
  action: string;
  action_code: string;
  urgency: string;
  color: string;
  combo_score: number;
  tech_score: number;
  social_score: number;
  price: number;
  buy_zone: number[];
  sell_zone: number[];
  stop_loss: number;
  take_profit: number;
  horizon: string;
  reasons: string[];
  checklist: string[];
  capital_label?: string;
  disclaimer: string;
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
    peers: { code: string; name: string; change_pct?: number; price?: number; relation?: string }[];
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
  social?: {
    mood_score: number;
    mood_label: string;
    polarity_score?: number;
    heat_score?: number;
    heat_label?: string;
    mood_breakdown?: { positive: number; negative: number; neutral: number };
    summary: string;
    platforms?: string[];
    posts?: SocialPost[];
    guba_count?: number;
    news_count?: number;
    hot_rank?: number | null;
    rank_change?: number | null;
    market_count?: number | null;
    focus_index?: number | null;
    community_score?: number | null;
    related?: { code: string; symbol?: string; change_pct?: number; relation?: string }[];
    keywords?: { name: string; heat: number }[];
  };
  sentiment: {
    score: number;
    label: string;
    summary: string;
    heat_score?: number | null;
    hot_rank?: number | null;
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
  capital?: {
    summary: string;
    chips?: {
      pit_low?: number | null;
      cost_zone?: { low: number; mid: number; high: number } | null;
      profit_ratio_vs_cost?: number | null;
      note?: string;
      placement_hint?: { note: string; ref_high?: number } | null;
    };
    volume_phase?: { label: string; up_volume_days?: number; vol_ratio_5_20?: number };
    money_flow?: { note?: string; available?: boolean; main_net_5d?: number };
    events?: Array<{
      type: string;
      label: string;
      title: string;
      published_at?: string;
      source?: string;
      bearish?: boolean;
    }>;
    thesis?: {
      code: string;
      label: string;
      direction: string;
      confidence: number;
      exit_score: number;
      rally_score: number;
      signals: string[];
      scenarios: Array<{ name: string; probability: number; desc: string }>;
      summary: string;
    };
  };
  macro?: {
    risk_score: number;
    regime: string;
    summary: string;
    bucket_counts?: Record<string, number>;
    items?: Array<{
      id: string;
      title: string;
      source: string;
      published_at?: string;
      buckets?: string[];
    }>;
  };
  llm?: {
    enabled: boolean;
    configured?: boolean;
    model?: string | null;
    provider?: string;
    hint?: string;
    summary?: string;
    degraded?: boolean;
    capital_view?: Record<string, unknown> | null;
  };
  llm_status?: { configured: boolean; hint?: string; model?: string | null };
  advice?: Advice;
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
  { id: "news", label: "聚合官方消息" },
  { id: "social", label: "抓取股吧/新闻舆情与关联" },
  { id: "macro", label: "采集美联储/地缘等宏观驱动" },
  { id: "capital", label: "估算筹码与资金行为" },
  { id: "sentiment", label: "评估市场情绪" },
  { id: "forecast", label: "生成走势研判" },
  { id: "llm", label: "AI深度研判（可选）" },
  { id: "advice", label: "给出买卖操作建议" },
  { id: "done", label: "研究完成" },
];

async function openStream(path: string): Promise<Response> {
  const errors: string[] = [];
  for (const base of API_FALLBACKS) {
    try {
      const res = await fetch(`${base}${path}`);
      if (res.ok && res.body) return res;
      errors.push(`${base}${path} -> HTTP ${res.status}`);
    } catch (e) {
      errors.push(`${base}${path} -> ${(e as Error).message}`);
    }
  }
  throw new Error(`无法连接研究服务。请先 ./scripts/start.sh。${errors.join(" | ")}`);
}

export async function streamResearch(
  code: string,
  onEvent: (ev: ProgressEvent) => void
): Promise<Research> {
  const res = await openStream(`/api/v1/stocks/${encodeURIComponent(code)}/research/stream`);
  const reader = res.body!.getReader();
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
    research = await get<Research>(`/api/v1/stocks/${encodeURIComponent(code)}/research`, 90000);
  }
  return research;
}

export const api = {
  search: (q: string) => get<{ items: StockHit[] }>(`/api/v1/stocks/search?q=${encodeURIComponent(q)}`),
  research: (code: string) => get<Research>(`/api/v1/stocks/${encodeURIComponent(code)}/research`, 90000),
  streamResearch,
  health: () => get<{ status: string }>("/api/v1/health", 8000),
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
