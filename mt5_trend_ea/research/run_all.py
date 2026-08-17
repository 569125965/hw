#!/usr/bin/env python3
"""Compare trend+momentum filters, then walk-forward ATR stop/target."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from continuation import analyze  # noqa: E402
from data import load_h1, load_m5  # noqa: E402
from indicators import adx_di, higher_tf_ema_dir  # noqa: E402
from momentum import attach_trend_and_score  # noqa: E402
from sltp import run_grid, window_stats  # noqa: E402

OUT = ROOT.parent / "results"
OUT.mkdir(parents=True, exist_ok=True)


def _pick_threshold(table: pd.DataFrame) -> float:
    """Lowest score whose bucket still has P(lasts>=10m) above unfiltered mean."""
    if table.empty:
        return 0.0
    baseline = float(table["lasts_30m"].mean())
    scored = table.dropna(subset=["score", "lasts_30m"]).sort_values("score")
    best_t, best_key = 0.0, -1.0
    for q in (0.4, 0.5, 0.6, 0.7):
        t = float(scored["score"].quantile(q))
        sub = scored[scored["score"] >= t]
        if len(sub) < 40:
            continue
        p30 = float(sub["lasts_30m"].mean())
        hit30 = float(sub["hit_30m"].mean())
        key = (p30 - baseline) + 0.5 * (hit30 - 0.5)
        if key > best_key:
            best_key, best_t = key, t
    return best_t


def _signal_index(trend, st, score, adx, h1_dir, atr_v, high, low, close, threshold, min_adx=18.0):
    n = len(trend)
    confirmed = np.zeros(n, dtype=bool)
    confirmed[2:] = (trend[2:] == trend[1:-1]) & (trend[1:-1] == trend[:-2])
    aligned = trend == h1_dir
    pull = np.zeros(n, dtype=bool)
    for i in range(2, n):
        if not np.isfinite(st[i]) or not np.isfinite(atr_v[i]) or atr_v[i] <= 0:
            continue
        if trend[i] > 0:
            pull[i] = (low[i] <= st[i] + 0.5 * atr_v[i]) and (close[i] >= st[i])
        else:
            pull[i] = (high[i] >= st[i] - 0.5 * atr_v[i]) and (close[i] <= st[i])
    warmup = np.arange(n) >= 60
    ok = (
        warmup
        & confirmed
        & aligned
        & pull
        & (score >= threshold)
        & (adx >= min_adx)
        & np.isfinite(score)
        & np.isfinite(adx)
    )
    idx = np.where(ok)[0]
    idx = idx[idx < n - 12]
    kept = []
    last = -999
    for i in idx:
        if i - last >= 6:
            kept.append(int(i))
            last = int(i)
    return np.array(kept, dtype=int)


def run_timeframe(df: pd.DataFrame, name: str, minutes_per_bar: int) -> dict:
    high = df["High"].to_numpy(float)
    low = df["Low"].to_numpy(float)
    close = df["Close"].to_numpy(float)
    trend, st, score, feats = attach_trend_and_score(high, low, close)
    adx, _p, _m = adx_di(high, low, close, 14)
    h1_dir = higher_tf_ema_dir(df.index, close, tf="1h" if minutes_per_bar <= 15 else "4h", period=50)
    cont = analyze(df, trend, score, feats["atr"])
    cont.table.to_csv(OUT / f"{name}_duration_samples.csv", index=False)
    cont.by_bucket.to_csv(OUT / f"{name}_momentum_buckets.csv")
    threshold = _pick_threshold(cont.table)
    sig = _signal_index(
        trend, st, score, adx, h1_dir, feats["atr"], high, low, close, threshold
    )
    n = len(df)
    split = df.index[int(n * 0.67)]
    train_mask = np.array(df.index < split)
    test_mask = np.array(df.index >= split)
    grid, best = run_grid(df, sig, trend, feats["atr"], train_mask, test_mask)
    grid.to_csv(OUT / f"{name}_sltp_grid.csv", index=False)

    last = df.index.max()
    windows = {}
    if minutes_per_bar == 5:
        windows = {
            "1d": (last - pd.Timedelta(days=1), last + pd.Timedelta(seconds=1)),
            "1w": (last - pd.Timedelta(days=7), last + pd.Timedelta(seconds=1)),
            "1m": (last - pd.Timedelta(days=30), last + pd.Timedelta(seconds=1)),
            "all_60d": (df.index.min(), last + pd.Timedelta(seconds=1)),
        }
    else:
        windows = {
            "1m": (last - pd.Timedelta(days=30), last + pd.Timedelta(seconds=1)),
            "1y": (last - pd.Timedelta(days=365), last + pd.Timedelta(seconds=1)),
            "all_2y": (df.index.min(), last + pd.Timedelta(seconds=1)),
        }
    window_out = {}
    for label, (a, b) in windows.items():
        window_out[label] = window_stats(
            df, sig, trend, feats["atr"], float(best["sl_atr"]), float(best["rr"]), a, b
        )
    return {
        "bars": int(len(df)),
        "start": str(df.index.min()),
        "end": str(df.index.max()),
        "flips": int(len(cont.table)),
        "regression": cont.regression,
        "threshold": threshold,
        "signals": int(len(sig)),
        "best_sltp": {k: (None if isinstance(v, float) and not np.isfinite(v) else v) for k, v in best.items() if k != "rank"},
        "windows": window_out,
        "bucket_preview": cont.by_bucket.reset_index().astype(str).to_dict(orient="records"),
    }


def main() -> None:
    m5 = load_m5()
    h1 = load_h1()
    report = {
        "symbol": "GC=F (XAUUSD proxy)",
        "note": (
            "Momentum is a persistence proxy: higher composite score should "
            "raise P(trend lasts >= 10m) and expected duration. Relationship "
            "is monotonic, not a guaranteed linear clock."
        ),
        "m5": run_timeframe(m5, "m5", 5),
        "h1": run_timeframe(h1, "h1", 60),
    }
    (OUT / "report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    _write_markdown(report)
    print((OUT / "summary.md").read_text(encoding="utf-8"))


def _write_markdown(report: dict) -> None:
    m5 = report["m5"]
    h1 = report["h1"]
    reg = m5.get("regression") or {}
    lines = [
        "# 短线趋势 + 动能代理回测摘要",
        "",
        f"- 品种代理: `{report['symbol']}`",
        f"- M5 样本: {m5['start']} → {m5['end']}（{m5['bars']} 根）",
        f"- H1 样本: {h1['start']} → {h1['end']}（{h1['bars']} 根）",
        "",
        "## 动能 vs 剩余时长（M5，趋势已确认 ≥10 分钟后再抽样）",
        "",
        f"- 已确认趋势抽样: {m5['flips']}",
        f"- 线性拟合 remaining_min ≈ {reg.get('intercept')} + {reg.get('slope')} × score",
        f"- r = {reg.get('r')}, r² = {reg.get('r2')}, 平均剩余 {reg.get('mean_duration_min')} 分钟",
        f"- 选用动能门槛: {m5['threshold']:.4f}，过滤后信号 {m5['signals']} 笔",
        "",
        "分位桶见 `m5_momentum_buckets.csv`。r>0 只说明方向对；本样本 r 很小，说明动能是弱代理，不是分钟数标尺。最高动能桶往往略差于中等动能（末端耗尽）。",
        "",
        "## 止盈止损（走步：前 67% 训练，后 33% 验证）",
        "",
        f"- 选中: SL = {m5['best_sltp'].get('sl_atr')} ATR, RR = {m5['best_sltp'].get('rr')}",
        f"- 训练集期望 R: {m5['best_sltp'].get('train_exp')}, 胜率 {m5['best_sltp'].get('train_win')}",
        f"- 验证集期望 R: {m5['best_sltp'].get('test_exp')}, 胜率 {m5['best_sltp'].get('test_win')}",
        "",
        "## 窗口表现（M5 执行）",
        "",
        "| 窗口 | 笔数 | 胜率 | 期望R | 利润因子 |",
        "|---|---:|---:|---:|---:|",
    ]
    for label, s in m5["windows"].items():
        lines.append(
            f"| {label} | {s['n']} | {_pct(s['win_rate'])} | {_num(s['expectancy_r'])} | {_num(s['profit_factor'])} |"
        )
    lines += [
        "",
        "## H1 稳健性（1 年尺度，不是 10 分钟尺度）",
        "",
        "| 窗口 | 笔数 | 胜率 | 期望R | 利润因子 |",
        "|---|---:|---:|---:|---:|",
    ]
    for label, s in h1["windows"].items():
        lines.append(
            f"| {label} | {s['n']} | {_pct(s['win_rate'])} | {_num(s['expectancy_r'])} | {_num(s['profit_factor'])} |"
        )
    lines += [
        "",
        "H1 用来看同一套动能过滤在更长样本上会不会立刻失效，不能代替 M5 的 10–60 分钟结论。",
        "",
    ]
    (OUT / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def _pct(x) -> str:
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "n/a"
    return f"{100 * float(x):.1f}%"


def _num(x) -> str:
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "n/a"
    return f"{float(x):.3f}"


if __name__ == "__main__":
    main()
