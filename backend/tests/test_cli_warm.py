"""`python -m app.cli warm-cache`가 warm_cache를 호출하고 exit 0을 반환하는지 검증."""

import app.services.cache_warmer as cache_warmer
import app.cli as cli


def test_cli_warm_cache_invokes_warmer(monkeypatch):
    calls = {"n": 0}

    def fake_warm(db=None):
        calls["n"] += 1
        return 1

    monkeypatch.setattr(cache_warmer, "warm_cache", fake_warm)

    rc = cli.main(["warm-cache"])

    assert rc == 0
    assert calls["n"] == 1
