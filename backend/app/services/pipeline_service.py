"""데이터 인제스천 파이프라인의 진입점.

실제 구현은 app.ingest 패키지에 레이어별로 분리되어 있다:
  - app.ingest.clients      : 외부 API 호출 (Extract)
  - app.ingest.transformers : raw → 우리 스키마 변환 + 검증 (Transform)
  - app.ingest.loaders      : 멱등 upsert (Load)
  - app.ingest.jobs         : E→T→L 오케스트레이션 + 실행 이력

크론(app.cli)과 관리자 엔드포인트(routers.admin)는 jobs.run_targets를 공유 호출한다.
"""

from app.ingest.jobs import JOBS, run_targets

__all__ = ["JOBS", "run_targets"]
