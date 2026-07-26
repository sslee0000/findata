# findata

개인 재테크용 **금융 데이터 공용 라이브러리**. 여러 repo(asset-flow, crypto-trading-bot, mock_real_estate ...)가 공유한다.

- 환율(역대/준실시간)
- 주가지수 (KOSPI / KOSDAQ / NASDAQ / DOW / S&P500)
- 서울 부동산 실거래가 (국토부)
- 네이버 부동산 단지 매물 (⚠️ 비공식 크롤)

데이터 소스 상세는 [RULEBOOK.md](RULEBOOK.md) 참조.

## 설치 (uv)

소비하는 repo에서 git 의존성으로 추가:

```bash
uv add "findata @ git+file:///home/seungsu-lee/workspace/finance/findata"
# 원격 저장소로 옮기면:  uv add "findata @ git+https://github.com/.../findata"
```

로컬 개발(editable):

```bash
cd findata
uv venv && uv pip install -e ".[extra,dev]"
```

## 사용

```python
from findata import fx, stocks, realestate, naver

usd = fx.get_fx("USD", "KRW", "2020-01-01")   # 역대 환율(캐시됨)
print(fx.latest("USD", "KRW"))                # 최근값

kospi = stocks.get_index("KOSPI")             # 역대 지수
nasdaq = stocks.get_index("NASDAQ")

trades = realestate.get_seoul_trades("강남구", "202607")  # 실거래가 (DATA_GO_KR_KEY 필요)

cands = naver.find_complex("신동아리버파크")               # 단지 검색 → hscpNo (예: 3280)
listings = naver.get_complex_listings("3280", trade="매매")  # 매물 목록(매매/전세/월세)
# listings 컬럼: articleNumber, articleName, dongName, dealManwon(만원), warrantyPrice,
#               exclusiveSpace, floorInfo, direction, feature, brokerage, confirmDate ...
```

> 네이버는 비공식 크롤이라 **개인 PC(집 IP) 권장** — 일부 서버/클라우드 IP는 차단될 수 있다.
> 빠른 테스트(venv로):
> ```bash
> uv run findata-naver 3280            # 단지번호 직접
> uv run findata-naver 신동아리버파크    # 검색 → 매물
> uv run findata-naver 3280 --probe-body  # 엔드포인트/바디 진단(깨졌을 때)
> ```

## 환경변수

`.env.example` 를 소비 repo의 `.env` 로 복사해 채운다. 키는 findata가 아니라 **사용하는 repo** 쪽에 둔다.

| 변수 | 용도 | 필요 시점 |
|---|---|---|
| `ECOS_API_KEY` | 한국은행 고시환율 | 정밀 역대 환율 |
| `DATA_GO_KR_KEY` | 국토부 실거래가 | 실거래가 조회 |
| `FINDATA_CACHE_DIR` | 캐시 경로 override | 선택 (기본 `~/.cache/findata`) |

## 테스트용 데모 웹페이지

라이브러리를 브라우저에서 눌러보는 얇은 FastAPI + HTML 콘솔 (`demo/`). 환율·지수·서울 실거래가 3개 탭.

```bash
./run_demo.sh                 # 설치 + 실행 한 방. 0.0.0.0 바인딩(LAN 접속 가능)
PORT=9000 ./run_demo.sh       # 포트 변경
```

실행하면 접속 주소를 출력한다:
- 이 PC: `http://localhost:8000`
- **같은 네트워크의 다른 머신**: `http://<이 PC의 LAN IP>:8000` (방화벽에서 해당 포트 인바운드 허용 필요)

탭 4개 — 환율 · 주가지수 · 서울 실거래가 · 네이버 매물.

- 환율/지수: 라인차트로 시계열 표시 (무인증, 바로 동작)
- 실거래가: 자치구 25개 드롭다운 + 계약년월 → **한글 컬럼** 표로 렌더
- **네이버 매물: 단지명으로 검색**(예: 신동아리버파크) → 단지 선택 → 매매/전세/월세 매물 표.
  단지번호를 몰라도 되고, 가격은 억/만원으로 표기.
- findata 를 실제 소비 repo처럼 `import` 하므로, 데모가 곧 사용 예시다.

## 캐시

역대 시계열은 `~/.cache/findata/*.parquet` 로 로컬 저장(재호출 최소화). `findata.cache.clear()` 로 초기화.

## 구조

```
src/findata/
  fx.py           환율
  stocks.py       주가지수
  realestate.py   서울 실거래가 (+ SEOUL_GU_CODE)
  naver.py        네이버 매물 크롤러 (격리 — 깨지면 여기만 수정)
  cache.py        parquet 로컬 캐시
  config.py       키/경로
```
