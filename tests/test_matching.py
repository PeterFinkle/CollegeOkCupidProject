import itertools
import random

import pytest

from campusmatch.data import generate_students
from campusmatch.matching import (
    greedy_pairs,
    is_stable,
    pair_roommates,
    preference_lists,
    stable_roommates,
    top_matches,
)
from campusmatch.scoring import score


def all_perfect_matchings(people):
    if not people:
        yield {}
        return
    a, rest = people[0], people[1:]
    for i, b in enumerate(rest):
        for m in all_perfect_matchings(rest[:i] + rest[i + 1 :]):
            yield {**m, a: b, b: a}


def random_prefs(n, rng):
    people = list(range(n))
    return {p: rng.sample([q for q in people if q != p], n - 1) for p in people}


# Classic instance with no stable matching (Gale & Shapley, 1962):
# 0, 1, 2 each rank someone in the trio first in a cycle, and everyone ranks 3 last.
NO_SOLUTION = {0: [1, 2, 3], 1: [2, 0, 3], 2: [0, 1, 3], 3: [0, 1, 2]}


def test_known_unsolvable_instance():
    assert stable_roommates(NO_SOLUTION) is None
    assert not any(is_stable(NO_SOLUTION, m) for m in all_perfect_matchings([0, 1, 2, 3]))


def test_irving_textbook_instance():
    # Example from Irving (1985) / Gusfield & Irving, 6 people, has a stable matching.
    prefs = {
        1: [3, 4, 2, 6, 5],
        2: [6, 5, 4, 1, 3],
        3: [2, 4, 5, 1, 6],
        4: [5, 2, 3, 6, 1],
        5: [3, 1, 2, 4, 6],
        6: [5, 1, 3, 4, 2],
    }
    m = stable_roommates(prefs)
    assert m is not None and is_stable(prefs, m)
    assert m == {1: 6, 6: 1, 2: 4, 4: 2, 3: 5, 5: 3}


@pytest.mark.parametrize("n", [2, 4, 6, 8])
def test_irving_agrees_with_brute_force(n):
    rng = random.Random(n)
    for _ in range(150 if n <= 6 else 60):
        prefs = random_prefs(n, rng)
        m = stable_roommates(prefs)
        exists = any(is_stable(prefs, cand) for cand in all_perfect_matchings(list(range(n))))
        if m is None:
            assert not exists, prefs
        else:
            assert is_stable(prefs, m), prefs
            assert all(m[m[p]] == p and m[p] != p for p in prefs)


def test_irving_rejects_bad_input():
    with pytest.raises(ValueError):
        stable_roommates({0: [1, 2], 1: [0, 2], 2: [0, 1]})  # odd
    with pytest.raises(ValueError):
        stable_roommates({0: [1], 1: [1]})  # ranks self


def test_top_matches_sorted_excludes_self_and_respects_k():
    students = generate_students(80, seed=3)
    me = students[0]
    res = top_matches(me, students, k=7)
    assert len(res) == 7
    assert all(o.id != me.id for o, _ in res)
    scores = [s.match for _, s in res]
    assert scores == sorted(scores, reverse=True)
    best_possible = max(score(me, o).match for o in students[1:])
    assert scores[0] == best_possible


def test_greedy_pairs_is_stable_on_mutual_score():
    students = generate_students(30, seed=11)
    pairs = greedy_pairs(students)
    by_id = {s.id: s for s in students}
    for a, b in itertools.combinations(students, 2):
        if pairs[a.id] == b.id:
            continue
        s_ab = score(a, b).match
        assert not (
            s_ab > score(a, by_id[pairs[a.id]]).match and s_ab > score(b, by_id[pairs[b.id]]).match
        )


@pytest.mark.parametrize("n", [10, 11, 40])
def test_pair_roommates_end_to_end(n):
    students = generate_students(n, seed=5)
    pairing = pair_roommates(students)
    p = pairing.pairs
    assert set(p) == {s.id for s in students}
    unpaired = [k for k, v in p.items() if v is None]
    assert len(unpaired) == n % 2
    assert all(p[v] == k for k, v in p.items() if v is not None)
    if pairing.method == "irving" and n % 2 == 0:
        assert is_stable(preference_lists(students), p)


def test_pair_roommates_without_fallback_can_fail():
    students = generate_students(400, seed=1)
    assert pair_roommates(students, fallback=False) is None
    assert pair_roommates(students).method == "greedy"


def test_generator_is_deterministic():
    a = generate_students(5, seed=9)
    b = generate_students(5, seed=9)
    assert [(p.name, p.answers) for p in a] == [(p.name, p.answers) for p in b]
