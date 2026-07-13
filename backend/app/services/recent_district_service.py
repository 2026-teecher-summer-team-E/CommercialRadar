import json

from redis import Redis

MAX_ITEMS = 10
TTL_SECONDS = 30 * 24 * 60 * 60  # 30일

# LRANGE(읽기) → 파이썬에서 중복 제거/정렬 → DELETE+RPUSH+EXPIRE(쓰기) 사이에 원자성이 없어,
# 동시 요청(같은 유저가 여러 탭/중복 클릭 등)이 겹치면 한쪽 갱신이 유실될 수 있었다(TOCTOU).
# Redis는 Lua 스크립트를 단일 명령처럼 서버에서 원자적으로 실행하므로, read-modify-write 전체를
# 스크립트 안에 봉인하면 WATCH/MULTI 낙관적 락 + 재시도 루프 없이도 경쟁 조건이 사라진다.
_ADD_SCRIPT = """
local key = KEYS[1]
local new_item_json = ARGV[1]
local new_id = ARGV[2]
local max_items = tonumber(ARGV[3])
local ttl_seconds = tonumber(ARGV[4])

local existing = redis.call('LRANGE', key, 0, -1)
local kept = {}
for _, raw in ipairs(existing) do
    local decoded = cjson.decode(raw)
    if tostring(decoded.id) ~= new_id then
        table.insert(kept, raw)
    end
end

redis.call('DEL', key)
redis.call('RPUSH', key, new_item_json, unpack(kept))
redis.call('LTRIM', key, 0, max_items - 1)
redis.call('EXPIRE', key, ttl_seconds)
return new_item_json
"""

_REMOVE_SCRIPT = """
local key = KEYS[1]
local remove_id = ARGV[1]
local ttl_seconds = tonumber(ARGV[2])

local existing = redis.call('LRANGE', key, 0, -1)
local kept = {}
for _, raw in ipairs(existing) do
    local decoded = cjson.decode(raw)
    if tostring(decoded.id) ~= remove_id then
        table.insert(kept, raw)
    end
end

redis.call('DEL', key)
if #kept > 0 then
    redis.call('RPUSH', key, unpack(kept))
    redis.call('EXPIRE', key, ttl_seconds)
end
return #kept
"""


class RecentDistrictService:
    @staticmethod
    def _key(user_id: int) -> str:
        return f"recent:user:{user_id}"

    @staticmethod
    def list_for_user(redis_client: Redis, user_id: int) -> list[dict]:
        raw_items = redis_client.lrange(RecentDistrictService._key(user_id), 0, MAX_ITEMS - 1)
        return [json.loads(raw) for raw in raw_items]

    @staticmethod
    def add(redis_client: Redis, user_id: int, item: dict) -> dict:
        key = RecentDistrictService._key(user_id)
        redis_client.eval(
            _ADD_SCRIPT,
            1,
            key,
            json.dumps(item, ensure_ascii=False),
            str(item["id"]),
            MAX_ITEMS,
            TTL_SECONDS,
        )
        return item

    @staticmethod
    def remove(redis_client: Redis, user_id: int, district_id: int) -> None:
        key = RecentDistrictService._key(user_id)
        redis_client.eval(_REMOVE_SCRIPT, 1, key, str(district_id), TTL_SECONDS)
