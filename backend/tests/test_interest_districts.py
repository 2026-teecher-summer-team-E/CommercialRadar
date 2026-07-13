def test_create_and_list(client, seed_district):
    create_res = client.post(
        "/api/interest-districts",
        json={"commercial_district_id": seed_district.id, "memo": "메모", "category_name": "카페"},
    )
    assert create_res.status_code == 201
    body = create_res.json()
    assert body["commercial_district_id"] == seed_district.id
    assert body["memo"] == "메모"
    assert body["category_name"] == "카페"

    list_res = client.get("/api/interest-districts")
    assert list_res.status_code == 200
    ids = [item["id"] for item in list_res.json()]
    assert body["id"] in ids


def test_create_duplicate_returns_409(client, seed_district):
    payload = {"commercial_district_id": seed_district.id}
    first = client.post("/api/interest-districts", json=payload)
    assert first.status_code == 201

    second = client.post("/api/interest-districts", json=payload)
    assert second.status_code == 409


def test_create_missing_district_returns_404(client):
    res = client.post("/api/interest-districts", json={"commercial_district_id": 999999})
    assert res.status_code == 404


def test_delete_removes_from_list(client, seed_district):
    created = client.post(
        "/api/interest-districts",
        json={"commercial_district_id": seed_district.id},
    ).json()

    delete_res = client.delete(f"/api/interest-districts/{created['id']}")
    assert delete_res.status_code == 204

    ids = [item["id"] for item in client.get("/api/interest-districts").json()]
    assert created["id"] not in ids


def test_delete_missing_returns_404(client):
    res = client.delete("/api/interest-districts/999999")
    assert res.status_code == 404


# ── PATCH /api/interest-districts/{id} (memo 수정) ──────────────────────────

def _create(client, seed_district, memo="메모", category="카페"):
    return client.post(
        "/api/interest-districts",
        json={"commercial_district_id": seed_district.id, "memo": memo, "category_name": category},
    ).json()


def test_update_memo_success(client, seed_district):
    created = _create(client, seed_district, memo="옛 메모", category="카페")

    res = client.patch(
        f"/api/interest-districts/{created['id']}",
        json={"memo": "임대료 재확인 필요"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["id"] == created["id"]
    assert body["memo"] == "임대료 재확인 필요"
    assert body["category_name"] == "카페"  # category_name 불변


def test_update_memo_null_clears(client, seed_district):
    created = _create(client, seed_district, memo="지울 메모")

    res = client.patch(f"/api/interest-districts/{created['id']}", json={"memo": None})

    assert res.status_code == 200
    assert res.json()["memo"] is None


def test_update_memo_empty_string_clears(client, seed_district):
    created = _create(client, seed_district, memo="지울 메모")

    res = client.patch(f"/api/interest-districts/{created['id']}", json={"memo": ""})

    assert res.status_code == 200
    assert res.json()["memo"] is None  # "" 는 None으로 정규화


def test_update_ignores_category_name(client, seed_district):
    created = _create(client, seed_district, memo="m", category="카페")

    res = client.patch(
        f"/api/interest-districts/{created['id']}",
        json={"memo": "새 메모", "category_name": "식당"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["memo"] == "새 메모"
    assert body["category_name"] == "카페"  # category_name 수정 요청은 무시됨


def test_update_missing_returns_404(client):
    res = client.patch("/api/interest-districts/999999", json={"memo": "x"})
    assert res.status_code == 404


def test_update_other_users_returns_404(client, db, seed_district):
    from app.models.interest_district import InterestDistrict
    from app.models.users import User

    other = User(name="타인", email="other@example.com", clerk_user_id="clerk_other")
    db.add(other)
    db.flush()
    others_interest = InterestDistrict(
        user_id=other.id, commercial_district_id=seed_district.id, memo="남의 메모"
    )
    db.add(others_interest)
    db.flush()

    res = client.patch(f"/api/interest-districts/{others_interest.id}", json={"memo": "침범"})
    assert res.status_code == 404


def test_update_memo_too_long_returns_422(client, seed_district):
    created = _create(client, seed_district)

    res = client.patch(
        f"/api/interest-districts/{created['id']}",
        json={"memo": "x" * 501},
    )
    assert res.status_code == 422
