#!/usr/bin/env python3
"""R-ONE 상권명 → 좌표 오프라인 지오코딩기 (카카오 로컬 keyword 검색).

임대료 이름 매칭이 실패/동점일 때 좌표로 보완하기 위한 정적 매핑
(backend/app/ingest/data/reb_coords.json)을 생성/갱신한다. 1회성 오프라인 도구로,
ETL 런타임(순수 트랜스포머)에서는 호출하지 않는다.

사용:
    python scripts/geocode_reb.py 숙명여대 도산대로 테헤란로     # 지정 이름만 갱신
    python scripts/geocode_reb.py                              # 기본 목록(현재 미매칭/경계 케이스)

키: 루트 .env 의 KAKAO_REST_KEY (카카오 REST API 키, JavaScript 키 아님).
카카오 keyword 검색 첫 결과의 (y=위도, x=경도)를 취하며, 결과가 애매할 수 있으니
place/address 를 함께 출력해 사람이 검수한 뒤 커밋한다.
"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
OUT_PATH = ROOT / "backend" / "app" / "ingest" / "data" / "reb_coords.json"

# 현재 이름 매칭이 못 붙이거나 동점인 경계 케이스(검수 대상). 필요 시 인자로 덮어씀.
DEFAULT_NAMES = ["숙명여대", "도산대로", "테헤란로", "서초대로"]


def normalize_name(name: str) -> str:
    """rent_transformer.normalize_name과 동일: 전각/반각 공백 제거."""
    return name.replace(" ", "").replace("　", "")


def read_key() -> str:
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == "KAKAO_REST_KEY":
            return v.strip().strip('"').strip("'")
    sys.exit("KAKAO_REST_KEY가 .env에 없습니다.")


def geocode(name: str, key: str) -> tuple[float, float, str] | None:
    url = "https://dapi.kakao.com/v2/local/search/keyword.json?" + urllib.parse.urlencode(
        {"query": name, "size": 1}
    )
    req = urllib.request.Request(url, headers={"Authorization": f"KakaoAK {key}"})
    with urllib.request.urlopen(req, timeout=8) as r:
        docs = json.load(r).get("documents", [])
    if not docs:
        return None
    d = docs[0]
    place = f"{d.get('place_name', '')} | {d.get('road_address_name') or d.get('address_name', '')}"
    return float(d["y"]), float(d["x"]), place


def main() -> None:
    names = sys.argv[1:] or DEFAULT_NAMES
    key = read_key()
    coords: dict[str, list[float]] = {}
    if OUT_PATH.exists():
        coords = json.loads(OUT_PATH.read_text(encoding="utf-8"))

    for name in names:
        try:
            res = geocode(name, key)
        except Exception as exc:  # noqa: BLE001 (오프라인 도구, 관대하게)
            print(f"[ERROR] {name}: {exc}")
            continue
        if res is None:
            print(f"[결과없음] {name}")
            continue
        lat, lng, place = res
        coords[normalize_name(name)] = [lat, lng]
        print(f"[OK] {name} → {lat},{lng}  ({place})")

    OUT_PATH.write_text(
        json.dumps(coords, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\n저장: {OUT_PATH} ({len(coords)}개)")


if __name__ == "__main__":
    main()
