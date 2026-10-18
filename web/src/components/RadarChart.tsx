import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import type { ScoreDimension } from "../api";

type Props = {
  dimensions: ScoreDimension[];
  overall?: number;
};

export default function RadarChart({ dimensions, overall }: Props) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!ref.current || !dimensions.length) return;
    const chart = echarts.init(ref.current, undefined, { renderer: "canvas" });
    chart.setOption({
      backgroundColor: "transparent",
      animation: false,
      title: overall != null
        ? {
            text: `${overall.toFixed(0)}`,
            subtext: "综合",
            left: "center",
            top: "42%",
            textStyle: { color: "#e8f1f4", fontSize: 22, fontWeight: 700 },
            subtextStyle: { color: "#8aa3ad", fontSize: 11 },
          }
        : undefined,
      radar: {
        indicator: dimensions.map((d) => ({ name: d.name, max: 100 })),
        center: ["50%", "55%"],
        radius: "62%",
        axisName: { color: "#8aa3ad", fontSize: 10 },
        splitArea: {
          areaStyle: {
            color: ["rgba(232,241,244,0.02)", "rgba(232,241,244,0.05)"],
          },
        },
        splitLine: { lineStyle: { color: "rgba(232,241,244,0.12)" } },
        axisLine: { lineStyle: { color: "rgba(232,241,244,0.18)" } },
      },
      series: [
        {
          type: "radar",
          data: [
            {
              value: dimensions.map((d) => d.score),
              name: "研判",
              areaStyle: { color: "rgba(232,168,56,0.28)" },
              lineStyle: { color: "#e8a838", width: 2 },
              itemStyle: { color: "#e8a838" },
            },
          ],
        },
      ],
    });
    const onResize = () => chart.resize();
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.dispose();
    };
  }, [dimensions, overall]);

  return <div className="radar-shell" ref={ref} />;
}
