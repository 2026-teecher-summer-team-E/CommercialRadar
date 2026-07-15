"""compute_scores가 점수 재계산 성공 시 캐시 무효화 후 워밍까지 호출하는지 검증.

db 픽스처(테스트 DB)로 실제 compute_scores를 돌리되, warm_cache/invalidate_all은 스파이로 대체.
"""

import app.services.business_score_service as bss
from app.services.business_score_service import BusinessScoreService


def test_compute_scores_warms_cache_on_success(db, monkeypatch):
    calls = {"invalidate": 0, "warm": 0}
    monkeypatch.setattr(bss, "invalidate_all", lambda: calls.__setitem__("invalidate", calls["invalidate"] + 1))
    monkeypatch.setattr(bss, "warm_cache", lambda arg=None: calls.__setitem__("warm", calls["warm"] + 1))

    run = BusinessScoreService.compute_scores(db)

    assert run.status == "success"
    assert calls["invalidate"] == 1
    assert calls["warm"] == 1
