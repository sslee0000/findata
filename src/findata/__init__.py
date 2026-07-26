"""findata — 개인 재테크용 금융 데이터 공용 라이브러리.

    from findata import fx, stocks, realestate, naver

    fx.get_fx("USD", "KRW", "2020-01-01")
    stocks.get_index("KOSPI")
    realestate.get_seoul_trades("강남구", "202607")
    naver.get_complex_listings("<complex_id>")   # ⚠️ 비공식 크롤러
"""
from . import cache, config, fx, naver, realestate, stocks

__version__ = "0.1.0"
__all__ = ["fx", "stocks", "realestate", "naver", "cache", "config"]
