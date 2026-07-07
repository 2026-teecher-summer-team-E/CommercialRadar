# schemas/

API 요청·응답 데이터의 형태(타입)가 정의된 곳입니다.

모델(`models/`)이 "DB에 저장되는 모양"이라면, 스키마는 "API를 통해 주고받는 데이터의 모양"입니다.
Pydantic으로 작성되어 자동 유효성 검사와 Swagger 문서 생성에 사용됩니다.

## 파일 목록

| 파일 | 관련 API | 설명 |
|------|----------|------|
| `commercial.py` | `/api/commercial-districts` | 상권 목록·상세 응답 스키마 |
| `population.py` | `/api/population`, `/api/street-population` | 유동인구 응답 스키마 |
| `sales.py` | `/api/sales` | 매출 응답 스키마 |
| `forecast.py` | `/api/*-forecast` | DL 예측 결과 응답 스키마 |
| `interest_district.py` | `/api/interest-districts` | 관심지역 등록 요청·응답 스키마 |
| `admin.py` | `/admin/data` | 어드민 요청·응답 스키마 |

## 모델 vs 스키마 차이

```
DB 테이블 (models/)  →  ORM 조회  →  스키마 변환 (schemas/)  →  JSON 응답
```

- 모델: DB 컬럼 그대로 (geometry, JSONB 등 DB 전용 타입 포함)
- 스키마: 클라이언트에 보낼 형태 (geometry는 좌표 배열로 변환, 불필요한 필드 제거 등)
