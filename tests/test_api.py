import pytest
from fastapi.testclient import TestClient

from campusmatch.api import create_app


@pytest.fixture
def client():
    return TestClient(create_app(seed_students=20, seed=1))


def new_profile(client, name="Test Student", **overrides):
    body = {
        "name": name,
        "major": "CS",
        "year": 2,
        "answers": [
            {"question_id": "sleep", "choice": 0, "acceptable": [0, 1], "importance": "very"},
            {"question_id": "clean", "choice": 1, "acceptable": [0, 1], "importance": "somewhat"},
            {"question_id": "noise", "choice": 0, "acceptable": [0], "importance": "mandatory"},
        ],
    }
    body.update(overrides)
    return client.post("/profiles", json=body)


def test_health_and_questions(client):
    assert client.get("/health").json() == {"status": "ok", "profiles": 20}
    qs = client.get("/questions").json()
    assert len(qs) >= 10 and {"id", "text", "options"} <= set(qs[0])


def test_index_serves_ui(client):
    r = client.get("/")
    assert r.status_code == 200 and "CampusMatch" in r.text


def test_create_profile_and_get_matches(client):
    r = new_profile(client)
    assert r.status_code == 201
    pid = r.json()["id"]
    matches = client.get(f"/profiles/{pid}/matches", params={"k": 5}).json()
    assert len(matches) == 5
    assert [m["match"] for m in matches] == sorted((m["match"] for m in matches), reverse=True)
    other = matches[0]["id"]
    cmp = client.get(f"/compare/{pid}/{other}").json()
    assert cmp["match"] == matches[0]["match"]
    assert len(cmp["breakdown"]) == cmp["shared_questions"]


@pytest.mark.parametrize(
    "bad",
    [
        {"answers": [{"question_id": "nope", "choice": 0, "acceptable": [0]}]},
        {"answers": [{"question_id": "sleep", "choice": 9, "acceptable": [0]}]},
        {"answers": [{"question_id": "sleep", "choice": 0, "acceptable": []}]},
        {
            "answers": [
                {"question_id": "sleep", "choice": 0, "acceptable": [0], "importance": "huge"}
            ]
        },
        {"name": ""},
    ],
)
def test_validation_errors(client, bad):
    assert new_profile(client, **bad).status_code == 422


def test_missing_profile_404(client):
    assert client.get("/profiles/doesnotexist/matches").status_code == 404


def test_pagination(client):
    page = client.get("/profiles", params={"limit": 5, "offset": 5}).json()
    assert page["total"] == 20 and len(page["items"]) == 5


def test_roommates_endpoint(client):
    ids = [p["id"] for p in client.get("/profiles", params={"limit": 9}).json()["items"]]
    r = client.post("/roommates", json=ids).json()
    assert r["method"] in {"irving", "greedy"}
    assert len(r["pairs"]) == 4 and len(r["unpaired"]) == 1
    paired = {x for p in r["pairs"] for x in (p["a"], p["b"])} | set(r["unpaired"])
    assert paired == set(ids)
    assert client.post("/roommates", json=[ids[0], ids[0]]).status_code == 422
