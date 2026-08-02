"""findata 테스트용 데모 웹서버.

findata 를 '소비 repo 처럼' import 해서 각 모듈을 브라우저에서 눌러보는 용도.

실행:
    ./run_demo.sh                  → http://localhost:8000 (+ LAN)

공개 노출(Tailscale Funnel 등)로 인터넷에 열 때는 반드시:
    FINDATA_PUBLIC=1 ./run_demo.sh
그러면 아래 보호가 켜진다 — 낯선 사람의 요청이 곧바로 네이버 크롤/정부 API 호출로
이어지지 않게 한다(집 IP 차단·일일 쿼터 소진 방지).
  · 응답 캐시(TTL): 같은 질의는 재조회 없이 캐시로 응답
  · IP당 rate limit
  · 네이버 매물은 화이트리스트 단지 + 캐시 전용(임의 단지 크롤 불가)
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from pathlib import Path
from threading import Lock

import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from findata import fx, naver, realestate, stocks

app = FastAPI(title="findata demo")
_HERE = Path(__file__).parent

# ---------------------------------------------------------------- 공개 모드
PUBLIC = os.environ.get("FINDATA_PUBLIC") == "1"

# 공개 모드에서 네이버 조회를 허용할 단지 (임의 단지 크롤링 방지 → 집 IP 밴 방지).
# 응답은 30분 캐시되므로 단지를 늘려도 실제 크롤 횟수는 단지수 × (30분당 1회) 수준.
ALLOWED_COMPLEXES = {
    "3280": "신동아리버파크",
    "22675": "파크리오",
    "22627": "잠실엘스",
    "22746": "리센츠",
    "19127": "트리지움",
    "22853": "반포자이",
}

_RATE_MAX, _RATE_WINDOW = 30, 60.0     # IP당 60초에 30요청
_hits: dict[str, deque] = defaultdict(deque)
_rate_lock = Lock()

_cache: dict[str, tuple[float, object]] = {}
_cache_lock = Lock()


def _cached(key: str, ttl: float, produce):
    """TTL 응답 캐시 — 공개 모드에서 외부 API 재호출을 막는 핵심 방어."""
    now = time.time()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
    value = produce()
    with _cache_lock:
        _cache[key] = (now, value)
    return value


@app.middleware("http")
async def _rate_limit(request: Request, call_next):
    if PUBLIC and request.url.path.startswith("/api/"):
        ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip()
              or (request.client.host if request.client else "?"))
        now = time.time()
        with _rate_lock:
            q = _hits[ip]
            while q and now - q[0] > _RATE_WINDOW:
                q.popleft()
            if len(q) >= _RATE_MAX:
                return JSONResponse({"note": "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요."},
                                    status_code=429)
            q.append(now)
    return await call_next(request)


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


def _records(df: pd.DataFrame, date_index: bool = False) -> list[dict]:
    """DataFrame → JSON 직렬화 가능한 records. 날짜 인덱스는 date 컬럼으로.

    NaN/Inf 는 JSON 비호환이므로 None 으로 치환. (float 컬럼에 None 을 넣으려면
    object 로 캐스팅해야 pandas 가 다시 NaN 으로 되돌리지 않는다.)
    """
    if df is None or df.empty:
        return []
    df = df.copy()
    if date_index:
        df = df.reset_index()
        df.rename(columns={df.columns[0]: "date"}, inplace=True)
        df["date"] = df["date"].astype(str)
    df = df.replace([float("inf"), float("-inf")], pd.NA)
    df = df.astype(object).where(pd.notna(df), None)
    return df.to_dict(orient="records")


@app.get("/")
def index():
    return FileResponse(_HERE / "index.html")


@app.get("/api/fx")
def api_fx(base: str = "USD", quote: str = "KRW", start: str = "2024-01-01", end: str | None = None):
    def _go():
        df = fx.get_fx(base, quote, start, end)
        return {"symbol": f"{base}/{quote}", "rows": _records(df, date_index=True)}

    return _cached(f"fx:{base}:{quote}:{start}:{end}", 3600, _go)


@app.get("/api/index")
def api_index(name: str = "KOSPI", start: str = "2024-01-01", end: str | None = None):
    def _go():
        try:
            df = stocks.get_index(name, start, end)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(400, f"{name}: {e}")
        return {"name": name, "rows": _records(df, date_index=True)}

    return _cached(f"idx:{name}:{start}:{end}", 3600, _go)


@app.get("/api/seoul-trades")
def api_seoul_trades(gu: str = "강남구", ym: str = "202406"):
    """컬럼은 한글(단지명/거래금액/전용면적/층/거래유형/해제여부 …)로 반환."""
    def _go():
        try:
            df = realestate.get_seoul_trades(gu, ym, korean=True)
        except Exception as e:  # noqa: BLE001
            # 키 미설정 등 → UI가 안내를 보여줄 수 있게 200 + note
            return JSONResponse({"gu": gu, "ym": ym, "rows": [], "note": str(e)})
        return {"gu": gu, "ym": ym, "rows": _records(df)}

    return _cached(f"re:{gu}:{ym}", 6 * 3600, _go)


@app.get("/api/naver/search")
def api_naver_search(q: str):
    """단지명 검색 → [{hscpNo, name}]. 사람이 단지번호를 몰라도 되게."""
    if PUBLIC:
        # 공개 모드: 임의 키워드 검색으로 크롤이 돌지 않게 화이트리스트만 응답
        hits = [{"hscpNo": no, "name": nm} for no, nm in ALLOWED_COMPLEXES.items()
                if q.replace(" ", "") in nm.replace(" ", "") or q == no]
        return {"query": q, "candidates": hits,
                "note": None if hits else "공개 데모에서는 예시 단지만 조회할 수 있습니다 (예: 신동아리버파크)."}

    def _go():
        try:
            return {"query": q, "candidates": naver.find_complex(q)}
        except Exception as e:  # noqa: BLE001
            return JSONResponse({"query": q, "candidates": [], "note": str(e)})

    return _cached(f"nvq:{q}", 6 * 3600, _go)


@app.get("/api/naver/listings")
def api_naver_listings(complexNo: str, trade: str = "매매"):
    """단지 매물 목록. complexNo 는 /api/naver/search 로 얻은 hscpNo."""
    if PUBLIC and complexNo not in ALLOWED_COMPLEXES:
        return JSONResponse({"complexNo": complexNo, "trade": trade, "rows": [],
                             "note": "공개 데모에서는 예시 단지만 조회할 수 있습니다."})

    def _go():
        try:
            df = naver.get_complex_listings(complexNo, trade=trade)
        except Exception as e:  # noqa: BLE001
            return JSONResponse({"complexNo": complexNo, "trade": trade, "rows": [], "note": str(e)})
        return {"complexNo": complexNo, "trade": trade, "rows": _records(df)}

    # 매물은 자주 안 바뀌고, 크롤이므로 길게 캐시 (공개 모드 방어의 핵심)
    return _cached(f"nvl:{complexNo}:{trade}", 30 * 60 if PUBLIC else 300, _go)


@app.get("/api/meta")
def api_meta():
    """UI 드롭다운 채우기용 메타."""
    return {
        "indices": list(stocks.INDEX_SYMBOLS.keys()),
        "seoul_gu": list(realestate.SEOUL_GU_CODE.keys()),
        "public": PUBLIC,
        "allowedComplexes": [{"hscpNo": k, "name": v} for k, v in ALLOWED_COMPLEXES.items()] if PUBLIC else None,
    }
