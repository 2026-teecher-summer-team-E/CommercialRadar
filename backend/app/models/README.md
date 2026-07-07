# models/

데이터베이스 테이블의 구조(모양)가 정의된 곳입니다.

각 파일은 하나의 테이블에 대응하며, SQLAlchemy ORM 클래스로 작성되어 있습니다.
Python 코드에서 테이블을 직접 다루는 대신 이 클래스들을 사용합니다.

## 파일 목록

| 파일 | 테이블 | 설명 |
|------|--------|------|
| `commercial_district.py` | `commercial_district` | 상권 마스터 (지도 폴리곤 포함) |
| `business_category.py` | `business_category` | 상권별 업종 현황 (분기별 생존율·매출 등) |
| `population_heatmap.py` | `population_heatmap` | 시간대/요일별 유동인구 히트맵 |
| `foreign_population.py` | `foreign_population` | 외국인/내국인 유동인구 비율 |
| `ml_predictions.py` | `ml_predictions` | 딥러닝 예측 결과 캐시 (생존율·유동인구·매출) |
| `rent_stats.py` | `rent_stats` | 상권별 임대료 통계 |
| `users.py` | `users` | 사용자 (Clerk 계정 연동) |
| `interest_district.py` | `interest_district` | 사용자가 즐겨찾기한 상권 |
| `reports.py` | `reports` | 사용자가 저장한 분석 리포트 |
| `report_content.py` | `report_content` | 리포트 생성 시점의 수치 스냅샷 |

## 새 모델 추가 시

1. 이 폴더에 `새파일.py` 생성 후 `Base`를 상속하는 클래스 작성
2. `__init__.py`에 import 추가
3. `alembic/env.py`는 `app.models`를 통해 자동으로 감지하므로 별도 수정 불필요
4. `alembic revision --autogenerate -m "설명"` 으로 마이그레이션 파일 생성
