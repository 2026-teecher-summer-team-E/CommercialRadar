"""OpenTelemetry 분산 트레이싱 설정 (OTLP export).

`OTEL_EXPORTER_OTLP_ENDPOINT` 환경변수가 있으면 활성화하고, 없으면 no-op이다
(로컬 개발·모니터링 미배포 환경에선 아무 것도 하지 않는다).

프로덕션에선 docker-compose.monitoring.yml이 이 값을 OTel Collector로 주입한다:
  OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
  OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
Collector가 트레이스를 Tempo·Jaeger 양쪽으로 팬아웃한다.

FastAPI(HTTP)와 SQLAlchemy(쿼리) 스팬을 자동 계측한다.
"""

import logging
import os

logger = logging.getLogger(__name__)


def setup_telemetry(app, engine=None) -> None:
    """OTLP 엔드포인트가 설정돼 있으면 트레이싱을 켠다. 실패해도 앱은 계속 뜬다."""
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        logger.info("OTEL_EXPORTER_OTLP_ENDPOINT 미설정 → 트레이싱 비활성")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        service_name = os.getenv("OTEL_SERVICE_NAME", "commercialradar-backend")
        provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
        # endpoint/protocol은 표준 OTEL_* 환경변수를 그대로 따르도록 인자 없이 생성.
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(provider)

        FastAPIInstrumentor.instrument_app(app)
        if engine is not None:
            SQLAlchemyInstrumentor().instrument(engine=engine)

        logger.info("OpenTelemetry 트레이싱 활성: endpoint=%s service=%s", endpoint, service_name)
    except Exception:
        logger.exception("OpenTelemetry 설정 실패 — 트레이싱 없이 계속")
