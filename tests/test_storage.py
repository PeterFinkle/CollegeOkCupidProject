import threading

import pytest
from fastapi.testclient import TestClient

from campusmatch.api import create_app
from campusmatch.data import generate_students
from campusmatch.models import Answer, Importance, Profile
from campusmatch.storage import ProfileStore, SQLiteStore, Store


@pytest.fixture(params=["memory", "sqlite"])
def store(request, tmp_path):
    """Every interface test runs against both implementations."""
    if request.param == "memory":
        yield Store()
    else:
        s = SQLiteStore(tmp_path / "campus.db")
        yield s
        s.close()


def test_both_stores_satisfy_the_protocol(store):
    assert isinstance(store, ProfileStore)


def test_round_trip(store, mk):
    p = mk(
        "a",
        sleep=(0, {0, 1}, "mandatory"),
        clean=(3, {2, 3}, "irrelevant"),
        noise=(1, {0, 1, 2, 3}, "a_little"),
    )
    p.name, p.major, p.year = "Ada L.", "Mathematics", 3
    store.add(p)
    assert store.get("a") == p
    assert store.all() == [p]
    assert len(store) == 1
    assert store.get("missing") is None


def test_round_trip_generated_population(store):
    students = generate_students(50, seed=3)
    store.add_many(students)
    assert len(store) == 50
    assert sorted(store.all(), key=lambda p: p.id) == students
    assert store.get(students[7].id) == students[7]


def test_profile_without_answers(store):
    store.add(Profile(id="x", name="X"))
    assert store.get("x") == Profile(id="x", name="X")


def test_add_replaces_profile_and_answers(store, mk):
    store.add(mk("a", sleep=(0, {0}, "very"), clean=(1, {1}, "very")))
    updated = mk("a", noise=(2, {2}, "somewhat"))
    store.add(updated)
    assert len(store) == 1
    assert store.get("a") == updated


def test_concurrent_writes(store):
    students = generate_students(80, seed=5)

    def writer(chunk):
        for p in chunk:
            store.add(p)
            store.all()  # interleave reads with other threads' writes

    threads = [threading.Thread(target=writer, args=(students[i::8],)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(store) == 80
    assert sorted(store.all(), key=lambda p: p.id) == students


def test_acceptable_bitmask_round_trip():
    a = Answer("sleep", 1, frozenset({0, 2, 5}), Importance.VERY)
    assert a.acceptable_mask == 0b100101
    assert Answer.options_from_mask(a.acceptable_mask) == a.acceptable
    assert Answer.options_from_mask(0) == frozenset()


def test_sqlite_persists_across_instances(tmp_path, mk):
    path = tmp_path / "nested" / "campus.db"  # parent directory is created on demand
    first = SQLiteStore(path)
    p = mk("a", sleep=(2, {1, 2}, "very"))
    first.add(p)
    first.close()

    second = SQLiteStore(path)
    assert len(second) == 1
    assert second.get("a") == p
    second.close()


def test_store_import_is_backward_compatible():
    from campusmatch import api

    assert api.Store is Store


def test_api_on_sqlite_store(tmp_path):
    db = tmp_path / "campus.db"
    client = TestClient(create_app(seed_students=20, seed=1, db_path=db))
    assert client.get("/health").json() == {"status": "ok", "profiles": 20}
    body = {
        "name": "Persisted Student",
        "answers": [
            {"question_id": "sleep", "choice": 0, "acceptable": [0, 1], "importance": "very"},
            {"question_id": "noise", "choice": 0, "acceptable": [0], "importance": "mandatory"},
        ],
    }
    pid = client.post("/profiles", json=body).json()["id"]
    matches = client.get(f"/profiles/{pid}/matches", params={"k": 3}).json()
    assert len(matches) == 3
    ids = [p["id"] for p in client.get("/profiles", params={"limit": 6}).json()["items"]]
    assert client.post("/roommates", json=ids).status_code == 200
    client.app.state.store.close()

    # A restart on the same file keeps the new profile and does not seed a second batch.
    restarted = TestClient(create_app(seed_students=20, seed=1, db_path=db))
    assert restarted.get("/health").json()["profiles"] == 21
    assert restarted.get(f"/profiles/{pid}").json()["name"] == "Persisted Student"
    assert restarted.get(f"/profiles/{pid}/matches", params={"k": 3}).json() == matches
    restarted.app.state.store.close()


def test_create_app_accepts_a_store_and_skips_seeding_when_not_empty(mk):
    store = Store()
    store.add(mk("only", sleep=(0, {0}, "very")))
    client = TestClient(create_app(store=store))
    assert client.get("/health").json()["profiles"] == 1


def test_create_app_rejects_store_and_db_path(tmp_path):
    with pytest.raises(ValueError):
        create_app(store=Store(), db_path=tmp_path / "x.db")
