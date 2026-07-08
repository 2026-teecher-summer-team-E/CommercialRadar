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
