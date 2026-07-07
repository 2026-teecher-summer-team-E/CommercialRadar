from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/commercialradar"
    CLERK_SECRET_KEY: str = ""
    CLERK_JWKS_URL: str = ""
    REDIS_URL: str = "redis://localhost:6379"
    SGIS_API_KEY: str = ""
    SEOUL_API_KEY: str = ""
    ADMIN_KEY: str = ""

    model_config = {"env_file": ".env"}


settings = Settings()
