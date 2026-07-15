"""run_targets가 인제스천 성공 시 캐시 무효화 후 워밍까지 호출하는지 검증."""

import app.ingest.jobs as jobs


class _FakeRun:
    status = "success"
    upserted_count = 5


def test_run_targets_warms_cache_on_success(monkeypatch):
    calls = {"invalidate": 0, "warm": 0}
    monkeypatch.setattr(jobs, "invalidate_all", lambda: calls.__setitem__("invalidate", calls["invalidate"] + 1))
    monkeypatch.setattr(jobs, "warm_cache", lambda: calls.__setitem__("warm", calls["warm"] + 1))
    monkeypatch.setattr(jobs, "JOBS", {"fake": lambda: _FakeRun()})

    jobs.run_targets(["fake"])

    assert calls["invalidate"] == 1
    assert calls["warm"] == 1


def test_run_targets_skips_warm_when_no_success(monkeypatch):
    calls = {"warm": 0}
    monkeypatch.setattr(jobs, "warm_cache", lambda: calls.__setitem__("warm", calls["warm"] + 1))

    jobs.run_targets(["unknown_target"])  # JOBS에 없음 → any_success False

    assert calls["warm"] == 0
