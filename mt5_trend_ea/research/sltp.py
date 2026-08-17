"""ATR stop/target grid with walk-forward. Optimize expectancy, not win rate."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

SL_MULTS = (1.0, 1.5, 2.0, 2.5, 3.0)
RR_MULTS = (1.0, 1.5, 2.0, 2.5, 3.0)
SPREAD = 0.30  # USD, conservative XAUUSD/GC proxy
MAX_BARS = 24  # 2 hours on M5; short-trend time stop


@dataclass
class Trade:
    entry_time: pd.Timestamp
    direction: int
    pnl_r: float
    win: bool
    bars: int


def simulate_trade(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    i: int,
    direction: int,
    sl_atr: float,
    rr: float,
    atr_i: float,
) -> tuple[float, int]:
    if not np.isfinite(atr_i) or atr_i <= 0:
        return 0.0, 0
    entry = close[i] + direction * (SPREAD / 2.0)
    sl_dist = sl_atr * atr_i
    sl = entry - direction * sl_dist
    tp = entry + direction * sl_dist * rr
    n = len(close)
    end = min(n, i + 1 + MAX_BARS)
    for j in range(i + 1, end):
        if direction > 0:
            if low[j] <= sl:
                return -1.0, j - i
            if high[j] >= tp:
                return rr, j - i
        else:
            if high[j] >= sl:
                return -1.0, j - i
            if low[j] <= tp:
                return rr, j - i
    # time stop at last close
    last = close[end - 1]
    pnl = (last - entry) * direction / sl_dist
    return float(np.clip(pnl, -1.0, rr)), end - 1 - i


def run_grid(
    df: pd.DataFrame,
    signal_idx: np.ndarray,
    direction: np.ndarray,
    atr_v: np.ndarray,
    train_mask: np.ndarray,
    test_mask: np.ndarray,
) -> tuple[pd.DataFrame, dict]:
    high = df["High"].to_numpy(float)
    low = df["Low"].to_numpy(float)
    close = df["Close"].to_numpy(float)
    rows = []
    for sl in SL_MULTS:
        for rr in RR_MULTS:
            pnls_tr = []
            pnls_te = []
            for i in signal_idx:
                pnl, _bars = simulate_trade(high, low, close, int(i), int(direction[i]), sl, rr, atr_v[i])
                if train_mask[i]:
                    pnls_tr.append(pnl)
                elif test_mask[i]:
                    pnls_te.append(pnl)
            tr = np.array(pnls_tr, dtype=float)
            te = np.array(pnls_te, dtype=float)
            rows.append(
                {
                    "sl_atr": sl,
                    "rr": rr,
                    "train_n": len(tr),
                    "train_win": float(np.mean(tr > 0)) if len(tr) else np.nan,
                    "train_exp": float(np.mean(tr)) if len(tr) else np.nan,
                    "train_pf": _profit_factor(tr),
                    "test_n": len(te),
                    "test_win": float(np.mean(te > 0)) if len(te) else np.nan,
                    "test_exp": float(np.mean(te)) if len(te) else np.nan,
                    "test_pf": _profit_factor(te),
                }
            )
    grid = pd.DataFrame(rows)
    # Robust pick: best train expectancy among cells with train_n>=30 and test not collapsing.
    usable = grid[grid["train_n"] >= 20].copy()
    if usable.empty:
        usable = grid.copy()
    usable["rank"] = usable["train_exp"].fillna(-999)
    best = usable.sort_values("rank", ascending=False).iloc[0].to_dict()
    return grid, best


def _profit_factor(pnls: np.ndarray) -> float:
    if len(pnls) == 0:
        return np.nan
    gains = pnls[pnls > 0].sum()
    losses = -pnls[pnls < 0].sum()
    if losses <= 0:
        return np.inf if gains > 0 else np.nan
    return float(gains / losses)


def window_stats(
    df: pd.DataFrame,
    signal_idx: np.ndarray,
    direction: np.ndarray,
    atr_v: np.ndarray,
    sl: float,
    rr: float,
    start,
    end,
) -> dict:
    high = df["High"].to_numpy(float)
    low = df["Low"].to_numpy(float)
    close = df["Close"].to_numpy(float)
    pnls = []
    for i in signal_idx:
        ts = df.index[int(i)]
        if ts < start or ts >= end:
            continue
        pnl, _ = simulate_trade(high, low, close, int(i), int(direction[i]), sl, rr, atr_v[i])
        pnls.append(pnl)
    a = np.array(pnls, dtype=float)
    return {
        "n": int(len(a)),
        "win_rate": float(np.mean(a > 0)) if len(a) else np.nan,
        "expectancy_r": float(np.mean(a)) if len(a) else np.nan,
        "profit_factor": _profit_factor(a),
        "sum_r": float(np.sum(a)) if len(a) else np.nan,
    }
