"""정적성 높은 GET 응답용 HTTP 캐싱(Cache-Control + ETag/If-None-Match) 헬퍼.

geo/geojson/ranking처럼 자주 바뀌지 않는 응답에서 재사용한다.
"""

import hashlib
import json

from fastapi import Request, Response
from fastapi.encoders import jsonable_encoder


def apply_http_cache(request: Request, response: Response, payload, max_age: int) -> Response | None:
    """payload의 ETag를 계산해 response에 Cache-Control/ETag 헤더를 설정한다.

    요청의 If-None-Match가 계산된 ETag와 일치하면 304 Response를 반환하니,
    호출부는 그 값이 None이 아니면 그대로 리턴하면 된다. None이면 payload를 그대로 리턴한다.
    """
    body = json.dumps(jsonable_encoder(payload), sort_keys=True, ensure_ascii=False).encode()
    etag = f'"{hashlib.sha256(body).hexdigest()}"'

    response.headers["Cache-Control"] = f"public, max-age={max_age}"
    response.headers["ETag"] = etag

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=dict(response.headers))
    return None
