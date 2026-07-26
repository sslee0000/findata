"""환율 — 역대(historical) 및 준실시간.

기본 소스: FinanceDataReader (무인증, 일별 종가).
정밀 역대(한국은행 고시환율)는 ECOS_API_KEY 설정 시 PublicDataReader 경로 사용.

주의: '진짜 실시간 tick' 환율 공식 소스는 없다. 일별/지연 시세가 한계.
"""
from __future__ import annotations

import pandas as pd

from . import cache


def get_fx(
    base: str = "USD",
    quote: str = "KRW",
    start: str = "2015-01-01",
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """역대 환율 시계열(일별). 예: get_fx("USD","KRW","2020-01-01").

    반환: DatetimeIndex + Open/High/Low/Close 컬럼(FDR 규격).
    """
    import FinanceDataReader as fdr

    symbol = f"{base}/{quote}"

    def _fetch() -> pd.DataFrame:
        return fdr.DataReader(symbol, start, end)

    if not use_cache:
        return _fetch()
    # 역대 시계열은 하루 단위로만 갱신되면 충분 → TTL 12h
    key = f"fx_{base}_{quote}_{start}_{end or 'now'}"
    return cache.get_or_fetch(key, _fetch, ttl_seconds=12 * 3600)


def latest(base: str = "USD", quote: str = "KRW") -> float:
    """가장 최근 종가(준실시간)."""
    df = get_fx(base, quote, start="2024-01-01", use_cache=False)
    return float(df["Close"].dropna().iloc[-1])
