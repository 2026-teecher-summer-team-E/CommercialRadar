# core/

앱 전체에서 공통으로 사용하는 설정과 의존성이 있는 곳입니다.

## 파일 목록

### `config.py` — 환경변수 설정

`.env` 파일의 값을 읽어 `settings` 객체로 제공합니다.
코드 어디서든 `from app.core.config import settings`로 불러와 사용합니다.

```python
from app.core.config import settings
print(settings.DATABASE_URL)
print(settings.SGIS_API_KEY)
```

### `deps.py` — FastAPI 의존성 (Depends)

라우터 함수에 주입되는 공통 의존성을 정의합니다.

- `get_db()` — DB 세션을 열고 요청이 끝나면 자동으로 닫습니다
- `get_current_user()` — Clerk JWT를 검증하고 로그인된 사용자를 반환합니다 (미구현 → TODO)

```python
# 사용 예시
@router.get("/my-page")
def my_page(db=Depends(get_db), user=Depends(get_current_user)):
    ...
```

## 환경변수 목록

| 변수명 | 설명 |
|--------|------|
| `DATABASE_URL` | PostgreSQL 연결 URL |
| `CLERK_SECRET_KEY` | Clerk 시크릿 키 |
| `CLERK_JWKS_URL` | Clerk JWT 공개키 URL |
| `REDIS_URL` | Redis 연결 URL |
| `SGIS_API_KEY` | 소상공인 상가정보 API 키 |
| `SEOUL_API_KEY` | 서울 열린데이터광장 API 키 |
| `ADMIN_KEY` | 어드민 엔드포인트 인증 키 |
