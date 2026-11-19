from fastapi.testclient import TestClient

from workboard.repository import STATUSES


def _create(c: TestClient, **body: object) -> dict[str, object]:
    resp = c.post("/api/items", json={"title": "T", **body})
    assert resp.status_code == 201, resp.text
    return resp.json()  # type: ignore[no-any-return]


def test_create_returns_201_in_callers_team(ann: TestClient) -> None:
    item = _create(ann, description="D")
    assert item["team_id"] == "red"
    assert item["status"] == "New"
    assert item["created_by"] == "ann"
    assert item["description"] == "D"
    assert item["assigned_to"] is None


def test_create_ignores_client_supplied_team(ann: TestClient) -> None:
    resp = ann.post("/api/items", json={"title": "T", "team_id": "blue"})
    assert resp.status_code in (201, 422)
    if resp.status_code == 201:
        assert resp.json()["team_id"] == "red"


def test_create_rejects_bad_titles(ann: TestClient) -> None:
    for title in ("", "   ", "x" * 201):
        assert ann.post("/api/items", json={"title": title}).status_code == 422


def test_create_accepts_200_char_title_and_trims(ann: TestClient) -> None:
    assert _create(ann, title="x" * 200)["title"] == "x" * 200
    assert _create(ann, title="  hi  ")["title"] == "hi"


def test_create_assignee_must_be_on_callers_team(ann: TestClient) -> None:
    assert ann.post("/api/items", json={"title": "T", "assigned_to": "cy"}).status_code == 422
    assert _create(ann, assigned_to="bob")["assigned_to"] == "bob"
    assert ann.post("/api/items", json={"title": "T", "assigned_to": "ghost"}).status_code == 422


def test_patch_status_each_valid_value_and_invalid_rejected(ann: TestClient) -> None:
    item_id = _create(ann)["id"]
    for status in STATUSES:
        resp = ann.patch(f"/api/items/{item_id}", json={"status": status})
        assert resp.status_code == 200 and resp.json()["status"] == status
    assert ann.patch(f"/api/items/{item_id}", json={"status": "Done"}).status_code == 422


def test_patch_reassign_unassign_and_cross_team_assignee(ann: TestClient) -> None:
    item_id = _create(ann)["id"]
    assert (
        ann.patch(f"/api/items/{item_id}", json={"assigned_to": "bob"}).json()["assigned_to"]
        == "bob"
    )
    assert (
        ann.patch(f"/api/items/{item_id}", json={"assigned_to": None}).json()["assigned_to"] is None
    )
    assert ann.patch(f"/api/items/{item_id}", json={"assigned_to": "cy"}).status_code == 422


def test_patch_edits_title_and_description(ann: TestClient) -> None:
    item_id = _create(ann)["id"]
    body = ann.patch(f"/api/items/{item_id}", json={"title": "New", "description": "Desc"}).json()
    assert (body["title"], body["description"]) == ("New", "Desc")


def test_patch_rejects_empty_unknown_and_null_required(ann: TestClient) -> None:
    item_id = _create(ann)["id"]
    url = f"/api/items/{item_id}"
    assert ann.patch(url, json={}).status_code == 422
    assert ann.patch(url, json={"colour": "red"}).status_code == 422
    assert ann.patch(url, json={"status": None}).status_code == 422
    assert ann.patch(url, json={"title": None}).status_code == 422
    assert ann.patch(url, json={"team_id": "blue"}).status_code == 422


def test_patch_nonexistent_id_is_404(ann: TestClient) -> None:
    assert ann.patch("/api/items/9999", json={"status": "Planning"}).status_code == 404


def test_any_teammate_can_patch(ann: TestClient, bob: TestClient) -> None:
    item_id = _create(ann)["id"]
    resp = bob.patch(f"/api/items/{item_id}", json={"assigned_to": "bob", "status": "Planning"})
    assert resp.status_code == 200


def test_other_team_cannot_write_and_item_unchanged(ann: TestClient, cy: TestClient) -> None:
    item_id = _create(ann)["id"]
    resp = cy.patch(f"/api/items/{item_id}", json={"status": "Finished", "title": "hacked"})
    assert resp.status_code == 403
    after = ann.patch(f"/api/items/{item_id}", json={"description": "x"}).json()
    assert after["status"] == "New" and after["title"] == "T"


def test_unauthenticated_writes_are_401(client: TestClient) -> None:
    assert client.post("/api/items", json={"title": "T"}).status_code == 401
    assert client.patch("/api/items/1", json={"status": "Planning"}).status_code == 401
