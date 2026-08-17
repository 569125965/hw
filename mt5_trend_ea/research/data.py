"""Download and cache gold futures bars (GC=F) as an XAUUSD proxy."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yfinance as yf

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [str(c[0]).title() for c in df.columns]
    else:
        df = df.copy()
        df.columns = [str(c).title() for c in df.columns]
    keep = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in df.columns]
    out = df[keep].dropna(subset=["Open", "High", "Low", "Close"])
    out.index = pd.to_datetime(out.index, utc=True)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out


def download_bars(interval: str, period: str, cache_name: str) -> pd.DataFrame:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache = DATA_DIR / cache_name
    if cache.exists():
        df = pd.read_csv(cache, index_col=0, parse_dates=True)
        if len(df) > 100:
            return df
    raw = yf.download("GC=F", interval=interval, period=period, progress=False, auto_adjust=True)
    df = _flatten(raw)
    if df.empty:
        raise RuntimeError(f"empty download GC=F {interval} {period}")
    df.to_csv(cache)
    return df


def load_m5() -> pd.DataFrame:
    return download_bars("5m", "60d", "gc_f_m5.csv")


def load_h1() -> pd.DataFrame:
    return download_bars("1h", "2y", "gc_f_h1.csv")
