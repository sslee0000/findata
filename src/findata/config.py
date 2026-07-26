"""환경설정 — API 키와 캐시 경로. 키는 소비 repo의 .env(환경변수)에서 주입받는다."""
from __future__ import annotations

import os
from pathlib import Path


def _env(name: str) -> str | None:
    v = os.environ.get(name)
    return v.strip() if v else None


ECOS_API_KEY = _env("ECOS_API_KEY")
DATA_GO_KR_KEY = _env("DATA_GO_KR_KEY")

CACHE_DIR = Path(_env("FINDATA_CACHE_DIR") or (Path.home() / ".cache" / "findata"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def require(name: str) -> str:
    """키가 없으면 어디서 발급하는지 알려주며 실패한다."""
    val = globals().get(name)
    if not val:
        hint = {
            "ECOS_API_KEY": "https://ecos.bok.or.kr/api/ 에서 발급 후 .env에 ECOS_API_KEY 설정",
            "DATA_GO_KR_KEY": "https://www.data.go.kr 에서 활용신청 후 .env에 DATA_GO_KR_KEY 설정",
        }.get(name, "")
        raise RuntimeError(f"{name} 미설정. {hint}")
    return val
