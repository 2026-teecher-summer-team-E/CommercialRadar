# routers/

API 엔드포인트(URL 경로)가 정의된 곳입니다.

클라이언트가 어떤 URL로 요청하면 어떤 함수를 실행할지 연결하는 역할입니다.
비즈니스 로직은 담지 않고 `services/`에 위임합니다.

## 파일 목록

| 파일 | 경로 접두사 | 엔드포인트 |
|------|-------------|------------|
| `commercial.py` | `/api` | `GET /api/commercial-districts`, `GET /api/commercial-districts/{district_code}` |
| `population.py` | `/api` | `GET /api/population`, `GET /api/population-by-code`, `GET /api/street-population/{district_code}` |
| `businesses.py` | `/api` | `GET /api/dongs`, `GET /api/businesses`, `GET /api/age`, `GET /api/comparison` |
| `sales.py` | `/api` | `GET /api/sales/{district_code}` |
| `forecast.py` | `/api` | `GET /api/survival-forecast/{district_code}`, `GET /api/population-forecast/{district_code}`, `GET /api/sales-forecast/{district_code}` |
| `analysis.py` | `/api` | `GET /api/commercial-districts/{district_id}/time-series` |
| `admin.py` | `/admin` | `POST /admin/data` — `X-Admin-Key` 헤더 인증 필요 |

## 인증이 필요한 엔드포인트

`get_current_user` Depends를 함수 파라미터에 추가하면 Clerk JWT 검증이 자동 적용됩니다.

```python
from app.core.deps import get_current_user

@router.get("/my-endpoint")
def my_endpoint(current_user=Depends(get_current_user)):
    ...
```
