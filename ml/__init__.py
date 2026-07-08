"""딥러닝 예측 파이프라인 (오프라인 배치).

로컬에서 학습·추론 후 결과를 CSV로 내보내고, backend의
`python -m app.cli load-predictions <csv>`로 ml_predictions에 적재한다.
"""
