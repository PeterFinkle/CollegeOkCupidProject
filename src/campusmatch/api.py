"""HTTP API (FastAPI) with an in-memory store, plus a single-page web UI at `/`."""

from __future__ import annotations

import uuid
from importlib.resources import files
from threading import Lock

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, field_validator

from .data import QUESTIONS, QUESTIONS_BY_ID, generate_students
from .matching import pair_roommates, top_matches
from .models import Answer, Importance, Profile
from .scoring import explain, score

IMPORTANCE_NAMES = {i.name.lower(): i for i in Importance}


class AnswerIn(BaseModel):
    question_id: str
    choice: int = Field(ge=0)
    acceptable: list[int] = Field(min_length=1)
    importance: str = "somewhat"

    @field_validator("importance")
    @classmethod
    def _known_importance(cls, v: str) -> str:
        if v.lower() not in IMPORTANCE_NAMES:
            raise ValueError(f"importance must be one of {sorted(IMPORTANCE_NAMES)}")
        return v.lower()


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    major: str = Field(default="", max_length=80)
    year: int = Field(default=1, ge=1, le=6)
    answers: list[AnswerIn] = Field(default_factory=list)


class Store:
    """Thread-safe in-memory repository. Swap for a database in production."""

    def __init__(self) -> None:
        self._profiles: dict[str, Profile] = {}
        self._lock = Lock()

    def add(self, p: Profile) -> None:
        with self._lock:
            self._profiles[p.id] = p

    def get(self, pid: str) -> Profile | None:
        return self._profiles.get(pid)

    def all(self) -> list[Profile]:
        with self._lock:
            return list(self._profiles.values())

    def __len__(self) -> int:
        return len(self._profiles)


def _to_profile(body: ProfileIn, pid: str) -> Profile:
    p = Profile(id=pid, name=body.name, major=body.major, year=body.year)
    for a in body.answers:
        q = QUESTIONS_BY_ID.get(a.question_id)
        if q is None:
            raise HTTPException(422, f"unknown question {a.question_id!r}")
        ans = Answer(
            a.question_id, a.choice, frozenset(a.acceptable), IMPORTANCE_NAMES[a.importance]
        )
        try:
            ans.validate(q)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        p.answer(ans)
    return p


def _profile_out(p: Profile) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "major": p.major,
        "year": p.year,
        "answered": len(p.answers),
    }


def create_app(seed_students: int = 60, seed: int = 7) -> FastAPI:
    app = FastAPI(
        title="CampusMatch",
        version="0.1.0",
        description="Compatibility matching and stable roommate pairing for college students.",
    )
    store = Store()
    for s in generate_students(seed_students, seed=seed):
        store.add(s)
    app.state.store = store

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def index() -> str:
        return files("campusmatch").joinpath("static/index.html").read_text(encoding="utf-8")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "profiles": len(store)}

    @app.get("/questions")
    def questions() -> list[dict]:
        return [
            {"id": q.id, "text": q.text, "options": list(q.options), "category": q.category}
            for q in QUESTIONS
        ]

    @app.get("/importance-levels")
    def importance_levels() -> dict[str, int]:
        return {name: int(level) for name, level in IMPORTANCE_NAMES.items()}

    @app.post("/profiles", status_code=201)
    def create_profile(body: ProfileIn) -> dict:
        p = _to_profile(body, pid=uuid.uuid4().hex[:12])
        store.add(p)
        return _profile_out(p)

    @app.get("/profiles")
    def list_profiles(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)) -> dict:
        everyone = sorted(store.all(), key=lambda p: p.id)
        return {
            "total": len(everyone),
            "items": [_profile_out(p) for p in everyone[offset : offset + limit]],
        }

    def _require(pid: str) -> Profile:
        p = store.get(pid)
        if p is None:
            raise HTTPException(404, f"profile {pid!r} not found")
        return p

    @app.get("/profiles/{pid}")
    def get_profile(pid: str) -> dict:
        return _profile_out(_require(pid))

    @app.get("/profiles/{pid}/matches")
    def matches(pid: str, k: int = Query(10, ge=1, le=100)) -> list[dict]:
        me = _require(pid)
        return [
            {
                **_profile_out(o),
                "match": s.percent,
                "you_like_them": round(s.satisfaction_a * 100),
                "they_like_you": round(s.satisfaction_b * 100),
                "shared_questions": s.shared_questions,
            }
            for o, s in top_matches(me, store.all(), k=k)
        ]

    @app.get("/compare/{a}/{b}")
    def compare(a: str, b: str) -> dict:
        pa, pb = _require(a), _require(b)
        s = score(pa, pb)
        return {
            "match": s.percent,
            "shared_questions": s.shared_questions,
            "breakdown": explain(pa, pb, QUESTIONS_BY_ID),
        }

    @app.post("/roommates")
    def roommates(ids: list[str]) -> dict:
        if len(ids) < 2:
            raise HTTPException(422, "need at least two students")
        if len(set(ids)) != len(ids):
            raise HTTPException(422, "student ids must be unique")
        if len(ids) > 400:
            raise HTTPException(422, "at most 400 students per request")
        students = [_require(i) for i in ids]
        pairing = pair_roommates(students)
        pairs, seen, unpaired = [], set(), []
        for a, b in pairing.pairs.items():
            if b is None:
                unpaired.append(a)
            elif a not in seen:
                seen.update((a, b))
                pairs.append({"a": a, "b": b, "match": score(store.get(a), store.get(b)).percent})
        return {"method": pairing.method, "pairs": pairs, "unpaired": unpaired}

    return app


app = create_app()
