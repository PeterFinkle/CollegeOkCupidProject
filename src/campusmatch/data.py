"""Question bank and a seeded generator of realistic synthetic students."""

from __future__ import annotations

import random

from .models import Answer, Importance, Profile, Question

QUESTIONS: tuple[Question, ...] = (
    Question(
        "sleep",
        "When do you usually go to sleep?",
        ("Before 11pm", "11pm-1am", "After 1am", "It varies a lot"),
        "lifestyle",
    ),
    Question(
        "clean",
        "How tidy do you keep your space?",
        ("Spotless", "Mostly tidy", "Organized chaos", "Messy"),
        "lifestyle",
    ),
    Question(
        "guests",
        "How often do you like having friends over?",
        ("Rarely", "Weekends", "Several times a week", "Always"),
        "social",
    ),
    Question(
        "noise",
        "What's your ideal noise level at home?",
        ("Silent", "Quiet background", "Music is always on", "Don't care"),
        "lifestyle",
    ),
    Question(
        "study",
        "Where do you study best?",
        ("My room", "Library", "Coffee shop", "With a group"),
        "academics",
    ),
    Question(
        "weekend",
        "Ideal Friday night?",
        ("Party", "Small hangout", "Movie in", "Catching up on work"),
        "social",
    ),
    Question(
        "substances",
        "How do you feel about drinking at home?",
        ("Not okay", "Occasionally fine", "Totally fine"),
        "values",
    ),
    Question(
        "share",
        "Sharing food, kitchen items and supplies?",
        ("Prefer separate", "Ask first", "What's mine is yours"),
        "lifestyle",
    ),
    Question("temp", "Thermostat preference?", ("Cold", "Moderate", "Warm"), "lifestyle"),
    Question("pets", "Would you live with a pet?", ("No", "Small pets only", "Yes, any"), "values"),
    Question(
        "gpa",
        "How do you prioritize grades?",
        ("Top priority", "Important, but balanced", "Just pass"),
        "academics",
    ),
    Question(
        "conflict",
        "When something bugs you about a roommate you...",
        ("Bring it up right away", "Wait for a good moment", "Leave a note", "Let it go"),
        "values",
    ),
)

QUESTIONS_BY_ID = {q.id: q for q in QUESTIONS}

_FIRST = (
    "Ava",
    "Ben",
    "Chloe",
    "Dev",
    "Elena",
    "Femi",
    "Grace",
    "Hiro",
    "Isla",
    "Jamal",
    "Kai",
    "Lena",
    "Marco",
    "Nia",
    "Omar",
    "Priya",
    "Quinn",
    "Rosa",
    "Sam",
    "Tariq",
    "Uma",
    "Vik",
    "Wren",
    "Xavier",
    "Yara",
    "Zoe",
)
_LAST = (
    "Adams",
    "Bose",
    "Chen",
    "Diaz",
    "Evans",
    "Fox",
    "Garcia",
    "Ito",
    "Khan",
    "Lopez",
    "Moreno",
    "Nguyen",
    "Okafor",
    "Patel",
    "Reyes",
    "Silva",
    "Tanaka",
    "Walsh",
)
_MAJORS = (
    "Computer Science",
    "Biology",
    "Economics",
    "English",
    "Psychology",
    "Mechanical Eng.",
    "Political Science",
    "Art History",
    "Mathematics",
    "Nursing",
    "Music",
    "Chemistry",
)

# Personas skew answers so the synthetic population has real structure
# (clusters of compatible people) instead of uniform noise.
_PERSONAS = {
    "early_bird": {"sleep": 0, "clean": 0, "noise": 0, "weekend": 3, "gpa": 0, "guests": 0},
    "social": {"sleep": 2, "guests": 3, "noise": 2, "weekend": 0, "substances": 2, "share": 2},
    "chill": {"sleep": 1, "clean": 2, "noise": 1, "weekend": 2, "share": 1, "conflict": 1},
    "studious": {"study": 1, "gpa": 0, "noise": 0, "weekend": 3, "guests": 0, "sleep": 1},
}
_IMPORTANCE_WEIGHTS = {
    Importance.IRRELEVANT: 1,
    Importance.A_LITTLE: 3,
    Importance.SOMEWHAT: 4,
    Importance.VERY: 2,
    Importance.MANDATORY: 0.4,
}


def random_answer(q: Question, rng: random.Random, lean: int | None = None) -> Answer:
    n = len(q.options)
    if lean is not None and rng.random() < 0.75:
        choice = lean
    else:
        choice = rng.randrange(n)
    # Most people accept their own answer plus neighbours on the scale.
    acceptable = {choice}
    for delta in (-1, 1):
        if 0 <= choice + delta < n and rng.random() < 0.55:
            acceptable.add(choice + delta)
    if rng.random() < 0.15:
        acceptable.add(rng.randrange(n))
    levels = list(_IMPORTANCE_WEIGHTS)
    importance = rng.choices(levels, weights=[_IMPORTANCE_WEIGHTS[x] for x in levels])[0]
    return Answer(q.id, choice, frozenset(acceptable), importance)


def generate_students(n: int, seed: int = 42, answer_rate: float = 0.9) -> list[Profile]:
    """Generate `n` synthetic students. Same seed, same students."""
    rng = random.Random(seed)
    personas = list(_PERSONAS)
    students = []
    for i in range(n):
        persona = _PERSONAS[rng.choice(personas)]
        p = Profile(
            id=f"s{i:04d}",
            name=f"{rng.choice(_FIRST)} {rng.choice(_LAST)}",
            major=rng.choice(_MAJORS),
            year=rng.randint(1, 4),
        )
        for q in QUESTIONS:
            if rng.random() < answer_rate:
                p.answer(random_answer(q, rng, persona.get(q.id)))
        students.append(p)
    return students
