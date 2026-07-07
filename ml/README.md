# ml/ — 딥러닝 예측 파이프라인

상권의 **생존율·유동인구·매출**을 분기 단위로 예측한다.
실시간 추론이 아니라 **오프라인 배치**: 로컬(Mac)에서 학습·추론 → CSV → DB 적재.

## 아키텍처

```
[로컬 Mac]                                      [AWS/backend]
DB 학습데이터 ──▶ train (ml/train/*)
                     │ 모델 저장 ml/models/
                     ▼
                 predict (ml/predict.py)
                     │ → ml/output/predictions.csv
                     ▼ (커밋/업로드)
                                    python -m app.cli load-predictions predictions.csv
                                                 │ → RDS.ml_predictions
                                                 ▼
                                            FastAPI 조회 → 프론트
```

API는 `ml_predictions` 캐시만 읽으므로 AWS엔 torch/darts 불필요.

## 구조

```
ml/
├── config.py              # 설정 (DATABASE_URL, horizon, device)
├── requirements.txt       # darts, lightgbm, pandas ... (backend와 분리)
├── data/
│   └── loaders.py         # DB → DataFrame → Darts TimeSeries (글로벌 멀티시리즈)
├── common/
│   ├── base.py            # Forecaster 인터페이스 (fit/predict/save/load)
│   ├── metrics.py         # MAE/RMSE
│   └── registry.py        # 모델명 → Forecaster (admin API targets 연결)
├── forecasters/
│   ├── survival.py        # 생존율: TFT + LightGBM 베이스라인
│   ├── population.py      # 유동인구: DeepAR
│   └── sales.py           # 매출: TFT
├── train/
│   ├── survival_train.py  # entrypoint
│   ├── population_train.py
│   └── sales_train.py
├── predict.py             # 3종 추론 → predictions.csv
├── models/{survival,population,sales}/   # 학습 바이너리 (gitignored)
└── output/                # 예측 CSV (gitignored, 샘플만 유지)
```

## 모델 선택

| 예측 | 소스 테이블 | 본 모델 | 베이스라인 |
|------|-------------|---------|-----------|
| survival | business_category | TFT | LightGBM |
| population | population_timeseries | DeepAR | N-BEATS/Prophet |
| sales | business_category | TFT | LightGBM |

분기별 시계열(시리즈당 포인트 적음, 시리즈 多)이라 **글로벌 모델**로 학습한다.
확률적 출력(quantile/분포)이 API의 `confidence`가 된다.

## 실행

```bash
# 설치 (로컬 1회)
python -m venv .venv && source .venv/bin/activate
pip install -r ml/requirements.txt

# 학습 (분기 데이터 적재 후)
python -m ml.train.survival_train
python -m ml.train.population_train
python -m ml.train.sales_train

# 추론 → CSV
python -m ml.predict            # ml/output/predictions.csv 생성

# 적재 (backend 쪽)
docker compose run --rm backend python -m app.cli load-predictions ml/output/predictions.csv
```

> Mac M2는 `ML_DEVICE=mps`로 GPU 가속 가능(로컬 실행 시). Docker 안에서는 CPU만.

## 상태

뼈대 단계. 데이터 로딩·인터페이스·CSV 핸드오프는 구현됨.
각 forecaster의 모델 하이퍼파라미터·공변량 구성은 데이터 적재 후 튜닝 필요 (코드 내 TODO).
