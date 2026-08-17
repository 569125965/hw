"""Measure realized trend duration vs momentum, and 10–60 minute continuation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


HORIZONS_BARS = (2, 4, 6, 12)  # 10 / 20 / 30 / 60 minutes on M5
MINUTES_PER_BAR = 5


@dataclass
class ContinuationResult:
    table: pd.DataFrame
    regression: dict
    by_bucket: pd.DataFrame


def _linreg(x: np.ndarray, y: np.ndarray) -> dict:
    mask = np.isfinite(x) & np.isfinite(y)
    x = x[mask]
    y = y[mask]
    if len(x) < 30:
        return {"n": int(len(x)), "slope": np.nan, "intercept": np.nan, "r": np.nan}
    xm = x.mean()
    ym = y.mean()
    var = np.sum((x - xm) ** 2)
    if var <= 0:
        return {"n": int(len(x)), "slope": np.nan, "intercept": np.nan, "r": np.nan}
    slope = float(np.sum((x - xm) * (y - ym)) / var)
    intercept = float(ym - slope * xm)
    yhat = intercept + slope * x
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - ym) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan
    r = float(np.sqrt(max(r2, 0.0)) * np.sign(slope)) if np.isfinite(r2) else np.nan
    return {
        "n": int(len(x)),
        "slope": slope,
        "intercept": intercept,
        "r": r,
        "r2": float(r2) if np.isfinite(r2) else np.nan,
        "mean_duration_min": float(ym),
    }


def realized_duration_bars(
    close: np.ndarray,
    trend: np.ndarray,
    atr_v: np.ndarray,
    max_bars: int = 36,
) -> np.ndarray:
    """Bars until SuperTrend flips or close moves 1 ATR against entry."""
    n = len(close)
    out = np.full(n, np.nan)
    for i in range(n - 1):
        d = trend[i]
        if d == 0 or not np.isfinite(d) or not np.isfinite(atr_v[i]):
            continue
        stop_adverse = close[i] - d * atr_v[i]
        end = min(n, i + 1 + max_bars)
        dur = max_bars
        for j in range(i + 1, end):
            if trend[j] != d:
                dur = j - i
                break
            if d > 0 and close[j] <= stop_adverse:
                dur = j - i
                break
            if d < 0 and close[j] >= stop_adverse:
                dur = j - i
                break
        else:
            if end - i - 1 > 0:
                dur = end - i - 1
        out[i] = dur
    return out


def continuation_hit(
    close: np.ndarray, trend: np.ndarray, bars: int
) -> np.ndarray:
    future = np.roll(close, -bars)
    future[-bars:] = np.nan
    move = (future - close) * trend
    return np.where(np.isfinite(move), (move > 0).astype(float), np.nan)


def analyze(df: pd.DataFrame, trend: np.ndarray, score: np.ndarray, atr_v: np.ndarray) -> ContinuationResult:
    close = df["Close"].to_numpy(dtype=float)
    n = len(close)
    # Score INSIDE an already-confirmed trend (past 10 minutes same direction).
    # Flip bars are the worst place to read momentum: the lookback still belongs
    # to the previous move, so duration ~ score looks flat/negative.
    confirmed = np.zeros(n, dtype=bool)
    confirmed[2:] = (trend[2:] == trend[1:-1]) & (trend[1:-1] == trend[:-2])
    warmup = np.arange(n) >= 60
    valid = warmup & confirmed & np.isfinite(score) & np.isfinite(atr_v) & np.isfinite(close)
    idx = np.where(valid)[0]
    idx = idx[idx < n - 12][::3]

    duration = realized_duration_bars(close, trend, atr_v, max_bars=24)
    rows = []
    for i in idx:
        row = {
            "time": df.index[i],
            "dir": int(trend[i]),
            "score": float(score[i]),
            "duration_min": float(duration[i] * MINUTES_PER_BAR) if np.isfinite(duration[i]) else np.nan,
            "lasts_10m": float(duration[i] >= 2) if np.isfinite(duration[i]) else np.nan,
            "lasts_30m": float(duration[i] >= 6) if np.isfinite(duration[i]) else np.nan,
            "lasts_60m": float(duration[i] >= 12) if np.isfinite(duration[i]) else np.nan,
        }
        for bars in HORIZONS_BARS:
            hits = continuation_hit(close, trend, bars)
            row[f"hit_{bars * MINUTES_PER_BAR}m"] = float(hits[i]) if np.isfinite(hits[i]) else np.nan
        rows.append(row)
    table = pd.DataFrame(rows)
    if table.empty:
        return ContinuationResult(table, {}, pd.DataFrame())

    reg = _linreg(table["score"].to_numpy(), table["duration_min"].to_numpy())
    table["bucket"] = pd.qcut(table["score"], 5, duplicates="drop")
    by_bucket = table.groupby("bucket", observed=True).agg(
        n=("score", "size"),
        mean_score=("score", "mean"),
        mean_duration_min=("duration_min", "mean"),
        p_lasts_10m=("lasts_10m", "mean"),
        p_lasts_30m=("lasts_30m", "mean"),
        p_lasts_60m=("lasts_60m", "mean"),
        hit_10m=("hit_10m", "mean"),
        hit_30m=("hit_30m", "mean"),
        hit_60m=("hit_60m", "mean"),
    )
    return ContinuationResult(table, reg, by_bucket)
