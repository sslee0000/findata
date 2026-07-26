"""서울 부동산 실거래가 — 국토교통부(공공데이터포털) 상세 자료 직접 호출.

DATA_GO_KR_KEY 필요. 지역은 법정동코드 앞5자리(sigungu code)로 지정.
서울 자치구 코드는 SEOUL_GU_CODE 참조.

⚠️ 중요: data.go.kr WAF가 기본 UA(python-requests/curl)를 차단한다 → 반드시 브라우저
   User-Agent 를 보낸다. (PublicDataReader 경유 시 이 UA가 없어 401/400 으로 막혔음)
엔드포인트: getRTMSDataSvcAptTradeDev (상세). 응답은 XML.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

import pandas as pd
import requests

from . import cache
from .config import require

# WAF 우회용 브라우저 UA
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
_ENDPOINT = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"

# 서울 25개 자치구 법정동코드 앞5자리 (sigungu code)
SEOUL_GU_CODE = {
    "종로구": "11110", "중구": "11140", "용산구": "11170", "성동구": "11200",
    "광진구": "11215", "동대문구": "11230", "중랑구": "11260", "성북구": "11290",
    "강북구": "11305", "도봉구": "11320", "노원구": "11350", "은평구": "11380",
    "서대문구": "11410", "마포구": "11440", "양천구": "11470", "강서구": "11500",
    "구로구": "11530", "금천구": "11545", "영등포구": "11560", "동작구": "11590",
    "관악구": "11620", "서초구": "11650", "강남구": "11680", "송파구": "11710",
    "강동구": "11740",
}

# 숫자로 다루면 편한 컬럼
_NUMERIC = {"dealAmount", "buildYear", "floor", "dealYear", "dealMonth", "dealDay"}

# 국토부 응답 영문 필드 → 한글 컬럼명 (getRTMSDataSvcAptTradeDev 상세 자료)
COLUMN_KO = {
    "aptNm": "단지명",
    "aptDong": "동",
    "aptSeq": "단지일련번호",
    "umdNm": "법정동",
    "jibun": "지번",
    "bonbun": "본번",
    "bubun": "부번",
    "buildYear": "건축년도",
    "excluUseAr": "전용면적",
    "floor": "층",
    "dealAmount": "거래금액",       # 만원
    "dealYear": "계약년도",
    "dealMonth": "계약월",
    "dealDay": "계약일",
    "dealingGbn": "거래유형",       # 중개거래/직거래
    "buyerGbn": "매수자",           # 개인/법인 등
    "slerGbn": "매도자",
    "cdealType": "해제여부",        # O = 해제된 거래
    "cdealDay": "해제사유발생일",
    "estateAgentSggNm": "중개사소재지",
    "rgstDate": "등기일자",
    "roadNm": "도로명",
    "landLeaseholdGbn": "토지임차권",
    "sggCd": "시군구코드",
    "umdCd": "법정동코드",
    "landCd": "지목코드",
    "roadNmCd": "도로명코드",
    "roadNmSggCd": "도로명시군구코드",
    "roadNmBonbun": "도로명본번",
    "roadNmBubun": "도로명부번",
    "roadNmSeq": "도로명일련번호",
    "roadNmbCd": "도로명지상지하코드",
}

# 사람이 먼저 보고 싶은 순서 (존재하는 것만 앞으로)
_KO_ORDER = ["단지명", "법정동", "지번", "동", "층", "전용면적", "거래금액",
             "계약년도", "계약월", "계약일", "건축년도", "거래유형",
             "매수자", "매도자", "해제여부", "해제사유발생일", "중개사소재지", "등기일자", "도로명"]


def to_korean(df: pd.DataFrame) -> pd.DataFrame:
    """실거래가 DataFrame 의 컬럼명을 한글로 바꾸고 보기 좋은 순서로 정렬."""
    if df is None or df.empty:
        return df
    out = df.rename(columns=COLUMN_KO)
    head = [c for c in _KO_ORDER if c in out.columns]
    return out[head + [c for c in out.columns if c not in head]]


def _fetch(sigungu_code: str, ym: str) -> pd.DataFrame:
    key = require("DATA_GO_KR_KEY")
    rows: list[dict] = []
    page = 1
    while True:
        r = requests.get(
            _ENDPOINT,
            params={
                "serviceKey": key,
                "LAWD_CD": sigungu_code,
                "DEAL_YMD": ym,
                "numOfRows": 1000,
                "pageNo": page,
            },
            headers={"User-Agent": _UA},
            timeout=20,
        )
        r.raise_for_status()
        try:
            root = ET.fromstring(r.text)
        except ET.ParseError as e:
            snippet = r.text[:200].replace("\n", " ")
            raise RuntimeError(
                f"XML 파싱 실패(WAF 차단/키 오류 가능): {snippet!r}"
            ) from e

        code = root.findtext(".//header/resultCode")
        if code not in (None, "000", "00"):
            raise RuntimeError(f"MOLIT API 오류 {code}: {root.findtext('.//header/resultMsg')}")

        items = root.findall(".//body/items/item")
        if not items:
            break
        for it in items:
            rows.append({c.tag: (c.text or "").strip() for c in it})

        total = root.findtext(".//body/totalCount")
        if len(items) < 1000 or (total and page * 1000 >= int(total)):
            break
        page += 1

    df = pd.DataFrame(rows)
    for col in _NUMERIC & set(df.columns):
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace(",", "", regex=False), errors="coerce"
        ).astype("Int64")
    return df


def get_seoul_trades(
    gu: str, ym: str, use_cache: bool = True, korean: bool = True
) -> pd.DataFrame:
    """서울 특정 구·월의 아파트 매매 실거래가(상세).

    gu: '강남구' 등 한글 구 이름 (또는 5자리 코드 직접).
    ym: 계약년월 6자리, 예 '202406'.
    korean=True(기본) 면 컬럼명을 한글로 (단지명/거래금액/전용면적/층/거래유형/해제여부 …).
           원본 영문 필드가 필요하면 korean=False. 캐시는 항상 영문 원본으로 저장한다.
    """
    key_code = SEOUL_GU_CODE.get(gu, gu)
    if not use_cache:
        df = _fetch(key_code, ym)
    else:
        # 과거 월은 확정되면 거의 안 변함 → TTL 하루
        df = cache.get_or_fetch(f"re_seoul_{key_code}_{ym}", lambda: _fetch(key_code, ym),
                                ttl_seconds=24 * 3600)
    return to_korean(df) if korean else df
