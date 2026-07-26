"""네이버 크롤러 스키마 회귀 테스트.

네이버가 응답 구조/엔드포인트를 바꾸면 여기서 먼저 실패 → naver.py 한 곳만 고친다.
네트워크가 필요하므로 기본은 skip. 점검 시 RUN_NAVER=1 로 실행.

    RUN_NAVER=1 pytest tests/test_naver_schema.py

기준 단지: 3280 (신동아리버파크, 동작구 노량진동).
동작 확정(2026-07): POST /front-api/v1/complex/article/list, 쿠키 웜업 세션,
complexNumber=문자열, size≤30, pyeongTypes/dongNumbers=[]; 페이지네이션은 result.lastInfo.
"""
import os

import pytest

RUN = os.environ.get("RUN_NAVER") == "1"
SAMPLE = os.environ.get("NAVER_SAMPLE_COMPLEX", "3280")

# 평탄화 결과가 반드시 포함해야 하는 컬럼 (바뀌면 _flatten_article 수정)
EXPECTED = {"articleNumber", "articleName", "dealPrice", "dealManwon",
            "exclusiveSpace", "floorInfo", "tradeType"}


@pytest.mark.skipif(not RUN, reason="RUN_NAVER=1 일 때만 실행")
def test_complex_listings_columns():
    from findata import naver

    df = naver.get_complex_listings(SAMPLE, trade="매매", max_pages=1)
    assert not df.empty, "매물 0건 — 엔드포인트/바디 변경 의심(naver.py 확인)"
    missing = EXPECTED - set(df.columns)
    assert not missing, f"기대 컬럼 누락: {missing} — _flatten_article 매핑 확인"


@pytest.mark.skipif(not RUN, reason="RUN_NAVER=1 일 때만 실행")
def test_find_complex_resolves_number():
    from findata import naver

    cands = naver.find_complex("신동아리버파크")
    assert any(c["hscpNo"] == "3280" for c in cands), "단지 검색이 3280 을 못 찾음"
