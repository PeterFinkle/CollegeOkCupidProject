import math

import pytest

from campusmatch.data import QUESTIONS_BY_ID
from campusmatch.models import Answer, Importance, Question
from campusmatch.scoring import explain, satisfaction, score


def test_no_shared_questions_scores_zero(mk):
    a = mk("a", sleep=(0, {0}, "very"))
    b = mk("b", clean=(0, {0}, "very"))
    s = score(a, b)
    assert s.match == 0 and s.shared_questions == 0


def test_perfect_match_is_penalized_by_margin_of_error(mk):
    ans = {"sleep": (0, {0}, "very"), "clean": (1, {1}, "somewhat")}
    s = score(mk("a", **ans), mk("b", **ans))
    assert s.satisfaction_a == s.satisfaction_b == 1.0
    assert s.match == pytest.approx(1 - 1 / 2)


def test_more_shared_questions_shrinks_the_penalty(mk):
    qids = ["sleep", "clean", "guests", "noise", "study", "weekend", "temp", "pets", "gpa", "share"]
    ans = {q: (0, {0}, "somewhat") for q in qids}
    assert score(mk("a", **ans), mk("b", **ans)).match == pytest.approx(0.9)


def test_geometric_mean_punishes_one_sided_matches(mk):
    # a is happy with b, b is unhappy with a.
    a = mk("a", sleep=(0, {0, 1}, "very"), clean=(0, {0, 1}, "very"), noise=(0, {0, 1}, "very"))
    b = mk("b", sleep=(1, {0, 2}, "very"), clean=(1, {0, 1}, "very"), noise=(1, {1}, "very"))
    s = score(a, b)
    assert s.satisfaction_a == 1.0
    assert s.satisfaction_b == pytest.approx(100 / 150)
    assert s.match == pytest.approx(math.sqrt(100 / 150) - 1 / 3)
    assert s.match < (s.satisfaction_a + s.satisfaction_b) / 2 - 1 / 3


def test_importance_weights_dominate(mk):
    # One mandatory mismatch outweighs a handful of minor agreements.
    shared = {q: (0, {0}, "a_little") for q in ["clean", "guests", "noise", "study"]}
    a = mk("a", sleep=(0, {0}, "mandatory"), **shared)
    b = mk("b", sleep=(2, {0, 1, 2, 3}, "irrelevant"), **shared)
    assert satisfaction(a, b, sorted(a.answers)) == pytest.approx(4 / 254)


def test_all_irrelevant_means_fully_satisfied(mk):
    a = mk("a", sleep=(0, {0}, "irrelevant"))
    b = mk("b", sleep=(3, {3}, "irrelevant"))
    assert satisfaction(a, b, ["sleep"]) == 1.0


def test_score_is_symmetric(mk):
    a = mk("a", sleep=(0, {0, 1}, "very"), clean=(2, {2}, "somewhat"))
    b = mk("b", sleep=(1, {0}, "a_little"), clean=(1, {1, 2}, "mandatory"))
    assert score(a, b).match == score(b, a).match


def test_explain_lists_disagreements_first(mk):
    a = mk("a", sleep=(0, {0}, "very"), clean=(0, {0}, "a_little"))
    b = mk("b", sleep=(2, {2}, "very"), clean=(0, {0}, "a_little"))
    rows = explain(a, b, QUESTIONS_BY_ID)
    assert [r["question_id"] for r in rows] == ["sleep", "clean"]
    assert rows[0]["a_satisfied"] is False and rows[1]["a_satisfied"] is True
    assert rows[0]["a_answer"] == "Before 11pm"


def test_answer_validation():
    q = Question("q", "?", ("x", "y"))
    Answer("q", 1, frozenset({0}), Importance.VERY).validate(q)
    with pytest.raises(ValueError):
        Answer("q", 2, frozenset({0})).validate(q)
    with pytest.raises(ValueError):
        Answer("q", 0, frozenset()).validate(q)
    with pytest.raises(ValueError):
        Answer("q", 0, frozenset({5})).validate(q)


def test_question_validation():
    with pytest.raises(ValueError):
        Question("q", "?", ("only one",))
    with pytest.raises(ValueError):
        Question("q", "?", ("dup", "dup"))
