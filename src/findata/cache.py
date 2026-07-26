"""역대(historical) 데이터용 로컬 parquet 캐시.

- 거의 변하지 않는 시계열(역대 환율/지수/실거래가)을 로컬에 저장해 재호출을 줄인다.
- key 단위로 parquet 1파일. TTL 지나면 재fetch.
- 실시간/매물 성격(naver)은 캐시하지 않거나 짧은 TTL만 쓴다.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

import pandas as pd

from .config import CACHE_DIR


def _path(key: str) -> Path:
    safe = key.replace("/", "_").replace(":", "_")
    return CACHE_DIR / f"{safe}.parquet"


def get_or_fetch(
    key: str,
    fetch: Callable[[], pd.DataFrame],
    ttl_seconds: float | None = None,
) -> pd.DataFrame:
    """key로 캐시를 조회하고, 없거나 TTL 만료 시 fetch()로 갱신한다.

    ttl_seconds=None 이면 무기한(역대 데이터에 적합). 파일이 있으면 그대로 반환.
    """
    p = _path(key)
    if p.exists():
        fresh = ttl_seconds is None or (time.time() - p.stat().st_mtime) < ttl_seconds
        if fresh:
            return pd.read_parquet(p)
    df = fetch()
    if df is not None and not df.empty:
        df.to_parquet(p)
    return df


def clear(key: str | None = None) -> None:
    """캐시 삭제. key 지정 시 해당 항목만, 없으면 전체."""
    if key:
        _path(key).unlink(missing_ok=True)
    else:
        for f in CACHE_DIR.glob("*.parquet"):
            f.unlink()
