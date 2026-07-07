"""서울 열린데이터광장 API 공통 클라이언트.

Extract 단계만 담당한다. 응답을 raw dict(row) 제너레이터로 반환하고,
스키마 변환은 각 transformer 레이어에서 담당한다.

URL 형식:
  http://openapi.seoul.go.kr:8088/{KEY}/json/{SERVICE}/{START}/{END}/
  분기 트레일링 필터(선택): .../{START}/{END}/{분기코드}/

응답 구조:
  { "{SERVICE}": { "list_total_count": N, "RESULT": {"CODE","MESSAGE"}, "row": [...] } }

성공 코드: INFO-000. 최대 1000건/호출. START/END(1-based)로 페이지네이션.
실측 확인 (2026-07-08):
  - 분기 트레일링 필터가 세 서비스 모두에서 정상 작동함.
  - TbgisTrdarRelm  전체 1,650건 / 분기 없음
  - VwsmTrdarFlpopQq 전체 34,633건 / 20261 필터 시 1,649건
  - VwsmTrdarSelngQq 전체 460,329건 / 20254 필터 시 21,333건
  - VwsmTrdarStorQq  전체 1,604,844건 / 20261 필터 시 75,972건
"""

import logging
import time
from collections.abc import Generator

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

SEOUL_BASE = "http://openapi.seoul.go.kr:8088"
PAGE_SIZE = 1000       # 서울 API 최대 건수/호출
MAX_RETRIES = 3
RETRY_BACKOFF_SEC = 2.0


class SeoulClient:
    """서울 열린데이터광장 단일 서비스를 페이지네이션하며 조회하는 클라이언트.

    사용 예:
        with SeoulClient("TbgisTrdarRelm") as client:
            for row in client.iter_rows():
                print(row)

        with SeoulClient("VwsmTrdarFlpopQq") as client:
            quarter = client.find_latest_quarter()
            for row in client.iter_rows(quarter_filter=quarter):
                ...
    """

    def __init__(
        self,
        service: str,
        api_key: str | None = None,
        timeout: float = 60.0,
    ):
        self.service = service
        self.api_key = api_key or settings.SEOUL_API_KEY
        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SeoulClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _build_url(self, start: int, end: int, quarter_filter: str | None = None) -> str:
        """URL 조립. 트레일링 필터(분기코드 또는 기준일 YYYYMMDD)가 있으면 뒤에 추가."""
        base = f"{SEOUL_BASE}/{self.api_key}/json/{self.service}/{start}/{end}"
        if quarter_filter:
            return f"{base}/{quarter_filter}/"
        return f"{base}/"

    def _get(self, start: int, end: int, quarter_filter: str | None = None) -> dict:
        """단일 페이지 요청 + 지수 백오프 재시도."""
        url = self._build_url(start, end, quarter_filter)
        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self._client.get(url)
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                last_exc = exc
                wait = RETRY_BACKOFF_SEC * attempt
                logger.warning(
                    "서울 API 요청 실패 [%s] (attempt %d/%d): %s. %.1fs 후 재시도",
                    self.service, attempt, MAX_RETRIES, exc, wait,
                )
                time.sleep(wait)
        raise RuntimeError(
            f"서울 API [{self.service}] 요청 {MAX_RETRIES}회 실패"
        ) from last_exc

    def _parse_response(self, data: dict) -> tuple[int, list[dict]]:
        """응답 dict에서 (total_count, rows) 추출 후 결과 코드 검증."""
        service_data = data.get(self.service, {})
        result = service_data.get("RESULT", {})
        code = result.get("CODE", "")
        if code != "INFO-000":
            raise RuntimeError(
                f"서울 API [{self.service}] 오류: {code} {result.get('MESSAGE')}"
            )
        total = service_data.get("list_total_count", 0)
        rows = service_data.get("row", [])
        return total, rows

    def fetch_total(self, quarter_filter: str | None = None) -> int:
        """서비스의 전체 건수를 조회한다(1건만 요청해 total만 읽음)."""
        data = self._get(1, 1, quarter_filter)
        total, _ = self._parse_response(data)
        return total

    def check_date(self, date_str: str) -> bool:
        """특정 기준일(YYYYMMDD)에 데이터가 있는지 1건 요청으로 확인한다.

        INFO-000 + list_total_count > 0 → True.
        INFO-200(데이터 없음) 또는 기타 비정상 코드 → False.
        네트워크 오류는 RuntimeError로 전파된다.

        생활인구 서비스(SPOP_*)의 기준일 필터 유효성 탐색에 사용한다.
        """
        data = self._get(1, 1, quarter_filter=date_str)
        service_data = data.get(self.service, {})
        # INFO-200(데이터 없음) 응답은 최상위에 RESULT만 있고 서비스 키가 없다.
        result_info = service_data.get("RESULT", data.get("RESULT", {}))
        code = result_info.get("CODE", "")
        total = service_data.get("list_total_count", 0)
        return code == "INFO-000" and int(total) > 0

    def iter_rows(self, quarter_filter: str | None = None) -> Generator[dict, None, None]:
        """전체 데이터를 PAGE_SIZE 단위로 페이지네이션하며 row dict를 yield한다.

        quarter_filter는 분기코드(예: "20261") 또는 기준일(YYYYMMDD, 예: "20260625")
        을 모두 받는다. 서울 API는 어떤 문자열이든 동일하게 트레일링 경로로 추가한다.

        첫 페이지 응답에서 list_total_count를 얻어 페이지 수를 결정하므로
        별도의 fetch_total 호출 없이 사용할 수 있다.
        """
        start = 1
        # 첫 페이지로 전체 건수 파악 + 첫 데이터 수신
        data = self._get(start, start + PAGE_SIZE - 1, quarter_filter)
        total, rows = self._parse_response(data)
        logger.info(
            "서울 API [%s] 전체 %d건 수신 시작 (분기필터=%s)",
            self.service, total, quarter_filter or "없음",
        )
        for row in rows:
            yield row
        start += PAGE_SIZE

        # 나머지 페이지 순차 수신
        while start <= total:
            end = min(start + PAGE_SIZE - 1, total)
            data = self._get(start, end, quarter_filter)
            _, rows = self._parse_response(data)
            for row in rows:
                yield row
            logger.debug(
                "서울 API [%s] 페이지 %d~%d 완료", self.service, start, end
            )
            start += PAGE_SIZE

    def find_latest_quarter(self, quarter_field: str = "STDR_YYQU_CD") -> str:
        """마지막 페이지를 조회해 최신 분기코드를 반환한다.

        데이터가 오래된 순으로 정렬돼 있다고 가정한다. 마지막 페이지의
        row에서 quarter_field 최댓값을 찾아 반환한다.
        2번의 API 호출(total 조회 + 마지막 페이지)로 동작한다.
        """
        total = self.fetch_total()
        if total == 0:
            raise RuntimeError(f"서울 API [{self.service}]: 데이터 없음")

        # 마지막 최대 PAGE_SIZE 건 조회
        last_start = max(1, total - PAGE_SIZE + 1)
        data = self._get(last_start, total)
        _, rows = self._parse_response(data)

        quarters = [r.get(quarter_field, "") for r in rows if r.get(quarter_field)]
        if not quarters:
            raise RuntimeError(
                f"서울 API [{self.service}]: {quarter_field} 필드를 찾을 수 없음"
            )
        latest = max(quarters)
        logger.info(
            "서울 API [%s] 최신 분기: %s (마지막 %d건에서 탐색)",
            self.service, latest, len(rows),
        )
        return latest
