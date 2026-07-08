"""예측 결과 → ml_predictions 적재용 CSV 내보내기.

ml/predict.py가 추론 결과를 이 헬퍼로 CSV로 저장하면,
backend의 `python -m app.cli load-predictions <csv>`가 DB에 적재한다.
CSV가 로컬(Mac) ↔ AWS 사이의 핸드오프 매개체다 (Mac이 RDS에 직접 쓸 필요 없음).

CSV 스키마 (backend/app/ingest/prediction_loader.py와 일치해야 함):
    commercial_district_id, prediction_type, target_quarter,
    category_name, predicted_value, confidence, model_version

- prediction_type: 'survival' | 'population' | 'sales'
- target_quarter: 'YYYY-QN'
- category_name: 업종명. 없으면 '__ALL__'(전체 합산). 업종별 예측 시 업종명 지정.
- predicted_value: 예측타입별 구조가 다른 dict → JSON 문자열로 직렬화
    survival:   {"survival_rate": 0.71}
    population: {"total": 91000, "breakdown": {"gender": {...}, "age": {...}}}
    sales:      {"total_sales": 1650000000, "tx_count": 13200}
- confidence, model_version: None이면 빈 칸
"""

import csv
import json
from pathlib import Path

CSV_COLUMNS = [
    "commercial_district_id",
    "prediction_type",
    "target_quarter",
    "category_name",
    "predicted_value",
    "confidence",
    "model_version",
]


def write_predictions_csv(rows: list[dict], path: str | Path) -> int:
    """예측 결과 dict 리스트를 CSV로 저장. 저장된 행 수를 반환.

    각 dict 필수 키: commercial_district_id, prediction_type, target_quarter,
    predicted_value(dict). 선택 키: confidence(float), model_version(str).

    Args:
        rows: 예측 결과 행 리스트.
        path: 출력 CSV 경로 (상위 디렉터리는 자동 생성).

    Returns:
        기록한 행 수.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for r in rows:
            writer.writerow({
                "commercial_district_id": r["commercial_district_id"],
                "prediction_type": r["prediction_type"],
                "target_quarter": r["target_quarter"],
                "category_name": r.get("category_name", "__ALL__"),
                # dict → JSON 문자열 (csv 모듈이 따옴표 이스케이프 처리)
                "predicted_value": json.dumps(r["predicted_value"], ensure_ascii=False),
                "confidence": r.get("confidence", ""),
                "model_version": r.get("model_version", ""),
            })

    return len(rows)
