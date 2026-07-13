import json

from redis import Redis

MAX_ITEMS = 10
TTL_SECONDS = 30 * 24 * 60 * 60  # 30일


class RecentDistrictService:
    @staticmethod
    def _key(user_id: int) -> str:
        return f"recent:user:{user_id}"

    @staticmethod
    def _replace_all(redis_client: Redis, key: str, items: list[dict]) -> None:
        """목록 전체를 통째로 다시 써서 순서를 고정하고 TTL을 30일로 갱신한다."""
        pipe = redis_client.pipeline()
        pipe.delete(key)
        if items:
            pipe.rpush(key, *[json.dumps(item, ensure_ascii=False) for item in items])
            pipe.expire(key, TTL_SECONDS)
        pipe.execute()

    @staticmethod
    def list_for_user(redis_client: Redis, user_id: int) -> list[dict]:
        raw_items = redis_client.lrange(RecentDistrictService._key(user_id), 0, MAX_ITEMS - 1)
        return [json.loads(raw) for raw in raw_items]

    @staticmethod
    def add(redis_client: Redis, user_id: int, item: dict) -> dict:
        key = RecentDistrictService._key(user_id)
        existing = [json.loads(raw) for raw in redis_client.lrange(key, 0, -1)]
        items = [item] + [i for i in existing if i["id"] != item["id"]]
        RecentDistrictService._replace_all(redis_client, key, items[:MAX_ITEMS])
        return item
