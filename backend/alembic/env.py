import os
from logging.config import fileConfig

from alembic import context
from geoalchemy2 import alembic_helpers
from sqlalchemy import engine_from_config, pool

from app.database import Base
import app.models  # noqa: F401 — 모든 모델 등록 (autogenerate에 필요)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

DATABASE_URL = os.environ.get("DATABASE_URL", config.get_main_option("sqlalchemy.url"))


def include_object(object, name, type_, reflected, compare_to):
    """마이그레이션 대상 필터.

    1) DB에 존재하지만 우리 모델(metadata)에 없는 테이블(PostGIS/tiger 시스템
       테이블 등)은 autogenerate가 DROP하지 않도록 무시한다.
    2) 그 외엔 GeoAlchemy2 헬퍼에 위임 → GeoAlchemy2가 자동 관리하는 공간
       인덱스를 alembic이 중복 생성하지 않게 한다.
    """
    if type_ == "table" and reflected and compare_to is None:
        return False
    return alembic_helpers.include_object(object, name, type_, reflected, compare_to)


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        render_item=alembic_helpers.render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = DATABASE_URL
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            render_item=alembic_helpers.render_item,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
