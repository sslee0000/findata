# 이 PC에서 데모를 인터넷에 공개하기 (Tailscale Funnel)

AWS 같은 클라우드 없이, **집 PC에서 직접** 데모를 공개한다.
Tailscale Funnel 은 무료이고 포트포워딩·고정IP·도메인이 필요 없다.
공개 주소는 이 노드의 이름으로 고정된다: `https://<노드>.<tailnet>.ts.net/`

## 1) Funnel 활성화 (최초 1회, 관리자 콘솔)

Funnel 은 tailnet 정책에 권한이 필요하다. 아래를 실행하면 필요한 경우
활성화 링크가 출력되니 브라우저에서 승인하면 된다.

```bash
tailscale funnel 8000
```

수동으로 하려면 <https://login.tailscale.com/admin/dns> 에서 **HTTPS Certificates** 를 켜고,
Access Controls 의 정책에 `nodeAttrs` 로 `funnel` 을 추가한다.

## 2) 데모를 공개 모드로 실행

```bash
FINDATA_PUBLIC=1 ./run_demo.sh
```

`FINDATA_PUBLIC=1` 이 켜는 보호 (인터넷 공개 시 **필수**):

| 보호 | 이유 |
|---|---|
| 응답 캐시(TTL) | 방문자 요청이 매번 외부 API/크롤로 이어지지 않게 |
| IP당 rate limit (60초 30회) | 남용·스크래핑 방지 |
| 네이버 **화이트리스트 단지만** | 임의 단지 크롤 차단 → **집 IP 밴 방지** |
| 정부 API 캐시 6시간 | 일일 10,000회 쿼터 보호 |

## 3) 상시 구동 (재부팅 후 자동 시작)

```bash
mkdir -p ~/.config/systemd/user
cp deploy/findata-demo.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now findata-demo
loginctl enable-linger "$USER"     # 로그아웃/재부팅 후에도 계속 실행

# Funnel 도 상시로
tailscale funnel --bg 8000
```

상태 확인:
```bash
systemctl --user status findata-demo
tailscale funnel status
```

## 4) 끄기

```bash
tailscale funnel --https=443 off
systemctl --user disable --now findata-demo
```

## 주의

- 노트북이 꺼져 있거나 네트워크가 끊기면 링크도 죽는다. 포트폴리오에 걸 때는
  이 점을 감안할 것(항상 살아있어야 한다면 정적 스냅샷이 안전).
- `.env` 의 API 키는 절대 커밋하지 않는다(.gitignore 처리됨).
- 공개 모드에서는 네이버 조회가 `demo/app.py` 의 `ALLOWED_COMPLEXES` 단지로 제한된다.
