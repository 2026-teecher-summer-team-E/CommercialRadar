"""ml_predictions 넓힌 유니크 키 동작 검증."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.ml_predictions import AGGREGATE_CATEGORY, MlPrediction
from app.models.commercial_district import CommercialDistrict


def _district(db, code="SCHEMA-CD-1"):
    d = CommercialDistrict(external_code=code, district_name="스키마테스트")
    db.add(d)
    db.flush()
    return d


def test_same_quarter_different_category_coexist(db):
    d = _district(db)
    db.add(MlPrediction(
        commercial_district_id=d.id, prediction_type="sales",
        target_quarter="2025-Q1", category_name=AGGREGATE_CATEGORY,
        predicted_value={"total_sales": 100},
    ))
    db.add(MlPrediction(
        commercial_district_id=d.id, prediction_type="sales",
        target_quarter="2025-Q1", category_name="카페",
        predicted_value={"total_sales": 40},
    ))
    db.flush()  # 넓힌 유니크 키 덕분에 충돌 없이 공존해야 함
    rows = db.query(MlPrediction).filter(
        MlPrediction.commercial_district_id == d.id
    ).all()
    assert len(rows) == 2


def test_identical_key_conflicts(db):
    d = _district(db, code="SCHEMA-CD-2")
    db.add(MlPrediction(
        commercial_district_id=d.id, prediction_type="sales",
        target_quarter="2025-Q1", category_name="카페",
        predicted_value={"total_sales": 40},
    ))
    db.flush()
    db.add(MlPrediction(
        commercial_district_id=d.id, prediction_type="sales",
        target_quarter="2025-Q1", category_name="카페",
        predicted_value={"total_sales": 99},
    ))
    with pytest.raises(IntegrityError):
        db.flush()


def test_category_name_defaults_to_sentinel(db):
    d = _district(db, code="SCHEMA-CD-3")
    row = MlPrediction(
        commercial_district_id=d.id, prediction_type="sales",
        target_quarter="2025-Q2", predicted_value={"total_sales": 1},
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    assert row.category_name == AGGREGATE_CATEGORY
