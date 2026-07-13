# seed/ — 테스트 DB 시드

외부 공개 API를 다시 긁지 않고도, 적재된 테스트 데이터를 팀원 DB에 복원한다.

시드 형식은 2가지다:
- **`.sql.gz`** — `buzz_stats`(화제성)까지 포함한 최신 덤프. `gunzip | psql`로 직접 복원. **현재 배포 서버가 이 방식으로 적재됨.** (아래 "리뉴얼 복원 명령")
- **`.zip`** — `scripts/seed-db.sh` 자동 복원용(기존). buzz_stats 미포함.

---

## 리뉴얼 복원 명령 (`.sql.gz`, buzz 포함)

`gunzip -c ... | psql` 로 직접 복원한다. 로컬/서버 차이는 **`-f docker-compose.prod.yml`** 하나뿐.

> ⚠️ `gunzip`은 **현재 폴더**에서 파일을 찾는다. 파일이 `seed/`에 있으면 `seed/commercialradar_seed.sql.gz` 로 경로를 붙인다.
> ⚠️ 이미 데이터가 있으면 복원 시 `duplicate key` 에러가 난다 → **반드시 1) TRUNCATE 먼저** 실행.

### 로컬 (기본 `docker-compose.yml`)

```bash
# 1) 기존 공개 테이블 비우기 (데이터 있을 때)
docker compose exec -T postgres psql -U postgres -d commercialradar -v ON_ERROR_STOP=1 -c "TRUNCATE commercial_district, business_category, population_heatmap, population_timeseries, foreign_population, rent_stats, ml_predictions, buzz_stats RESTART IDENTITY CASCADE;"

# 2) 복원
gunzip -c commercialradar_seed.sql.gz | docker compose exec -T postgres psql -U postgres -d commercialradar -v ON_ERROR_STOP=1 -q

# 3) 확인
docker compose exec -T postgres psql -U postgres -d commercialradar -c "SELECT 'districts', count(*) FROM commercial_district UNION ALL SELECT 'predictions', count(*) FROM ml_predictions UNION ALL SELECT 'buzz', count(*) FROM buzz_stats;"
```

### 서버 (프로덕션, `docker-compose.prod.yml`)

로컬과 동일하되 모든 명령에 `-f docker-compose.prod.yml`만 붙인다.

```bash
# 1) 비우기
docker compose -f docker-compose.prod.yml exec -T postgres psql -U postgres -d commercialradar -v ON_ERROR_STOP=1 -c "TRUNCATE commercial_district, business_category, population_heatmap, population_timeseries, foreign_population, rent_stats, ml_predictions, buzz_stats RESTART IDENTITY CASCADE;"

# 2) 복원
gunzip -c commercialradar_seed.sql.gz | docker compose -f docker-compose.prod.yml exec -T postgres psql -U postgres -d commercialradar -v ON_ERROR_STOP=1 -q

# 3) 확인 → districts 1650 / predictions 19524 / buzz 60
docker compose -f docker-compose.prod.yml exec -T postgres psql -U postgres -d commercialradar -c "SELECT 'districts', count(*) FROM commercial_district UNION ALL SELECT 'predictions', count(*) FROM ml_predictions UNION ALL SELECT 'buzz', count(*) FROM buzz_stats;"
```

### `.sql.gz` 덤프 생성 (적재한 사람)

```bash
docker compose exec -T postgres pg_dump -U postgres -d commercialradar --data-only --no-owner \
  -t commercial_district -t business_category -t population_heatmap \
  -t population_timeseries -t foreign_population -t rent_stats \
  -t ml_predictions -t buzz_stats | gzip > seed/commercialradar_seed.sql.gz
```

---

## 팀원 (데이터 받는 쪽)

```bash
./scripts/seed-db.sh
```

- postgres 기동 → alembic 스키마 → 공개 테이블 초기화 → 시드 복원까지 자동.
- 선행: `seed/commercialradar_seed.zip` 파일이 있어야 함 (아래 배포 참고).

## 데이터 적재한 사람 (시드 만드는 쪽)

```bash
# 1) 외부 API 전부 적재 (5개 소스, 시간 소요)
docker compose run --rm backend python -m app.cli ingest all
# 2) geometry 적재 (상권영역 셰이프파일 → commercial_district.geometry, 재투영 5181→4326)
./scripts/load-geometry.sh
# 3) (선택) 예측 결과도 포함하려면
docker compose run --rm backend python -m app.cli load-predictions ml/output/predictions.csv
# 4) 덤프 생성
./scripts/dump-seed.sh          # → seed/commercialradar_seed.zip
```

> geometry는 인제스천이 안 채우므로(수동 적재 정책) `load-geometry.sh`를 1회 실행한다.
> 이렇게 채운 뒤 시드를 뜨면 팀원은 geometry 포함본을 받으므로 셰이프파일이 따로 필요 없다.

## 시드 파일 배포

`seed/commercialradar_seed.zip`는 기본적으로 git 에서 제외된다(재생성 가능한 바이너리).
둘 중 하나로 팀원에게 전달:

- **팀 드라이브 공유** (권장, 파일 클수록): 팀원이 받아 `seed/` 에 두고 `seed-db.sh` 실행.
- **git 커밋** (작을 때 간편): `git add -f seed/commercialradar_seed.zip` 로 강제 추가.
  → 이 경우 팀원은 `git pull` 후 바로 `seed-db.sh` (진짜 한 줄).

## 포함 테이블

공개(적재) 데이터만 포함. 사용자별 런타임 데이터(users/reports/interest)는 제외.

`commercial_district`, `business_category`, `population_heatmap`,
`population_timeseries`, `foreign_population`, `rent_stats`, `ml_predictions`

## 주의

- `seed-db.sh`는 위 공개 테이블을 **TRUNCATE 후 복원**한다 (기존 로컬 공개데이터는 대체됨).
- 사용자 테이블(users/reports/interest)은 건드리지 않는다.
