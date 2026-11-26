"""Compatibility scoring.

The model, popularized by early online-dating sites, works like this:

1. For every question both students answered, student A "earns" A's importance
   weight if B's answer is one A finds acceptable.
2. A's satisfaction with B is earned / possible, over the shared questions.
3. The match score is the geometric mean of the two satisfactions, so a
   one-sided match (A loves B, B is lukewarm on A) is pulled down hard.
4. With few shared questions the estimate is noisy, so we subtract a margin of
   error of 1 / n_shared and clamp at zero.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .models import Profile


@dataclass(frozen=True)
class MatchScore:
    match: float
    """Final score in [0, 1], after the margin-of-error penalty."""
    satisfaction_a: float
    """How well B's answers satisfy A, in [0, 1]."""
    satisfaction_b: float
    """How well A's answers satisfy B, in [0, 1]."""
    shared_questions: int

    @property
    def percent(self) -> int:
        return round(self.match * 100)


def satisfaction(judge: Profile, candidate: Profile, shared: list[str]) -> float:
    """Fraction of `judge`'s importance-weighted preferences that `candidate` meets.

    If the judge marked every shared question irrelevant they have no
    preferences to violate, so they are fully satisfied.
    """
    earned = 0
    possible = 0
    for qid in shared:
        mine = judge.answers[qid]
        weight = int(mine.importance)
        possible += weight
        if candidate.answers[qid].choice in mine.acceptable:
            earned += weight
    if possible == 0:
        return 1.0
    return earned / possible


def score(a: Profile, b: Profile) -> MatchScore:
    shared = sorted(a.answers.keys() & b.answers.keys())
    if not shared:
        return MatchScore(0.0, 0.0, 0.0, 0)
    sat_a = satisfaction(a, b, shared)
    sat_b = satisfaction(b, a, shared)
    raw = math.sqrt(sat_a * sat_b)
    adjusted = max(0.0, raw - 1.0 / len(shared))
    return MatchScore(adjusted, sat_a, sat_b, len(shared))


def explain(a: Profile, b: Profile, questions: dict) -> list[dict]:
    """Per-question breakdown of why two students do or don't match.

    Returns one row per shared question with whether each side's preference
    was met, sorted so the most important disagreements come first.
    """
    rows = []
    for qid in sorted(a.answers.keys() & b.answers.keys()):
        qa, qb = a.answers[qid], b.answers[qid]
        q = questions.get(qid)
        rows.append(
            {
                "question_id": qid,
                "question": q.text if q else qid,
                "a_answer": q.options[qa.choice] if q else qa.choice,
                "b_answer": q.options[qb.choice] if q else qb.choice,
                "a_satisfied": qb.choice in qa.acceptable,
                "b_satisfied": qa.choice in qb.acceptable,
                "weight": int(qa.importance) + int(qb.importance),
            }
        )
    rows.sort(key=lambda r: (r["a_satisfied"] and r["b_satisfied"], -r["weight"]))
    return rows
