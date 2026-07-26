#!/usr/bin/env bash
# findata 테스트 데모를 한 번에 실행. 같은 로컬 네트워크의 다른 머신에서도 접속 가능.
#
#   ./run_demo.sh                 # 기본 포트 8000, 0.0.0.0 바인딩
#   PORT=9000 ./run_demo.sh       # 포트 변경
#
# 다른 머신에서 접속: 출력되는 http://<이 PC의 LAN IP>:<PORT>
set -euo pipefail
cd "$(dirname "$0")"

UV="${UV:-$HOME/.local/bin/uv}"
HOST="${HOST:-0.0.0.0}"     # 0.0.0.0 = LAN의 모든 인터페이스에서 접속 허용
PORT="${PORT:-8000}"

# 1) venv 준비 + 데모 의존성 설치(멱등)
[ -d .venv ] || "$UV" venv
"$UV" pip install -e ".[demo]" --quiet

# 2) .env 있으면 로드(실거래가 키 등)
if [ -f .env ]; then set -a; . ./.env; set +a; fi

# 3) 접속 주소 안내 (LAN IP 자동 탐지)
LAN_IP="$(ip -4 -o addr show scope global 2>/dev/null | grep -v tailscale0 | awk '{print $4}' | cut -d/ -f1 | head -1)"
echo "──────────────────────────────────────────────"
echo "  findata 데모 실행 중"
echo "  이 PC:        http://localhost:${PORT}"
[ -n "${LAN_IP:-}" ] && echo "  같은 네트워크: http://${LAN_IP}:${PORT}"
if [ "${FINDATA_PUBLIC:-}" = "1" ]; then
  TS_NAME="$(tailscale status --json 2>/dev/null | sed -n 's/.*"DNSName":[[:space:]]*"\([^"]*\)\.".*/\1/p' | head -1)"
  echo "  공개 모드:    ON (캐시 + rate limit + 네이버 화이트리스트)"
  [ -n "${TS_NAME:-}" ] && echo "  인터넷 공개:  https://${TS_NAME}/   ← Funnel 실행 중일 때"
else
  echo "  공개 모드:    OFF (로컬 전용) — 인터넷 공개 시 FINDATA_PUBLIC=1 로 실행"
fi
echo "  (방화벽에서 ${PORT}/tcp 인바운드 허용 필요할 수 있음)"
echo "  종료: Ctrl+C"
echo "──────────────────────────────────────────────"

# 4) 서버 실행
exec "$UV" run uvicorn demo.app:app --host "$HOST" --port "$PORT"
