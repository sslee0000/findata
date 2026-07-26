"""findata 테스트용 데모 웹서버.

findata 를 '소비 repo 처럼' import 해서 각 모듈을 브라우저에서 눌러보는 용도.

실행:
    uv run --extra demo uvicorn demo.app:app --reload
    → http://127.0.0.1:8000
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response

from findata import fx, naver, realestate, stocks

app = FastAPI(title="findata demo")
_HERE = Path(__file__).parent


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
    df = fx.get_fx(base, quote, start, end)
    return {"symbol": f"{base}/{quote}", "rows": _records(df, date_index=True)}


@app.get("/api/index")
def api_index(name: str = "KOSPI", start: str = "2024-01-01", end: str | None = None):
    try:
        df = stocks.get_index(name, start, end)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"{name}: {e}")
    return {"name": name, "rows": _records(df, date_index=True)}


@app.get("/api/seoul-trades")
def api_seoul_trades(gu: str = "강남구", ym: str = "202406"):
    """컬럼은 한글(단지명/거래금액/전용면적/층/거래유형/해제여부 …)로 반환."""
    try:
        df = realestate.get_seoul_trades(gu, ym, korean=True)
    except Exception as e:  # noqa: BLE001
        # 키 미설정 등 → UI가 안내를 보여줄 수 있게 200 + note
        return JSONResponse({"gu": gu, "ym": ym, "rows": [], "note": str(e)})
    return {"gu": gu, "ym": ym, "rows": _records(df)}


@app.get("/api/naver/search")
def api_naver_search(q: str):
    """단지명 검색 → [{hscpNo, name}]. 사람이 단지번호를 몰라도 되게."""
    try:
        return {"query": q, "candidates": naver.find_complex(q)}
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"query": q, "candidates": [], "note": str(e)})


@app.get("/api/naver/listings")
def api_naver_listings(complexNo: str, trade: str = "매매"):
    """단지 매물 목록. complexNo 는 /api/naver/search 로 얻은 hscpNo."""
    try:
        df = naver.get_complex_listings(complexNo, trade=trade)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"complexNo": complexNo, "trade": trade, "rows": [], "note": str(e)})
    return {"complexNo": complexNo, "trade": trade, "rows": _records(df)}


@app.get("/api/meta")
def api_meta():
    """UI 드롭다운 채우기용 메타."""
    return {
        "indices": list(stocks.INDEX_SYMBOLS.keys()),
        "seoul_gu": list(realestate.SEOUL_GU_CODE.keys()),
    }
