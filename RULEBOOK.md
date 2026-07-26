# findata 룰북 — 데이터 소스 참조

라이브러리 코드로 감싸지 못하는 "발급 절차·코드표·엔드포인트" 만 얇게 기록한다.
동작하는 로직은 `src/findata/` 에 있고, 여기는 그 배경 참조다.

## 데이터 소스 한눈에

| 도메인 | 모듈 | 소스 | 인증키 | 실시간성 | 안정성 |
|---|---|---|---|---|---|
| 환율(역대/준실시간) | `fx` | FinanceDataReader / ECOS | ECOS는 선택 | 일별 | 높음 |
| 주가지수 | `stocks` | FinanceDataReader | 불필요 | 지연 시세 | 높음 |
| 서울 실거래가 | `realestate` | 국토부(공공데이터포털) | 필요 | 월 단위 신고 | 높음 |
| 네이버 단지 매물 | `naver` | 비공식 크롤 | 불필요 | 실시간 | **낮음** |

> **진짜 실시간 tick 환율/주가 공식 무료 소스는 없다.** 모두 일별·지연 시세가 한계.

## 1. 환율 — 한국은행 ECOS (정밀 역대용)

- 발급: <https://ecos.bok.or.kr/api/> (가입 즉시 인증키, ~1일 내 활성화)
- 기본 경로는 FinanceDataReader(무인증)로 충분. 고시환율 원천이 필요할 때만 ECOS.
- 참고 통계표: `731Y001` (원/달러 등 주요국 통화 환율). 세부 항목코드는 ECOS 통계표 검색으로 확인.

## 2. 주가지수 — FinanceDataReader 심볼

| 이름 | 심볼 |
|---|---|
| KOSPI | `KS11` |
| KOSDAQ | `KQ11` |
| NASDAQ | `IXIC` |
| DOW | `DJI` |
| S&P500 | `US500` |

- 국내 상세(구성종목/시총 등) → `pykrx` (extra). 해외 상세 → `yfinance` (extra).

## 3. 서울 실거래가 — 국토부 공공데이터포털

- **★ 신청할 것: "아파트 매매 실거래가 상세 자료" (데이터셋 `15126468`)**
  <https://www.data.go.kr/data/15126468/openapi.do>
  - endpoint: `getRTMSDataSvcAptTradeDev` — **PublicDataReader(우리 라이브러리)가 바로 이걸 호출**한다.
  - 일반 자료(`15126469`, `getRTMSDataSvcAptTrade`)와 헷갈리지 말 것. 상세가 컬럼이 더 많다:
    거래유형(중개/직거래), 해제여부·해제사유발생일(취소거래 필터), 도로명, 중개사소재지 등.
- 전월세는 `getRTMSDataSvcAptRent` (전세/월세 분석 시).
- 파라미터: `sigungu_code`(법정동 앞5자리) + `year_month`(YYYYMM)
- 서울 자치구 코드표는 `realestate.SEOUL_GU_CODE` 에 내장. 전국 코드는 <https://www.code.go.kr> 법정동코드.
- ⚠️ 상세 자료는 프라이버시 보호로 층 정보만, 동/호는 소유권이전등기 완료분만 추가 공개.

## 4. 네이버 부동산 — ⚠️ 비공식 (2026-07 확정 동작)

- 공식 API 없음. 네이버가 `fin.land.naver.com`(Next.js SPA + front-api)로 이전.
- **매물 목록 (확정)**: `POST https://fin.land.naver.com/front-api/v1/complex/article/list`
  - **쿠키 웜업 필수**: 먼저 `GET /complexes/{번호}` 로 쿠키(NNB 등)를 받은 세션으로 POST.
    (쿠키 없으면 429 TOO_MANY_REQUESTS, 잘못된 바디면 400 Error)
  - 바디: `{"size":30,"complexNumber":"3280","tradeTypes":["A1"],"pyeongTypes":[],`
    `"dongNumbers":[],"userChannelType":"PC","articleSortType":"RANKING_DESC","seed":<uuid>,"lastInfo":[]}`
    - ★ **complexNumber 는 문자열** (정수면 400!). size ≤ 30. tradeTypes: A1(매매)/B1(전세)/B2(월세)/B3(단기).
    - articleSortType: PRICE_ASC|PRICE_DESC|DATE_DESC|SPACE_ASC|SPACE_DESC|RANKING_DESC.
  - 페이지네이션: 응답 `result.lastInfo` 를 다음 요청 `lastInfo` 로, `result.hasNextPage=false` 까지.
  - 매물 항목: `result.list[].representativeArticleInfo` (가격 dealPrice=**원** 단위, spaceInfo/articleDetail/brokerInfo 중첩) → `naver._flatten_article` 로 평탄화.
- **단지 검색**: `GET m.land.naver.com/search/result/{키워드}` → 최종 URL `/complexes/{번호}` 에서 번호 추출.
- **단지 정보**: `GET /front-api/v1/complex?complexNumber={번호}` (쿠키 웜업 세션).
- 규칙:
  1. 요청 간 delay(기본 1.2s), 소량만. **서버/클라우드 IP는 차단**될 수 있음(개인 PC는 정상).
  2. 파싱/엔드포인트는 `naver.py` 한 곳에만. 깨지면 `--probe`/`--probe-body`로 진단 후 여기만 수정.
  3. `RUN_NAVER=1 pytest tests/test_naver_schema.py` 로 스키마 고정 — 변경 조기 감지.
  4. 단지번호는 new.land/fin.land 단지 URL `/complexes/<숫자>` 또는 `find_complex()` 로 확보.

## 참고 링크

- FinanceDataReader: <https://github.com/FinanceData/FinanceDataReader>
- PublicDataReader: <https://github.com/WooilJeong/PublicDataReader>
- 국토부 실거래가 공개시스템: <https://rt.molit.go.kr/>
- ECOS: <https://ecos.bok.or.kr/>
