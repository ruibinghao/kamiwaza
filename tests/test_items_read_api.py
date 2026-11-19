from fastapi.testclient import TestClient


def test_user_sees_own_team_items(ann: TestClient) -> None:
    created = ann.post("/api/items", json={"title": "mine"}).json()
    items = ann.get("/api/teams/red/items").json()
    assert [i["id"] for i in items] == [created["id"]]


def test_user_can_read_other_teams_items_and_members(ann: TestClient, cy: TestClient) -> None:
    cy.post("/api/items", json={"title": "blue work"})
    items = ann.get("/api/teams/blue/items")
    assert items.status_code == 200
    assert [i["title"] for i in items.json()] == ["blue work"]
    assert ann.get("/api/teams/blue/members").json() == ["cy"]


def test_items_do_not_leak_between_teams(ann: TestClient, cy: TestClient) -> None:
    ann.post("/api/items", json={"title": "red work"})
    assert cy.get("/api/teams/blue/items").json() == []
    assert [i["title"] for i in cy.get("/api/teams/red/items").json()] == ["red work"]


def test_teams_lists_distinct_teams(ann: TestClient) -> None:
    assert ann.get("/api/teams").json() == ["blue", "red"]


def test_members_sorted(ann: TestClient) -> None:
    assert ann.get("/api/teams/red/members").json() == ["ann", "bob"]


def test_unknown_team_is_404(ann: TestClient) -> None:
    assert ann.get("/api/teams/nope/items").status_code == 404
    assert ann.get("/api/teams/nope/members").status_code == 404


def test_unauthenticated_reads_are_401(client: TestClient) -> None:
    for url in ("/api/teams", "/api/teams/red/items", "/api/teams/red/members"):
        assert client.get(url).status_code == 401


def test_reads_do_not_modify_data(ann: TestClient) -> None:
    ann.post("/api/items", json={"title": "x"})
    first = ann.get("/api/teams/red/items").json()
    ann.get("/api/teams/red/items")
    assert ann.get("/api/teams/red/items").json() == first
