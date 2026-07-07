# services/

실제 비즈니스 로직이 구현되는 곳입니다.

라우터(`routers/`)는 요청을 받아 서비스에 넘기고, 서비스는 DB 조회·계산·외부 API 호출 등 실질적인 처리를 담당합니다.

## 파일 목록

| 파일 | 역할 |
|------|------|
| `commercial_service.py` | 상권 목록 조회, 상세 정보 조합 |
| `population_service.py` | 유동인구 데이터 조회 및 가공 |
| `sales_service.py` | 매출 데이터 조회 (업종별·성별·연령대) |
| `forecast_service.py` | `ml_predictions` 테이블에서 예측 결과 조회 및 타입별 파싱 |
| `pipeline_service.py` | 공공데이터 API(서울 열린데이터광장 · 한국부동산원 R-ONE) 수집 → DB upsert (구현은 `app/ingest`) |

## 패턴

```python
# routers/commercial.py
@router.get("/commercial-districts")
def list_districts(db: Session = Depends(get_db)):
    return CommercialService.list(db)   # 로직은 서비스에

# services/commercial_service.py
class CommercialService:
    @staticmethod
    def list(db: Session):
        return db.query(CommercialDistrict).filter_by(is_deleted=False).all()
```
