from __future__ import annotations

from typing import Any, Literal

import pandas as pd

from app.services.indicators import add_indicators, kline_to_df

Cycle = Literal["short", "medium"]
Side = Literal["buy", "sell"]


def detect_signals(kline_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect paired buy/sell signals for short and medium cycles independently."""
    df = add_indicators(kline_to_df(kline_items))
    if df.empty or len(df) < 30:
        return []

    short = _pair_cycle(df, cycle="short")
    medium = _pair_cycle(df, cycle="medium")
    merged = short + medium
    merged.sort(key=lambda s: (s["index"], 0 if s["side"] == "buy" else 1, s["cycle"]))
    return merged


def _pair_cycle(df: pd.DataFrame, cycle: Cycle) -> list[dict[str, Any]]:
    buys = _buy_indices(df, cycle)
    signals: list[dict[str, Any]] = []
    prefix = "S" if cycle == "short" else "M"
    label_buy = "短买" if cycle == "short" else "中买"
    label_sell = "短卖" if cycle == "short" else "中卖"

    open_buy: int | None = None
    pair_no = 0
    peak = 0.0
    buy_ptr = 0
    i = 0
    n = len(df)

    while i < n:
        # open new buy only when flat
        if open_buy is None:
            while buy_ptr < len(buys) and buys[buy_ptr] < i:
                buy_ptr += 1
            if buy_ptr < len(buys) and buys[buy_ptr] == i:
                pair_no += 1
                open_buy = i
                peak = float(df.iloc[i]["close"])
                signals.append(
                    _mk(df, i, cycle, "buy", f"{prefix}-{pair_no}", label_buy, False)
                )
                buy_ptr += 1
            i += 1
            continue

        close = float(df.iloc[i]["close"])
        peak = max(peak, close)
        if _sell_trigger(df, i, cycle, open_buy, peak):
            signals.append(
                _mk(df, i, cycle, "sell", f"{prefix}-{pair_no}", label_sell, False)
            )
            open_buy = None
        i += 1

    if open_buy is not None:
        last = n - 1
        signals.append(
            _mk(df, last, cycle, "sell", f"{prefix}-{pair_no}", label_sell, True)
        )

    return _ensure_pairs(signals)


def _buy_indices(df: pd.DataFrame, cycle: Cycle) -> list[int]:
    out: list[int] = []
    for i in range(1, len(df)):
        if cycle == "short" and _short_buy(df, i):
            out.append(i)
        elif cycle == "medium" and _medium_buy(df, i):
            out.append(i)
    return out


def _short_buy(df: pd.DataFrame, i: int) -> bool:
    row, prev = df.iloc[i], df.iloc[i - 1]
    if any(pd.isna([row["ma5"], row["ma10"], prev["ma5"], prev["ma10"]])):
        return False
    golden = float(prev["ma5"]) <= float(prev["ma10"]) and float(row["ma5"]) > float(row["ma10"])
    if not golden:
        return False
    rsi = float(row["rsi"]) if not pd.isna(row["rsi"]) else 50.0
    # 避免极端超买追高；允许超卖区金叉（常见短线买点）
    if rsi > 72:
        return False
    vol = df["volume"].astype(float)
    avg10 = float(vol.iloc[max(0, i - 10) : i].mean()) if i > 0 else 0.0
    if avg10 > 0 and float(row["volume"]) < avg10 * 0.85:
        return False
    return True


def _medium_buy(df: pd.DataFrame, i: int) -> bool:
    row, prev = df.iloc[i], df.iloc[i - 1]
    need = ("ma20", "ma60", "macd", "dif", "dea", "boll_mid")
    if any(pd.isna(row.get(k)) or pd.isna(prev.get(k)) for k in need):
        return False

    golden = float(prev["ma20"]) <= float(prev["ma60"]) and float(row["ma20"]) > float(row["ma60"])
    ma20_slope_up = float(row["ma20"]) > float(prev["ma20"])
    reclaim_ma20 = (
        float(prev["close"]) <= float(prev["ma20"])
        and float(row["close"]) > float(row["ma20"])
        and ma20_slope_up
        and float(row["close"]) > float(row["boll_mid"])
    )
    macd_turn = (float(prev["macd"]) <= 0 < float(row["macd"])) or (
        float(prev["dif"]) <= float(prev["dea"]) and float(row["dif"]) > float(row["dea"])
    )
    # 中期：均线金叉，或「收复中轨+MA20 且 MACD 转向」
    if golden:
        return True
    return bool(reclaim_ma20 and macd_turn)


def _sell_trigger(
    df: pd.DataFrame,
    i: int,
    cycle: Cycle,
    buy_idx: int,
    peak: float,
) -> bool:
    if i <= buy_idx:
        return False
    # 最短持有，避免噪声秒平
    min_hold = 3 if cycle == "short" else 8
    if i - buy_idx < min_hold:
        return False

    row, prev = df.iloc[i], df.iloc[i - 1]
    close = float(row["close"])
    dd = (peak - close) / peak if peak > 0 else 0.0

    if cycle == "short":
        if not any(pd.isna([row["ma5"], row["ma10"], prev["ma5"], prev["ma10"]])):
            if float(prev["ma5"]) >= float(prev["ma10"]) and float(row["ma5"]) < float(row["ma10"]):
                return True
        if not pd.isna(row.get("rsi")) and not pd.isna(prev.get("rsi")):
            if float(prev["rsi"]) >= 70 and float(row["rsi"]) < float(prev["rsi"]) and float(row["rsi"]) < 68:
                return True
        if dd >= 0.035:
            return True
        return False

    if not any(pd.isna([row.get("ma20"), row.get("ma60"), prev.get("ma20"), prev.get("ma60")])):
        if float(prev["ma20"]) >= float(prev["ma60"]) and float(row["ma20"]) < float(row["ma60"]):
            return True
    if not any(pd.isna([row.get("boll_mid"), row.get("macd")])):
        if float(row["close"]) < float(row["boll_mid"]) and float(row["macd"]) < 0:
            return True
    if dd >= 0.07:
        return True
    return False


def _mk(
    df: pd.DataFrame,
    idx: int,
    cycle: Cycle,
    side: Side,
    pair_id: str,
    label: str,
    forced: bool,
) -> dict[str, Any]:
    row = df.iloc[idx]
    date = row["date"]
    date_s = date.date().isoformat() if hasattr(date, "date") else str(date)[:10]
    return {
        "id": f"{pair_id}-{side}",
        "cycle": cycle,
        "side": side,
        "pair_id": pair_id,
        "index": int(idx),
        "date": date_s,
        "price": round(float(row["close"]), 2),
        "label": label,
        "forced_close": forced,
    }


def _ensure_pairs(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_pair: dict[str, list[dict[str, Any]]] = {}
    for s in signals:
        by_pair.setdefault(s["pair_id"], []).append(s)
    out: list[dict[str, Any]] = []
    for _, items in by_pair.items():
        items_sorted = sorted(items, key=lambda x: (x["index"], 0 if x["side"] == "buy" else 1))
        buy = next((x for x in items_sorted if x["side"] == "buy"), None)
        sell = next(
            (x for x in items_sorted if x["side"] == "sell" and buy and x["index"] >= buy["index"]),
            None,
        )
        if buy and sell:
            out.extend([buy, sell])
    out.sort(key=lambda s: (s["index"], 0 if s["side"] == "buy" else 1, s["cycle"]))
    return out
