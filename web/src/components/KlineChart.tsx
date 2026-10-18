import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import type { ChartOverlay, KlineItem, Signal } from "../api";

type Props = {
  items: KlineItem[];
  signals?: Signal[];
  overlays?: ChartOverlay[];
  compact?: boolean;
};

const SHORT_COLOR = "#E8A838";
const MEDIUM_COLOR = "#26A69A";

type SignalPoint = {
  value: [string, number];
  symbol: string;
  symbolRotate: number;
  symbolSize: number;
  itemStyle: {
    color: string;
    borderColor: string;
    borderWidth?: number;
  };
  signal: Signal;
};

function toPoints(items: KlineItem[], signals: Signal[], cycle: "short" | "medium"): SignalPoint[] {
  return signals
    .filter((s) => s.cycle === cycle)
    .map((s) => {
      const date = items[s.index]?.date ?? s.date;
      if (cycle === "short") {
        return {
          value: [date, s.price] as [string, number],
          symbol: "triangle",
          symbolRotate: s.side === "sell" ? 180 : 0,
          symbolSize: 12,
          itemStyle: { color: SHORT_COLOR, borderColor: SHORT_COLOR },
          signal: s,
        };
      }
      if (s.side === "buy") {
        return {
          value: [date, s.price] as [string, number],
          symbol: "emptyCircle",
          symbolRotate: 0,
          symbolSize: 13,
          itemStyle: { color: "transparent", borderColor: MEDIUM_COLOR, borderWidth: 2 },
          signal: s,
        };
      }
      return {
        value: [date, s.price] as [string, number],
        symbol: "rect",
        symbolRotate: 0,
        symbolSize: 10,
        itemStyle: { color: "transparent", borderColor: MEDIUM_COLOR, borderWidth: 2 },
        signal: s,
      };
    });
}

function formatTooltip(params: unknown): string {
  const list = Array.isArray(params) ? params : [params];
  if (!list.length) return "";
  const axis =
    (list[0] as { axisValueLabel?: string; axisValue?: string }).axisValueLabel ??
    (list[0] as { axisValue?: string }).axisValue ??
    "";
  const lines: string[] = [String(axis)];
  for (const raw of list) {
    const p = raw as {
      seriesName?: string;
      marker?: string;
      data?: SignalPoint | number | number[] | null;
      value?: unknown;
    };
    const name = p.seriesName ?? "";
    if (name === "短期" || name === "中期") {
      const sig = (p.data as SignalPoint | undefined)?.signal;
      if (sig) lines.push(`${p.marker ?? ""}${sig.label}　${sig.price.toFixed(2)}`);
      continue;
    }
    if (name === "K线") {
      const rawD = Array.isArray(p.data) ? (p.data as number[]) : [];
      const ohlc = rawD.length >= 5 ? rawD.slice(1, 5) : rawD.length >= 4 ? rawD.slice(0, 4) : [];
      if (ohlc.length >= 4) {
        const fmt = (n: number) => (typeof n === "number" ? n.toFixed(2) : String(n));
        lines.push(`${p.marker ?? ""}开 ${fmt(ohlc[0])}　收 ${fmt(ohlc[1])}　低 ${fmt(ohlc[2])}　高 ${fmt(ohlc[3])}`);
      }
      continue;
    }
    if (p.value == null || (Array.isArray(p.value) && p.value[1] == null)) continue;
    const v = Array.isArray(p.value) ? p.value[1] : p.value;
    const num = typeof v === "number" ? v : Number(v);
    lines.push(`${p.marker ?? ""}${name}　${Number.isFinite(num) ? num.toFixed(2) : String(v)}`);
  }
  return lines.join("<br/>");
}

function buildMarkArea(overlays: ChartOverlay[]) {
  const bands = overlays.filter((o) => o.type === "band");
  if (!bands.length) return undefined;
  return {
    silent: true,
    data: bands.map((b) => [
      {
        yAxis: b.y0,
        itemStyle: { color: b.color || "rgba(232,168,56,0.16)" },
        label: {
          show: true,
          position: "insideTopLeft",
          formatter: b.label,
          color: b.border || "#e8a838",
          fontSize: 10,
        },
      },
      { yAxis: b.y1 },
    ]),
  };
}

function buildMarkLine(overlays: ChartOverlay[]) {
  const lines = overlays.filter((o) => o.type === "line");
  if (!lines.length) return undefined;
  return {
    symbol: "none",
    silent: true,
    data: lines.map((l) => ({
      yAxis: l.y,
      lineStyle: {
        color: l.color || "#e8a838",
        type: l.style === "dashed" ? "dashed" : l.style === "dotted" ? "dotted" : "solid",
        width: 1.2,
      },
      label: {
        formatter: `${l.label} ${Number(l.y).toFixed(2)}`,
        position: "insideEndTop",
        color: l.color || "#e8a838",
        fontSize: 10,
      },
    })),
  };
}

export default function KlineChart({ items, signals = [], overlays = [], compact = false }: Props) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!ref.current || !items.length) return;
    const chart = echarts.init(ref.current, undefined, { renderer: "canvas" });
    const dates = items.map((i) => i.date);
    const ohlc = items.map((i) => [i.open, i.close, i.low, i.high]);
    const volumes = items.map((i) => i.volume);
    const ma5 = items.map((i) => i.ma5 ?? null);
    const ma20 = items.map((i) => i.ma20 ?? null);
    const macd = items.map((i) => i.macd ?? null);
    const shortPoints = toPoints(items, signals, "short");
    const mediumPoints = toPoints(items, signals, "medium");
    const markArea = buildMarkArea(overlays);
    const markLine = buildMarkLine(overlays);

    chart.setOption({
      backgroundColor: "transparent",
      animation: false,
      legend: {
        data: ["K线", "MA5", "MA20", "短期", "中期"],
        textStyle: { color: "#8aa3ad", fontSize: 11 },
        top: 0,
        itemWidth: 12,
        itemHeight: 8,
      },
      tooltip: { trigger: "axis", axisPointer: { type: "cross" }, formatter: formatTooltip },
      axisPointer: { link: [{ xAxisIndex: "all" }] },
      grid: compact
        ? [
            { left: 44, right: 16, top: 28, height: "58%" },
            { left: 44, right: 16, top: "72%", height: "10%" },
            { left: 44, right: 16, top: "86%", height: "8%" },
          ]
        : [
            { left: 48, right: 24, top: 36, height: "52%" },
            { left: 48, right: 24, top: "68%", height: "12%" },
            { left: 48, right: 24, top: "84%", height: "10%" },
          ],
      xAxis: [
        {
          type: "category",
          data: dates,
          boundaryGap: true,
          axisLine: { lineStyle: { color: "#8aa3ad" } },
          axisLabel: { show: false },
        },
        {
          type: "category",
          gridIndex: 1,
          data: dates,
          axisLabel: { show: false },
          axisLine: { lineStyle: { color: "#8aa3ad" } },
        },
        {
          type: "category",
          gridIndex: 2,
          data: dates,
          axisLabel: { color: "#8aa3ad", fontSize: 10 },
          axisLine: { lineStyle: { color: "#8aa3ad" } },
        },
      ],
      yAxis: [
        {
          scale: true,
          splitLine: { lineStyle: { color: "rgba(232,241,244,0.08)" } },
          axisLabel: { color: "#8aa3ad", fontSize: 10 },
        },
        {
          scale: true,
          gridIndex: 1,
          splitNumber: 2,
          axisLabel: { show: false },
          splitLine: { show: false },
        },
        {
          scale: true,
          gridIndex: 2,
          splitNumber: 2,
          axisLabel: { color: "#8aa3ad", fontSize: 10 },
          splitLine: { show: false },
        },
      ],
      dataZoom: [{ type: "inside", xAxisIndex: [0, 1, 2], start: 50, end: 100 }],
      series: [
        {
          name: "K线",
          type: "candlestick",
          data: ohlc,
          itemStyle: {
            color: "#e53935",
            color0: "#26a69a",
            borderColor: "#e53935",
            borderColor0: "#26a69a",
          },
          markArea,
          markLine,
        },
        {
          name: "MA5",
          type: "line",
          data: ma5,
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 1.1, color: "#e8a838" },
        },
        {
          name: "MA20",
          type: "line",
          data: ma20,
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 1.1, color: "#7ec8e3" },
        },
        {
          name: "短期",
          type: "scatter",
          data: shortPoints,
          z: 12,
          itemStyle: { color: SHORT_COLOR },
        },
        {
          name: "中期",
          type: "scatter",
          data: mediumPoints,
          z: 12,
          itemStyle: { color: MEDIUM_COLOR, borderColor: MEDIUM_COLOR, borderWidth: 2 },
        },
        {
          name: "成交量",
          type: "bar",
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: volumes.map((v, idx) => ({
            value: v,
            itemStyle: { color: items[idx].close >= items[idx].open ? "#e53935" : "#26a69a" },
          })),
        },
        {
          name: "MACD",
          type: "bar",
          xAxisIndex: 2,
          yAxisIndex: 2,
          data: macd.map((v) => ({
            value: v,
            itemStyle: { color: (v ?? 0) >= 0 ? "#e53935" : "#26a69a" },
          })),
        },
      ],
    });

    const onResize = () => chart.resize();
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.dispose();
    };
  }, [items, signals, overlays, compact]);

  return <div className={compact ? "chart-shell chart-shell-compact" : "chart-shell"} ref={ref} />;
}
