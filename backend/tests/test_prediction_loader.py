"""prediction_loader의 category_name 처리 및 캐시 무효화 검증."""

import pytest

from app.ingest import prediction_loader
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


def test_partial_batch_failure_still_invalidates_cache(db, tmp_path, monkeypatch):
    """2번째 배치가 실패해도 1번째 배치는 이미 커밋됐으니 캐시는 무효화돼야 한다."""
    d = _district(db, "LOADER-CD-3")
    monkeypatch.setattr(prediction_loader, "BATCH_SIZE", 2)

    original_upsert = prediction_loader._upsert_batch
    calls = {"n": 0}

    def failing_upsert(db_arg, rows):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return original_upsert(db_arg, rows)

    monkeypatch.setattr(prediction_loader, "_upsert_batch", failing_upsert)

    invalidate_calls = {"n": 0}
    monkeypatch.setattr(
        prediction_loader,
        "invalidate_all",
        lambda: invalidate_calls.__setitem__("n", invalidate_calls["n"] + 1),
    )

    csv_path = _write_csv(tmp_path, [
        f'{d.id},survival,2025-Q{i + 1},,"{{""survival_rate"": 0.5}}",0.8,tft-v1\n'
        for i in range(4)
    ])

    with pytest.raises(RuntimeError):
        prediction_loader.import_predictions(csv_path, db=db)

    # 1번째 배치(2행)는 이미 커밋됐고, 2번째 배치는 실패해 반영되지 않는다.
    committed = (
        db.query(MlPrediction).filter(MlPrediction.commercial_district_id == d.id).count()
    )
    assert committed == 2
    assert invalidate_calls["n"] == 1


def test_no_batches_committed_leaves_progress_at_zero(db, tmp_path, monkeypatch):
    """헤더 검증 실패처럼 배치 upsert 자체가 시작 전에 실패하면 progress도 0으로 남는다.

    import_predictions는 finally에서 이 progress["upserted"]를 보고 invalidate_all()
    호출 여부를 정하므로, 이 값이 정확해야 무효화 판단이 정확해진다.
    """
    monkeypatch.setattr(
        prediction_loader, "_upsert_batch", lambda *a, **k: pytest.fail("should not run")
    )

    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("not,the,right,header\n1,2,3,4", encoding="utf-8")

    progress: dict = {}
    with pytest.raises(ValueError):
        prediction_loader.load_predictions_csv(db, str(bad_csv), progress)

    assert progress["upserted"] == 0


def test_full_success_invalidates_cache_once(db, tmp_path, monkeypatch):
    d = _district(db, "LOADER-CD-4")
    invalidate_calls = {"n": 0}
    monkeypatch.setattr(
        prediction_loader,
        "invalidate_all",
        lambda: invalidate_calls.__setitem__("n", invalidate_calls["n"] + 1),
    )

    csv_path = _write_csv(tmp_path, [
        f'{d.id},survival,2025-Q1,,"{{""survival_rate"": 0.5}}",0.8,tft-v1\n',
    ])

    run = prediction_loader.import_predictions(csv_path, db=db)

    assert run.status == "success"
    assert invalidate_calls["n"] == 1
