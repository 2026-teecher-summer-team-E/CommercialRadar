"""loader 멱등성 검증 (실 Postgres `db` 픽스처, 종료 시 rollback).

모든 loader의 계약:
  - 같은 rows를 재실행해도 중복 row가 생기지 않는다 (ON CONFLICT DO UPDATE).
  - 같은 UNIQUE 키에 다른 값을 재실행하면 값이 갱신된다.
rent는 추가로 _dedupe가 같은 키 중복(다중 이름매칭)을 평균으로 합쳐
CardinalityViolation을 방지한다.
"""

from app.ingest.loaders import (
    business_loader,
    commercial_loader,
    foreign_loader,
    population_loader,
    population_timeseries_loader,
    rent_loader,
)
from app.models.business_category import BusinessCategory
from app.models.commercial_district import CommercialDistrict
from app.models.foreign_population import ForeignPopulation
from app.models.population_heatmap import PopulationHeatmap
from app.models.population_timeseries import PopulationTimeseries
from app.models.rent_stats import RentStat


def _make_district(db, code: str) -> CommercialDistrict:
    d = CommercialDistrict(external_code=code, district_name="멱등테스트")
    db.add(d)
    db.flush()
    return d


# ── commercial (external_code UNIQUE) ─────────────────────────────────────────

def test_commercial_loader_idempotent_and_updates(db):
    row = {"external_code": "IDEMP-C1", "district_name": "최초명"}
    q = db.query(CommercialDistrict).filter_by(external_code="IDEMP-C1")

    commercial_loader.upsert_all(db, [row])
    commercial_loader.upsert_all(db, [row])  # 재실행 → 중복 없음
    assert q.count() == 1

    commercial_loader.upsert_all(db, [{**row, "district_name": "갱신명"}])
    assert q.count() == 1
    assert q.one().district_name == "갱신명"


# ── population_heatmap ((cd_id, dimension, slot) UNIQUE) ───────────────────────

def test_population_heatmap_idempotent_and_updates(db):
    d = _make_district(db, "IDEMP-POP")
    row = {"commercial_district_id": d.id, "dimension": "time", "slot": "00~06", "avg_population": 10.0}
    q = db.query(PopulationHeatmap).filter_by(commercial_district_id=d.id)

    population_loader.upsert_all(db, [row])
    population_loader.upsert_all(db, [row])
    assert q.count() == 1

    population_loader.upsert_all(db, [{**row, "avg_population": 99.0}])
    assert q.count() == 1
    assert q.one().avg_population == 99.0


# ── population_timeseries ((cd_id, year_quarter, dim, slot) UNIQUE) ────────────

def test_population_timeseries_idempotent_and_updates(db):
    d = _make_district(db, "IDEMP-POPTS")
    row = {
        "commercial_district_id": d.id, "year_quarter": "2024-Q1",
        "dimension": "total", "slot": "total", "avg_population": 1000.0,
    }
    q = db.query(PopulationTimeseries).filter_by(commercial_district_id=d.id)

    population_timeseries_loader.upsert_all(db, [row])
    population_timeseries_loader.upsert_all(db, [row])
    assert q.count() == 1

    population_timeseries_loader.upsert_all(db, [{**row, "avg_population": 1234.0}])
    assert q.count() == 1
    assert q.one().avg_population == 1234.0


# ── business ((cd_id, category_name, year_quarter) UNIQUE) ─────────────────────

def test_business_loader_idempotent_and_updates(db):
    d = _make_district(db, "IDEMP-BIZ")
    row = {
        "commercial_district_id": d.id, "category_name": "한식음식점", "year_quarter": "2025-Q4",
        "peak_start": None, "peak_end": None, "total_sales": 100, "tx_count": 10,
        "total_business": 5, "open_rate": 1.0, "closure_rate": 3.2, "survival_rate": 96.8,
    }
    q = db.query(BusinessCategory).filter_by(commercial_district_id=d.id)

    business_loader.upsert_all(db, [row])
    business_loader.upsert_all(db, [row])
    assert q.count() == 1

    business_loader.upsert_all(db, [{**row, "total_sales": 999}])
    assert q.count() == 1
    assert q.one().total_sales == 999


# ── foreign ((cd_id, dimension, slot) UNIQUE) ─────────────────────────────────

def test_foreign_loader_idempotent_and_updates(db):
    d = _make_district(db, "IDEMP-FGN")
    row = {
        "commercial_district_id": d.id, "dimension": "time", "slot": "11~14",
        "foreigner_count": 15.0, "total_count": 115.0,
    }
    q = db.query(ForeignPopulation).filter_by(commercial_district_id=d.id)

    foreign_loader.upsert_all(db, [row])
    foreign_loader.upsert_all(db, [row])
    assert q.count() == 1

    foreign_loader.upsert_all(db, [{**row, "foreigner_count": 42.0}])
    assert q.count() == 1
    assert q.one().foreigner_count == 42.0


# ── rent ((cd_id, year_quarter, floor_type) UNIQUE) + _dedupe ─────────────────

def test_rent_loader_idempotent_and_updates(db):
    d = _make_district(db, "IDEMP-RENT")
    row = {
        "commercial_district_id": d.id, "avg_rent_per_sqm": 50.0,
        "year_quarter": "2026-Q1", "floor_type": "소규모",
    }
    q = db.query(RentStat).filter_by(commercial_district_id=d.id)

    rent_loader.upsert_all(db, [row])
    rent_loader.upsert_all(db, [row])
    assert q.count() == 1

    rent_loader.upsert_all(db, [{**row, "avg_rent_per_sqm": 77.0}])
    assert q.count() == 1
    assert float(q.one().avg_rent_per_sqm) == 77.0


def test_rent_dedupe_averages_duplicate_keys(db):
    # 같은 (상권, 분기, 층유형) 키가 다중 이름매칭으로 두 번 나와도 CardinalityViolation
    # 없이 임대료 평균으로 합쳐진다.
    d = _make_district(db, "IDEMP-RENT-DUP")
    rows = [
        {"commercial_district_id": d.id, "avg_rent_per_sqm": 40.0, "year_quarter": "2026-Q1", "floor_type": "소규모"},
        {"commercial_district_id": d.id, "avg_rent_per_sqm": 60.0, "year_quarter": "2026-Q1", "floor_type": "소규모"},
    ]

    rent_loader.upsert_all(db, rows)

    q = db.query(RentStat).filter_by(commercial_district_id=d.id)
    assert q.count() == 1
    assert float(q.one().avg_rent_per_sqm) == 50.0  # (40 + 60) / 2
