"""ML 파이프라인 공통 설정.

환경변수로 오버라이드 가능. 로컬(Mac)·컨테이너 어디서든 동작하도록
DATABASE_URL과 디바이스를 env에서 읽는다.
"""

import os
from pathlib import Path

ML_ROOT = Path(__file__).resolve().parent
MODELS_DIR = ML_ROOT / "models"          # 학습된 모델 바이너리 저장 (gitignored)
OUTPUT_DIR = ML_ROOT / "output"          # 예측 결과 CSV 출력

# 학습 데이터를 읽고, (원한다면) 결과를 쓸 DB. 보통 RDS 또는 로컬 postgres.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/commercialradar",
)

# 예측 설정
DEFAULT_HORIZON = int(os.getenv("ML_HORIZON", "4"))      # 예측 분기 수 (API 기본값과 일치)
MIN_TRAIN_QUARTERS = int(os.getenv("ML_MIN_QUARTERS", "8"))  # 최소 학습 분기 (미만이면 경고)

# 학습 디바이스: Mac M2 로컬 실행은 "mps", Docker/서버 CPU는 "cpu".
# (Docker 안에서는 MPS 사용 불가 → cpu)
DEVICE = os.getenv("ML_DEVICE", "cpu")

# 예측 결과 CSV 기본 경로 (backend 로더가 읽는 파일)
PREDICTIONS_CSV = OUTPUT_DIR / "predictions.csv"

# 각 예측 타입 → 모델 저장 하위 디렉터리 / ml_predictions.prediction_type
PREDICTION_TYPES = ("survival", "population", "sales")
