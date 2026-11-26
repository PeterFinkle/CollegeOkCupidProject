import random

import pytest

np = pytest.importorskip("numpy")

from campusmatch.data import QUESTIONS, generate_students, random_answer  # noqa: E402
from campusmatch.fast import encode, match_matrix, top_matches_fast  # noqa: E402
from campusmatch.matching import top_matches  # noqa: E402
from campusmatch.models import Answer, Importance, Profile  # noqa: E402
from campusmatch.scoring import score  # noqa: E402


def reference(profiles):
    return np.array([[score(a, b).match for b in profiles] for a in profiles])


@pytest.mark.parametrize(
    ("n", "seed", "answer_rate"),
    [(40, 0, 0.9), (60, 1, 0.5), (80, 2, 0.2), (25, 3, 1.0)],
)
def test_matrix_equals_scalar_score(n, seed, answer_rate):
    # A low answer rate produces pairs with no shared questions and pairs sharing just one.
    students = generate_students(n, seed=seed, answer_rate=answer_rate)
    assert np.allclose(match_matrix(students), reference(students), rtol=0, atol=1e-12)


def test_shared_and_satisfaction_match_scalar_score():
    students = generate_students(40, seed=9, answer_rate=0.4)
    arrays = encode(students)
    sat, shared = arrays.satisfaction(), arrays.shared()
    for i, a in enumerate(students):
        for k, b in enumerate(students):
            s = score(a, b)
            assert shared[i, k] == s.shared_questions
            if s.shared_questions:
                assert sat[i, k] == pytest.approx(s.satisfaction_a)
                assert sat[k, i] == pytest.approx(s.satisfaction_b)


def test_no_shared_questions_scores_zero(mk):
    a = mk("a", sleep=(0, {0}, "very"))
    b = mk("b", clean=(0, {0}, "very"))
    m = match_matrix([a, b])
    assert m[0, 1] == m[1, 0] == 0.0


def test_all_irrelevant_judge_is_fully_satisfied(mk):
    a = mk("a", sleep=(0, {0}, "irrelevant"), clean=(0, {0}, "irrelevant"))
    b = mk("b", sleep=(3, {3}, "very"), clean=(2, {2}, "very"))
    profiles = [a, b]
    sat = encode(profiles).satisfaction()
    assert sat[0, 1] == 1.0  # a has nothing to be unhappy about
    assert sat[1, 0] == 0.0  # b's preferences are all violated
    assert np.allclose(match_matrix(profiles), reference(profiles))


def test_everyone_irrelevant_population():
    rng = random.Random(4)
    students = []
    for i in range(30):
        p = Profile(id=f"p{i:02d}", name=str(i))
        for q in rng.sample(QUESTIONS, rng.randint(0, 4)):
            a = random_answer(q, rng)
            p.answer(Answer(a.question_id, a.choice, a.acceptable, Importance.IRRELEVANT))
        students.append(p)
    assert np.allclose(match_matrix(students), reference(students))


def test_random_answers_with_wide_option_sets(mk):
    # Questions outside the bank, with up to 10 options and arbitrary acceptable sets.
    rng = random.Random(11)
    levels = [lvl.name.lower() for lvl in Importance]
    profiles = []
    for i in range(50):
        answers = {}
        for q in range(8):
            if rng.random() < 0.6:
                n_opts = 2 + q
                acceptable = set(rng.sample(range(n_opts), rng.randint(1, n_opts)))
                answers[f"q{q}"] = (rng.randrange(n_opts), acceptable, rng.choice(levels))
        profiles.append(mk(f"x{i:02d}", **answers))
    assert np.allclose(match_matrix(profiles), reference(profiles))


def test_degenerate_populations(mk):
    assert match_matrix([]).shape == (0, 0)
    assert match_matrix([Profile(id="a", name="A"), Profile(id="b", name="B")]).tolist() == [
        [0.0, 0.0],
        [0.0, 0.0],
    ]
    solo = [mk("a", sleep=(0, {0}, "very"))]
    assert np.allclose(match_matrix(solo), reference(solo))


def test_top_matches_fast_agrees_with_top_matches():
    students = generate_students(120, seed=6, answer_rate=0.6)  # ids are sorted already
    arrays = encode(students)
    matrix, shared = arrays.match(), arrays.shared()
    for i in range(0, 120, 7):
        slow = top_matches(students[i], students, k=10)
        fast = top_matches_fast(i, matrix, k=10, shared=shared)
        assert [students[j].id for j, _ in fast] == [p.id for p, _ in slow]
        assert [m for _, m in fast] == pytest.approx([s.match for _, s in slow])


def test_top_matches_fast_excludes_self_and_respects_min_shared(mk):
    a = mk("a", sleep=(0, {0}, "very"))
    b = mk("b", sleep=(0, {0}, "very"), clean=(0, {0}, "very"))
    c = mk("c", clean=(0, {0}, "very"))  # shares nothing with a
    arrays = encode([a, b, c])
    matrix, shared = arrays.match(), arrays.shared()
    assert [j for j, _ in top_matches_fast(0, matrix, k=5)] == [1, 2]
    assert [j for j, _ in top_matches_fast(0, matrix, k=5, shared=shared)] == [1]
    assert top_matches_fast(0, matrix, k=1) == [(1, 0.0)]
