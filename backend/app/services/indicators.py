from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def kline_to_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    close = out["close"]
    for w in (5, 10, 20, 60):
        out[f"ma{w}"] = close.rolling(w).mean()

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    out["dif"] = ema12 - ema26
    out["dea"] = out["dif"].ewm(span=9, adjust=False).mean()
    out["macd"] = (out["dif"] - out["dea"]) * 2

    # RSI
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean().replace(0, np.nan)
    rs = avg_gain / avg_loss
    out["rsi"] = 100 - (100 / (1 + rs))

    # Bollinger
    mid = close.rolling(20).mean()
    std = close.rolling(20).std()
    out["boll_mid"] = mid
    out["boll_up"] = mid + 2 * std
    out["boll_dn"] = mid - 2 * std
    return out


def df_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    records: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        item: dict[str, Any] = {
            "date": row["date"].date().isoformat()
            if hasattr(row["date"], "date")
            else str(row["date"])[:10],
            "open": _num(row["open"]),
            "high": _num(row["high"]),
            "low": _num(row["low"]),
            "close": _num(row["close"]),
            "volume": int(row["volume"]) if not pd.isna(row["volume"]) else 0,
            "amount": _num(row.get("amount", 0)),
        }
        for key in (
            "ma5",
            "ma10",
            "ma20",
            "ma60",
            "dif",
            "dea",
            "macd",
            "rsi",
            "boll_mid",
            "boll_up",
            "boll_dn",
        ):
            if key in row and not pd.isna(row[key]):
                item[key] = _num(row[key])
        records.append(item)
    return records


def _num(v: Any) -> float:
    try:
        return round(float(v), 4)
    except Exception:
        return 0.0
