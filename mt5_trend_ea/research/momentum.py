"""Momentum as a proxy for remaining trend duration.

Industry momentum measures (ROC, ADX slope, Kaufman ER) do not output
"minutes remaining", but they are monotonically related to the probability
that price is still in the same direction after T minutes. This module
builds a composite score and later we regress realized duration on it.
"""

from __future__ import annotations

import numpy as np

from indicators import adx_di, atr, efficiency_ratio, roc, supertrend, zscore


def signed_momentum_features(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    trend_dir: np.ndarray,
) -> dict[str, np.ndarray]:
    adx, plus_di, minus_di = adx_di(high, low, close, 14)
    atr_v = atr(high, low, close, 14)
    roc6 = roc(close, 6)  # 30 minutes on M5
    roc12 = roc(close, 12)  # 60 minutes on M5
    er = efficiency_ratio(close, 10)
    adx_slope = adx - np.roll(adx, 6)
    adx_slope[:6] = np.nan

    signed_roc6 = roc6 * trend_dir
    signed_roc12 = roc12 * trend_dir
    di_align = np.where(trend_dir > 0, plus_di - minus_di, minus_di - plus_di)

    # Extension: distance from close to opposite extreme in ATR units.
    # Moderate extension is healthy; extreme extension is exhaustion.
    rng = np.maximum(atr_v, 1e-9)
    ext = np.where(trend_dir > 0, (close - low) / rng, (high - close) / rng)
    ext_penalty = -np.clip(ext - 1.8, 0, None)

    return {
        "adx": adx,
        "adx_slope": adx_slope,
        "er": er,
        "signed_roc6": signed_roc6,
        "signed_roc12": signed_roc12,
        "di_align": di_align,
        "ext_penalty": ext_penalty,
        "atr": atr_v,
    }


def composite_score(features: dict[str, np.ndarray]) -> np.ndarray:
    parts = [
        zscore(features["signed_roc6"]),
        zscore(features["signed_roc12"]),
        zscore(features["er"]),
        zscore(features["adx_slope"]),
        zscore(features["di_align"]),
        zscore(features["ext_penalty"]),
    ]
    stacked = np.vstack(parts)
    with np.errstate(all="ignore"):
        return np.nanmean(stacked, axis=0)


def attach_trend_and_score(high, low, close) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, np.ndarray]]:
    trend, st = supertrend(high, low, close, period=10, multiplier=3.0)
    feats = signed_momentum_features(high, low, close, trend)
    score = composite_score(feats)
    return trend, st, score, feats
