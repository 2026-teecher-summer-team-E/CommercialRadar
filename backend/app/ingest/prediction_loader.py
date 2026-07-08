"""ML 예측 결과 CSV → ml_predictions 멱등 적재.

로컬(또는 GPU 박스)에서 학습·추론한 결과를 `ml/predict.py`가 CSV로 내보내면,
이 로더가 DB에 upsert한다. 무거운 ML 의존성(torch/darts) 없이 stdlib `csv`만
사용하므로 가벼운 backend/AWS 환경에서 그대로 실행할 수 있다.

CSV 스키마 (헤더 필수):
    commercial_district_id, prediction_type, target_quarter,
    category_name, predicted_value, confidence, model_version

- category_name: 업종명. 빈 칸이면 '__ALL__'(전체 합산)로 저장.
- predicted_value: JSON 문자열. 예) '{"survival_rate": 0.71}'
- confidence, model_version: 빈 칸이면 NULL
- 멱등 키: (commercial_district_id, prediction_type, target_quarter, category_name)
  → uq_ml_pred_cd_type_quarter_category 제약으로 재실행 시 중복 없이 갱신.
"""

import csv
import json
import logging

from pydantic import BaseModel, ValidationError, field_validator
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.ingestion_run import IngestionRun
from app.models.ml_predictions import MlPrediction

logger = logging.getLogger(__name__)

BATCH_SIZE = 500

REQUIRED_COLUMNS = {
    "commercial_district_id",
    "prediction_type",
    "target_quarter",
    "category_name",
    "predicted_value",
    "confidence",
    "model_version",
}

_VALID_TYPES = {"survival", "population", "sales"}


class PredictionRowIn(BaseModel):
    """예측 CSV 1행의 검증 스키마."""

    commercial_district_id: int
    prediction_type: str
    category_name: str = "__ALL__"
    target_quarter: str
    predicted_value: dict
    confidence: float | None = None
    model_version: str | None = None

    model_config = {"extra": "ignore"}

    @field_validator("prediction_type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        if v not in _VALID_TYPES:
            raise ValueError(f"prediction_type must be one of {sorted(_VALID_TYPES)}, got {v!r}")
        return v


def _parse_row(raw: dict) -> dict:
    """CSV raw dict → 파싱된 dict (predicted_value JSON 디코딩, 빈 칸 → None)."""
    conf = (raw.get("confidence") or "").strip()
    model_version = (raw.get("model_version") or "").strip()
    return {
        "commercial_district_id": int((raw.get("commercial_district_id") or "").strip()),
        "prediction_type": (raw.get("prediction_type") or "").strip(),
        "target_quarter": (raw.get("target_quarter") or "").strip(),
        "category_name": (raw.get("category_name") or "").strip() or "__ALL__",
        "predicted_value": json.loads(raw.get("predicted_value") or ""),
        "confidence": float(conf) if conf else None,
        "model_version": model_version or None,
    }


def _upsert_batch(db: Session, rows: list[dict]) -> int:
    if not rows:
        return 0
    stmt = insert(MlPrediction).values([{**r, "updated_at": func.now()} for r in rows])
    stmt = stmt.on_conflict_do_update(
        constraint="uq_ml_pred_cd_type_quarter_category",
        set_={
            "predicted_value": stmt.excluded.predicted_value,
            "confidence": stmt.excluded.confidence,
            "model_version": stmt.excluded.model_version,
            "updated_at": func.now(),
        },
    )
    db.execute(stmt)
    return len(rows)


def load_predictions_csv(db: Session, csv_path: str) -> tuple[int, int, int]:
    """CSV를 읽어 ml_predictions에 upsert. (total, upserted, failed) 반환.

    깨진 행(JSON 파싱 실패·검증 실패)은 스킵하고 경고 로그를 남긴다.
    """
    header_checked = False
    valid_rows: list[dict] = []
    total = 0
    failed = 0

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            raise ValueError("CSV에 헤더가 없습니다.")
        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            raise ValueError(f"CSV 필수 컬럼 누락: {sorted(missing)}")
        header_checked = True

        for line_no, raw in enumerate(reader, start=2):  # 2 = 첫 데이터 행
            total += 1
            try:
                parsed = _parse_row(raw)
                PredictionRowIn.model_validate(parsed)
                valid_rows.append(parsed)
            except (ValidationError, ValueError, KeyError, json.JSONDecodeError) as exc:
                failed += 1
                logger.warning("예측 CSV %d행 스킵: %s | raw=%s", line_no, exc, raw)

    if not header_checked:
        raise ValueError("CSV 헤더 검증 실패.")

    upserted = 0
    for start in range(0, len(valid_rows), BATCH_SIZE):
        batch = valid_rows[start : start + BATCH_SIZE]
        try:
            upserted += _upsert_batch(db, batch)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("예측 배치 upsert 실패 (start=%d, size=%d)", start, len(batch))
            raise

    return total, upserted, failed


def import_predictions(csv_path: str, db: Session | None = None) -> IngestionRun:
    """CSV 적재를 ingestion_run 이력에 기록하며 실행한다 (jobs.py와 동일한 관측 패턴).

    db를 주입하지 않으면 자체 세션을 생성한다(CLI에서 이렇게 호출).
    """
    owns_session = db is None
    db = db or SessionLocal()
    source = "ml_predictions_csv"

    run = IngestionRun(source=source, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        total, upserted, failed = load_predictions_csv(db, csv_path)

        run.status = "success"
        run.fetched_count = total
        run.upserted_count = upserted
        run.failed_count = failed
        run.finished_at = func.now()
        db.commit()
        logger.info(
            "예측 적재 완료 [%s]: file=%s total=%d upserted=%d failed=%d",
            source, csv_path, total, upserted, failed,
        )
        return run
    except Exception as exc:
        db.rollback()
        run.status = "failed"
        run.error_message = str(exc)[:2000]
        run.finished_at = func.now()
        db.commit()
        logger.exception("예측 적재 실패 [%s] file=%s", source, csv_path)
        raise
    finally:
        if owns_session:
            db.close()
