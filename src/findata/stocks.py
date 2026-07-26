"""주가 지수 — KOSPI/KOSDAQ/NASDAQ/DOW/S&P500.

단일 소스: FinanceDataReader (무인증). 심볼 매핑만 신경 쓰면 된다.
국내 상세(구성종목 등)는 pykrx, 해외 상세는 yfinance를 extra로 설치해 확장.
"""
from __future__ import annotations

import pandas as pd

from . import cache

# 사람이 읽는 이름 → FinanceDataReader 심볼
INDEX_SYMBOLS = {
    "KOSPI": "KS11",
    "KOSDAQ": "KQ11",
    "NASDAQ": "IXIC",
    "DOW": "DJI",
    "S&P500": "US500",   # FDR: 'US500' 또는 'S&P500'
    "SP500": "US500",
}


def get_index(
    name: str,
    start: str = "2015-01-01",
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """지수 시계열(일별 OHLCV). 예: get_index("KOSPI"), get_index("NASDAQ")."""
    import FinanceDataReader as fdr

    key_name = name.upper().replace(" ", "")
    symbol = INDEX_SYMBOLS.get(key_name, name)  # 미매핑이면 원문 심볼로 시도

    def _fetch() -> pd.DataFrame:
        return fdr.DataReader(symbol, start, end)

    if not use_cache:
        return _fetch()
    key = f"idx_{key_name}_{start}_{end or 'now'}"
    return cache.get_or_fetch(key, _fetch, ttl_seconds=12 * 3600)


def latest_close(name: str) -> float:
    df = get_index(name, start="2024-01-01", use_cache=False)
    return float(df["Close"].dropna().iloc[-1])
