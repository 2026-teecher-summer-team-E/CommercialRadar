"""prediction_loader의 category_name 처리 검증."""

from app.ingest.prediction_loader import load_predictions_csv
from app.models.commercial_district import CommercialDistrict
from app.models.ml_predictions import MlPrediction


def _district(db, code):
    d = CommercialDistrict(external_code=code, district_name="로더테스트")
    db.add(d)
    db.flush()
    return d


def _write_csv(tmp_path, rows):
    p = tmp_path / "preds.csv"
    header = "commercial_district_id,prediction_type,target_quarter,category_name,predicted_value,confidence,model_version\n"
    p.write_text(header + "".join(rows), encoding="utf-8")
    return str(p)


def test_loads_category_rows(db, tmp_path):
    d = _district(db, "LOADER-CD-1")
    csv_path = _write_csv(tmp_path, [
        f'{d.id},sales,2025-Q1,__ALL__,"{{""total_sales"": 100}}",0.8,tft-v1\n',
        f'{d.id},sales,2025-Q1,카페,"{{""total_sales"": 40}}",0.8,tft-v1\n',
    ])

    total, upserted, failed = load_predictions_csv(db, csv_path)

    assert (total, upserted, failed) == (2, 2, 0)
    rows = db.query(MlPrediction).filter(
        MlPrediction.commercial_district_id == d.id
    ).all()
    assert sorted(r.category_name for r in rows) == sorted(["__ALL__", "카페"])


def test_blank_category_defaults_to_sentinel(db, tmp_path):
    d = _district(db, "LOADER-CD-2")
    csv_path = _write_csv(tmp_path, [
        f'{d.id},sales,2025-Q1,,"{{""total_sales"": 100}}",0.8,tft-v1\n',
    ])

    load_predictions_csv(db, csv_path)

    row = db.query(MlPrediction).filter(
        MlPrediction.commercial_district_id == d.id
    ).one()
    assert row.category_name == "__ALL__"
