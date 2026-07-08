"""Clerk 웹훅 수신 엔드포인트.

svix 서명을 검증한 뒤 user.created / user.updated / user.deleted 이벤트를
users 테이블에 반영한다. ENV=dev 일 때는 서명 검증을 건너뛰어 로컬 Swagger
테스트를 가능하게 한다.
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db
from app.models.users import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])


@router.post("/webhooks/clerk")
async def clerk_webhook(request: Request, db: Session = Depends(get_db)):
    """Clerk(svix) 웹훅을 수신하여 users 테이블을 동기화한다."""
    payload = await request.body()

    if settings.ENV != "dev":
        # --- svix 서명 검증 ---
        if not settings.CLERK_WEBHOOK_SECRET:
            raise HTTPException(status_code=400, detail="웹훅 시크릿이 설정되지 않았습니다.")

        svix_id = request.headers.get("svix-id")
        svix_timestamp = request.headers.get("svix-timestamp")
        svix_signature = request.headers.get("svix-signature")

        if not (svix_id and svix_timestamp and svix_signature):
            raise HTTPException(status_code=400, detail="svix 헤더가 누락되었습니다.")

        headers = {
            "svix-id": svix_id,
            "svix-timestamp": svix_timestamp,
            "svix-signature": svix_signature,
        }

        try:
            from svix.webhooks import Webhook, WebhookVerificationError  # noqa: PLC0415

            evt = Webhook(settings.CLERK_WEBHOOK_SECRET).verify(payload, headers)
        except Exception as exc:  # WebhookVerificationError 포함
            raise HTTPException(status_code=400, detail="웹훅 서명 검증 실패") from exc
    else:
        # dev 환경: 서명 검증 없이 본문을 직접 파싱 (Swagger 로컬 테스트용)
        evt = json.loads(payload)

    event_type: str = evt.get("type", "")
    data: dict = evt.get("data", {})

    logger.info("Clerk 웹훅 수신: %s", event_type)

    if event_type in ("user.created", "user.updated"):
        # --- clerk_user_id ---
        clerk_user_id: str = data["id"]

        # --- name: 성+이름 순(한국식). 빈 경우 이메일 → clerk_user_id 순으로 대체 ---
        name = f"{data.get('last_name') or ''}{data.get('first_name') or ''}".strip()

        # --- 기본 이메일 추출 ---
        email_addresses: list = data.get("email_addresses", [])
        primary_id: str | None = data.get("primary_email_address_id")
        email: str | None = None
        for addr in email_addresses:
            if addr.get("id") == primary_id:
                email = addr.get("email_address")
                break
        if email is None and email_addresses:
            email = email_addresses[0].get("email_address")

        # name이 비어있으면 이메일 → clerk_user_id 순으로 폴백 (NOT NULL 제약)
        if not name:
            name = email or clerk_user_id

        # name 최대 100자 트런케이션
        name = name[:100]

        # --- Upsert ---
        stmt = insert(User).values(
            clerk_user_id=clerk_user_id,
            name=name,
            email=email,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["clerk_user_id"],
            set_={
                "name": stmt.excluded.name,
                "email": stmt.excluded.email,
                # 재가입 복구: 소프트-삭제 플래그를 초기화한다
                "is_deleted": False,
                "updated_at": func.now(),
                # is_admin / is_company 는 건드리지 않는다 (권한은 별도 관리)
            },
        )
        db.execute(stmt)

    elif event_type == "user.deleted":
        # Clerk deleted 이벤트는 data.id 만 포함한다 — 소프트 삭제 처리
        clerk_user_id = data["id"]
        db.execute(
            update(User)
            .where(User.clerk_user_id == clerk_user_id)
            .values(is_deleted=True, updated_at=func.now())
        )

    # 그 외 이벤트 타입은 무시 (Clerk은 다양한 이벤트를 전송하므로 200만 반환)

    db.commit()
    return {"status": "ok"}
