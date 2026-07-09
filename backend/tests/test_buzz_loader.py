from app.ingest.loaders.buzz_loader import upsert_all
from app.models.buzz_stats import BuzzStats


def _row(cid, buzz, period="2025-12"):
    return {"commercial_district_id": cid, "source": "naver_datalab",
            "period": period, "buzz_index": buzz}


def test_upsert_inserts_then_updates(db, seed_district):
    cid = seed_district.id
    assert upsert_all(db, [_row(cid, 50.0)]) == 1

    stored = db.query(BuzzStats).filter_by(commercial_district_id=cid).one()
    assert stored.buzz_index == 50.0

    # 같은 키로 다시 → update
    upsert_all(db, [_row(cid, 88.0)])
    db.refresh(stored)
    assert stored.buzz_index == 88.0
    assert db.query(BuzzStats).filter_by(commercial_district_id=cid).count() == 1


def test_upsert_empty_returns_zero(db):
    assert upsert_all(db, []) == 0
