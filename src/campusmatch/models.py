"""Core domain types: questions, answers, and student profiles."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class Importance(IntEnum):
    """How much a student cares about the other person's answer to a question.

    The weights grow roughly geometrically so that a single "very important"
    question outweighs many "a little important" ones, and a "mandatory"
    question behaves almost like a dealbreaker without being a hard filter.
    """

    IRRELEVANT = 0
    A_LITTLE = 1
    SOMEWHAT = 10
    VERY = 50
    MANDATORY = 250


@dataclass(frozen=True)
class Question:
    id: str
    text: str
    options: tuple[str, ...]
    category: str = "general"

    def __post_init__(self) -> None:
        if len(self.options) < 2:
            raise ValueError(f"question {self.id!r} needs at least two options")
        if len(set(self.options)) != len(self.options):
            raise ValueError(f"question {self.id!r} has duplicate options")


@dataclass(frozen=True)
class Answer:
    """One student's response to one question.

    choice:      index of the option the student picked for themselves.
    acceptable:  indices of options the student would accept from a match.
    importance:  how much the student cares about the match's answer.
    """

    question_id: str
    choice: int
    acceptable: frozenset[int]
    importance: Importance = Importance.SOMEWHAT

    @property
    def acceptable_mask(self) -> int:
        """`acceptable` as a bitmask (bit i set = option i acceptable).

        "Is B's choice acceptable to A?" becomes `mask >> choice & 1`, which is what lets
        the SQLite store keep it in one INTEGER column and the NumPy path test it in bulk.
        """
        return sum(1 << i for i in self.acceptable)

    @staticmethod
    def options_from_mask(mask: int) -> frozenset[int]:
        """Inverse of `acceptable_mask`."""
        return frozenset(i for i in range(mask.bit_length()) if mask >> i & 1)

    def validate(self, question: Question) -> None:
        n = len(question.options)
        if not 0 <= self.choice < n:
            raise ValueError(f"choice {self.choice} out of range for {question.id!r}")
        if not self.acceptable:
            raise ValueError(f"answer to {question.id!r} must accept at least one option")
        if any(not 0 <= a < n for a in self.acceptable):
            raise ValueError(f"acceptable option out of range for {question.id!r}")


@dataclass
class Profile:
    id: str
    name: str
    major: str = ""
    year: int = 1
    answers: dict[str, Answer] = field(default_factory=dict)

    def answer(self, a: Answer) -> None:
        self.answers[a.question_id] = a
