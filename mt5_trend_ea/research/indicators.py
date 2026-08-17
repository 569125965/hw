"""Vector-friendly trend / momentum indicators used by the research pipeline."""

from __future__ import annotations

import numpy as np
import pandas as pd


def rma(values: np.ndarray, period: int) -> np.ndarray:
    out = np.full_like(values, np.nan, dtype=float)
    if len(values) < period:
        return out
    seed = np.nanmean(values[:period])
    out[period - 1] = seed
    alpha = 1.0 / period
    for i in range(period, len(values)):
        prev = out[i - 1]
        x = values[i]
        if np.isnan(x):
            out[i] = prev
        else:
            out[i] = prev + alpha * (x - prev)
    return out


def true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    prev = np.roll(close, 1)
    prev[0] = close[0]
    return np.maximum(high - low, np.maximum(np.abs(high - prev), np.abs(low - prev)))


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    return rma(true_range(high, low, close), period)


def supertrend(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 10,
    multiplier: float = 3.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Pine-style SuperTrend. Returns (direction +1/-1, supertrend line)."""
    n = len(close)
    atr_v = atr(high, low, close, period)
    src = (high + low) / 2.0
    up = src - multiplier * atr_v
    dn = src + multiplier * atr_v
    trend = np.ones(n)
    st = np.full(n, np.nan)
    for i in range(1, n):
        up_prev = up[i - 1] if not np.isnan(up[i - 1]) else up[i]
        dn_prev = dn[i - 1] if not np.isnan(dn[i - 1]) else dn[i]
        if not np.isnan(up[i]) and not np.isnan(up_prev):
            up[i] = max(up[i], up_prev) if close[i - 1] > up_prev else up[i]
        if not np.isnan(dn[i]) and not np.isnan(dn_prev):
            dn[i] = min(dn[i], dn_prev) if close[i - 1] < dn_prev else dn[i]
        prev_trend = trend[i - 1]
        if prev_trend == -1 and not np.isnan(dn_prev) and close[i] > dn_prev:
            trend[i] = 1
        elif prev_trend == 1 and not np.isnan(up_prev) and close[i] < up_prev:
            trend[i] = -1
        else:
            trend[i] = prev_trend
        st[i] = up[i] if trend[i] == 1 else dn[i]
    return trend, st


def adx_di(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    up_move = np.diff(high, prepend=high[0])
    down_move = -np.diff(low, prepend=low[0])
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    atr_v = atr(high, low, close, period)
    plus_di = 100.0 * rma(plus_dm.astype(float), period) / atr_v
    minus_di = 100.0 * rma(minus_dm.astype(float), period) / atr_v
    denom = np.abs(plus_di + minus_di)
    dx = np.where(denom > 0, 100.0 * np.abs(plus_di - minus_di) / denom, np.nan)
    dx = np.nan_to_num(dx, nan=0.0)
    adx = rma(dx, period)
    return adx, plus_di, minus_di


def donchian_dir(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 20) -> np.ndarray:
    h = pd.Series(high).rolling(period).max().to_numpy()
    l = pd.Series(low).rolling(period).min().to_numpy()
    mid = (h + l) / 2.0
    return np.where(close >= mid, 1.0, -1.0)


def ema(values: np.ndarray, period: int) -> np.ndarray:
    return pd.Series(values).ewm(span=period, adjust=False).mean().to_numpy()


def efficiency_ratio(close: np.ndarray, period: int = 10) -> np.ndarray:
    c = pd.Series(close)
    change = (c - c.shift(period)).abs()
    vol = c.diff().abs().rolling(period).sum()
    return (change / vol.replace(0, np.nan)).to_numpy()


def roc(close: np.ndarray, period: int) -> np.ndarray:
    c = pd.Series(close)
    return (c / c.shift(period) - 1.0).to_numpy()


def zscore(arr: np.ndarray, lookback: int = 200) -> np.ndarray:
    s = pd.Series(arr)
    mu = s.rolling(lookback, min_periods=50).mean()
    sd = s.rolling(lookback, min_periods=50).std()
    return ((s - mu) / sd.replace(0, np.nan)).to_numpy()


def higher_tf_ema_dir(index: pd.DatetimeIndex, close: np.ndarray, tf: str = "1h", period: int = 50) -> np.ndarray:
    s = pd.Series(close, index=index)
    ht = s.resample(tf).last().dropna()
    e = ht.ewm(span=period, adjust=False).mean()
    direction = np.where(ht.to_numpy() >= e.to_numpy(), 1.0, -1.0)
    dir_s = pd.Series(direction, index=ht.index)
    aligned = dir_s.reindex(index, method="ffill")
    return aligned.to_numpy()
