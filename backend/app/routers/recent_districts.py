from fastapi import APIRouter, Depends, status
from redis import Redis

from app.core.deps import get_current_user, get_redis
from app.models.users import User
from app.schemas.recent_district import RecentDistrictCreate, RecentDistrictResponse
from app.services.recent_district_service import RecentDistrictService

router = APIRouter(tags=["recent-districts"])


@router.post(
    "/recent-districts",
    response_model=RecentDistrictResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_recent_district(
    body: RecentDistrictCreate,
    redis_client: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    return RecentDistrictService.add(redis_client, current_user.id, body.model_dump())
