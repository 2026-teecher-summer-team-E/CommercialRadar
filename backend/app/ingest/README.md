# 데이터 인제스천 (외부 API → DB)

외부 공공 API를 긁어와 우리 스키마로 변환 후 저장하는 ETL 파이프라인.

## 소스 1: 서울 상권분석서비스 (Seoul Open API)

- **API**: 서울 열린데이터광장 `http://openapi.seoul.go.kr:8088/{KEY}/json/{SERVICE}/{START}/{END}/`
- **인증**: `settings.SEOUL_API_KEY` (환경변수 `SEOUL_API_KEY`)
- **페이지네이션**: 1000건/호출, START/END(1-based)로 페이지네이션
- **분기 트레일링 필터**: URL 뒤에 `/{분기코드}/` 추가로 해당 분기만 조회 가능 (실측 확인)

### 4개 Job 요약 (Seoul Open API)

| Job 이름 | 서비스 | 타겟 테이블 | 건수/일 | 수집 방식 |
|---|---|---|---|---|
| `seoul_commercial` | `TbgisTrdarRelm` | `commercial_district` | ~1,650 | 전체 (분기 없음) |
| `seoul_population` | `VwsmTrdarFlpopQq` | `population_heatmap` | ~1,650 | 최신 분기 필터 |
| `seoul_business`   | `VwsmTrdarSelngQq` + `VwsmTrdarStorQq` | `business_category` | ~21k + ~76k | 최신 분기 필터 |
| `seoul_foreign`    | `SPOP_FORN_LONG_RESD_DONG` + `SPOP_FORN_TEMP_RESD_DONG` + `SPOP_LOCAL_RESD_DONG` | `foreign_population` | ~10,176×3/일 | 기준일(YYYYMMDD) 필터, 최근 14일 |

## 소스 2: 한국부동산원 R-ONE 상가임대료

- **API**: `https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do`
- **인증**: `settings.REB_API_KEY` (환경변수 `REB_API_KEY`)
- **페이지네이션**: `pIndex`(1-based) + `pSize=1000`, 응답에 `list_total_count` 포함
- **분기 단위 데이터**: 전 분기 데이터가 한 번에 반환됨. 최신 분기는 마지막 페이지의 `WRTTIME_IDTFR_ID` 최댓값으로 탐색.
- **수집 방식**: 전체 행 수신 후 transformer에서 최신 분기 + 서울 말단 상권 필터링.

### 1개 Job 요약 (R-ONE)

| Job 이름 | STATBL_ID × 3 | 타겟 테이블 | 수집 방식 |
|---|---|---|---|
| `seoul_rent` | `T248223134698125`(소규모) / `T244363134858603`(중대형) / `T244913134948657`(집합) | `rent_stats` | 최신 분기 + 서울 말단 상권 필터 |

### 서울 말단 상권 필터

`CLS_FULLNM`이 `"서울"` 로 시작하고 `">"` 구분 세그먼트가 3개 이상인 행만 처리한다.
예: `"서울>도심>명동"` (O), `"서울>도심"` 권역 집계 (✕), `"서울"` 시도 집계 (✕).

### 부동산원 상권명 → 서울 상권 이름 매칭

부동산원 `CLS_NM` ↔ `commercial_district.district_name` 이름 매칭 (코드가 달라 이름 기반):
1. **MANUAL_MAP** (`rent_transformer.py`): `{부동산원상권명: [external_code, ...]}` 오버라이드 우선 적용.
   빈 리스트 = 의도적 스킵. 코드 직접 기입으로 추후 정확도 향상 가능.
2. 정규화 완전 일치 (공백 제거 후 동일).
3. 부동산원 이름 ⊆ 서울 이름 (예: `"광화문"` ⊆ `"광화문역"`).
4. 서울 이름 ⊆ 부동산원 이름, 최소 3자.
- 1개 부동산원 상권 → N개 서울 상권 팬아웃 가능 (각각 rent_stats row 생성).
- 미매칭 부동산원 상권은 스킵 (해당 서울 상권은 `avg_rent_per_sqm = NULL` — 의도된 동작).

실측 자동 매칭 결과 (202601 기준, 서울 59개 상권): **50/59 매칭**.
미매칭 9개: 강남대로·도산대로·테헤란로(도로명), 동교/연남·신촌/이대·홍대/합정·독산/시흥·잠실/송파(복합명), 숙명여대.

### 상권코드/이름 연결

`seoul_commercial/population/business`는 **상권코드 `TRDAR_CD`** 로 연결된다:
- `commercial_district.external_code` = TRDAR_CD
- `population_heatmap.commercial_district_id` → `commercial_district.id`
- `business_category.commercial_district_id` → `commercial_district.id`
- `load_trdar_map(db)` (loaders/resolver.py) 로 {external_code→id} 매핑을 한 번에 로드

`seoul_foreign`은 **행정동코드 `ADSTRD_CODE_SE`** 로 근사 연결된다:
- 생활인구 서비스의 `ADSTRD_CODE_SE`(8자리) ↔ `commercial_district.adstrd_code`(8자리)
- 1 행정동 → N 상권 (1:N 팬아웃)
- `load_adstrd_map(db)` (loaders/resolver.py) 로 {adstrd_code→[id, ...]} 매핑을 한 번에 로드

`seoul_rent`는 **상권명 `district_name`** 이름 매칭으로 연결된다:
- `commercial_district.district_name` ↔ 부동산원 `CLS_NM`
- `load_district_name_map(db)` (loaders/resolver.py) 로 {district_name→[id, ...]} 매핑을 한 번에 로드
- 행정동 단위 근사 매핑이므로 매핑 없는 행정동은 스킵 (로그에 기록)

### geometry 정책

`commercial_district.geometry`(MULTIPOLYGON) 는 **수동 적재**한다.
인제스천 파이프라인은 geometry를 건드리지 않는다.

## 구조 (레이어 분리)

```
app/ingest/
├─ clients/
│   ├─ seoul_client.py      # E: 서울 API 공통 클라이언트 (페이지네이션 + 재시도 + check_date)
│   └─ reb_client.py        # E: R-ONE API 클라이언트 (페이지네이션 + 재시도 + 최신분기탐색)
├─ transformers/
│   ├─ commercial_transformer.py   # T: 상권영역 → commercial_district dict
│   ├─ population_transformer.py   # T: 유동인구 → UNPIVOT 13행/상권
│   ├─ business_transformer.py     # T: 추정매출+점포 병합·변환
│   ├─ foreign_transformer.py      # T: 3개 생활인구 서비스 정렬·집계·팬아웃
│   └─ rent_transformer.py         # T: 서울 필터 + 이름매칭 + 임대료 row 생성
├─ loaders/
│   ├─ commercial_loader.py        # L: commercial_district upsert
│   ├─ population_loader.py        # L: population_heatmap upsert
│   ├─ business_loader.py          # L: business_category upsert
│   ├─ foreign_loader.py           # L: foreign_population upsert
│   ├─ rent_loader.py              # L: rent_stats upsert (uq_rent_cd_yq_floor)
│   └─ resolver.py                 # 공유: TRDAR_CD·adstrd_code·district_name 매핑
└─ jobs.py                         # E→T→L 오케스트레이션 + ingestion_run 이력 기록
```

크론(`app/cli.py`)과 관리자 엔드포인트(`routers/admin.py POST /admin/data`)가
`jobs.run_targets()`를 **공유 호출** → 자동/수동 실행이 같은 코드를 탄다.

## 설계 원칙

- **멱등성**: 각 테이블의 UNIQUE 제약 기준으로 upsert → 재실행에도 중복 없음.
  - `commercial_district`: `external_code` (단일 컬럼 unique index)
  - `population_heatmap`: `(commercial_district_id, dimension, slot)` → `uq_pop_heatmap_cd_dim_slot`
  - `business_category`: `(commercial_district_id, category_name, year_quarter)` → `uq_biz_cat_cd_name_yq`
  - `rent_stats`: `(commercial_district_id, year_quarter, floor_type)` → `uq_rent_cd_yq_floor`
- **검증 우선**: transformer에서 Pydantic 검증 → 깨진 레코드는 로드 전 스킵.
- **관측**: 매 실행을 `ingestion_run` 테이블에 기록(fetched/upserted/failed/error).
- **격리**: 크론은 웹 프로세스와 별도로 실행 → 무거운 인제스천이 API를 안 막음.

## 실행

```bash
# 컨테이너 안에서 직접
python -m app.cli ingest seoul_commercial   # 상권영역만
python -m app.cli ingest seoul_population   # 유동인구만 (commercial 선행 필요)
python -m app.cli ingest seoul_business     # 추정매출+점포만 (commercial 선행 필요)
python -m app.cli ingest seoul_foreign      # 외국인생활인구만 (commercial 선행 필요)
python -m app.cli ingest seoul_rent         # 상가임대료만 (commercial 선행 필요, R-ONE)
python -m app.cli ingest all               # 5개 모두 순서대로

# docker-compose 환경(호스트에서)
docker compose exec -T backend python -m app.cli ingest all
```

CLI는 실패 시 exit code 1을 반환 → 크론이 실패를 감지/알림에 쓸 수 있다.

## 크론 설정 (단일 AWS 인스턴스)

```cron
# 매월 1일 새벽 4시 서울 상권 데이터 전체 갱신 (분기 단위 갱신 → 월 1회면 충분)
0 4 1 * * cd /home/ubuntu/CommercialRadar && \
  /usr/bin/docker compose exec -T backend python -m app.cli ingest all \
  >> /var/log/commercialradar/ingest.log 2>&1
```

`seoul_foreign`은 일별 데이터이므로 더 짧은 주기(주 1회 이상)로 실행 가능하나,
14일 롤링 윈도우 평균을 사용하므로 월 1회 "all" 실행으로도 충분하다.

설치: `crontab -e` 로 위 줄 추가. 로그 디렉터리는 미리 `mkdir -p /var/log/commercialradar`.

## DB 마이그레이션 (새 컬럼·제약 반영 필요)

누적 변경 항목:

| 테이블 | 변경 내용 |
|---|---|
| `commercial_district` | `signgu_code VARCHAR(10)`, `adstrd_code VARCHAR(10)` 컬럼 추가 (각 인덱스 포함) |
| `population_heatmap` | UNIQUE 제약 `uq_pop_heatmap_cd_dim_slot` 추가 |
| `business_category` | UNIQUE 제약 `uq_biz_cat_cd_name_yq` 추가 |
| `foreign_population` | UNIQUE 제약 `uq_foreign_pop_cd_dim_slot` 추가 (`commercial_district_id`, `dimension`, `slot`) |
| `rent_stats` | UNIQUE 제약 `uq_rent_cd_yq_floor` 추가 (`commercial_district_id`, `year_quarter`, `floor_type`) |

```bash
docker compose exec backend alembic revision --autogenerate -m "seoul etl: add signgu/adstrd codes, unique constraints"
docker compose exec backend alembic upgrade head
```

> **주의:** `seoul_foreign` job은 `commercial_district.adstrd_code` 컬럼을 참조한다.
> `commercial_district` 마이그레이션이 먼저 적용돼 있어야 한다.

## 소스 추가하는 법

1. `clients/`에 API 클라이언트 작성 (또는 `SeoulClient` 재사용)
2. `transformers/`에 매핑 함수(+ Pydantic 스키마) 작성
3. `loaders/`에 upsert 함수 작성
4. `jobs.py`의 `JOBS` 딕셔너리에 `"소스명": 함수` 등록
5. 크론에 `python -m app.cli ingest 소스명` 한 줄 추가
