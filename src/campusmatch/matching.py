"""Turning pairwise scores into decisions.

* `top_matches`      ranked recommendations for one student (heap, O(n log k)).
* `stable_roommates` Irving's algorithm (1985): find a pairing where no two
                     students would both rather be with each other than with
                     their assigned partner, or prove none exists.
* `pair_roommates`   end-to-end: build each student's preference list from how
                     well others satisfy *them*, run Irving, and fall back to a
                     greedy pairing on mutual score if no stable pairing exists.
"""

from __future__ import annotations

import heapq
from collections import deque
from collections.abc import Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass

from .models import Profile
from .scoring import MatchScore, satisfaction, score


def top_matches(
    student: Profile, pool: Iterable[Profile], k: int = 10, min_shared: int = 1
) -> list[tuple[Profile, MatchScore]]:
    """Return the k best matches for `student`, best first.

    Ties are broken by profile id so results are deterministic.
    """
    scored = (
        (s, other)
        for other in pool
        if other.id != student.id
        for s in [score(student, other)]
        if s.shared_questions >= min_shared
    )
    best = heapq.nsmallest(k, scored, key=lambda t: (-t[0].match, t[1].id))
    return [(other, s) for s, other in best]


Person = Hashable


def stable_roommates(prefs: Mapping[Person, Sequence[Person]]) -> dict[Person, Person] | None:
    """Irving's stable roommates algorithm.

    `prefs[p]` lists everyone else in p's order of preference (most preferred
    first). Every person must rank every other person. Returns a symmetric
    dict {p: partner} or None if no stable matching exists.

    Runs in O(n^2) list operations for n people, which is fine for the dorm-
    and cohort-sized groups this is meant for.
    """
    people = list(prefs)
    if len(people) % 2:
        raise ValueError("stable_roommates needs an even number of people")
    everyone = set(people)
    for p, lst in prefs.items():
        if p in lst or set(lst) != everyone - {p} or len(lst) != len(everyone) - 1:
            raise ValueError(f"{p!r} must rank every other person exactly once")

    table: dict[Person, list[Person]] = {p: list(lst) for p, lst in prefs.items()}
    rank = {p: {q: i for i, q in enumerate(lst)} for p, lst in prefs.items()}

    def drop(a: Person, b: Person) -> None:
        """Remove the pair (a, b) from each other's lists."""
        if b in table[a]:
            table[a].remove(b)
        if a in table[b]:
            table[b].remove(a)

    # Phase 1: proposals. holder[y] = the proposer y is currently holding.
    holder: dict[Person, Person] = {}
    free = deque(people)
    while free:
        x = free.popleft()
        while True:
            if not table[x]:
                return None
            y = table[x][0]
            current = holder.get(y)
            if current is None:
                holder[y] = x
                break
            if rank[y][x] < rank[y][current]:
                holder[y] = x
                drop(y, current)
                free.append(current)
                break
            drop(y, x)

    # Each y holding x discards everyone it likes less than x.
    for y, x in holder.items():
        cut = table[y].index(x)
        for z in table[y][cut + 1 :]:
            drop(y, z)

    # Phase 2: find and eliminate rotations until every list has one entry.
    while True:
        if any(not lst for lst in table.values()):
            return None
        start = next((p for p in people if len(table[p]) > 1), None)
        if start is None:
            break
        seen: dict[Person, int] = {}
        seq: list[Person] = []
        p = start
        while p not in seen:
            seen[p] = len(seq)
            seq.append(p)
            p = table[table[p][1]][-1]
        cycle = seq[seen[p] :]
        seconds = [table[x][1] for x in cycle]
        for x, y in zip(cycle, seconds, strict=True):
            if x not in table[y]:
                continue
            cut = table[y].index(x)
            for z in table[y][cut + 1 :]:
                drop(y, z)

    result = {p: table[p][0] for p in people}
    if any(result[result[p]] != p for p in people):  # pragma: no cover - invariant
        return None
    return result


def is_stable(prefs: Mapping[Person, Sequence[Person]], matching: Mapping[Person, Person]) -> bool:
    """True if no pair would both rather be with each other than their partners."""
    rank = {p: {q: i for i, q in enumerate(lst)} for p, lst in prefs.items()}
    people = list(prefs)
    for i, a in enumerate(people):
        for b in people[i + 1 :]:
            if matching[a] == b:
                continue
            if rank[a][b] < rank[a][matching[a]] and rank[b][a] < rank[b][matching[b]]:
                return False
    return True


_NOBODY = object()


@dataclass
class Pairing:
    pairs: dict[str, str | None]
    """Symmetric {student_id: partner_id}; None means left unpaired (odd group)."""
    method: str
    """"irving" if a stable pairing on individual preferences was found, else "greedy"."""


def greedy_pairs(students: Sequence[Profile]) -> dict[str, str | None]:
    """Pair students greedily by descending mutual match score.

    Because the match score is symmetric, the greedy result is stable with
    respect to it: any two students who'd both prefer each other by score
    would have been paired when their edge was reached. O(n^2 log n).
    """
    edges = []
    for i, a in enumerate(students):
        for b in students[i + 1 :]:
            edges.append((-score(a, b).match, a.id, b.id))
    edges.sort()
    result: dict[str, str | None] = {}
    for _, a, b in edges:
        if a not in result and b not in result:
            result[a], result[b] = b, a
    for s in students:
        result.setdefault(s.id, None)
    return result


def preference_lists(students: Sequence[Profile]) -> dict[str, list[str]]:
    """Each student's ranking of everyone else, by how well they satisfy *that student*.

    Ties (common when few questions are shared) break on overall match score,
    then on id, so the lists are total orders.
    """
    prefs = {}
    for me in students:

        def key(o: Profile, me: Profile = me) -> tuple:
            shared = sorted(me.answers.keys() & o.answers.keys())
            sat = satisfaction(me, o, shared) if shared else 0.0
            return (-sat, -score(me, o).match, o.id)

        prefs[me.id] = [o.id for o in sorted((o for o in students if o.id != me.id), key=key)]
    return prefs


def pair_roommates(students: Sequence[Profile], fallback: bool = True) -> Pairing | None:
    """Pair students into roommates.

    First tries Irving's algorithm on *asymmetric* individual preferences
    (A ranks B by how well B satisfies A). A stable solution, when it exists,
    means no two students would both rather swap to room together.

    Stable solutions often don't exist for large groups with asymmetric
    preferences. In that case, with `fallback=True`, we return the greedy
    pairing on the symmetric match score (stable with respect to that score);
    with `fallback=False` we return None.

    With an odd number of students, one is left unpaired (value None).
    """
    ids = [s.id for s in students]
    if len(set(ids)) != len(ids):
        raise ValueError("student ids must be unique")
    if len(ids) < 2:
        return Pairing({sid: None for sid in ids}, "irving")

    prefs: dict = preference_lists(students)
    if len(ids) % 2:
        for sid in ids:
            prefs[sid].append(_NOBODY)
        prefs[_NOBODY] = sorted(ids)

    result = stable_roommates(prefs)
    if result is not None:
        return Pairing(
            {sid: (None if result[sid] is _NOBODY else result[sid]) for sid in ids}, "irving"
        )
    if not fallback:
        return None
    return Pairing(greedy_pairs(students), "greedy")
