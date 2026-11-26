"""Vectorized all-pairs scoring with NumPy (optional: `pip install campusmatch[fast]`).

`scoring.score` compares two profiles in a Python loop over their shared questions, so
scoring a whole population costs n² interpreted loops. Here the population is encoded once
as dense per-question arrays and the n×n matrices fall out of three matrix products:

    shared[i, k]   = Σ_q answered[i, q] · answered[k, q]
    possible[i, k] = Σ_q weight[i, q] · answered[k, q]
    earned[i, k]   = Σ_q Σ_o weight[i, q] · accepts[i, q, o] · picked[k, q, o]

where `accepts` unpacks i's acceptable bitmask and `picked` one-hot encodes k's choice. The
weights are small integers, so the float64 sums are exact and the result matches
`scoring.score` to the last bit, not just approximately.

Memory is O(n²): a few float64 matrices, about 32 MB each at n = 2000.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from .models import Profile


@dataclass(frozen=True)
class AnswerArrays:
    """A population's answers as (n_profiles, n_questions) arrays.

    Unanswered cells have answered=False and zeros elsewhere, so they drop out of every
    sum without needing a separate mask in the arithmetic.
    """

    question_ids: tuple[str, ...]
    choice: np.ndarray
    """int64, index of the option the student picked."""
    acceptable: np.ndarray
    """int64, bitmask of options the student accepts (see `Answer.acceptable_mask`)."""
    weight: np.ndarray
    """float64, importance weight (0 for unanswered)."""
    answered: np.ndarray
    """bool."""

    @property
    def n_options(self) -> int:
        """Enough option slots for every choice and every acceptable bit in the data."""
        if self.choice.size == 0:
            return 1
        top_bit = int(self.acceptable.max()).bit_length()
        return max(int(self.choice.max()) + 1, top_bit, 1)

    def shared(self) -> np.ndarray:
        """shared[i, k] = number of questions both i and k answered."""
        a = self.answered.astype(np.float64)
        return (a @ a.T).astype(np.int64)

    def satisfaction(self) -> np.ndarray:
        """sat[i, k] = how well k's answers satisfy i, as in `scoring.satisfaction`."""
        n, q = self.choice.shape
        options = np.arange(self.n_options)
        width = q * len(options)
        accepts = (self.acceptable[:, :, None] >> options) & 1  # (n, q, o)
        picked = (self.choice[:, :, None] == options) & self.answered[:, :, None]
        weighted = (self.weight[:, :, None] * accepts).reshape(n, width)
        earned = weighted @ picked.reshape(n, width).astype(np.float64).T
        possible = self.weight @ self.answered.astype(np.float64).T
        # A judge with zero possible weight (no shared questions, or all marked irrelevant)
        # has nothing to be unhappy about: satisfaction 1.0, as in the scalar version.
        safe = np.where(possible > 0, possible, 1.0)
        return np.where(possible > 0, earned / safe, 1.0)

    def match(self) -> np.ndarray:
        """match[i, k] = `scoring.score(profiles[i], profiles[k]).match`."""
        sat = self.satisfaction()
        shared = self.shared()
        raw = np.sqrt(sat * sat.T)
        margin = 1.0 / np.maximum(shared, 1)
        return np.where(shared > 0, np.maximum(raw - margin, 0.0), 0.0)


def encode(profiles: Sequence[Profile]) -> AnswerArrays:
    """Pack profiles into `AnswerArrays`. Columns follow the sorted union of question ids."""
    qids = tuple(sorted({qid for p in profiles for qid in p.answers}))
    col = {qid: j for j, qid in enumerate(qids)}
    shape = (len(profiles), len(qids))
    choice = np.zeros(shape, dtype=np.int64)
    acceptable = np.zeros(shape, dtype=np.int64)
    weight = np.zeros(shape, dtype=np.float64)
    answered = np.zeros(shape, dtype=bool)
    for i, p in enumerate(profiles):
        for qid, a in p.answers.items():
            j = col[qid]
            choice[i, j] = a.choice
            acceptable[i, j] = a.acceptable_mask
            weight[i, j] = int(a.importance)
            answered[i, j] = True
    return AnswerArrays(qids, choice, acceptable, weight, answered)


def match_matrix(profiles: Sequence[Profile]) -> np.ndarray:
    """The full n×n match-score matrix, row and column order = `profiles` order."""
    return encode(profiles).match()


def top_matches_fast(
    student_index: int,
    matrix: np.ndarray,
    k: int = 10,
    shared: np.ndarray | None = None,
    min_shared: int = 1,
) -> list[tuple[int, float]]:
    """The k best matches for one row of `matrix`, as (index, score), best first.

    Ties break on index, so for profiles sorted by id this returns the same ranking as
    `matching.top_matches`. Pass the `shared` matrix to also apply its `min_shared` filter;
    without it, pairs with no shared questions are kept and simply score 0.
    """
    row = matrix[student_index]
    keep = np.ones(row.shape[0], dtype=bool)
    keep[student_index] = False
    if shared is not None:
        keep &= shared[student_index] >= min_shared
    candidates = np.flatnonzero(keep)
    # A stable sort on the negated scores keeps equal scores in index order.
    order = candidates[np.argsort(-row[candidates], kind="stable")[:k]]
    return [(int(i), float(row[i])) for i in order]
