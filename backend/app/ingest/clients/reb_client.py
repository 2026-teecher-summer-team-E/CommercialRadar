"""한국부동산원 R-ONE OpenAPI 클라이언트.

Extract 단계만 담당한다. SttsApiTblData 엔드포인트를 페이지네이션하며 조회하고,
raw row dict 제너레이터를 반환한다. 스키마 변환은 rent_transformer에서 담당한다.

URL: https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do
필수 파라미터: KEY, Type=json, STATBL_ID, DTACYCLE_CD=QY, pIndex, pSize

응답 구조:
  { "SttsApiTblData": [
      {"head": [{"list_total_count": N}, {"RESULT": {"CODE": "INFO-000", ...}}]},
      {"row": [{...}, ...]}
    ]
  }
성공 코드: INFO-000. 데이터 없음: INFO-200. 파라미터 오류: ERROR-300.

실측 확인 (2026-07-08):
  - WRTTIME_IDTFR 파라미터는 서버에서 필터로 동작하지 않음 (전 분기 데이터가 항상 반환됨).
  - 소규모(T248223134698125) 전체 1,932건 / 최신 분기 202601 필터 후 서울 말단 59건.
  - 최신 분기는 마지막 페이지 WRTTIME_IDTFR_ID 최댓값으로 확인한다.
"""

import logging
import time
from collections.abc import Generator

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

REB_BASE = "https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do"
PAGE_SIZE = 1000       # R-ONE API 페이지당 최대 건수
MAX_RETRIES = 3
RETRY_BACKOFF_SEC = 2.0

# STATBL_ID → 상가유형 매핑 (2024년 3분기~ 서울 상가유형별 임대료 통계)
STATBL_FLOOR_TYPE: dict[str, str] = {
    "T248223134698125": "소규모",
    "T244363134858603": "중대형",
    "T244913134948657": "집합",
}


class RebClient:
    """R-ONE SttsApiTblData를 페이지네이션하며 조회하는 클라이언트.

    사용 예:
        with RebClient("T248223134698125") as client:
            latest = client.find_latest_wrttime()
            for row in client.iter_rows():
                print(row)
    """

    def __init__(
        self,
        statbl_id: str,
        api_key: str | None = None,
        timeout: float = 60.0,
    ):
        self.statbl_id = statbl_id
        # 인증키는 환경변수(settings.REB_API_KEY)에서 읽는다 — 하드코딩 금지
        self.api_key = api_key or settings.REB_API_KEY
        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "RebClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _get(self, p_index: int, p_size: int) -> dict:
        """단일 페이지 요청 + 지수 백오프 재시도.

        WRTTIME_IDTFR는 API 문서상 필수이나 서버에서 필터로 동작하지 않아
        파라미터에서 제외한다(항상 전 분기 데이터 반환).
        """
        params = {
            "KEY": self.api_key,
            "Type": "json",
            "STATBL_ID": self.statbl_id,
            "DTACYCLE_CD": "QY",
            "pIndex": p_index,
            "pSize": p_size,
        }
        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self._client.get(REB_BASE, params=params)
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                last_exc = exc
                wait = RETRY_BACKOFF_SEC * attempt
                logger.warning(
                    "R-ONE API 요청 실패 [%s] (attempt %d/%d): %s. %.1fs 후 재시도",
                    self.statbl_id, attempt, MAX_RETRIES, exc, wait,
                )
                time.sleep(wait)
        raise RuntimeError(
            f"R-ONE API [{self.statbl_id}] 요청 {MAX_RETRIES}회 실패"
        ) from last_exc

    def _parse_response(self, data: dict) -> tuple[int, list[dict]]:
        """응답 dict에서 (total_count, rows) 추출 후 결과 코드 검증."""
        payload = data.get("SttsApiTblData", [])
        if not payload:
            raise RuntimeError(
                f"R-ONE API [{self.statbl_id}]: 응답에 'SttsApiTblData' 키 없음"
            )
        head_list = payload[0].get("head", [])
        result_info: dict = {}
        total = 0
        for item in head_list:
            if "list_total_count" in item:
                total = int(item["list_total_count"])
            if "RESULT" in item:
                result_info = item["RESULT"]
        code = result_info.get("CODE", "")
        # INFO-200: 해당 조건의 데이터 없음 — 오류가 아닌 빈 결과
        if code == "INFO-200":
            return 0, []
        if code != "INFO-000":
            raise RuntimeError(
                f"R-ONE API [{self.statbl_id}] 오류: {code} {result_info.get('MESSAGE')}"
            )
        rows: list[dict] = payload[1].get("row", []) if len(payload) > 1 else []
        return total, rows

    def fetch_total(self) -> int:
        """전체 건수를 조회한다 (1건만 요청해 list_total_count만 읽음)."""
        data = self._get(1, 1)
        total, _ = self._parse_response(data)
        return total

    def iter_rows(self) -> Generator[dict, None, None]:
        """전체 데이터를 PAGE_SIZE 단위로 페이지네이션하며 row dict를 yield한다.

        R-ONE API는 WRTTIME_IDTFR 필터를 무시하고 전 분기 데이터를 반환하므로
        분기 필터링은 transformer 레이어에서 수행한다.
        """
        p_index = 1
        data = self._get(p_index, PAGE_SIZE)
        total, rows = self._parse_response(data)
        if total == 0:
            return
        logger.info(
            "R-ONE API [%s] 전체 %d건 수신 시작",
            self.statbl_id, total,
        )
        for row in rows:
            yield row
        p_index += 1

        # 마지막 페이지 인덱스 (1-based, pSize 단위)
        last_page = (total + PAGE_SIZE - 1) // PAGE_SIZE
        while p_index <= last_page:
            data = self._get(p_index, PAGE_SIZE)
            _, rows = self._parse_response(data)
            if not rows:
                break
            for row in rows:
                yield row
            logger.debug(
                "R-ONE API [%s] 페이지 %d 완료 (%d건)", self.statbl_id, p_index, len(rows)
            )
            p_index += 1

    def find_latest_wrttime(self) -> str:
        """마지막 페이지를 조회해 최신 기준시점(WRTTIME_IDTFR_ID)을 반환한다.

        R-ONE API는 최신 분기가 마지막 페이지에 위치한다고 가정한다(오래된 순 정렬).
        2번의 API 호출(전체 건수 조회 + 마지막 페이지)로 동작한다.
        """
        total = self.fetch_total()
        if total == 0:
            raise RuntimeError(f"R-ONE API [{self.statbl_id}]: 데이터 없음")

        last_page = (total + PAGE_SIZE - 1) // PAGE_SIZE
        data = self._get(last_page, PAGE_SIZE)
        _, rows = self._parse_response(data)

        wrttimes = [r.get("WRTTIME_IDTFR_ID", "") for r in rows if r.get("WRTTIME_IDTFR_ID")]
        if not wrttimes:
            raise RuntimeError(
                f"R-ONE API [{self.statbl_id}]: WRTTIME_IDTFR_ID 필드를 찾을 수 없음"
            )
        latest = max(wrttimes)
        logger.info(
            "R-ONE API [%s] 최신 기준시점: %s (마지막 페이지 %d건에서 탐색)",
            self.statbl_id, latest, len(rows),
        )
        return latest
