"""네이버 부동산 단지 매물 — ⚠️ 비공식 크롤러 (격리 모듈).

경고
----
- 공식 API 없음. 모바일 사이트(m.land.naver.com)의 내부 엔드포인트를 사용한다.
- 과다 요청 시 IP 차단, 응답 구조가 예고 없이 변경될 수 있음, ToS 이슈.
- **일부 클라우드/서버 IP는 네이버가 아예 차단**한다(개인 PC/집 IP에선 정상).
  → 그래서 이 모듈은 사용자 머신에서 직접 실행해 검증한다.
- 깨지기 쉬우므로 파싱 로직을 '이 파일 하나'에만 두어, 문제 시 여기만 고친다.

사용
----
    from findata import naver
    cands = naver.find_complex("신동아리버파크")   # 단지 후보 [{hscpNo, name, ...}]
    df = naver.get_complex_listings(cands[0]["hscpNo"])  # 매물 목록(매매)

CLI (로컬 머신에서 테스트):
    python -m findata.naver 신동아리버파크
"""
from __future__ import annotations

import json
import re
import time

import pandas as pd
import requests

_MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 13; SM-S918N) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"
)

# 거래유형 코드
TRADE = {"매매": "A1", "전세": "B1", "월세": "B2"}

# 네이버 부동산은 2024~ fin.land.naver.com (Next.js SPA + front-api) 로 이전됨.
_FIN = "https://fin.land.naver.com/front-api/v1"
_DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def _session(referer: str = "https://m.land.naver.com/") -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": _MOBILE_UA,
            "Referer": referer,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ko-KR,ko;q=0.9",
        }
    )
    return s


def _warm_session(complexNumber: str | int, base: str = "https://fin.land.naver.com") -> requests.Session:
    """front-api 는 쿠키 없는 요청을 429로 막는다 → 단지 페이지를 먼저 GET해 쿠키를 받는다."""
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": _DESKTOP_UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Referer": f"{base}/complexes/{complexNumber}",
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
        }
    )
    try:
        s.get(f"{base}/complexes/{complexNumber}", timeout=10)  # 쿠키(NNB 등) 수집
    except requests.RequestException:
        pass
    return s


def get_complex_info(complexNumber: str | int, delay: float = 0.8) -> dict:
    """단지 기본정보 (fin.land front-api, 토큰 불필요 GET). front-api 도달 확인용으로도 유용.

        get_complex_info(3280)   # 신동아리버파크
    """
    time.sleep(delay)
    s = _session(referer=f"https://fin.land.naver.com/complexes/{complexNumber}")
    r = s.get(f"{_FIN}/complex", params={"complexNumber": str(complexNumber)}, timeout=10)
    r.raise_for_status()
    return _loads(r.text)


def _search_raw(keyword: str, delay: float = 0.8) -> requests.Response:
    time.sleep(delay)
    s = _session()
    url = f"https://m.land.naver.com/search/result/{requests.utils.quote(keyword)}"
    return s.get(url, timeout=10)  # 단일 매칭이면 /complex/info/{hscpNo} 로 리다이렉트


def find_complex(keyword: str, delay: float = 0.8) -> list[dict]:
    """키워드로 단지 후보 검색 → [{hscpNo, name}].

    전략(견고성 순):
      1) 단일 매칭이면 최종 URL이 /complex/info/{hscpNo} 로 리다이렉트됨 → URL에서 추출
      2) 결과 페이지 본문의 hscpNo/hscpNm JSON 패턴
      3) 그래도 없으면 본문의 /complex/info/{id} 링크
    """
    r = _search_raw(keyword, delay)
    r.raise_for_status()
    html = r.text

    out: list[dict] = []
    seen: set[str] = set()

    def _add(no: str, nm: str) -> None:
        if no and no not in seen:
            seen.add(no)
            out.append({"hscpNo": no, "name": nm or keyword})

    # 1) 리다이렉트된 최종 URL (신규 fin.land: /complexes/3280, 구 m.land: /complex/info/3280)
    m = re.search(r"/complex(?:es)?/(?:info/|article/)?(\d{3,})", r.url)
    if m:
        _add(m.group(1), keyword)

    # 2) 본문 JSON 패턴
    for m in re.finditer(r'"hscpNo"\s*:\s*"?(\d{3,})"?[^}]*?"hscpNm"\s*:\s*"([^"]+)"', html):
        _add(m.group(1), m.group(2))

    # 3) 본문 링크 패턴
    if not out:
        for m in re.finditer(r"/complex/(?:info|article)/(\d{3,})", html):
            _add(m.group(1), keyword)

    return out


def debug_search(keyword: str) -> dict:
    """진단용: 검색 응답의 실제 구조를 요약. find_complex 가 빌 때 원인 파악."""
    r = _search_raw(keyword)
    body = r.text
    return {
        "status": r.status_code,
        "final_url": r.url,
        "length": len(body),
        "keyword_in_body": keyword in body,
        "has_hscpNo": "hscpNo" in body,
        "sample_ids": re.findall(r"/complex/(?:info|article)/(\d{3,})", body)[:5],
        "head": body[:600],
    }


def _dig_list(data: dict) -> list[dict]:
    """응답 구조가 유동적이라 매물 배열이 들어있을 만한 위치를 방어적으로 탐색."""
    if not isinstance(data, dict):
        return []
    for path in (
        ("result", "list"),
        ("result", "articleList"),
        ("result", "articles"),
        ("articleList",),
        ("list",),
        ("articles",),
        ("data", "articleList"),
    ):
        cur: object = data
        for k in path:
            cur = cur.get(k) if isinstance(cur, dict) else None
        if isinstance(cur, list) and cur:
            return cur
    return []


_ARTICLE_LIST = "https://fin.land.naver.com/front-api/v1/complex/article/list"


def _flatten_article(item: dict) -> dict:
    """list[].representativeArticleInfo 에서 유용한 필드를 평탄화. dealPrice 는 원 단위."""
    a = item.get("representativeArticleInfo") or item
    sp = a.get("spaceInfo") or {}
    pr = a.get("priceInfo") or {}
    det = a.get("articleDetail") or {}
    bro = a.get("brokerInfo") or {}
    ver = a.get("verificationInfo") or {}
    deal = pr.get("dealPrice") or 0
    return {
        "articleNumber": a.get("articleNumber"),
        "articleName": a.get("articleName"),
        "dongName": a.get("dongName"),
        "tradeType": a.get("tradeType"),
        "dealPrice": deal,                       # 원
        "dealManwon": (deal // 10000) if deal else 0,  # 만원(사용자 관례)
        "warrantyPrice": pr.get("warrantyPrice"),
        "rentPrice": pr.get("rentPrice"),
        "mgmtFee": pr.get("managementFeeAmount"),
        "exclusiveSpace": sp.get("exclusiveSpace"),
        "supplySpace": sp.get("supplySpace"),
        "supplySpaceName": sp.get("supplySpaceName"),
        "floorInfo": det.get("floorInfo"),
        "direction": det.get("direction"),
        "directTrade": det.get("directTrade"),
        "feature": det.get("articleFeatureDescription"),
        "brokerage": bro.get("brokerageName"),
        "confirmDate": ver.get("articleConfirmDate"),
        "verifyType": ver.get("verificationType"),
    }


def get_complex_listings(
    hscpNo: str,
    trade: str = "매매",
    max_pages: int = 10,
    delay: float = 1.2,
    raw: bool = False,
) -> pd.DataFrame:
    """단지 매물 목록 (fin.land front-api, 확정 동작). hscpNo=단지번호(예 3280).

    trade: '매매'(A1) | '전세'(B1) | '월세'(B2).
    raw=True 면 원본 중첩 구조(list 항목) 그대로, 아니면 _flatten_article 로 평탄화.

    동작 핵심(2026-07 확정):
    - POST /front-api/v1/complex/article/list, 쿠키 웜업 세션 필요.
    - complexNumber 는 **문자열**, size≤30, pyeongTypes/dongNumbers 는 빈 배열 허용.
    - 페이지네이션: 응답 result.lastInfo 를 다음 요청 lastInfo 로, hasNextPage=false 까지.
    스키마가 바뀌면 tests/test_naver_schema.py 가 먼저 실패한다.
    """
    import uuid

    tradTpCd = TRADE.get(trade, trade)
    s = _warm_session(hscpNo, "https://fin.land.naver.com")
    seed = str(uuid.uuid4())
    last_info: list = []
    rows: list[dict] = []
    for _ in range(max_pages):
        time.sleep(delay)
        body = {
            "size": 30,
            "complexNumber": str(hscpNo),
            "tradeTypes": [tradTpCd],
            "pyeongTypes": [],
            "dongNumbers": [],
            "userChannelType": "PC",
            "articleSortType": "RANKING_DESC",
            "seed": seed,
            "lastInfo": last_info,
        }
        r = s.post(_ARTICLE_LIST, json=body,
                   headers={"Content-Type": "application/json"}, timeout=10)
        if r.status_code == 429:
            raise RuntimeError("429 — IP 일시 차단. 20~30분 쉬고 재시도.")
        r.raise_for_status()
        res = (_loads(r.text) or {}).get("result") or {}
        page_list = res.get("list") or []
        if not page_list:
            break
        rows.extend(page_list if raw else [_flatten_article(x) for x in page_list])
        if not res.get("hasNextPage"):
            break
        last_info = res.get("lastInfo") or []
        if not last_info:
            break
    return pd.DataFrame(rows)


def _loads(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def probe_endpoints(complexNumber: str | int, delay: float = 1.2) -> list[dict]:
    """여러 후보 매물 엔드포인트를 한 번씩 때려보고 어느 게 매물 JSON을 주는지 조사.

    집 IP에서 한 번만 돌리면(=DevTools 없이) 살아있는 엔드포인트를 찾을 수 있다.
    각 항목: {name, method, status, len, sample}. status 200 + 매물스러운 sample 을 찾으면 됨.
    """
    n = str(complexNumber)
    body = {"complexNumber": n, "tradeTypes": ["A1"], "page": 1}
    # base별로 쿠키 웜업 세션을 한 번씩만 만든다(요청 최소화).
    fin = _warm_session(n, "https://fin.land.naver.com")
    new = _warm_session(n, "https://new.land.naver.com")
    mob = _session()

    # (name, session, method, url, params, json_body)
    cands = [
        ("m.land getComplexArticleList", mob, "GET",
         "https://m.land.naver.com/complex/getComplexArticleList",
         {"hscpNo": n, "tradTpCd": "A1", "order": "point_", "showR0": "", "page": 1}, None),
        ("fin.land v1 complex(정보)", fin, "GET",
         "https://fin.land.naver.com/front-api/v1/complex", {"complexNumber": n}, None),
        ("fin.land v1 complex/article/list GET", fin, "GET",
         "https://fin.land.naver.com/front-api/v1/complex/article/list",
         {"complexNumber": n, "tradeType": "A1", "page": 1}, None),
        ("fin.land v1 complex/article/list POST", fin, "POST",
         "https://fin.land.naver.com/front-api/v1/complex/article/list", None, body),
        ("fin.land v1 articles POST", fin, "POST",
         "https://fin.land.naver.com/front-api/v1/articles", None, body),
        ("new.land articles/complex", new, "GET",
         f"https://new.land.naver.com/api/articles/complex/{n}",
         {"realEstateType": "APT", "tradeType": "A1", "page": 1}, None),
    ]
    out: list[dict] = []
    for name, sess, method, url, params, jbody in cands:
        time.sleep(delay)
        try:
            if method == "POST":
                r = sess.post(url, params=params, json=jbody,
                              headers={"Content-Type": "application/json"}, timeout=10)
            else:
                r = sess.get(url, params=params, timeout=10)
            txt = r.text
            out.append({"name": name, "method": method, "status": r.status_code,
                        "len": len(txt), "sample": txt[:180].replace("\n", " ")})
        except Exception as e:  # noqa: BLE001
            out.append({"name": name, "method": method, "status": "ERR",
                        "len": 0, "sample": str(e)[:180]})
    return out


_ARTICLE_LIST_URL = "https://fin.land.naver.com/front-api/v1/complex/article/list"


def probe_article_list_body(complexNumber: str | int, delay: float = 1.2) -> list[dict]:
    """확정된 POST 엔드포인트(complex/article/list)에 바디 후보들을 던져 200을 찾는다."""
    n = str(complexNumber)
    ni = int(n)
    variants = [
        ("int complexNumber", {"complexNumber": ni, "tradeTypes": ["A1"], "page": 1}),
        ("PC + 빈 필터", {"complexNumber": ni, "userChannelType": "PC",
                          "tradeTypes": ["A1"], "pyeongTypes": [], "page": 1}),
        ("풀 필터", {"complexNumber": ni, "userChannelType": "PC", "tradeTypes": ["A1"],
                    "pyeongTypes": [], "buildingNumbers": [], "priceRange": None,
                    "areaRange": None, "page": 1}),
        ("최소 complexNumber", {"complexNumber": ni}),
        ("단수 tradeType", {"complexNumber": ni, "tradeType": "A1", "page": 1}),
        ("size 포함", {"complexNumber": ni, "tradeTypes": ["A1"], "page": 1, "size": 20}),
        ("문자 complexNumber+PC", {"complexNumber": n, "userChannelType": "PC",
                                  "tradeTypes": ["A1"], "page": 1}),
    ]
    fin = _warm_session(n, "https://fin.land.naver.com")
    out: list[dict] = []
    for label, body in variants:
        time.sleep(delay)
        try:
            r = fin.post(_ARTICLE_LIST_URL, json=body,
                         headers={"Content-Type": "application/json"}, timeout=10)
            txt = r.text
            out.append({"label": label, "status": r.status_code, "len": len(txt),
                        "sample": txt[:200].replace("\n", " ")})
        except Exception as e:  # noqa: BLE001
            out.append({"label": label, "status": "ERR", "len": 0, "sample": str(e)[:200]})
    return out


def _cli() -> None:
    import sys

    flags = {"--dump", "--probe", "--probe-body"}
    args = [a for a in sys.argv[1:] if a not in flags]
    dump = "--dump" in sys.argv
    probe = "--probe" in sys.argv
    probe_body = "--probe-body" in sys.argv
    if not args:
        print("사용법:")
        print("  findata-naver <단지명|단지번호> [매매|전세|월세]")
        print("  findata-naver <단지번호> --probe-body  # 확정 엔드포인트 바디 탐색(지금 권장)")
        print("  findata-naver <단지번호> --probe       # 후보 엔드포인트 탐색")
        print("  findata-naver <단지명> --dump          # 검색 응답 진단")
        raise SystemExit(1)
    query = args[0]
    trade = args[1] if len(args) > 1 else "매매"

    # --probe-body: 확정된 complex/article/list POST 에 바디 후보들을 던져 200 찾기
    if probe_body:
        n = query if query.isdigit() else (find_complex(query) or [{}])[0].get("hscpNo", query)
        print(f"[probe-body] complexNumber={n} — POST 바디 후보 탐색 (200 찾기)\n")
        for r in probe_article_list_body(n):
            print(f"  [{r['status']}] len={r['len']:>6}  {r['label']}")
            print(f"        {r['sample']}")
        print("\n→ [200] 나온 줄의 label 과 sample 을 알려주세요. 그 바디로 확정합니다.")
        return

    # --dump: 검색 응답 구조만 출력하고 종료 (진단용)
    if dump:
        import json as _json

        print(_json.dumps(debug_search(query), ensure_ascii=False, indent=2))
        return

    # --probe: 후보 엔드포인트 탐색
    if probe:
        n = query if query.isdigit() else (find_complex(query) or [{}])[0].get("hscpNo", query)
        print(f"[probe] complexNumber={n} — 후보 엔드포인트 탐색 (200 + 매물 sample 찾기)\n")
        for r in probe_endpoints(n):
            print(f"  [{r['status']}] {r['method']:4} len={r['len']:>6}  {r['name']}")
            print(f"        {r['sample']}")
        print("\n→ status 200 이고 sample 에 매물/가격/면적이 보이는 줄을 알려주세요. 그걸로 확정합니다.")
        return

    # 숫자면 단지번호로 간주하고 검색 생략
    if query.isdigit():
        hscpNo, name = query, f"단지 {query}"
    else:
        print(f"[1] '{query}' 단지 검색…")
        cands = find_complex(query)
        if not cands:
            print("  단지를 못 찾음. 아래로 진단해 주세요:")
            print(f"    findata-naver '{query}' --dump")
            print("  또는 웹에서 단지번호를 확인해 직접 넣으세요:")
            print("    new.land.naver.com 에서 단지 클릭 → URL의 /complexes/<숫자>")
            print(f"    findata-naver <그 숫자> {trade}")
            raise SystemExit(2)
        for c in cands:
            print(f"    - hscpNo={c['hscpNo']}  {c['name']}")
        hscpNo, name = cands[0]["hscpNo"], cands[0]["name"]

    print(f"[2] hscpNo={hscpNo} ({name}) '{trade}' 매물 조회…")
    try:
        df = get_complex_listings(hscpNo, trade=trade)
    except (RuntimeError, requests.RequestException) as e:
        print(f"    실패: {e}")
        print(f"    → 살아있는 엔드포인트를 찾으려면:  findata-naver {hscpNo} --probe")
        raise SystemExit(3)
    print(f"    매물 {len(df)}건")
    if not df.empty:
        cols = [c for c in ["articleName", "dongName", "dealManwon", "warrantyPrice",
                            "exclusiveSpace", "floorInfo", "direction", "brokerage",
                            "tradeTypeName", "floorInfo", "dealOrWarrantPrc",
                            "areaName", "direction", "atclNm", "tradTpNm", "flrInfo", "prcInfo"]
                if c in df.columns]
        print(df[cols].head(15).to_string() if cols else df.head(15).to_string())
        print("\n실제 컬럼:", list(df.columns))
    else:
        print(
            "    매물 0건 = 엔드포인트/파라미터가 아직 안 맞음.\n"
            "    브라우저 DevTools에서 실제 매물 요청을 캡처해 주세요(문서 참고)."
        )


if __name__ == "__main__":
    _cli()
