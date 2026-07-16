# seed/rent_predictions.csv — 임대료 4분기 예측 데이터

상권×상가유형별 임대료(천원/㎡)를 향후 **4분기(2026-Q2 ~ 2027-Q1)** 예측한 결과다.
`ml_predictions` 테이블(`prediction_type='rent'`)에 적재해서 쓴다. 팀원은 이 CSV만
받아서 아래 한 줄로 로컬/운영 DB에 넣으면 된다 — ML 환경(torch/darts) 불필요.

- 행수: **2,360행** = 590 시리즈(상권×상가유형) × 4분기
- 모델: **시리즈별 선형추세(OLS) + 예측구간**, `model_version = linear-trend-v0.1`
- 대상 분기: `2026-Q2, 2026-Q3, 2026-Q4, 2027-Q1` (전부 미래 분기)

---

## 받는 쪽 (팀원): 적재 방법

전제: `docker compose up -d`로 postgres/backend가 떠 있고, 스키마(alembic)가 적용돼 있을 것.
(임대료 예측은 `commercial_district`가 이미 있어야 FK가 맞는다 → 시드 DB 복원이 선행돼야 함.
 `seed/README.md`의 시드 복원을 먼저 하거나, 최신 `.sql.gz`에는 이 데이터가 이미 포함될 수 있다.)

```bash
# 로컬
./scripts/load-predictions.sh seed/rent_predictions.csv

# 운영(EC2)
./scripts/load-predictions.sh seed/rent_predictions.csv --prod
```

이 래퍼가 CSV를 backend 컨테이너로 복사한 뒤 `app.cli load-predictions`를 실행한다.
멱등 upsert라 **여러 번 돌려도 중복 없이 갱신**된다(키: 상권×타입×분기×상가유형).

### 적재 확인

```bash
docker compose exec -T postgres psql -U postgres -d commercialradar -c \
  "SELECT category_name AS floor_type, count(*) FROM ml_predictions WHERE prediction_type='rent' GROUP BY 1;"
# 기대: 소규모 848 / 중대형 916 / 집합 596  (각 상권수 × 4분기)
```

---

## API로 조회

```
GET /api/commercial-districts/{district_id}/rent-forecast?floor_type=중대형&quarters=4
```

- `floor_type`: `소규모 | 중대형 | 집합` (기본 `중대형`)
- 응답: 분기별 `avg_rent_per_sqm`(대표=추세 중앙값)와 `low`/`high`(P10/P90 밴드), `confidence`
- 데이터 없는 상권 → 503, 없는 상권 id → 404, 잘못된 floor_type → 400

예:
```bash
curl "http://localhost:8000/api/commercial-districts/29/rent-forecast?floor_type=소규모&quarters=2"
```

---

## CSV 스키마

`ml_predictions` 로더 포맷과 동일(헤더 필수):

| 컬럼 | 값 |
|------|-----|
| `commercial_district_id` | 상권 id |
| `prediction_type` | `rent` 고정 |
| `target_quarter` | `YYYY-QN` (예측 분기) |
| `category_name` | **상가유형**을 실음 (`소규모`/`중대형`/`집합`) |
| `predicted_value` | JSON: `{"avg_rent_per_sqm", "floor_type", "scenarios": {low, mid, high}}` |
| `confidence` | 0~1 (예측구간 상대폭 기반 간이 신뢰도) |
| `model_version` | `linear-trend-v0.1` |

> 임대료는 상가유형마다 독립 시계열이라, sales/survival의 `category_name`(업종) 자리에
> **floor_type**을 실어 저장한다. 조회는 API의 `floor_type` 파라미터로 한다.

---

## 데이터 정직성(중요)

- 원본 `rent_stats`는 실측 **7분기(2024-Q3 ~ 2026-Q1)뿐**이다. 딥러닝 예측기(TFT/DeepAR)는
  최소 8분기가 필요해 학습이 불가 → 그래서 **선형추세**로 뽑았다.
- 7개 점 외삽이라 급변동은 못 잡는다. `low`/`high` 밴드는 horizon이 멀수록 넓어지도록 해
  불확실성을 표기한다. **추세 방향성 참고용**으로 쓰고, 절대값을 과신하지 말 것.

---

## 만드는 쪽: 재생성 방법

로컬 ML 환경(`.venv`, `ml/requirements.txt`)에서:

```bash
# 1) rent_stats가 적재된 DB를 바라보게 하고 학습(선형추세 적합) → ml/models/rent/params.json
python -m ml.train.rent_train

# 2) 추론 → CSV (registry의 rent-forecast만 뽑으려면 아래처럼)
python -m ml.predict --horizon 4            # 전체 4종(rent 포함) → ml/output/predictions.csv
#   또는 rent만:
python -c "from ml import config; from ml.forecasters.rent import RentForecaster; \
from ml.export import write_predictions_csv; fc=RentForecaster(); fc.load(config.MODELS_DIR/'rent'); \
write_predictions_csv(fc.predict(4), 'seed/rent_predictions.csv')"

# 3) 적재
./scripts/load-predictions.sh seed/rent_predictions.csv
```

관련 코드: `ml/forecasters/rent.py`(모델), `ml/train/rent_train.py`, `ml/data/loaders.py`(`load_rent_frame`),
`backend/app/routers/ml.py`(`rent-forecast` 엔드포인트).
