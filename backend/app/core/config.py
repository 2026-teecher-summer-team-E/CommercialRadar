from pathlib import Path

from pydantic_settings import BaseSettings

# .env는 프로젝트 루트에 둔다 (docker-compose와 같은 위치).
# config.py = backend/app/core/config.py → parents[3] = 레포 루트
ENV_PATH = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/commercialradar"
    CLERK_SECRET_KEY: str = ""
    CLERK_JWKS_URL: str = ""
    REDIS_URL: str = "redis://localhost:6379"
    SEOUL_API_KEY: str = ""
    # 한국부동산원 R-ONE 부동산통계 서비스 인증키
    REB_API_KEY: str = ""
    ADMIN_KEY: str = ""

    # 로컬 실행 시 루트 .env를 읽는다. 도커 환경에선 compose의 env_file이
    # 환경변수로 주입하므로 파일이 없어도 정상 동작한다.
    model_config = {"env_file": str(ENV_PATH), "extra": "ignore"}


settings = Settings()
