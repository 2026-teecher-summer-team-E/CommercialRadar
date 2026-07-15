from pathlib import Path

from pydantic_settings import BaseSettings

# .env는 프로젝트 루트에 둔다 (docker-compose와 같은 위치).
# config.py = backend/app/core/config.py → parents[3] = 레포 루트
ENV_PATH = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/commercialradar"
    CLERK_SECRET_KEY: str = ""
    CLERK_JWKS_URL: str = ""
    # Clerk(svix) 웹훅 서명 시크릿 (whsec_...)
    CLERK_WEBHOOK_SECRET: str = ""
    # 실행 환경. dev면 웹훅 서명 검증을 건너뛴다(로컬 Swagger 테스트용).
    ENV: str = "prod"
    REDIS_URL: str = "redis://localhost:6379"
    SEOUL_API_KEY: str = ""
    # 한국부동산원 R-ONE 부동산통계 서비스 인증키
    REB_API_KEY: str = ""
    # 네이버 데이터랩 검색어 트렌드 API 인증키
    NAVER_CLIENT_ID: str = ""
    NAVER_CLIENT_SECRET: str = ""
    ADMIN_KEY: str = ""

    # CORS 허용 origin(콤마 구분). 프로덕션은 프론트 도메인을 명시한다.
    # 기본값은 로컬 개발용(Vite 5173 등). '*'는 main.py에서 credential 호환 정규식으로 처리한다.
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"

    # 로컬 실행 시 루트 .env를 읽는다. 도커 환경에선 compose의 env_file이
    # 환경변수로 주입하므로 파일이 없어도 정상 동작한다.
    model_config = {"env_file": str(ENV_PATH), "extra": "ignore"}

    @property
    def cors_origins_list(self) -> list[str]:
        """CORS_ORIGINS(콤마 구분 문자열)을 origin 리스트로 파싱한다."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
