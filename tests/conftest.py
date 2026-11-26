import pytest

from campusmatch.models import Answer, Importance, Profile


def make(pid: str, **answers) -> Profile:
    """make("a", sleep=(0, {0, 1}, "very")) -> Profile with that answer."""
    p = Profile(id=pid, name=pid.upper())
    for qid, (choice, acceptable, importance) in answers.items():
        p.answer(Answer(qid, choice, frozenset(acceptable), Importance[importance.upper()]))
    return p


@pytest.fixture
def mk():
    return make
