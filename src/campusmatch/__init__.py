"""CampusMatch: compatibility matching and stable roommate pairing for college students."""

from .matching import (
    Pairing,
    greedy_pairs,
    is_stable,
    pair_roommates,
    preference_lists,
    stable_roommates,
    top_matches,
)
from .models import Answer, Importance, Profile, Question
from .scoring import MatchScore, explain, score

__all__ = [
    "Answer",
    "Importance",
    "MatchScore",
    "Pairing",
    "Profile",
    "Question",
    "explain",
    "greedy_pairs",
    "is_stable",
    "preference_lists",
    "pair_roommates",
    "score",
    "stable_roommates",
    "top_matches",
]
__version__ = "0.1.0"
